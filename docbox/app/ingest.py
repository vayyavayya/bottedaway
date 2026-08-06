"""Everything that puts a new file into the library.

One entry point per shape of input: raw bytes (upload / share sheet), a set of
photos to staple into one PDF (multi-page scan), or a shared link.
"""

from __future__ import annotations

import hashlib
import io
import time
from datetime import datetime

from . import db, storage, worker
from .config import settings
from .naming import safe_filename, safe_folder
from .pipeline import enqueue


class IngestError(Exception):
    pass


def _duplicate(sha: str) -> dict | None:
    row = db.query_one(
        "SELECT * FROM documents WHERE sha256 = ? ORDER BY id DESC LIMIT 1", (sha,)
    )
    if not row:
        return None
    if not storage.doc_path(row["folder"], row["filename"]).exists():
        return None  # deleted outside the app; allow re-ingest
    return dict(row)


def ingest_bytes(
    data: bytes,
    filename: str,
    user: str,
    folder: str | None = None,
    mime: str = "",
    process: bool = True,
) -> dict:
    if not data:
        raise IngestError("empty file")
    limit = settings.max_upload_mb * 1024 * 1024
    if len(data) > limit:
        raise IngestError(f"file is larger than {settings.max_upload_mb} MB")

    original = safe_filename(filename or "scan")
    ext = storage.guess_ext(original, mime)
    if ext and not original.lower().endswith(ext):
        original = f"{original}{ext}"
    if ext and ext not in storage.ALLOWED_EXTS:
        raise IngestError(f"unsupported file type: {ext}")

    sha = hashlib.sha256(data).hexdigest()
    existing = _duplicate(sha)
    if existing:
        db.log_event(int(existing["id"]), "duplicate", f"re-uploaded as {original}", user)
        return {"duplicate": True, "document": existing}

    target_folder = safe_folder(folder or settings.inbox_name, settings.inbox_name)
    name, path = storage.write_upload(target_folder, original, data)

    now = time.time()
    doc_id = db.insert("documents", {
        "folder": target_folder,
        "filename": name,
        "original_name": original,
        "ext": ext,
        "mime": mime or storage.guess_mime(name),
        "size": len(data),
        "sha256": sha,
        "status": "pending" if process else "done",
        "next_attempt": now,
        "uploaded_by": user,
        "created_at": now,
        "updated_at": now,
    })
    db.log_event(doc_id, "uploaded", f"{original} -> {target_folder}/{name}", user)

    if process:
        enqueue(doc_id)
        worker.wake()

    row = db.query_one("SELECT * FROM documents WHERE id = ?", (doc_id,))
    return {"duplicate": False, "document": dict(row) if row else {"id": doc_id}}


def images_to_pdf(images: list[tuple[str, bytes]]) -> bytes:
    """Multi-page phone scan -> a single PDF, in the order given."""
    try:
        from PIL import Image  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on install
        raise IngestError("Pillow is required to combine images into a PDF") from exc

    try:
        import pillow_heif  # type: ignore

        pillow_heif.register_heif_opener()
    except Exception:
        pass

    pages = []
    for name, data in images:
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
        except Exception as exc:
            raise IngestError(f"could not read image {name}: {exc}") from exc
        pages.append(img.convert("RGB"))
    if not pages:
        raise IngestError("no images given")

    buffer = io.BytesIO()
    pages[0].save(buffer, format="PDF", save_all=True, append_images=pages[1:], resolution=200)
    for page in pages:
        page.close()
    return buffer.getvalue()


def ingest_scan(
    images: list[tuple[str, bytes]],
    user: str,
    folder: str | None = None,
    name_hint: str = "",
) -> dict:
    pdf = images_to_pdf(images)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = safe_filename(name_hint or f"scan-{stamp}")
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    return ingest_bytes(pdf, filename, user, folder=folder, mime="application/pdf")


def ingest_link(url: str, user: str, title: str = "", note: str = "", folder: str | None = None) -> dict:
    """iOS shares links far more often than files; keep them as readable notes."""
    url = (url or "").strip()
    if not url:
        raise IngestError("no url given")
    body = "\n".join(part for part in [title.strip(), url, note.strip()] if part)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = safe_filename(title or url.split("//")[-1].replace("/", "-") or f"link-{stamp}")[:60]
    return ingest_bytes(
        body.encode(),
        f"{filename}.txt",
        user,
        folder=folder,
        mime="text/plain",
    )
