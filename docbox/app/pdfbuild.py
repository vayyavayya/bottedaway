"""Build the PDF a scan turns into.

Two things matter here and CamScanner charges for both:

1. **Quality.** Pages are embedded at their real resolution with an explicit
   DPI, so a page is A4-sized when printed instead of "1536 pixels wide".
2. **Searchable text.** Tesseract emits a PDF with an invisible text layer over
   the image, so Spotlight, the iOS Files app and Preview can all find words
   inside your scans. We build one of those per page and merge them.

Without tesseract you still get a good image-only PDF.
"""

from __future__ import annotations

import io
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("docbox.pdf")

# Standard page geometries in inches, used to pick a sane DPI for odd captures.
PAGE_SIZES_IN = {
    "a4": (8.27, 11.69),
    "letter": (8.5, 11.0),
    "a5": (5.83, 8.27),
    "legal": (8.5, 14.0),
}


@dataclass
class PdfReport:
    pages: int = 0
    searchable: bool = False
    dpi: int = 300
    bytes_out: int = 0
    warnings: list[str] | None = None

    def as_dict(self) -> dict:
        return {
            "pages": self.pages,
            "searchable": self.searchable,
            "dpi": self.dpi,
            "size": self.bytes_out,
            "warnings": self.warnings or [],
        }


def _has(binary: str) -> bool:
    return shutil.which(binary) is not None


def _open(data: bytes):
    from PIL import Image, ImageOps

    try:
        import pillow_heif  # type: ignore

        pillow_heif.register_heif_opener()
    except Exception:
        pass

    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)
    return img


def effective_dpi(width: int, height: int, page: str = "a4", target: int = 300) -> int:
    """Pick the DPI that makes this pixel size land on a real page.

    A 2400x3300 photo of an A4 sheet is ~290 dpi; tagging it 300 would make the
    page slightly small, and tagging it 72 would make it enormous. Derive it.
    """
    size = PAGE_SIZES_IN.get(page, PAGE_SIZES_IN["a4"])
    long_in = max(size)
    short_in = min(size)
    long_px, short_px = max(width, height), min(width, height)
    guess = (long_px / long_in + short_px / short_in) / 2
    if 72 <= guess <= 1200:
        return int(round(guess))
    return target


def _page_pdf_with_ocr(image_path: Path, langs: str, timeout: int = 180) -> bytes | None:
    """tesseract writes a one-page PDF with an invisible text layer."""
    if not _has("tesseract"):
        return None
    out_base = image_path.with_suffix("")
    try:
        result = subprocess.run(
            ["tesseract", str(image_path), str(out_base), "-l", langs, "pdf"],
            capture_output=True, timeout=timeout, check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning("tesseract pdf failed: %s", exc)
        return None
    produced = out_base.with_suffix(".pdf")
    if result.returncode != 0 or not produced.exists():
        log.warning("tesseract pdf returned %s", result.returncode)
        return None
    return produced.read_bytes()


def build_pdf(
    pages: list[bytes],
    dpi: int = 300,
    quality: int = 92,
    searchable: bool = True,
    langs: str = "eng",
    page_size: str = "a4",
) -> tuple[bytes, PdfReport]:
    """Images (already enhanced) -> one PDF. Order is preserved."""
    report = PdfReport(dpi=dpi, warnings=[])
    if not pages:
        raise ValueError("no pages given")

    from pypdf import PdfWriter

    prepared: list[Path] = []
    tmpdir = tempfile.TemporaryDirectory()
    root = Path(tmpdir.name)

    try:
        for index, raw in enumerate(pages):
            img = _open(raw)
            # Bilevel scans stay bilevel — they compress far better that way.
            if img.mode not in {"1", "L", "RGB"}:
                img = img.convert("RGB")
            resolved = effective_dpi(img.width, img.height, page_size, dpi)

            path = root / f"page-{index:04d}.png"
            if img.mode == "RGB":
                path = root / f"page-{index:04d}.jpg"
                img.save(path, "JPEG", quality=quality, dpi=(resolved, resolved),
                         optimize=True, progressive=True)
            else:
                img.save(path, "PNG", dpi=(resolved, resolved), optimize=True)
            prepared.append(path)
            report.dpi = resolved

        page_pdfs: list[bytes] = []
        if searchable:
            for path in prepared:
                produced = _page_pdf_with_ocr(path, langs)
                if produced is None:
                    page_pdfs = []
                    report.warnings.append(
                        "tesseract unavailable — the PDF has no searchable text layer"
                    )
                    break
                page_pdfs.append(produced)

        if page_pdfs:
            writer = PdfWriter()
            for blob in page_pdfs:
                from pypdf import PdfReader

                for page in PdfReader(io.BytesIO(blob)).pages:
                    writer.add_page(page)
            buffer = io.BytesIO()
            writer.write(buffer)
            report.searchable = True
            report.pages = len(page_pdfs)
            data = buffer.getvalue()
        else:
            data = _image_only_pdf(prepared, report)

        report.bytes_out = len(data)
        return data, report
    finally:
        tmpdir.cleanup()


def _image_only_pdf(paths: list[Path], report: PdfReport) -> bytes:
    """One PDF per page, then merge.

    Pillow applies a single `resolution` to every page of a multi-page save and
    ignores each image's own DPI, so pages of different pixel sizes come out at
    different physical sizes. Writing them one at a time keeps every page at its
    correct dimensions.
    """
    from PIL import Image
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    count = 0
    for path in paths:
        with Image.open(path) as img:
            img.load()
            resolution = float(
                (img.info.get("dpi") or (report.dpi, report.dpi))[0] or report.dpi
            )
            single = io.BytesIO()
            img.save(single, "PDF", resolution=resolution)
        single.seek(0)
        for page in PdfReader(single).pages:
            writer.add_page(page)
        count += 1

    buffer = io.BytesIO()
    writer.write(buffer)
    report.pages = count
    return buffer.getvalue()


def pdf_page_count(data: bytes) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(io.BytesIO(data)).pages)
    except Exception:
        return 0


def capabilities() -> dict:
    return {"tesseract_pdf": _has("tesseract")}
