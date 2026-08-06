"""Background worker thread.

A plain daemon thread, not asyncio: OCR and the model call are blocking and
CPU-bound, and one document at a time is right for a small local model.
Queue state lives in SQLite, so a restart resumes where it left off.
"""

from __future__ import annotations

import logging
import threading
import time

from . import db, pipeline
from .config import settings

log = logging.getLogger("docbox.worker")

_thread: threading.Thread | None = None
_stop = threading.Event()
_wake = threading.Event()


def wake() -> None:
    """Called after an upload so a new document is picked up immediately."""
    _wake.set()


def _requeue_orphans() -> None:
    """Anything left 'processing' by a crash goes back on the queue."""
    cur = db.execute(
        "UPDATE documents SET status = 'pending', next_attempt = ? WHERE status = 'processing'",
        (time.time(),),
    )
    if cur.rowcount:
        log.info("requeued %s interrupted document(s)", cur.rowcount)


def _loop() -> None:
    db.init_db()
    _requeue_orphans()
    while not _stop.is_set():
        doc_id = None
        try:
            doc_id = pipeline.claim_next()
            if doc_id is not None:
                log.info("processing document %s", doc_id)
                result = pipeline.process_document(doc_id)
                log.info("document %s -> %s", doc_id, result)
        except Exception:  # never let the worker die
            log.exception("worker iteration failed (doc %s)", doc_id)
            if doc_id is not None:
                try:
                    db.update("documents", doc_id, {
                        "status": "failed",
                        "error": "worker crashed",
                        "updated_at": time.time(),
                    })
                except Exception:
                    log.exception("could not mark document %s failed", doc_id)
            time.sleep(1)
        if doc_id is None:
            _wake.wait(settings.worker_poll_seconds)
            _wake.clear()


def start() -> None:
    global _thread
    if not settings.worker_enabled:
        log.info("worker disabled")
        return
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="docbox-worker", daemon=True)
    _thread.start()
    log.info("worker started")


def stop(timeout: float = 5.0) -> None:
    _stop.set()
    _wake.set()
    if _thread and _thread.is_alive():
        _thread.join(timeout=timeout)


def is_running() -> bool:
    return bool(_thread and _thread.is_alive())
