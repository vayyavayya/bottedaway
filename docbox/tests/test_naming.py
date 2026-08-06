from app.naming import (
    build_filename,
    dedupe_filename,
    find_date_in_text,
    looks_machine_generated,
    normalize_date,
    safe_filename,
    safe_folder,
    slugify,
)


def test_slugify_basic():
    assert slugify("Rechnung Stadtwerke März 2024") == "rechnung-stadtwerke-maerz-2024"
    assert slugify("  Electricity   Bill!! ") == "electricity-bill"
    assert slugify("") == "document"


def test_slugify_drops_stopwords_but_keeps_short_titles():
    assert slugify("Invoice for the flat") == "invoice-flat"
    assert slugify("the a") == "the-a"  # too short to strip everything


def test_slugify_respects_max_length():
    slug = slugify("a very long document title that keeps going and going and going", max_len=20)
    assert len(slug) <= 20
    assert not slug.endswith("-")


def test_normalize_date_forms():
    assert normalize_date("2024-03-17") == "20240317"
    assert normalize_date("17.03.2024") == "20240317"
    assert normalize_date("20240317") == "20240317"
    assert normalize_date("not a date") == ""
    assert normalize_date(None) == ""
    assert normalize_date("2024-13-45") == ""  # impossible date is rejected


def test_find_date_in_text():
    assert find_date_in_text("Invoice date: 17.03.2024, due in 14 days") == "20240317"
    assert find_date_in_text("Dated 2023-11-02 by the office") == "20231102"
    assert find_date_in_text("Berlin, 5. Januar 2022") == "20220105"
    assert find_date_in_text("March 4, 2021 statement") == "20210304"
    assert find_date_in_text("no dates here") == ""


def test_build_filename():
    assert build_filename("2024-03-17", "electricity bill", "pdf", extra="Stadtwerke") == (
        "20240317-stadtwerke-electricity-bill.pdf"
    )
    assert build_filename("20240317", "notes", "") == "20240317-notes"


def test_build_filename_without_date_uses_today():
    name = build_filename("", "some scan", "pdf")
    assert name.endswith("-some-scan.pdf")
    assert len(name.split("-")[0]) == 8


def test_dedupe_filename():
    taken = {"20240317-bill.pdf", "20240317-bill-2.pdf"}
    assert dedupe_filename("20240317-bill.pdf", taken) == "20240317-bill-3.pdf"
    assert dedupe_filename("other.pdf", taken) == "other.pdf"


def test_safe_filename_blocks_traversal():
    assert "/" not in safe_filename("../../etc/passwd")
    assert safe_filename("../../etc/passwd") == "etc-passwd"
    assert safe_filename("") == "file"


def test_safe_folder():
    assert safe_folder("Inbox") == "Inbox"
    assert safe_folder("Bills 2024") == "Bills 2024"
    assert safe_folder("") == "Inbox"


def test_safe_folder_nests():
    assert safe_folder("Finance/Invoices/2024") == "Finance/Invoices/2024"
    assert safe_folder("/Finance/Invoices/") == "Finance/Invoices"
    assert safe_folder("Finance\\Invoices") == "Finance/Invoices"
    assert safe_folder("a/b/c/d/e/f") == "a/b/c/d"  # capped depth


def test_safe_folder_drops_traversal():
    # `..` segments are removed rather than kept, so the path stays relative and
    # inside the library; storage.folder_path() re-checks containment on top.
    for attempt in ["../secrets", "../../etc/passwd", "..", "foo/../../bar"]:
        result = safe_folder(attempt)
        assert ".." not in result.split("/")
        assert not result.startswith("/")


def test_looks_machine_generated():
    for name in ["IMG_0042.pdf", "Scan 12.pdf", "20240312_113355.jpg", "untitled.pdf", "DOC_1.pdf"]:
        assert looks_machine_generated(name), name
    for name in ["tax-return-2023.pdf", "rental contract.pdf"]:
        assert not looks_machine_generated(name), name
