"""Bulk import of an old scanner library, and the rules that file it."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from app import db, importer, routing, storage
from app.config import settings
from app.llm import Analysis


# ------------------------------------------------------------------ routing


def analysis(**kwargs) -> Analysis:
    base = dict(date="20240317", title="monthly statement", doc_type="invoice",
                correspondent="Acme Ltd", summary="", confidence=0.9, source="llm")
    base.update(kwargs)
    return Analysis(**base)


def test_type_rule_files_by_year():
    route = routing.choose_folder(analysis(doc_type="payslip", date="20220105"))
    assert route.folder == "Finance/Payslips/2022"
    assert route.confident


def test_keyword_rule_wins_over_the_type_rule():
    # doc_type says invoice (-> Finance/Invoices) but the sender is a utility.
    route = routing.choose_folder(analysis(correspondent="Stadtwerke Munich"))
    assert route.folder == "Home/Utilities/2024"
    assert route.rule == "utilities"


def test_undated_documents_get_an_undated_folder():
    route = routing.choose_folder(analysis(doc_type="tax", date="", correspondent="HMRC"))
    assert route.folder == "Finance/Tax/undated"


def test_low_confidence_stays_in_the_inbox():
    route = routing.choose_folder(analysis(confidence=0.2), current="Inbox")
    assert route.folder == "Inbox"
    assert not route.confident


def test_heuristic_results_are_never_auto_filed():
    route = routing.choose_folder(analysis(source="heuristic", confidence=0.95), current="Inbox")
    assert not route.confident


def test_unmatched_type_stays_put():
    route = routing.choose_folder(
        analysis(doc_type="note", correspondent="a friend", title="a handwritten note"),
        current="Inbox",
    )
    assert route.folder == "Inbox"


def test_auto_file_off_disables_everything():
    config = dict(routing.load_rules())
    config["auto_file"] = False
    route = routing.choose_folder(analysis(), current="Inbox", config=config)
    assert route.folder == "Inbox"
    assert not route.confident


def test_rules_file_is_created_with_defaults():
    path = routing.rules_path()
    if path.exists():
        path.unlink()
    config = routing.load_rules()
    assert path.exists()
    assert config["rules"] and config["auto_file"] is True


def test_broken_rules_file_falls_back_instead_of_crashing():
    routing.rules_path().write_text("{ this is not json")
    try:
        config = routing.load_rules()
        assert config["rules"]  # defaults
    finally:
        routing.rules_path().unlink(missing_ok=True)


# ------------------------------------------------------------------- import


@pytest.fixture()
def export_tree(tmp_path: Path) -> Path:
    """A folder shaped like a real CamScanner export."""
    root = tmp_path / "CamScanner"
    (root / "Insurance").mkdir(parents=True)
    (root / "Bills" / "2023").mkdir(parents=True)

    # Content is salted per test: the library dedupes by hash, so identical
    # bytes from an earlier test would be reported as duplicates here.
    salt = tmp_path.name
    (root / "CamScanner 03-17-2024 10.22.pdf").write_bytes(
        f"%PDF-1.4\nfake {salt}\n%%EOF\n".encode()
    )
    (root / "Insurance" / "Doc 12.jpg").write_bytes(b"\xff\xd8\xff\xe0fake-jpeg " + salt.encode())
    (root / "Bills" / "2023" / "invoice.txt").write_text(f"Stadtwerke invoice 04.05.2023 {salt}")
    (root / ".DS_Store").write_bytes(b"junk")
    (root / "Insurance" / "notes.ini").write_text("[settings]")
    (root / "._resource").write_bytes(b"apple metadata")
    return root


def test_collect_skips_junk_and_unsupported(export_tree: Path):
    names = {p.name for p in importer.collect(export_tree)}
    assert names == {"CamScanner 03-17-2024 10.22.pdf", "Doc 12.jpg", "invoice.txt"}


def test_source_hint_keeps_the_old_folder_names(export_tree: Path):
    path = export_tree / "Bills" / "2023" / "invoice.txt"
    assert importer.source_hint(path, export_tree) == "Bills/2023"
    # The export's own top folder is noise, not signal.
    assert importer.source_hint(export_tree / "CamScanner 03-17-2024 10.22.pdf", export_tree) == ""


def test_import_folder_ingests_everything_once(export_tree: Path):
    report = importer.import_folder(export_tree, "tester", process=False)
    assert report.total == 3
    assert report.imported == 3
    assert report.failed == 0

    again = importer.import_folder(export_tree, "tester", process=False)
    assert again.imported == 0
    assert again.skipped_duplicate == 3  # content hash, not filename


def test_imported_documents_carry_their_hint_and_batch(export_tree: Path):
    report = importer.import_folder(export_tree, "tester", process=False)
    row = db.query_one(
        "SELECT * FROM documents WHERE original_name = ? ORDER BY id DESC", ("invoice.txt",)
    )
    assert row["source_hint"] == "Bills/2023"
    assert row["batch_id"] == report.batch_id
    assert row["uploaded_by"] == "tester"
    assert storage.doc_path(row["folder"], row["filename"]).exists()


def test_batch_status_reports_progress(export_tree: Path):
    report = importer.import_folder(export_tree, "tester", process=False)
    status = importer.batch_status(report.batch_id)
    assert status["total"] == 3
    assert status["imported"] == 3
    assert status["status"] == "done"


def test_group_key_pairs_split_pages():
    assert importer.group_key(Path("/x/Doc 3_1.jpg")) == importer.group_key(Path("/x/Doc 3_2.jpg"))
    assert importer.group_key(Path("/x/Doc 3.jpg")) != importer.group_key(Path("/y/Doc 3.jpg"))


def test_import_zip_extracts_and_ingests(tmp_path: Path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "Export/Taxes/2021 return.txt", f"tax return 2021, dated 04.02.2022 {tmp_path.name}"
        )
        archive.writestr("Export/.DS_Store", "junk")
    report = importer.import_zip(buffer.getvalue(), "tester", process=False)
    assert report.imported == 1
    assert report.total == 1


def test_import_zip_refuses_path_traversal(tmp_path: Path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../escaped.txt", "should never be written")
        archive.writestr("fine.txt", f"a normal document from 01.02.2020 {tmp_path.name}")
    report = importer.import_zip(buffer.getvalue(), "tester", process=False)
    assert report.imported == 1
    assert not (Path(settings.data_dir).parent / "escaped.txt").exists()


def test_import_rejects_a_missing_folder():
    from app.ingest import IngestError

    with pytest.raises(IngestError):
        importer.import_folder(Path("/nope/not/here"), "tester")
