"""Get text out of whatever landed in the inbox.

Order of preference: embedded text -> OCR -> nothing (the vision model then gets
a shot at the raw image in llm.py). Every dependency here is optional; a missing
binary degrades the result instead of failing the upload.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .config import settings
from .storage import IMAGE_EXTS, TEXT_EXTS


@dataclass
class Extraction:
    text: str = ""
    method: str = "none"
    pages: int = 0

    @property
    def usable(self) -> bool:
        return len(self.text.strip()) >= 40


def _has(binary: str) -> bool:
    return shutil.which(binary) is not None


def _run(cmd: list[str], timeout: int = 120) -> str:
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return result.stdout.decode("utf-8", "replace")


def clean_text(text: str, limit: int | None = None) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = text.strip()
    cap = limit if limit is not None else settings.extract_max_chars
    return text[:cap]


# --------------------------------------------------------------------------- pdf


def _pdf_text(path: Path) -> tuple[str, int]:
    """pdftotext if present (fast, better layout), else pypdf."""
    if _has("pdftotext"):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            out = Path(tmp.name)
        try:
            _run(["pdftotext", "-l", str(settings.ocr_max_pages), "-q", str(path), str(out)])
            text = out.read_text("utf-8", "replace") if out.exists() else ""
        finally:
            out.unlink(missing_ok=True)
        if text.strip():
            return text, 0
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        pages = reader.pages[: settings.ocr_max_pages]
        return "\n".join((p.extract_text() or "") for p in pages), len(reader.pages)
    except Exception:
        return "", 0


def _pdf_ocr(path: Path) -> str:
    """Render the first pages to PNG, then OCR them."""
    if not (settings.ocr_enabled and _has("tesseract") and _has("pdftoppm")):
        return ""
    with tempfile.TemporaryDirectory() as tmpdir:
        prefix = Path(tmpdir) / "page"
        _run([
            "pdftoppm", "-r", "200", "-png",
            "-f", "1", "-l", str(settings.ocr_max_pages),
            str(path), str(prefix),
        ], timeout=180)
        chunks = []
        for png in sorted(Path(tmpdir).glob("page*.png")):
            chunks.append(_ocr_image(png))
        return "\n".join(c for c in chunks if c)


# ------------------------------------------------------------------------ images


def _ocr_image(path: Path) -> str:
    if not (settings.ocr_enabled and _has("tesseract")):
        return ""
    return _run(
        ["tesseract", str(path), "stdout", "-l", settings.ocr_langs, "--psm", "3"],
        timeout=120,
    )


def normalize_image(path: Path) -> Path:
    """HEIC and friends -> PNG so tesseract and vision models can read them."""
    if path.suffix.lower() not in {".heic", ".heif", ".tif", ".tiff", ".webp", ".bmp", ".gif"}:
        return path
    try:
        from PIL import Image  # type: ignore

        try:  # optional, only needed for HEIC
            import pillow_heif  # type: ignore

            pillow_heif.register_heif_opener()
        except Exception:
            pass

        with Image.open(path) as img:
            converted = path.with_suffix(".converted.png")
            img.convert("RGB").save(converted, "PNG")
            return converted
    except Exception:
        if _has("sips"):  # macOS
            converted = path.with_suffix(".converted.png")
            _run(["sips", "-s", "format", "png", str(path), "--out", str(converted)])
            if converted.exists():
                return converted
        return path


# -------------------------------------------------------------------------- docx


def _docx_text(path: Path) -> str:
    """Read the XML directly — no python-docx dependency for a few paragraphs."""
    try:
        with zipfile.ZipFile(path) as archive:
            xml = archive.read("word/document.xml")
    except Exception:
        return ""
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return ""
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    lines = []
    for para in root.iter(f"{ns}p"):
        text = "".join(node.text or "" for node in para.iter(f"{ns}t"))
        if text.strip():
            lines.append(text.strip())
    return "\n".join(lines)


# --------------------------------------------------------------------------- api


def extract(path: Path) -> Extraction:
    ext = path.suffix.lower()

    if ext in TEXT_EXTS:
        try:
            return Extraction(clean_text(path.read_text("utf-8", "replace")), "text")
        except OSError:
            return Extraction()

    if ext == ".pdf":
        raw, pages = _pdf_text(path)
        found = Extraction(clean_text(raw), "pdf-text", pages)
        if found.usable:
            return found
        ocr = clean_text(_pdf_ocr(path))
        if ocr.strip():
            return Extraction(ocr, "pdf-ocr", pages)
        return found

    if ext in IMAGE_EXTS:
        prepared = normalize_image(path)
        try:
            text = clean_text(_ocr_image(prepared))
        finally:
            if prepared != path:
                prepared.unlink(missing_ok=True)
        return Extraction(text, "image-ocr" if text else "none")

    if ext == ".docx":
        return Extraction(clean_text(_docx_text(path)), "docx")

    return Extraction()


def capabilities() -> dict[str, bool]:
    """Surfaced in /api/health so you can see what the box can actually do."""
    return {
        "tesseract": _has("tesseract"),
        "pdftoppm": _has("pdftoppm"),
        "pdftotext": _has("pdftotext"),
        "pypdf": _module_available("pypdf"),
        "pillow": _module_available("PIL"),
    }


def _module_available(name: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(name) is not None
