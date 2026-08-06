"""Import from Google Drive, which is where CamScanner auto-exports to.

The point: you keep scanning with whatever you like, the files land in Drive,
and Docbox picks them up on its own — no export step, no zip, no copying.

Two ways to authenticate:

* **Service account** (recommended, and the only one that needs no browser).
  Create one in Google Cloud, download the JSON key, then *share the Drive
  folder with the service account's email address* exactly as you would with a
  person. It sees that folder and nothing else, which is the security property
  you want for something running unattended.
* **OAuth refresh token**, if you would rather it act as you. Set the client id,
  secret and refresh token in the credentials file.

Sync is incremental: each run asks Drive only for files modified since the last
one, and content-hash dedupe means a re-run or an overlapping window never
imports anything twice.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from . import db, importer, storage
from .config import settings
from .ingest import IngestError, ingest_bytes

log = logging.getLogger("docbox.gdrive")

DRIVE_API = "https://www.googleapis.com/drive/v3"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE_READONLY = "https://www.googleapis.com/auth/drive.readonly"

# Google's own formats have no bytes to download; they would need exporting, and
# a CamScanner export never produces them.
GOOGLE_NATIVE_PREFIX = "application/vnd.google-apps"

STATE_KEY = "gdrive_last_sync"


@dataclass
class SyncReport:
    scanned: int = 0
    imported: int = 0
    duplicates: int = 0
    skipped: int = 0
    failed: int = 0
    batch_id: int | None = None
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "scanned": self.scanned,
            "imported": self.imported,
            "duplicates": self.duplicates,
            "skipped": self.skipped,
            "failed": self.failed,
            "batch_id": self.batch_id,
            "errors": self.errors[:20],
        }


class DriveError(Exception):
    pass


# --------------------------------------------------------------------- tokens


_token_cache: dict = {"value": "", "expires": 0.0}


def _credentials() -> dict:
    path = settings.gdrive_credentials
    if not path:
        raise DriveError("DOCBOX_GDRIVE_CREDENTIALS is not set")
    file = Path(path).expanduser()
    if not file.exists():
        raise DriveError(f"credentials file not found: {file}")
    try:
        return json.loads(file.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise DriveError(f"could not read {file}: {exc}") from exc


def access_token(force: bool = False) -> str:
    """A valid bearer token, cached until a minute before it expires."""
    if not force and _token_cache["value"] and _token_cache["expires"] > time.time() + 60:
        return _token_cache["value"]

    creds = _credentials()
    if creds.get("type") == "service_account":
        token, ttl = _service_account_token(creds)
    elif creds.get("refresh_token"):
        token, ttl = _refresh_token_grant(creds)
    else:
        raise DriveError(
            "credentials file must be a service-account key or contain "
            "client_id, client_secret and refresh_token"
        )
    _token_cache.update({"value": token, "expires": time.time() + ttl})
    return token


def _service_account_token(creds: dict) -> tuple[str, float]:
    try:
        from google.auth import jwt as google_jwt  # type: ignore
        from google.oauth2 import service_account  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on install
        raise DriveError(
            "service-account auth needs `google-auth` — pip install google-auth"
        ) from exc
    del google_jwt

    credentials = service_account.Credentials.from_service_account_info(
        creds, scopes=[SCOPE_READONLY]
    )
    from google.auth.transport.requests import Request  # type: ignore

    credentials.refresh(Request())
    expiry = credentials.expiry.timestamp() if credentials.expiry else time.time() + 3000
    return credentials.token, max(60.0, expiry - time.time())


def _refresh_token_grant(creds: dict) -> tuple[str, float]:
    response = httpx.post(TOKEN_URL, data={
        "client_id": creds["client_id"],
        "client_secret": creds["client_secret"],
        "refresh_token": creds["refresh_token"],
        "grant_type": "refresh_token",
    }, timeout=30)
    if response.status_code >= 400:
        raise DriveError(f"token refresh failed: {response.status_code} {response.text[:200]}")
    body = response.json()
    return body["access_token"], float(body.get("expires_in", 3600))


def _headers() -> dict:
    return {"authorization": f"Bearer {access_token()}"}


def _get(path: str, params: dict | None = None, stream: bool = False) -> httpx.Response:
    url = f"{DRIVE_API}{path}"
    for attempt in range(3):
        response = httpx.get(url, params=params, headers=_headers(), timeout=120,
                             follow_redirects=True)
        if response.status_code == 401 and attempt == 0:
            access_token(force=True)
            continue
        if response.status_code in {429, 500, 502, 503} and attempt < 2:
            time.sleep(2 ** attempt)
            continue
        if response.status_code >= 400:
            raise DriveError(f"drive {path}: {response.status_code} {response.text[:200]}")
        return response
    raise DriveError(f"drive {path}: giving up after retries")


# ----------------------------------------------------------------- discovery


def find_folder(name: str) -> str | None:
    """Resolve a folder name to an id. Shared-with-me folders count."""
    escaped = name.replace("'", "\\'")
    response = _get("/files", {
        "q": f"mimeType = 'application/vnd.google-apps.folder' and name = '{escaped}' "
             f"and trashed = false",
        "fields": "files(id,name)",
        "pageSize": 10,
        "includeItemsFromAllDrives": "true",
        "supportsAllDrives": "true",
    })
    files = response.json().get("files", [])
    if not files:
        return None
    if len(files) > 1:
        log.warning("%s folders named %r; using the first", len(files), name)
    return files[0]["id"]


def list_children(folder_id: str, modified_after: float = 0.0) -> list[dict]:
    """Every file under a folder, recursively, newest sync window only."""
    found: list[dict] = []
    stack = [(folder_id, "")]
    seen_folders: set[str] = set()

    while stack:
        current, prefix = stack.pop()
        if current in seen_folders:
            continue
        seen_folders.add(current)

        page_token = None
        while True:
            query = f"'{current}' in parents and trashed = false"
            params = {
                "q": query,
                "fields": "nextPageToken, files(id,name,mimeType,size,md5Checksum,modifiedTime)",
                "pageSize": 200,
                "includeItemsFromAllDrives": "true",
                "supportsAllDrives": "true",
                "orderBy": "modifiedTime",
            }
            if page_token:
                params["pageToken"] = page_token
            body = _get("/files", params).json()

            for item in body.get("files", []):
                if item["mimeType"] == f"{GOOGLE_NATIVE_PREFIX}.folder":
                    child_prefix = f"{prefix}/{item['name']}" if prefix else item["name"]
                    stack.append((item["id"], child_prefix))
                    continue
                item["_path"] = prefix
                # The recursive walk cannot be filtered server-side per folder,
                # so window the files here instead.
                if modified_after and _epoch(item.get("modifiedTime")) <= modified_after:
                    continue
                found.append(item)

            page_token = body.get("nextPageToken")
            if not page_token:
                break
    return found


def _epoch(timestamp: str | None) -> float:
    if not timestamp:
        return 0.0
    try:
        from datetime import datetime

        return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def download(file_id: str) -> bytes:
    return _get(f"/files/{file_id}", {"alt": "media", "supportsAllDrives": "true"}).content


# --------------------------------------------------------------------- state


def _get_state(key: str, default: str = "") -> str:
    row = db.query_one("SELECT value FROM state WHERE key = ?", (key,))
    return row["value"] if row else default


def _set_state(key: str, value: str) -> None:
    db.execute(
        "INSERT INTO state (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        (key, value, time.time()),
    )


# ---------------------------------------------------------------------- sync


def sync(user: str = "", into: str | None = None, full: bool = False,
         limit: int = 0) -> SyncReport:
    """Pull new files from the configured Drive folder into the library."""
    report = SyncReport()

    folder_id = settings.gdrive_folder_id
    if not folder_id:
        folder_id = find_folder(settings.gdrive_folder_name) or ""
        if not folder_id:
            raise DriveError(
                f"no Drive folder named {settings.gdrive_folder_name!r} is visible. "
                "Share it with the service account, or set DOCBOX_GDRIVE_FOLDER_ID."
            )

    since = 0.0 if full else float(_get_state(STATE_KEY, "0") or 0)
    started = time.time()
    files = list_children(folder_id, modified_after=since)
    files.sort(key=lambda f: f.get("modifiedTime") or "")
    if limit:
        files = files[:limit]

    report.scanned = len(files)
    if not files:
        _set_state(STATE_KEY, str(started))
        return report

    if not user:
        row = db.query_one("SELECT username FROM users ORDER BY id LIMIT 1")
        user = row["username"] if row else "gdrive"

    destination = into or settings.gdrive_into or settings.inbox_name
    report.batch_id = importer._start_batch(
        f"google-drive:{settings.gdrive_folder_name or folder_id}",
        len(files), user, kind="gdrive",
    )

    newest = since
    for item in files:
        newest = max(newest, _epoch(item.get("modifiedTime")))
        name = item.get("name") or item["id"]

        if item["mimeType"].startswith(GOOGLE_NATIVE_PREFIX):
            report.skipped += 1
            continue
        if Path(name).suffix.lower() not in storage.ALLOWED_EXTS:
            report.skipped += 1
            continue
        if importer.is_junk(Path(name)):
            report.skipped += 1
            continue

        try:
            data = download(item["id"])
        except DriveError as exc:
            report.failed += 1
            report.errors.append(f"{name}: {exc}")
            continue

        try:
            result = ingest_bytes(
                data, name, user,
                folder=destination,
                mime=item.get("mimeType", ""),
                hint=item.get("_path", ""),
                batch_id=report.batch_id,
            )
        except IngestError as exc:
            report.failed += 1
            report.errors.append(f"{name}: {exc}")
            continue

        if result.get("duplicate"):
            report.duplicates += 1
        else:
            report.imported += 1

    # Resume from the newest file we actually saw, not from "now": a file
    # uploaded while we were downloading would otherwise be skipped forever.
    _set_state(STATE_KEY, str(newest if newest > since else started))

    db.update("batches", report.batch_id, {
        "imported": report.imported,
        "skipped": report.skipped + report.duplicates,
        "failed": report.failed,
        "status": "done",
        "note": "; ".join(report.errors[:5]),
        "finished_at": time.time(),
    })
    log.info("drive sync: %s", report.as_dict())
    return report


def status() -> dict:
    last = float(_get_state(STATE_KEY, "0") or 0)
    return {
        "enabled": settings.gdrive_enabled,
        "configured": bool(settings.gdrive_credentials),
        "folder": settings.gdrive_folder_id or settings.gdrive_folder_name,
        "into": settings.gdrive_into or settings.inbox_name,
        "poll_minutes": settings.gdrive_poll_minutes,
        "last_sync": last,
        "watcher_running": is_running(),
    }


# -------------------------------------------------------------------- watcher


_thread: threading.Thread | None = None
_stop = threading.Event()
_wake = threading.Event()


def poke() -> None:
    _wake.set()


def _loop() -> None:
    db.init_db()
    # Give the app a moment to finish starting before the first call out.
    if _stop.wait(10):
        return
    while not _stop.is_set():
        try:
            sync()
        except DriveError as exc:
            log.warning("drive sync failed: %s", exc)
        except Exception:
            log.exception("drive watcher crashed; continuing")
        _wake.clear()
        _wake.wait(max(60, settings.gdrive_poll_minutes * 60))


def start() -> None:
    global _thread
    if not (settings.gdrive_enabled and settings.gdrive_credentials):
        return
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="docbox-gdrive", daemon=True)
    _thread.start()
    log.info("google drive watcher started (every %s min)", settings.gdrive_poll_minutes)


def stop(timeout: float = 5.0) -> None:
    _stop.set()
    _wake.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=timeout)


def is_running() -> bool:
    return bool(_thread and _thread.is_alive())
