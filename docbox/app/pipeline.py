"""The actual job: read a document, ask the local model what it is, rename it."""

from __future__ import annotations

import time
from pathlib import Path

from . import db, extract, llm, storage
from .config import settings
from .naming import build_filename, find_date_in_text

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


def analyze_file(path: Path, original_name: str) -> tuple[llm.Analysis, extract.Extraction]:
    """Extraction + model call, with the fallbacks laid out in order."""
    extraction = extract.extract(path)

    analysis = llm.Analysis(source="none")
    if extraction.usable:
        analysis = llm.analyze_text(extraction.text, original_name)

    if analysis.source == "none" and path.suffix.lower() in storage.IMAGE_EXTS:
        vision = llm.analyze_image(path)
        if vision.source != "none":
            analysis = vision

    if analysis.source == "none" or not analysis.title:
        fallback = llm.heuristic(extraction.text, original_name)
        fallback.error = analysis.error
        analysis = fallback

    # The model is told never to invent a date; if it gave none, scrape the text.
    if not analysis.date:
        analysis.date = find_date_in_text(extraction.text)

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
        analysis, extraction = analyze_file(path, row["original_name"] or row["filename"])
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

    filename = row["filename"]
    renamed = False
    if not row["pinned_name"]:
        wanted = build_filename(
            analysis.date,
            analysis.title,
            row["ext"].lstrip("."),
            extra=analysis.correspondent,
        )
        if wanted != filename:
            filename = storage.move_document(row["folder"], filename, row["folder"], wanted)
            renamed = True

    weak = (
        analysis.source == "heuristic"
        or analysis.confidence < CONFIDENCE_FLOOR
        or not analysis.date
        or not analysis.title
    )

    db.update("documents", doc_id, {
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
        "updated_at": time.time(),
        "processed_at": time.time(),
    })
    db.log_event(
        doc_id,
        "processed",
        f"{analysis.source}/{extraction.method} -> {filename}"
        + (f" ({analysis.error})" if analysis.error else ""),
    )
    return {
        "ok": True,
        "filename": filename,
        "renamed": renamed,
        "source": analysis.source,
        "method": extraction.method,
        "needs_review": weak,
    }
