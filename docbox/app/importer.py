"""Bulk import — bringing years of CamScanner exports into the library.

Feed it a folder or a zip. It walks everything, skips what is already here
(hash match), keeps the source folder name as a hint for the model, and queues
each document for OCR, classification and filing.

Getting your documents out of CamScanner first (Premium can do all of these):
  * iOS app -> select all -> Share -> Save to Files -> a folder in iCloud Drive
  * or Share -> Save as PDF for each folder, which preserves multi-page docs
  * or the desktop web app at cs.camscanner.com -> select -> Download

Then either point Docbox at that folder:

    python -m app.cli import ~/Downloads/CamScanner --user you

or zip it and upload it in the app under Settings -> Import.
"""

from __future__ import annotations

import logging
import re
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from . import db, storage, worker
from .config import settings
from .ingest import IngestError, ingest_bytes
from .naming import safe_folder

log = logging.getLogger("docbox.import")

# Files an export leaves behind that are not documents.
JUNK_NAMES = {".ds_store", "thumbs.db", ".localized", "desktop.ini"}
JUNK_SUFFIXES = {".ini", ".plist", ".db", ".sqlite", ".json.bak"}

# `CamScanner 03-17-2024 10.22.pdf`, `Doc 3 Mar 12, 2024.pdf`, `新文档 2024-01-02`
_SEQ_SUFFIX = re.compile(r"[ _-]?\(?\d{1,3}\)?$")


@dataclass
class ImportReport:
    total: int = 0
    imported: int = 0
    skipped_duplicate: int = 0
    skipped_unsupported: int = 0
    failed: int = 0
    batch_id: int | None = None
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "total": self.total,
            "imported": self.imported,
            "duplicates": self.skipped_duplicate,
            "unsupported": self.skipped_unsupported,
            "failed": self.failed,
            "batch_id": self.batch_id,
            "errors": self.errors[:20],
        }


def is_junk(path: Path) -> bool:
    name = path.name.lower()
    if name in JUNK_NAMES or name.startswith("._") or name.startswith("."):
        return True
    return path.suffix.lower() in JUNK_SUFFIXES


def collect(root: Path) -> list[Path]:
    """Every importable file under `root`, deepest paths last for stable order."""
    found = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or is_junk(path):
            continue
        if path.suffix.lower() not in storage.ALLOWED_EXTS:
            continue
        found.append(path)
    return found


def source_hint(path: Path, root: Path) -> str:
    """The export's own folder names — real signal about what a document is."""
    try:
        relative = path.relative_to(root).parent
    except ValueError:
        return ""
    parts = [
        part for part in relative.parts
        if part not in {".", ""} and not part.lower().startswith("camscanner")
    ]
    return "/".join(parts[-3:])


def group_key(path: Path) -> str:
    """`Doc 3_1.jpg` and `Doc 3_2.jpg` -> the same key, so pages stay together."""
    stem = path.stem
    stem = _SEQ_SUFFIX.sub("", stem)
    return f"{path.parent}/{stem.strip().lower()}"


def _start_batch(source: str, total: int, actor: str, kind: str = "import") -> int:
    return db.insert("batches", {
        "kind": kind,
        "source": source[:300],
        "total": total,
        "status": "running",
        "actor": actor,
        "created_at": time.time(),
    })


def _finish_batch(batch_id: int, report: ImportReport) -> None:
    db.update("batches", batch_id, {
        "imported": report.imported,
        "skipped": report.skipped_duplicate + report.skipped_unsupported,
        "failed": report.failed,
        "status": "done",
        "note": "; ".join(report.errors[:5]),
        "finished_at": time.time(),
    })


def import_folder(
    root: Path,
    user: str,
    into: str | None = None,
    group_images: bool = False,
    process: bool = True,
    progress=None,
) -> ImportReport:
    """Import a directory tree. Everything lands in the inbox (or `into`) and is
    filed by the worker once the model has read it."""
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise IngestError(f"not a folder: {root}")

    files = collect(root)
    report = ImportReport(total=len(files))
    report.batch_id = _start_batch(str(root), len(files), user)
    destination = safe_folder(into or settings.inbox_name, settings.inbox_name)

    groups: dict[str, list[Path]] = {}
    if group_images:
        for path in files:
            if path.suffix.lower() in storage.IMAGE_EXTS:
                groups.setdefault(group_key(path), []).append(path)
        groups = {k: v for k, v in groups.items() if len(v) > 1}

    consumed: set[Path] = set()
    for key, pages in groups.items():
        consumed.update(pages)
        _import_image_group(pages, root, user, destination, report, process)
        if progress:
            progress(report)

    for path in files:
        if path in consumed:
            continue
        _import_one(path, root, user, destination, report, process)
        if progress:
            progress(report)

    _finish_batch(report.batch_id, report)
    if process:
        worker.wake()
    return report


