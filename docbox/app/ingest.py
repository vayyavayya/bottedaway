"""Everything that puts a new file into the library.

One entry point per shape of input: raw bytes (upload / share sheet), a set of
photos to turn into a scanned PDF, or a shared link.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from . import db, enhance, pdfbuild, storage, worker
from .config import settings
from .naming import safe_filename, safe_folder
from .pipeline import enqueue

log = logging.getLogger("docbox.ingest")


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
    hint: str = "",
    batch_id: int | None = None,
    extra: dict | None = None,
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
    values = {
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
        "source_hint": hint[:200],
        "batch_id": batch_id,
        "created_at": now,
        "updated_at": now,
    }
    values.update(extra or {})
    doc_id = db.insert("documents", values)
    db.log_event(doc_id, "uploaded", f"{original} -> {target_folder}/{name}", user)

    if process:
        enqueue(doc_id)
        worker.wake()

    row = db.query_one("SELECT * FROM documents WHERE id = ?", (doc_id,))
    return {"duplicate": False, "document": dict(row) if row else {"id": doc_id}}


# ------------------------------------------------------------------ scanning


def _prepare_one(name: str, data: bytes, mode: str, crop: bool, orient: bool):
    try:
        return enhance.enhance(data, mode=mode, crop=crop, orient=orient)
    except Exception as exc:  # a bad page must not lose the whole scan
        log.warning("enhancement failed for %s: %s", name, exc)
        report = enhance.ScanReport(mode=mode, applied="failed")
        report.warnings.append(str(exc))
        return data, report


def prepare_pages(
    images: list[tuple[str, bytes]],
    mode: str = "auto",
    crop: bool = True,
    orient: bool = False,
) -> tuple[list[bytes], list[dict]]:
    """Run every captured photo through the enhancement pipeline.

    Pages go through a thread pool: OpenCV releases the GIL, so a 5-page scan
    costs about as much wall-clock as its slowest page rather than the sum.
    """
    if not images:
        return [], []
    if len(images) == 1:
        cleaned, report = _prepare_one(images[0][0], images[0][1], mode, crop, orient)
        return [cleaned], [report.as_dict()]

    for name, data in images:
        if not data:
            raise IngestError(f"empty page: {name}")

    workers = min(len(images), max(1, (os.cpu_count() or 2) - 1), 4)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(
            lambda item: _prepare_one(item[0], item[1], mode, crop, orient), images
        ))
    return [r[0] for r in results], [r[1].as_dict() for r in results]


def images_to_pdf(
    images: list[tuple[str, bytes]],
    mode: str = "auto",
    crop: bool = True,
    orient: bool = False,
    searchable: bool = True,
    dpi: int | None = None,
    quality: int | None = None,
) -> tuple[bytes, dict]:
    """Phone photos -> one enhanced, searchable, print-resolution PDF."""
    if not images:
        raise IngestError("no images given")

    pages, reports = prepare_pages(images, mode=mode, crop=crop, orient=orient)
    try:
        pdf, report = pdfbuild.build_pdf(
            pages,
            dpi=dpi or settings.scan_dpi,
            quality=quality or settings.scan_quality,
            searchable=searchable,
            langs=settings.ocr_langs,
            page_size=settings.scan_page_size,
        )
    except Exception as exc:
        raise IngestError(f"could not build the PDF: {exc}") from exc

    return pdf, {"pages": reports, "pdf": report.as_dict()}


def ingest_scan(
    images: list[tuple[str, bytes]],
    user: str,
    folder: str | None = None,
    name_hint: str = "",
    enhance_mode: str = "auto",
    crop: bool = True,
    orient: bool = False,
    searchable: bool = True,
    hint: str = "",
    batch_id: int | None = None,
    process: bool = True,
) -> dict:
    pdf, report = images_to_pdf(
        images, mode=enhance_mode, crop=crop, orient=orient, searchable=searchable
    )
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = safe_filename(name_hint or f"scan-{stamp}")
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    result = ingest_bytes(
        pdf, filename, user,
        folder=folder,
        mime="application/pdf",
        process=process,
        hint=hint,
        batch_id=batch_id,
        extra={
            "page_count": report["pdf"].get("pages", len(images)),
            "scan_report": json.dumps(report)[:4000],
            "enhance_mode": enhance_mode,
            "searchable": 1 if report["pdf"].get("searchable") else 0,
        },
    )
    result["scan"] = report
    return result


def rebuild_scan(doc_id: int, mode: str, user: str) -> dict:
    """Re-run enhancement on an existing scan (a different mode, or a retry).

    Only possible for image files — a PDF's original photos are gone once the
    PDF is built, which is exactly why the UI asks for the mode before saving.
    """
    row = db.query_one("SELECT * FROM documents WHERE id = ?", (doc_id,))
    if not row:
        raise IngestError("document not found")
    if row["ext"] not in storage.IMAGE_EXTS:
        raise IngestError("only image documents can be re-enhanced")

    path = storage.doc_path(row["folder"], row["filename"])
    if not path.exists():
        raise IngestError("file missing on disk")

    cleaned, report = enhance.enhance(path.read_bytes(), mode=mode)
    path.write_bytes(cleaned)
    db.update("documents", doc_id, {
        "size": len(cleaned),
        "sha256": hashlib.sha256(cleaned).hexdigest(),
        "enhance_mode": mode,
        "scan_report": json.dumps({"pages": [report.as_dict()]})[:4000],
        "updated_at": time.time(),
    })
    db.log_event(doc_id, "enhanced", f"mode={mode}", user)
    return {"ok": True, "report": report.as_dict()}


# --------------------------------------------------------------------- links


def ingest_link(url: str, user: str, title: str = "", note: str = "",
                folder: str | None = None) -> dict:
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
