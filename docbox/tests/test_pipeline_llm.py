"""Full ingest -> model -> rename flow against a stub Ollama.

Keeps CI honest about the part that matters: what the model says has to end up
as the filename on disk.
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app import db, storage
from app.config import settings
from app.pipeline import process_document

REPLY = {
    "date": "2024-03-17",
    "correspondent": "Stadtwerke Munich",
    "doc_type": "invoice",
    "title": "electricity bill march",
    "summary": "Monthly electricity invoice for 84.20 EUR.",
    "confidence": 0.92,
}


class _StubOllama(BaseHTTPRequestHandler):
    prompts: list[str] = []

    def log_message(self, *_args):  # keep pytest output clean
        pass

    def do_GET(self):  # /api/tags
        self._send({"models": [{"name": "qwen2.5:3b"}]})

    def do_POST(self):  # /api/chat
        length = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        _StubOllama.prompts.append(json.dumps(body))
        # Answer the way small models really do: JSON wrapped in chatter.
        content = f"Here you go:\n```json\n{json.dumps(REPLY)}\n```"
        self._send({"message": {"role": "assistant", "content": content}})

    def _send(self, payload: dict):
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture()
def stub_ollama(monkeypatch):
    server = HTTPServer(("127.0.0.1", 0), _StubOllama)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(settings, "ollama_url", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setattr(settings, "llm_enabled", True)
    _StubOllama.prompts.clear()
    yield server
    server.shutdown()
    server.server_close()


@pytest.fixture()
def signed_in(client):
    from app import auth

    if not db.query_one("SELECT id FROM users WHERE username = ?", ("llmtester",)):
        auth.create_user("llmtester", "hunter2hunter2")
    client.post("/api/login", json={"username": "llmtester", "password": "hunter2hunter2"})
    return client


def test_model_output_becomes_the_filename(signed_in, stub_ollama):
    client = signed_in
    upload = client.post(
        "/api/upload",
        files={"files": ("IMG_0042.txt", b"Stadtwerke Munich\nRechnung 17.03.2024\n84,20 EUR", "text/plain")},
    )
    doc_id = upload.json()["results"][0]["document"]["id"]

    result = process_document(doc_id)
    assert result["ok"] and result["source"] == "llm"

    doc = client.get(f"/api/documents/{doc_id}").json()["document"]
    assert doc["filename"] == "20240317-stadtwerke-munich-electricity-bill-march.txt"
    assert doc["correspondent"] == "Stadtwerke Munich"
    assert doc["doc_type"] == "invoice"
    assert doc["doc_date"] == "20240317"
    assert doc["needs_review"] is False  # confident answer, no human needed
    assert storage.doc_path(doc["folder"], doc["filename"]).exists()

    # The document text really was sent to the model.
    assert "Stadtwerke" in _StubOllama.prompts[0]


def test_low_confidence_is_flagged_for_review(signed_in, stub_ollama, monkeypatch):
    client = signed_in
    monkeypatch.setitem(REPLY, "confidence", 0.1)
    try:
        upload = client.post(
            "/api/upload",
            files={"files": ("IMG_0043.txt", b"something barely legible 17.03.2024", "text/plain")},
        )
        doc_id = upload.json()["results"][0]["document"]["id"]
        process_document(doc_id)
        doc = client.get(f"/api/documents/{doc_id}").json()["document"]
        assert doc["needs_review"] is True
        assert doc["filename"].startswith("20240317-")
    finally:
        REPLY["confidence"] = 0.92


def test_unreachable_model_falls_back_instead_of_failing(signed_in, monkeypatch):
    client = signed_in
    monkeypatch.setattr(settings, "llm_enabled", True)
    monkeypatch.setattr(settings, "ollama_url", "http://127.0.0.1:1")  # nothing listening
    upload = client.post(
        "/api/upload",
        files={"files": ("IMG_0044.txt", b"Zahnarzt Dr Klein\nRechnung vom 02.06.2022", "text/plain")},
    )
    doc_id = upload.json()["results"][0]["document"]["id"]
    process_document(doc_id)

    doc = client.get(f"/api/documents/{doc_id}").json()["document"]
    assert doc["status"] == "done"          # the file is safe either way
    assert doc["filename"].startswith("20220602-")  # date still scraped from the text
    assert doc["needs_review"] is True      # but a human should look
    assert "ollama" in doc["error"].lower()


def test_confident_documents_are_filed_into_folders(signed_in, stub_ollama, monkeypatch):
    """The model says invoice/Stadtwerke -> the utilities rule files it by year."""
    client = signed_in
    monkeypatch.setattr(settings, "auto_file", True)
    upload = client.post(
        "/api/upload",
        files={"files": ("IMG_9001.txt", b"Stadtwerke Munich electricity 17.03.2024", "text/plain")},
    )
    doc_id = upload.json()["results"][0]["document"]["id"]
    assert upload.json()["results"][0]["document"]["folder"] == settings.inbox_name

    result = process_document(doc_id)
    assert result["folder"] == "Home/Utilities/2024"
    assert result["routed_by"] == "utilities"

    doc = client.get(f"/api/documents/{doc_id}").json()["document"]
    assert doc["folder"] == "Home/Utilities/2024"
    assert storage.doc_path(doc["folder"], doc["filename"]).exists()
    # ...and the folder filter finds it, including from the parent.
    assert any(d["id"] == doc_id for d in
               client.get("/api/documents", params={"folder": "Home"}).json()["documents"])


def test_unsure_documents_stay_in_the_inbox(signed_in, stub_ollama, monkeypatch):
    monkeypatch.setattr(settings, "auto_file", True)
    monkeypatch.setitem(REPLY, "confidence", 0.2)
    try:
        upload = signed_in.post(
            "/api/upload",
            files={"files": ("IMG_9002.txt", b"something illegible 18.03.2024", "text/plain")},
        )
        doc_id = upload.json()["results"][0]["document"]["id"]
        result = process_document(doc_id)
        assert result["folder"] == settings.inbox_name
        assert result["routed_by"] == ""
    finally:
        REPLY["confidence"] = 0.92


def test_auto_file_can_be_turned_off(signed_in, stub_ollama, monkeypatch):
    monkeypatch.setattr(settings, "auto_file", False)
    upload = signed_in.post(
        "/api/upload",
        files={"files": ("IMG_9003.txt", b"Stadtwerke Munich electricity 19.03.2024", "text/plain")},
    )
    doc_id = upload.json()["results"][0]["document"]["id"]
    assert process_document(doc_id)["folder"] == settings.inbox_name


def test_pinned_names_are_never_moved_or_renamed(signed_in, stub_ollama, monkeypatch):
    monkeypatch.setattr(settings, "auto_file", True)
    upload = signed_in.post(
        "/api/upload",
        files={"files": ("IMG_9004.txt", b"Stadtwerke Munich electricity 20.03.2024", "text/plain")},
    )
    doc_id = upload.json()["results"][0]["document"]["id"]
    signed_in.patch(f"/api/documents/{doc_id}", json={"filename": "my-own-name"})
    result = process_document(doc_id)
    assert result["filename"] == "my-own-name.txt"
    assert result["folder"] == settings.inbox_name


def test_organize_endpoint_dry_runs_then_applies(signed_in, stub_ollama, monkeypatch):
    """Filing rules can be applied to documents that are already in the library."""
    monkeypatch.setattr(settings, "auto_file", False)   # land in the inbox first
    upload = signed_in.post(
        "/api/upload",
        files={"files": ("IMG_9005.txt", b"Stadtwerke Munich electricity 21.03.2024", "text/plain")},
    )
    doc_id = upload.json()["results"][0]["document"]["id"]
    process_document(doc_id)
    assert signed_in.get(f"/api/documents/{doc_id}").json()["document"]["folder"] == settings.inbox_name

    dry = signed_in.post("/api/organize", json={"apply": False}).json()
    assert dry["applied"] is False
    assert dry["moved"] == 0
    assert any(m["id"] == doc_id and m["to"] == "Home/Utilities/2024" for m in dry["moves"])
    # nothing actually moved
    assert signed_in.get(f"/api/documents/{doc_id}").json()["document"]["folder"] == settings.inbox_name

    applied = signed_in.post("/api/organize", json={"apply": True}).json()
    assert applied["moved"] >= 1
    doc = signed_in.get(f"/api/documents/{doc_id}").json()["document"]
    assert doc["folder"] == "Home/Utilities/2024"
    assert storage.doc_path(doc["folder"], doc["filename"]).exists()


def test_import_hint_reaches_the_model(signed_in, stub_ollama):
    """The folder a document sat in before the import is real signal about what
    it is, so it has to reach the prompt."""
    from app.ingest import ingest_bytes

    _StubOllama.prompts.clear()
    doc = ingest_bytes(
        b"Allianz Versicherung policy documents for the car, dated 05.06.2023, "
        b"renewal terms enclosed.",
        "scan.txt", "tester", hint="Insurance/Car", process=False,
    )
    process_document(doc["document"]["id"])
    assert any("Insurance/Car" in prompt for prompt in _StubOllama.prompts)