def _import_one(path: Path, root: Path, user: str, destination: str,
                report: ImportReport, process: bool) -> None:
    try:
        data = path.read_bytes()
    except OSError as exc:
        report.failed += 1
        report.errors.append(f"{path.name}: {exc}")
        return
    if not data:
        report.skipped_unsupported += 1
        return
    try:
        result = ingest_bytes(
            data, path.name, user,
            folder=destination,
            mime=storage.guess_mime(path.name),
            process=process,
            hint=source_hint(path, root),
            batch_id=report.batch_id,
        )
    except IngestError as exc:
        message = str(exc)
        if "unsupported" in message:
            report.skipped_unsupported += 1
        else:
            report.failed += 1
            report.errors.append(f"{path.name}: {message}")
        return
    if result.get("duplicate"):
        report.skipped_duplicate += 1
    else:
        report.imported += 1


def _import_image_group(pages: list[Path], root: Path, user: str, destination: str,
                        report: ImportReport, process: bool) -> None:
    """Several JPGs that were one document before the export split them."""
    from .ingest import ingest_scan

    payload = []
    for page in sorted(pages):
        try:
            payload.append((page.name, page.read_bytes()))
        except OSError as exc:
            report.errors.append(f"{page.name}: {exc}")
    if not payload:
        report.failed += len(pages)
        return
    try:
        result = ingest_scan(
            payload, user,
            folder=destination,
            name_hint=Path(payload[0][0]).stem,
            enhance_mode="none",  # already processed by whatever exported them
            searchable=True,
            hint=source_hint(pages[0], root),
            batch_id=report.batch_id,
            process=process,
        )
    except IngestError as exc:
        report.failed += len(pages)
        report.errors.append(f"{pages[0].name} (+{len(pages) - 1}): {exc}")
        return
    if result.get("duplicate"):
        report.skipped_duplicate += 1
    else:
        report.imported += 1


def import_zip(data: bytes, user: str, into: str | None = None,
               group_images: bool = False, process: bool = True) -> ImportReport:
    """Same, from an uploaded archive. Extracted to a temp dir, then imported."""
    import tempfile

    with tempfile.TemporaryDirectory(prefix="docbox-import-") as tmp:
        root = Path(tmp)
        try:
            with zipfile.ZipFile(_as_stream(data)) as archive:
                for member in archive.infolist():
                    if member.is_dir():
                        continue
                    target = _safe_extract_path(root, member.filename)
                    if target is None:
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(member) as source, target.open("wb") as out:
                        while chunk := source.read(1024 * 256):
                            out.write(chunk)
        except zipfile.BadZipFile as exc:
            raise IngestError(f"not a readable zip: {exc}") from exc

        return import_folder(root, user, into=into, group_images=group_images, process=process)


def _as_stream(data: bytes):
    import io

    return io.BytesIO(data)


def _safe_extract_path(root: Path, name: str) -> Path | None:
    """Refuse zip entries that would write outside the extraction directory."""
    candidate = (root / name).resolve()
    if root.resolve() not in candidate.parents and candidate != root.resolve():
        log.warning("skipping unsafe zip entry %r", name)
        return None
    return candidate


def batch_status(batch_id: int) -> dict | None:
    row = db.query_one("SELECT * FROM batches WHERE id = ?", (batch_id,))
    if not row:
        return None
    data = dict(row)
    pending = db.query_one(
        "SELECT COUNT(*) AS n FROM documents WHERE batch_id = ? AND status IN ('pending','processing')",
        (batch_id,),
    )
    done = db.query_one(
        "SELECT COUNT(*) AS n FROM documents WHERE batch_id = ? AND status = 'done'",
        (batch_id,),
    )
    data["queued"] = int(pending["n"] or 0) if pending else 0
    data["processed"] = int(done["n"] or 0) if done else 0
    return data
