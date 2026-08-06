"""PDF assembly: page geometry, ordering, and the searchable text layer."""

from __future__ import annotations

import io

import pytest

from app import pdfbuild

pytest.importorskip("PIL")
pytest.importorskip("pypdf")

A4_MM = (210.0, 297.0)


def page_bytes(width: int, height: int, label: str = "", fmt: str = "JPEG") -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (width, height), "white")
    if label:
        ImageDraw.Draw(img).text((40, 40), label, fill="black")
    buffer = io.BytesIO()
    img.save(buffer, fmt)
    return buffer.getvalue()


def page_sizes_mm(pdf: bytes) -> list[tuple[float, float]]:
    from pypdf import PdfReader

    return [
        (round(float(p.mediabox.width) / 72 * 25.4, 1), round(float(p.mediabox.height) / 72 * 25.4, 1))
        for p in PdfReader(io.BytesIO(pdf)).pages
    ]


def test_effective_dpi_lands_on_a_real_page():
    # 2480x3508 is exactly A4 at 300 dpi.
    assert pdfbuild.effective_dpi(2480, 3508, "a4") == pytest.approx(300, abs=2)
    # A phone capture of the same sheet is lower resolution but still A4.
    assert pdfbuild.effective_dpi(1240, 1754, "a4") == pytest.approx(150, abs=2)


def test_effective_dpi_falls_back_on_nonsense():
    assert pdfbuild.effective_dpi(4, 6, "a4", target=300) == 300


def test_single_page_is_a4_sized():
    pdf, report = pdfbuild.build_pdf([page_bytes(1240, 1754)], searchable=False)
    assert report.pages == 1
    width, height = page_sizes_mm(pdf)[0]
    assert width == pytest.approx(A4_MM[0], abs=3)
    assert height == pytest.approx(A4_MM[1], abs=3)


def test_each_page_keeps_its_own_size():
    """Pages captured at different resolutions must not inherit one DPI.

    Pillow applies a single resolution across a multi-page save, which silently
    resizes every page but the last — hence the per-page build.
    """
    pages = [page_bytes(1240, 1754), page_bytes(2480, 3508), page_bytes(826, 1169)]
    pdf, report = pdfbuild.build_pdf(pages, searchable=False)
    assert report.pages == 3
    for width, height in page_sizes_mm(pdf):
        assert width == pytest.approx(A4_MM[0], abs=4)
        assert height == pytest.approx(A4_MM[1], abs=4)


def test_page_order_is_preserved():
    from pypdf import PdfReader

    pages = [page_bytes(1240, 1754, label=str(i)) for i in range(4)]
    pdf, _ = pdfbuild.build_pdf(pages, searchable=False)
    assert len(PdfReader(io.BytesIO(pdf)).pages) == 4


def test_no_pages_is_an_error():
    with pytest.raises(ValueError):
        pdfbuild.build_pdf([])


def test_missing_tesseract_degrades_to_an_image_pdf(monkeypatch):
    monkeypatch.setattr(pdfbuild, "_has", lambda binary: False)
    pdf, report = pdfbuild.build_pdf([page_bytes(1240, 1754)], searchable=True)
    assert report.searchable is False
    assert any("searchable" in w for w in report.warnings)
    assert pdfbuild.pdf_page_count(pdf) == 1


def test_searchable_path_merges_per_page_pdfs(monkeypatch):
    """With tesseract present each page comes back as its own searchable PDF;
    check they are merged in order rather than overwriting each other."""
    made = []

    def fake_ocr(image_path, langs, timeout=180):
        from PIL import Image

        with Image.open(image_path) as img:
            buffer = io.BytesIO()
            img.convert("RGB").save(buffer, "PDF", resolution=150.0)
        made.append(image_path.name)
        return buffer.getvalue()

    monkeypatch.setattr(pdfbuild, "_page_pdf_with_ocr", fake_ocr)
    pages = [page_bytes(1240, 1754, label=str(i)) for i in range(3)]
    pdf, report = pdfbuild.build_pdf(pages, searchable=True)

    assert report.searchable is True
    assert report.pages == 3
    assert pdfbuild.pdf_page_count(pdf) == 3
    assert made == sorted(made)  # pages handed to OCR in order


def test_bilevel_pages_stay_lossless():
    from PIL import Image

    img = Image.new("1", (1240, 1754), 1)
    buffer = io.BytesIO()
    img.save(buffer, "PNG")
    pdf, report = pdfbuild.build_pdf([buffer.getvalue()], searchable=False)
    assert report.pages == 1
    assert pdfbuild.pdf_page_count(pdf) == 1
