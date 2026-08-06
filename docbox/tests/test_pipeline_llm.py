"""Full ingest -> model -> rename -> file flow, against a stub model server.

The stub speaks both dialects — OpenAI-compatible (Nous, the default) and
Ollama — so the same expectations run against either backend.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app import auth, db, storage
from app.config import settings
from app.pipeline import process_document

REPLY = {
    "date": "2024-03-17",
    "correspondent": "Stadtwerke Munich",
    "doc_type": "invoice",
    "title": "electricity bill march",
    "person": "",
    "summary": "Monthly electricity invoice for 84.20 EUR.",
    "confidence": 0.92,
}

# Test knobs the stub reads before answering.
BEHAVIOUR = {"fail_times": 0, "reject_json_mode": False}


class _StubModel(BaseHTTPRequestHandler):
    prompts: list[str] = []
    requests: list[str] = []

    def log_message(self, *_args):
        pass

    def do_GET(self):
        _StubModel.requests.append(f"GET {self.path}")
        if self.path.startswith("/api/tags"):            # ollama
            self._send({"models": [{"name": "qwen2.5:3b"}]})
        else:                                            # openai-compatible
            self._send({"data": [{"id": "Hermes-4-70B"}, {"id": "Hermes-4-405B"}]})

    def do_POST(self):
        _StubModel.requests.append(f"POST {self.path}")
        body = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
        _StubModel.prompts.append(json.dumps(body))

        if BEHAVIOUR["fail_times"] > 0:
            BEHAVIOUR["fail_times"] -= 1
            self.send_response(429)
            self.send_header("content-length", "0")
            self.end_headers()
            return

        if BEHAVIOUR["reject_json_mode"] and "response_format" in body:
            payload = json.dumps({"error": "response_format unsupported"}).encode()
            self.send_response(400)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        # Answer the way real models do: JSON wrapped in chatter.
        content = f"Here you go:\n```json\n{json.dumps(REPLY)}\n```"
        if self.path.startswith("/api/chat"):            # ollama
            self._send({"message": {"role": "assistant", "content": content}})
        else:                                            # openai-compatible
            self._send({"choices": [{"message": {"role": "assistant", "content": content}}]})

    def _send(self, payload: dict):
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture()
def stub_server():
    server = HTTPServer(("127.0.0.1", 0), _StubModel)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _StubModel.prompts.clear()
    _StubModel.requests.clear()
    BEHAVIOUR.update({"fail_times": 0, "reject_json_mode": False})
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture()
def stub_llm(stub_server, monkeypatch):
    """The default deployment: a hosted, OpenAI-compatible provider."""
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "nous")
    monkeypatch.setattr(settings, "llm_base_url", f"http://127.0.0.1:{stub_server.server_port}/v1")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_model", "Hermes-4-70B")
    return stub_server


@pytest.fixture()
def stub_ollama(stub_server, monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "ollama")
    monkeypatch.setattr(settings, "llm_base_url", f"http://127.0.0.1:{stub_server.server_port}")
    monkeypatch.setattr(settings, "llm_api_key", "")
    monkeypatch.setattr(settings, "llm_model", "qwen2.5:3b")
    return stub_server


@pytest.fixture()
def signed_in(client):
    if not db.query_one("SELECT id FROM users WHERE username = ?", ("llmtester",)):
        auth.create_user("llmtester", "hunter2hunter2")
    client.post("/api/login", json={"username": "llmtester", "password": "hunter2hunter2"})
    return client


def upload(client, name: str, body: bytes):
    response = client.post("/api/upload", files={"files": (name, body, "text/plain")})
    assert response.status_code == 200, response.text
    return response.json()["results"][0]["document"]["id"]


# ------------------------------------------------------------------ backends


def test_hosted_provider_output_becomes_the_filename(signed_in, stub_llm):
    doc_id = upload(signed_in, "IMG_0042.txt",
                    b"Stadtwerke Munich\nRechnung 17.03.2024\n84,20 EUR")
    result = process_document(doc_id)
    assert result["ok"] and result["source"] == "llm"

    doc = signed_in.get(f"/api/documents/{doc_id}").json()["document"]
    assert doc["filename"] == "20240317-stadtwerke-munich-electricity-bill-march.txt"
    assert doc["doc_type"] == "invoice"
    assert doc["needs_review"] is False
    assert storage.doc_path(doc["folder"], doc["filename"]).exists()

    sent = json.loads(_StubModel.prompts[0])
    assert "Stadtwerke" in json.dumps(sent["messages"])
    assert sent["model"] == "Hermes-4-70B"
    assert any("/v1/chat/completions" in r for r in _StubModel.requests)


def test_ollama_provider_still_works(signed_in, stub_ollama):
    doc_id = upload(signed_in, "IMG_0142.txt",
                    b"Stadtwerke Munich\nRechnung 17.03.2024\n84,20 EUR zahlbar")
    result = process_document(doc_id)
    assert result["ok"] and result["source"] == "llm"
    assert any("/api/chat" in r for r in _StubModel.requests)


def test_hosted_provider_retries_a_rate_limit(signed_in, stub_llm):
    BEHAVIOUR["fail_times"] = 2      # two 429s, then success
    doc_id = upload(signed_in, "IMG_0043.txt",
                    b"Stadtwerke Munich\nRechnung 17.03.2024\nbetrag 84,20 EUR")
    result = process_document(doc_id)
    assert result["ok"] and result["source"] == "llm"
    assert len([r for r in _StubModel.requests if r.startswith("POST")]) == 3


def test_provider_without_json_mode_is_retried_plainly(signed_in, stub_llm):
    """Not every OpenAI-compatible server implements response_format."""
    BEHAVIOUR["reject_json_mode"] = True
    doc_id = upload(signed_in, "IMG_0044.txt",
                    b"Stadtwerke Munich\nRechnung 17.03.2024\nsumme 84,20 EUR")
    result = process_document(doc_id)
    assert result["ok"] and result["source"] == "llm"
    bodies = [json.loads(p) for p in _StubModel.prompts]
    assert "response_format" in bodies[0] and "response_format" not in bodies[-1]


def test_missing_api_key_is_reported_not_crashed(signed_in, monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "nous")
    monkeypatch.setattr(settings, "llm_api_key", "")
    doc_id = upload(signed_in, "IMG_0045.txt", b"Zahnarzt Dr Klein\nRechnung vom 02.06.2022")
    process_document(doc_id)
    doc = signed_in.get(f"/api/documents/{doc_id}").json()["document"]
    assert doc["status"] == "done"
    assert "api key" in doc["error"].lower()
    assert doc["needs_review"] is True


def test_unreachable_model_falls_back_instead_of_failing(signed_in, monkeypatch):
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "llm_provider", "nous")
    monkeypatch.setattr(settings, "llm_api_key", "test-key")
    monkeypatch.setattr(settings, "llm_base_url", "http://127.0.0.1:1/v1")  # nothing there
    doc_id = upload(signed_in, "IMG_0046.txt", b"Zahnarzt Dr Klein\nRechnung vom 02.06.2022")
    process_document(doc_id)

    doc = signed_in.get(f"/api/documents/{doc_id}").json()["document"]
    assert doc["status"] == "done"                   # the file is safe either way
    assert doc["filename"].startswith("20220602-")   # date still scraped from the text
    assert doc["needs_review"] is True
    assert doc["error"]


# -------------------------------------------------------------------- filing


def test_low_confidence_is_flagged_for_review(signed_in, stub_llm, monkeypatch):
    monkeypatch.setitem(REPLY, "confidence", 0.1)
    try:
        doc_id = upload(signed_in, "IMG_0047.txt", b"something barely legible 17.03.2024 here")
        process_document(doc_id)
        doc = signed_in.get(f"/api/documents/{doc_id}").json()["document"]
        assert doc["needs_review"] is True
        assert doc["filename"].startswith("20240317-")
    finally:
        REPLY["confidence"] = 0.92


def test_confident_documents_are_filed_into_folders(signed_in, stub_llm, monkeypatch):
    monkeypatch.setattr(settings, "auto_file", True)
    doc_id = upload(signed_in, "IMG_9001.txt", b"Stadtwerke Munich electricity 17.03.2024 bill")
    result = process_document(doc_id)
    assert result["folder"] == "Home/Utilities/2024"
    assert result["routed_by"] == "utilities"

    doc = signed_in.get(f"/api/documents/{doc_id}").json()["document"]
    assert storage.doc_path(doc["folder"], doc["filename"]).exists()
    # the parent folder lists it too
    assert any(d["id"] == doc_id for d in
               signed_in.get("/api/documents", params={"folder": "Home"}).json()["documents"])


def test_documents_about_a_person_go_to_their_folder(signed_in, stub_llm, monkeypatch):
    monkeypatch.setattr(settings, "auto_file", True)
    monkeypatch.setattr(settings, "household", ["Ajit Jose", "Cashmy Joy", "Aiden John"])
    monkeypatch.setitem(REPLY, "doc_type", "medical")
    monkeypatch.setitem(REPLY, "person", "Aiden John")
    monkeypatch.setitem(REPLY, "correspondent", "Dr Meyer")
    try:
        doc_id = upload(signed_in, "IMG_9002.txt",
                        b"Vaccination record for Aiden John, seen 17.03.2024 by Dr Meyer")
        result = process_document(doc_id)
        assert result["folder"] == "Family/Aiden John/Medical"
        assert result["routed_by"] == "person:Aiden John"
    finally:
        REPLY.update({"doc_type": "invoice", "person": "", "correspondent": "Stadtwerke Munich"})


def test_a_bill_is_not_filed_under_a_person(signed_in, stub_llm, monkeypatch):
    """A gas bill addressed to Ajit is still a bill, not a document about him."""
    monkeypatch.setattr(settings, "auto_file", True)
    monkeypatch.setattr(settings, "household", ["Ajit Jose", "Cashmy Joy"])
    monkeypatch.setitem(REPLY, "person", "Ajit Jose")
    try:
        doc_id = upload(signed_in, "IMG_9003.txt",
                        b"Invoice to Ajit Jose from Stadtwerke Munich, 17.03.2024, electricity")
        result = process_document(doc_id)
        assert result["folder"] == "Home/Utilities/2024"   # invoice is not a people doc_type
    finally:
        REPLY["person"] = ""


def test_unsure_documents_stay_in_the_inbox(signed_in, stub_llm, monkeypatch):
    monkeypatch.setattr(settings, "auto_file", True)
    monkeypatch.setitem(REPLY, "confidence", 0.2)
    try:
        doc_id = upload(signed_in, "IMG_9004.txt", b"something illegible 18.03.2024 here now")
        result = process_document(doc_id)
        assert result["folder"] == settings.inbox_name
        assert result["routed_by"] == ""
    finally:
        REPLY["confidence"] = 0.92


def test_auto_file_can_be_turned_off(signed_in, stub_llm, monkeypatch):
    monkeypatch.setattr(settings, "auto_file", False)
    doc_id = upload(signed_in, "IMG_9005.txt", b"Stadtwerke Munich electricity 19.03.2024 bill")
    assert process_document(doc_id)["folder"] == settings.inbox_name


def test_pinned_names_are_never_moved_or_renamed(signed_in, stub_llm, monkeypatch):
    monkeypatch.setattr(settings, "auto_file", True)
    doc_id = upload(signed_in, "IMG_9006.txt", b"Stadtwerke Munich electricity 20.03.2024 bill")
    signed_in.patch(f"/api/documents/{doc_id}", json={"filename": "my-own-name"})
    result = process_document(doc_id)
    assert result["filename"] == "my-own-name.txt"
    assert result["folder"] == settings.inbox_name


def test_organize_endpoint_dry_runs_then_applies(signed_in, stub_llm, monkeypatch):
    monkeypatch.setattr(settings, "auto_file", False)   # land in the inbox first
    doc_id = upload(signed_in, "IMG_9007.txt", b"Stadtwerke Munich electricity 21.03.2024 bill")
    process_document(doc_id)
    assert signed_in.get(f"/api/documents/{doc_id}").json()["document"]["folder"] == settings.inbox_name

    dry = signed_in.post("/api/organize", json={"apply": False}).json()
    assert dry["applied"] is False and dry["moved"] == 0
    assert any(m["id"] == doc_id and m["to"] == "Home/Utilities/2024" for m in dry["moves"])
    assert signed_in.get(f"/api/documents/{doc_id}").json()["document"]["folder"] == settings.inbox_name

    applied = signed_in.post("/api/organize", json={"apply": True}).json()
    assert applied["moved"] >= 1
    doc = signed_in.get(f"/api/documents/{doc_id}").json()["document"]
    assert doc["folder"] == "Home/Utilities/2024"
    assert storage.doc_path(doc["folder"], doc["filename"]).exists()


def test_import_hint_and_household_reach_the_model(signed_in, stub_llm, monkeypatch):
    """The folder a document sat in before the import, and who lives here, are
    both real signal — they have to be in the prompt."""
    monkeypatch.setattr(settings, "household", ["Ajit Jose", "Cashmy Joy"])
    from app.ingest import ingest_bytes

    _StubModel.prompts.clear()
    doc = ingest_bytes(
        b"Allianz Versicherung policy documents for the car, dated 05.06.2023, "
        b"renewal terms enclosed.",
        "scan.txt", "tester", hint="Insurance/Car", process=False,
    )
    process_document(doc["document"]["id"])
    sent = json.dumps([json.loads(p) for p in _StubModel.prompts])
    assert "Insurance/Car" in sent
    assert "Cashmy Joy" in sent
