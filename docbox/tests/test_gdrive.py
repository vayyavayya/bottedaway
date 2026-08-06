"""Google Drive sync, against a stub Drive API.

CamScanner auto-exports to Drive, so this path runs unattended on a timer —
which makes "never import the same file twice" and "never lose a file that
arrived mid-sync" the properties worth pinning down.
"""

from __future__ import annotations

import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest

from app import db, gdrive, storage
from app.config import settings

FOLDER_ID = "folder-root"

# id -> (name, mimeType, parent, modifiedTime, content)
FILES: dict[str, tuple] = {}


def reset_drive():
    """Fresh, uniquely-salted contents per test.

    The library dedupes by content hash across the whole session, so reusing the
    same bytes in two tests would make the second one see duplicates.
    """
    salt = secrets.token_hex(4)
    FILES.clear()
    FILES.update({
        "sub-insurance": ("Insurance", "application/vnd.google-apps.folder", FOLDER_ID,
                          "2024-01-01T00:00:00Z", b""),
        "f1": ("CamScanner 03-17-2024 10.22.pdf", "application/pdf", FOLDER_ID,
               "2024-03-17T10:22:00Z", f"%PDF-1.4\ndrive one {salt}\n%%EOF\n".encode()),
        "f2": ("policy.txt", "text/plain", "sub-insurance",
               "2024-04-01T09:00:00Z",
               f"Allianz policy 4711 dated 05.06.2023 annual premium {salt}".encode()),
        "f3": ("notes.ini", "text/plain", FOLDER_ID, "2024-04-02T09:00:00Z", b"[junk]"),
        "f4": ("Meeting notes", "application/vnd.google-apps.document", FOLDER_ID,
               "2024-04-03T09:00:00Z", b""),
    })


