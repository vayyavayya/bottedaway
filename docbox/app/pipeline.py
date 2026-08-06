"""The actual job: read a document, ask the local model what it is, name it,
and file it in the right folder."""

from __future__ import annotations

import time
from pathlib import Path

from . import db, extract, llm, routing, storage
from .config import settings
from .naming import build_filename, find_date_in_text
from .storage import IMAGE_EXTS

# Below this the model is guessing; keep the name but ask a human to glance at it.
CONFIDENCE_FLOOR = 0.35


def enqueue(doc_id: int, delay: float = 0.0) -> None:
    db.update(
        "documents",
        doc_id,
        {
            "status": "pending",
            "next_attempt": time.time() + delay,
            "error": "",
            "updated_at": time.time(),
        },
    )


def claim_next() -> int | None:
    """Atomically take one pending document off the queue."""
    row = db.query_one(
        "SELECT id FROM documents WHERE status = 'pending' AND next_attempt <= ? "
        "ORDER BY next_attempt ASC, id ASC LIMIT 1",
        (time.time(),),
    )
    if not row:
        return None
    cur = db.execute(
        "UPDATE documents SET status = 'processing', updated_at = ? "
        "WHERE id = ? AND status = 'pending'",
        (time.time(), row["id"]),
    )
    return int(row["id"]) if cur.rowcount else None


def analyze_file(path: Path, original_name: str, hint: str = "") -> tuple[llm.Analysis, extract.Extraction]:
    """Extraction + model call, with the fallbacks laid out in order."""
    extraction = extract.extract(path)

    analysis = llm.Analysis(source="none")
    if extraction.usable:
        analysis = llm.analyze_text(extraction.text, original_name, hint=hint)

    if analysis.source == "none" and path.suffix.lower() in IMAGE_EXTS:
        vision = llm.analyze_image(path)
        if vision.source != "none":
            analysis = vision

    if analysis.source == "none" or not analysis.title:
        fallback = llm.heuristic(extraction.text, original_name)
        fallback.error = analysis.error
        analysis = fallback

    # The model is told never to invent a date. If it gave none, scrape the
    # text, then the filename — scanner apps stamp the date into it.
    if not analysis.date:
        analysis.date = find_date_in_text(extraction.text) or find_date_in_text(original_name)

    return analysis, extraction


def process_document(doc_id: int) -> dict:
    row = db.query_one("SELECT * FROM documents WHERE id = ?", (doc_id,))
    if not row:
        return {"ok": False, "error": "not found"}

    path = storage.doc_path(row["folder"], row["filename"])
    if not path.exists():
        db.update("documents", doc_id, {
            "status": "failed",
            "error": "file missing on disk",
            "updated_at": time.time(),
        })
        db.log_event(doc_id, "error", "file missing on disk")
        return {"ok": False, "error": "file missing"}

    try:
        analysis, extraction = analyze_file(
            path, row["original_name"] or row["filename"], hint=row["source_hint"]
        )
    except Exception as exc:  # extraction/model crash must not lose the file
        attempts = int(row["attempts"]) + 1
        failed = attempts >= settings.max_attempts
        db.update("documents", doc_id, {
            "status": "failed" if failed else "pending",
            "attempts": attempts,
            "next_attempt": time.time() + min(60 * attempts, 300),
            "error": f"{type(exc).__name__}: {exc}"[:500],
            "needs_review": 1,
            "updated_at": time.time(),
        })
        db.log_event(doc_id, "error", f"{type(exc).__name__}: {exc}")
        return {"ok": False, "error": str(exc)}

    weak = (
        analysis.source == "heuristic"
        or analysis.confidence < CONFIDENCE_FLOOR
        or not analysis.date
        or not analysis.title
    )

    # --- where does it belong?
    folder = row["folder"]
    routed_by = ""
    if settings.auto_file and not row["pinned_name"]:
        route = routing.choose_folder(analysis, extraction.text, current=folder)
        if route.confident and route.folder != folder:
            folder = route.folder
            routed_by = route.rule

    # --- what is it called?
    filename = row["filename"]
    renamed = False
    if not row["pinned_name"]:
        filename = build_filename(
            analysis.date,
            analysis.title,
            row["ext"].lstrip("."),
            extra=analysis.correspondent,
        )

    if (folder, filename) != (row["folder"], row["filename"]):
        filename = storage.move_document(row["folder"], row["filename"], folder, filename)
        renamed = True
        if routed_by:
            db.log_event(doc_id, "filed", f"{row['folder']} -> {folder} ({routed_by})")

    db.update("documents", doc_id, {
        "folder": folder,
        "filename": filename,
        "status": "done",
        "attempts": int(row["attempts"]) + 1,
        "needs_review": 1 if weak else 0,
        "title": analysis.title,
        "doc_date": analysis.date,
        "doc_type": analysis.doc_type,
        "correspondent": analysis.correspondent,
        "summary": analysis.summary,
        "confidence": analysis.confidence,
        "text_excerpt": extraction.text[:4000],
        "error": analysis.error,
        "renamed": 1 if (renamed or row["renamed"]) else 0,
        "routed_by": routed_by,
        "updated_at": time.time(),
        "processed_at": time.time(),
    })
    db.log_event(
        doc_id,
        "processed",
        f"{analysis.source}/{extraction.method} -> {folder}/{filename}"
        + (f" ({analysis.error})" if analysis.error else ""),
    )
    return {
        "ok": True,
        "folder": folder,
        "filename": filename,
        "renamed": renamed,
        "routed_by": routed_by,
        "source": analysis.source,
        "method": extraction.method,
        "needs_review": weak,
    }
