"""Files on disk. The library is a plain folder tree you can also open in Finder."""

from __future__ import annotations

import hashlib
import mimetypes
import shutil
from pathlib import Path

from .config import settings
from .naming import dedupe_filename, safe_filename, safe_folder

TEXT_EXTS = {".txt", ".md", ".csv", ".log", ".json", ".url"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif", ".tif", ".tiff", ".bmp"}
DOC_EXTS = {".pdf", ".docx", ".doc", ".rtf", ".odt", ".pptx", ".xlsx"}
ALLOWED_EXTS = TEXT_EXTS | IMAGE_EXTS | DOC_EXTS | {".eml", ".epub", ".zip"}


def library_root() -> Path:
    settings.ensure_dirs()
    return settings.library_dir


def folder_path(folder: str) -> Path:
    """Resolve a folder name inside the library, refusing anything that escapes it."""
    name = safe_folder(folder, settings.inbox_name)
    path = (library_root() / name).resolve()
    root = library_root().resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"folder escapes library: {folder!r}")
    return path


def doc_path(folder: str, filename: str) -> Path:
    return folder_path(folder) / safe_filename(filename)


def list_folders() -> list[str]:
    root = library_root()
    names = sorted(
        (p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")),
        key=lambda n: (n != settings.inbox_name, n.lower()),
    )
    if settings.inbox_name not in names:
        names.insert(0, settings.inbox_name)
    return names


def create_folder(name: str) -> str:
    folder = safe_folder(name, "")
    if not folder:
        raise ValueError("invalid folder name")
    (library_root() / folder).mkdir(parents=True, exist_ok=True)
    return folder


def taken_names(folder: str) -> set[str]:
    path = folder_path(folder)
    if not path.exists():
        return set()
    return {p.name for p in path.iterdir() if p.is_file()}


def guess_ext(filename: str, mime: str = "") -> str:
    ext = Path(filename or "").suffix.lower()
    if ext and len(ext) <= 6:
        return ext
    if mime:
        guessed = mimetypes.guess_extension(mime.split(";")[0].strip())
        if guessed:
            return guessed.lower()
    return ""


def guess_mime(filename: str, fallback: str = "application/octet-stream") -> str:
    mime, _ = mimetypes.guess_type(filename)
    return mime or fallback


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_upload(folder: str, filename: str, data: bytes) -> tuple[str, Path]:
    """Write bytes into a folder under a free, sanitized name. Returns (name, path)."""
    target_dir = folder_path(folder)
    target_dir.mkdir(parents=True, exist_ok=True)
    name = dedupe_filename(safe_filename(filename), taken_names(folder))
    path = target_dir / name
    path.write_bytes(data)
    return name, path


def move_document(src_folder: str, src_name: str, dst_folder: str, dst_name: str | None = None) -> str:
    """Move/rename on disk, avoiding collisions. Returns the final filename."""
    source = doc_path(src_folder, src_name)
    target_dir = folder_path(dst_folder)
    target_dir.mkdir(parents=True, exist_ok=True)
    wanted = safe_filename(dst_name or src_name)
    taken = taken_names(dst_folder)
    if src_folder == dst_folder:
        taken.discard(src_name)
    final = dedupe_filename(wanted, taken)
    destination = target_dir / final
    if source.resolve() == destination.resolve():
        return final
    if not source.exists():
        raise FileNotFoundError(str(source))
    shutil.move(str(source), str(destination))
    return final


def delete_document(folder: str, filename: str, trash: bool = True) -> None:
    """Default is a soft delete into `.trash/` — two people share this library."""
    source = doc_path(folder, filename)
    if not source.exists():
        return
    if not trash:
        source.unlink()
        return
    trash_dir = library_root() / ".trash" / folder
    trash_dir.mkdir(parents=True, exist_ok=True)
    final = dedupe_filename(filename, {p.name for p in trash_dir.iterdir() if p.is_file()})
    shutil.move(str(source), str(trash_dir / final))
