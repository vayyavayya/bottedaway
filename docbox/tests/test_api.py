"""End-to-end through the HTTP API, with the worker off so we drive the
pipeline synchronously and assert on the rename."""

from __future__ import annotations

import pytest

from app import db, storage
from app.config import settings
from app.pipeline import process_document

USERNAME = "tester"
PASSWORD = "hunter2hunter2"


@pytest.fixture()
def signed_in(client):
    if not db.query_one("SELECT id FROM users WHERE username = ?", (USERNAME,)):
        response = client.post("/api/setup", json={"username": USERNAME, "password": PASSWORD})
        if response.status_code == 403:  # another test already created a user
            client.post("/api/login", json={"username": USERNAME, "password": PASSWORD})
    else:
        client.post("/api/login", json={"username": USERNAME, "password": PASSWORD})
    return client


def test_health_is_open(client):
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert "llm" in body


def test_documents_require_auth(client):
    assert client.get("/api/documents").status_code == 401


def test_upload_lands_in_inbox_and_gets_renamed(signed_in):
    content = b"Stadtwerke Munich electricity invoice\nInvoice date 17.03.2024\nAmount 84.20 EUR\n"
    response = signed_in.post(
        "/api/upload",
        files={"files": ("IMG_0042.txt", content, "text/plain")},
    )
    assert response.status_code == 200, response.text
    doc = response.json()["results"][0]["document"]
    assert doc["folder"] == settings.inbox_name
    assert doc["status"] == "pending"

    result = process_document(doc["id"])
    assert result["ok"] is True

    after = signed_in.get(f"/api/documents/{doc['id']}").json()["document"]
    assert after["filename"].startswith("20240317-")
    assert after["filename"].endswith(".txt")
    assert after["original_name"] == "IMG_0042.txt"
    assert storage.doc_path(after["folder"], after["filename"]).exists()


def test_duplicate_upload_is_not_stored_twice(signed_in):
    payload = b"a one of a kind receipt from 2019-05-04\n"
    first = signed_in.post("/api/upload", files={"files": ("a.txt", payload, "text/plain")})
    second = signed_in.post("/api/upload", files={"files": ("b.txt", payload, "text/plain")})
    assert first.json()["results"][0]["duplicate"] is False
    assert second.json()["results"][0]["duplicate"] is True


def test_rename_and_move(signed_in):
    signed_in.post("/api/folders", json={"name": "Bills"})
    upload = signed_in.post(
        "/api/upload", files={"files": ("thing.txt", b"some contract text 2020-01-02", "text/plain")}
    )
    doc_id = upload.json()["results"][0]["document"]["id"]

    patched = signed_in.patch(
        f"/api/documents/{doc_id}",
        json={"filename": "20200102-rental-contract", "folder": "Bills"},
    ).json()["document"]

    assert patched["folder"] == "Bills"
    assert patched["filename"] == "20200102-rental-contract.txt"
    assert patched["pinned_name"] is True  # a hand-picked name survives the next AI pass
    assert storage.doc_path("Bills", patched["filename"]).exists()

    # A pinned document keeps its name when reprocessed through the pipeline...
    process_document(doc_id)
    still = signed_in.get(f"/api/documents/{doc_id}").json()["document"]
    assert still["filename"] == "20200102-rental-contract.txt"


def test_reprocess_unpins(signed_in):
    upload = signed_in.post(
        "/api/upload", files={"files": ("x.txt", b"gas bill dated 03.09.2021", "text/plain")}
    )
    doc_id = upload.json()["results"][0]["document"]["id"]
    signed_in.patch(f"/api/documents/{doc_id}", json={"filename": "manual-name"})
    signed_in.post(f"/api/documents/{doc_id}/reprocess")
    process_document(doc_id)
    doc = signed_in.get(f"/api/documents/{doc_id}").json()["document"]
    assert doc["filename"].startswith("20210903-")


def test_search_matches_extracted_text(signed_in):
    upload = signed_in.post(
        "/api/upload",
        files={"files": ("y.txt", b"Hospital Sankt Marien discharge letter 2022-07-08", "text/plain")},
    )
    doc_id = upload.json()["results"][0]["document"]["id"]
    process_document(doc_id)  # search covers the text the model read, not just names

    docs = signed_in.get("/api/documents", params={"q": "Sankt Marien"}).json()["documents"]
    assert any(d["id"] == doc_id for d in docs)


def test_delete_moves_to_trash(signed_in):
    upload = signed_in.post(
        "/api/upload", files={"files": ("z.txt", b"disposable note 2018-02-02", "text/plain")}
    )
    doc = upload.json()["results"][0]["document"]
    assert signed_in.delete(f"/api/documents/{doc['id']}").status_code == 200
    assert not storage.doc_path(doc["folder"], doc["filename"]).exists()
    assert (settings.library_dir / ".trash" / doc["folder"] / doc["filename"]).exists()
    assert signed_in.get(f"/api/documents/{doc['id']}").status_code == 404


def test_api_token_works_for_shortcut_uploads(signed_in):
    token = signed_in.get("/api/me").json()["api_token"]
    fresh = signed_in
    fresh.cookies.clear()
    response = fresh.post(
        "/api/upload",
        files={"files": ("shortcut.txt", b"shared from the phone 2024-05-06", "text/plain")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text


def test_upload_rejects_unknown_extension(signed_in):
    response = signed_in.post(
        "/api/upload", files={"files": ("nasty.exe", b"MZ binary", "application/octet-stream")}
    )
    assert response.status_code == 400