class _StubDrive(BaseHTTPRequestHandler):
    calls: list[str] = []

    def log_message(self, *_args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        _StubDrive.calls.append(parsed.path)

        if parsed.path == "/drive/v3/files":
            query = params.get("q", "")
            if "mimeType = 'application/vnd.google-apps.folder' and name =" in query:
                name = query.split("name = '")[1].split("'")[0]
                found = [{"id": fid, "name": meta[0]} for fid, meta in FILES.items()
                         if meta[1].endswith("folder") and meta[0] == name]
                if name == "CamScanner":
                    found = [{"id": FOLDER_ID, "name": "CamScanner"}]
                return self._send({"files": found})

            parent = query.split("'")[1] if "' in parents" in query else ""
            files = []
            for fid, (name, mime, par, modified, _body) in FILES.items():
                if par != parent:
                    continue
                files.append({"id": fid, "name": name, "mimeType": mime,
                              "modifiedTime": modified, "size": "10"})
            return self._send({"files": files})

        if parsed.path.startswith("/drive/v3/files/"):
            file_id = parsed.path.rsplit("/", 1)[-1]
            if file_id not in FILES:
                self.send_response(404)
                self.send_header("content-length", "0")
                self.end_headers()
                return
            body = FILES[file_id][4]
            self.send_response(200)
            self.send_header("content-type", "application/octet-stream")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.send_header("content-length", "0")
        self.end_headers()

    def _send(self, payload: dict):
        raw = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


@pytest.fixture()
def drive(monkeypatch):
    reset_drive()
    _StubDrive.calls.clear()
    server = HTTPServer(("127.0.0.1", 0), _StubDrive)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    monkeypatch.setattr(gdrive, "DRIVE_API", f"http://127.0.0.1:{server.server_port}/drive/v3")
    monkeypatch.setattr(gdrive, "access_token", lambda force=False: "stub-token")
    monkeypatch.setattr(settings, "gdrive_folder_id", FOLDER_ID)
    monkeypatch.setattr(settings, "gdrive_folder_name", "CamScanner")
    monkeypatch.setattr(settings, "gdrive_into", "")
    db.execute("DELETE FROM state WHERE key = ?", (gdrive.STATE_KEY,))
    yield server
    server.shutdown()
    server.server_close()


def test_sync_imports_documents_and_skips_the_rest(drive):
    report = gdrive.sync(user="tester")
    assert report.imported == 2                    # the PDF and the txt
    assert report.skipped == 2                     # the .ini and the Google Doc
    assert report.failed == 0

    row = db.query_one(
        "SELECT * FROM documents WHERE original_name = ? ORDER BY id DESC", ("policy.txt",)
    )
    assert row is not None
    assert row["source_hint"] == "Insurance"       # the Drive subfolder is kept
    assert storage.doc_path(row["folder"], row["filename"]).exists()


def test_second_sync_finds_nothing_new(drive):
    gdrive.sync(user="tester")
    again = gdrive.sync(user="tester")
    assert again.scanned == 0
    assert again.imported == 0


def test_new_file_is_picked_up_on_the_next_sync(drive):
    gdrive.sync(user="tester")
    FILES["f5"] = ("new scan.pdf", "application/pdf", FOLDER_ID,
                   "2024-06-01T12:00:00Z",
                   f"%PDF-1.4\nbrand new {secrets.token_hex(4)}\n%%EOF\n".encode())
    report = gdrive.sync(user="tester")
    assert report.scanned == 1
    assert report.imported == 1


def test_the_same_content_under_a_new_name_is_a_duplicate(drive):
    gdrive.sync(user="tester")
    FILES["f6"] = ("renamed copy.pdf", "application/pdf", FOLDER_ID,
                   "2024-06-02T12:00:00Z", FILES["f1"][4])
    report = gdrive.sync(user="tester")
    assert report.imported == 0
    assert report.duplicates == 1


def test_full_resync_rereads_everything_without_duplicating(drive):
    gdrive.sync(user="tester")
    report = gdrive.sync(user="tester", full=True)
    assert report.scanned == 4          # everything is looked at again
    assert report.imported == 0         # ...and nothing is stored twice
    assert report.duplicates == 2


def test_cursor_follows_the_newest_file_seen(drive):
    """Resuming from `now` would silently skip a file uploaded mid-sync, so the
    cursor tracks the newest file actually processed."""
    gdrive.sync(user="tester")
    cursor = float(db.query_one("SELECT value FROM state WHERE key = ?", (gdrive.STATE_KEY,))["value"])
    newest = gdrive._epoch("2024-04-03T09:00:00Z")
    assert cursor == pytest.approx(newest, abs=1)


def test_folder_can_be_found_by_name(drive, monkeypatch):
    monkeypatch.setattr(settings, "gdrive_folder_id", "")
    report = gdrive.sync(user="tester")
    assert report.imported == 2


def test_missing_folder_is_a_clear_error(drive, monkeypatch):
    monkeypatch.setattr(settings, "gdrive_folder_id", "")
    monkeypatch.setattr(settings, "gdrive_folder_name", "Nope")
    with pytest.raises(gdrive.DriveError, match="Nope"):
        gdrive.sync(user="tester")


def test_import_lands_in_a_configured_folder(drive, monkeypatch):
    monkeypatch.setattr(settings, "gdrive_into", "Scanner")
    gdrive.sync(user="tester")
    row = db.query_one(
        "SELECT * FROM documents WHERE original_name = ? ORDER BY id DESC", ("policy.txt",)
    )
    assert row["folder"] == "Scanner"


def test_status_reports_configuration(drive):
    gdrive.sync(user="tester")
    status = gdrive.status()
    assert status["last_sync"] > 0
    assert status["folder"] == FOLDER_ID


def test_missing_credentials_is_a_clear_error(monkeypatch):
    monkeypatch.setattr(settings, "gdrive_credentials", "")
    with pytest.raises(gdrive.DriveError, match="DOCBOX_GDRIVE_CREDENTIALS"):
        gdrive._credentials()
