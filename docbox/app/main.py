"""FastAPI app: JSON API + the PWA that iOS Safari installs to the home screen."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import auth, db, extract, ingest, llm, storage, worker
from .config import settings
from .naming import safe_filename, safe_folder
from .pipeline import enqueue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("docbox")

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.ensure_dirs()
    settings.resolve_secret()
    db.init_db()
    worker.start()
    log.info("library at %s", settings.library_dir)
    yield
    worker.stop()


app = FastAPI(title="Docbox", version="1.0.0", lifespan=lifespan)


def user_dep(request: Request) -> dict:
    return auth.require_user(request)


# ------------------------------------------------------------------ payloads


class LoginBody(BaseModel):
    username: str
    password: str


class SetupBody(BaseModel):
    username: str
    password: str


class FolderBody(BaseModel):
    name: str


class DocumentPatch(BaseModel):
    filename: str | None = None
    folder: str | None = None
    title: str | None = None
    doc_type: str | None = None
    correspondent: str | None = None
    needs_review: bool | None = None
    pinned_name: bool | None = None


class LinkBody(BaseModel):
    url: str
    title: str = ""
    note: str = ""
    folder: str | None = None


def doc_json(row) -> dict:
    data = dict(row)
    data.pop("text_excerpt", None)
    data["needs_review"] = bool(data.get("needs_review"))
    data["pinned_name"] = bool(data.get("pinned_name"))
    data["renamed"] = bool(data.get("renamed"))
    return data


# --------------------------------------------------------------------- auth


@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "needs_setup": auth.user_count() == 0,
        "library": str(settings.library_dir),
        "inbox": settings.inbox_name,
        "worker_running": worker.is_running(),
        "llm": {
            "enabled": settings.llm_enabled,
            "reachable": llm.available(),
            "model": settings.llm_model,
            "vision_model": settings.vision_model or None,
            "installed": llm.installed_models(),
        },
        "extraction": extract.capabilities(),
    }


@app.post("/api/setup")
def setup(body: SetupBody) -> Response:
    """First run only: create the first account. Locked once a user exists."""
    if auth.user_count() > 0:
        raise HTTPException(status_code=403, detail="already set up; use the CLI to add users")
    try:
        user = auth.create_user(body.username, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = JSONResponse({"ok": True, "user": user})
    _set_session_cookie(response, user["id"])
    return response


@app.post("/api/login")
def login(body: LoginBody) -> Response:
    user = auth.authenticate(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="wrong username or password")
    response = JSONResponse({"ok": True, "user": {"id": user["id"], "username": user["username"]}})
    _set_session_cookie(response, user["id"])
    return response


def _set_session_cookie(response: Response, user_id: int) -> None:
    response.set_cookie(
        auth.SESSION_COOKIE,
        auth.make_session(user_id),
        max_age=settings.session_days * 86400,
        httponly=True,
        samesite="lax",
        path="/",
    )


@app.post("/api/logout")
def logout() -> Response:
    response = JSONResponse({"ok": True})
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return response


@app.get("/api/me")
def me(user: dict = Depends(user_dep)) -> dict:
    row = db.query_one("SELECT api_token FROM users WHERE id = ?", (user["id"],))
    return {"user": user, "api_token": row["api_token"] if row else ""}


@app.post("/api/me/token")
def rotate_token(user: dict = Depends(user_dep)) -> dict:
    return {"api_token": auth.rotate_token(user["id"])}


# ---------------------------------------------------------------- documents


@app.get("/api/folders")
def folders(user: dict = Depends(user_dep)) -> dict:
    counts = {
        row["folder"]: row["n"]
        for row in db.query("SELECT folder, COUNT(*) AS n FROM documents GROUP BY folder")
    }
    return {
        "folders": [
            {"name": name, "count": counts.get(name, 0), "inbox": name == settings.inbox_name}
            for name in storage.list_folders()
        ]
    }


@app.post("/api/folders")
def add_folder(body: FolderBody, user: dict = Depends(user_dep)) -> dict:
    try:
        return {"name": storage.create_folder(body.name)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/documents")
def list_documents(
    folder: str = "",
    q: str = "",
    status: str = "",
    review: bool = False,
    limit: int = 100,
    offset: int = 0,
    user: dict = Depends(user_dep),
) -> dict:
    where, params = [], []
    if folder:
        where.append("folder = ?")
        params.append(safe_folder(folder, settings.inbox_name))
    if status:
        where.append("status = ?")
        params.append(status)
    if review:
        where.append("needs_review = 1")
    if q:
        like = f"%{q.strip()}%"
        where.append(
            "(filename LIKE ? OR title LIKE ? OR correspondent LIKE ? "
            "OR summary LIKE ? OR original_name LIKE ? OR text_excerpt LIKE ?)"
        )
        params.extend([like] * 6)

    clause = f"WHERE {' AND '.join(where)}" if where else ""
    total = db.query_one(f"SELECT COUNT(*) AS n FROM documents {clause}", params)
    rows = db.query(
        f"SELECT * FROM documents {clause} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
        [*params, max(1, min(limit, 500)), max(0, offset)],
    )
    return {
        "documents": [doc_json(r) for r in rows],
        "total": int(total["n"]) if total else 0,
    }


def _get_doc(doc_id: int):
    row = db.query_one("SELECT * FROM documents WHERE id = ?", (doc_id,))
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    return row


@app.get("/api/documents/{doc_id}")
def get_document(doc_id: int, user: dict = Depends(user_dep)) -> dict:
    row = _get_doc(doc_id)
    events = db.query(
        "SELECT kind, message, actor, created_at FROM events WHERE doc_id = ? "
        "ORDER BY id DESC LIMIT 20",
        (doc_id,),
    )
    data = doc_json(row)
    data["text_excerpt"] = row["text_excerpt"]
    data["events"] = [dict(e) for e in events]
    return {"document": data}


@app.get("/api/documents/{doc_id}/file")
def get_file(doc_id: int, download: bool = False, user: dict = Depends(user_dep)):
    row = _get_doc(doc_id)
    path = storage.doc_path(row["folder"], row["filename"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="file missing on disk")
    disposition = "attachment" if download else "inline"
    return FileResponse(
        path,
        media_type=row["mime"] or storage.guess_mime(row["filename"]),
        headers={"Content-Disposition": f'{disposition}; filename="{row["filename"]}"'},
    )


@app.patch("/api/documents/{doc_id}")
def patch_document(doc_id: int, body: DocumentPatch, user: dict = Depends(user_dep)) -> dict:
    row = _get_doc(doc_id)
    updates: dict = {}

    new_folder = row["folder"]
    new_name = row["filename"]
    if body.folder is not None:
        new_folder = safe_folder(body.folder, settings.inbox_name)
    if body.filename is not None:
        new_name = safe_filename(body.filename)
        if not new_name:
            raise HTTPException(status_code=400, detail="invalid filename")
        if row["ext"] and not new_name.lower().endswith(row["ext"]):
            new_name += row["ext"]

    if (new_folder, new_name) != (row["folder"], row["filename"]):
        try:
            final = storage.move_document(row["folder"], row["filename"], new_folder, new_name)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="file missing on disk") from exc
        updates["folder"] = new_folder
        updates["filename"] = final
        # A hand-picked name should survive the next AI pass.
        if body.filename is not None and body.pinned_name is None:
            updates["pinned_name"] = 1
        db.log_event(doc_id, "moved", f"{row['folder']}/{row['filename']} -> {new_folder}/{final}", user["username"])

    for field in ("title", "doc_type", "correspondent"):
        value = getattr(body, field)
        if value is not None:
            updates[field] = value.strip()[:120]
    if body.needs_review is not None:
        updates["needs_review"] = 1 if body.needs_review else 0
    if body.pinned_name is not None:
        updates["pinned_name"] = 1 if body.pinned_name else 0

    if updates:
        updates["updated_at"] = time.time()
        db.update("documents", doc_id, updates)
    return {"document": doc_json(_get_doc(doc_id))}


@app.post("/api/documents/{doc_id}/reprocess")
def reprocess(doc_id: int, unpin: bool = True, user: dict = Depends(user_dep)) -> dict:
    row = _get_doc(doc_id)
    if unpin and row["pinned_name"]:
        db.update("documents", doc_id, {"pinned_name": 0})
    db.update("documents", doc_id, {"attempts": 0})
    enqueue(doc_id)
    worker.wake()
    db.log_event(doc_id, "requeued", "manual reprocess", user["username"])
    return {"ok": True, "status": "pending"}


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int, user: dict = Depends(user_dep)) -> dict:
    row = _get_doc(doc_id)
    storage.delete_document(row["folder"], row["filename"])
    db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    db.log_event(None, "deleted", f"{row['folder']}/{row['filename']}", user["username"])
    return {"ok": True}


@app.get("/api/stats")
def stats(user: dict = Depends(user_dep)) -> dict:
    row = db.query_one(
        "SELECT COUNT(*) AS total, "
        "SUM(status = 'pending') AS pending, "
        "SUM(status = 'processing') AS processing, "
        "SUM(status = 'failed') AS failed, "
        "SUM(needs_review = 1) AS review FROM documents"
    )
    inbox = db.query_one(
        "SELECT COUNT(*) AS n FROM documents WHERE folder = ?", (settings.inbox_name,)
    )
    return {
        "total": int(row["total"] or 0),
        "pending": int(row["pending"] or 0),
        "processing": int(row["processing"] or 0),
        "failed": int(row["failed"] or 0),
        "needs_review": int(row["review"] or 0),
        "inbox": int(inbox["n"] or 0) if inbox else 0,
    }


# ------------------------------------------------------------------- ingest


@app.post("/api/upload")
async def upload(
    request: Request,
    files: list[UploadFile] = File(default=[]),
    folder: str = Form(default=""),
    combine: bool = Form(default=False),
    name: str = Form(default=""),
    user: dict = Depends(user_dep),
) -> dict:
    """Multipart upload. `combine=true` staples the images into one PDF."""
    uploads = list(files)
    if not uploads:
        # Shortcuts and some share extensions post the part under a different name.
        form = await request.form()
        uploads = [v for v in form.values() if isinstance(v, UploadFile)]
    if not uploads:
        raise HTTPException(status_code=400, detail="no files in request")

    payloads: list[tuple[str, bytes, str]] = []
    for item in uploads:
        payloads.append((item.filename or "scan", await item.read(), item.content_type or ""))

    try:
        if combine and len(payloads) > 1:
            result = ingest.ingest_scan(
                [(fname, data) for fname, data, _ in payloads],
                user["username"],
                folder=folder or None,
                name_hint=name,
            )
            return {"results": [result]}

        results = []
        for fname, data, mime in payloads:
            results.append(
                ingest.ingest_bytes(
                    data, name or fname, user["username"], folder=folder or None, mime=mime
                )
            )
        return {"results": results}
    except ingest.IngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/scan")
async def scan(
    files: list[UploadFile] = File(...),
    folder: str = Form(default=""),
    name: str = Form(default=""),
    user: dict = Depends(user_dep),
) -> dict:
    """Camera pages in order -> one PDF in the inbox."""
    images = [(f.filename or "page", await f.read()) for f in files]
    try:
        return ingest.ingest_scan(images, user["username"], folder=folder or None, name_hint=name)
    except ingest.IngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/link")
def add_link(body: LinkBody, user: dict = Depends(user_dep)) -> dict:
    try:
        return ingest.ingest_link(
            body.url, user["username"], title=body.title, note=body.note, folder=body.folder
        )
    except ingest.IngestError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/share-target")
async def share_target(
    request: Request,
    title: str = Form(default=""),
    text: str = Form(default=""),
    url: str = Form(default=""),
    files: list[UploadFile] = File(default=[]),
    user: dict = Depends(user_dep),
):
    """Web Share Target (Android/desktop PWAs). iOS uses the Shortcut in SHORTCUT.md."""
    handled = 0
    for item in files:
        data = await item.read()
        if data:
            ingest.ingest_bytes(data, item.filename or "shared", user["username"], mime=item.content_type or "")
            handled += 1
    shared_url = url or next((w for w in text.split() if w.startswith("http")), "")
    if shared_url:
        ingest.ingest_link(shared_url, user["username"], title=title, note=text)
        handled += 1
    elif text and not handled:
        ingest.ingest_bytes(
            text.encode(), f"{safe_filename(title or 'note')}.txt", user["username"], mime="text/plain"
        )
        handled += 1
    return RedirectResponse(url="/?shared=1", status_code=303)


# ----------------------------------------------------------------- web shell


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html", media_type="text/html")


@app.get("/manifest.webmanifest")
def manifest() -> FileResponse:
    return FileResponse(WEB_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker() -> FileResponse:
    return FileResponse(
        WEB_DIR / "sw.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")
