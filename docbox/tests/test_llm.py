from app.llm import extract_json, heuristic, normalize_analysis


def test_extract_json_plain():
    assert extract_json('{"title": "bill"}') == {"title": "bill"}


def test_extract_json_from_fence():
    raw = 'Sure!\n```json\n{"title": "bill", "date": "2024-01-02"}\n```\nHope that helps.'
    assert extract_json(raw)["date"] == "2024-01-02"


def test_extract_json_embedded_in_prose():
    raw = 'The document is an invoice. {"title": "power bill", "confidence": 0.8} Done.'
    assert extract_json(raw)["title"] == "power bill"


def test_extract_json_handles_braces_inside_strings():
    raw = 'noise {"title": "a } tricky { title", "confidence": 0.5} tail'
    assert extract_json(raw)["title"] == "a } tricky { title"


def test_extract_json_gives_up_cleanly():
    assert extract_json("no json at all") == {}
    assert extract_json("") == {}


def test_normalize_analysis_cleans_fields():
    result = normalize_analysis({
        "date": "17.03.2024",
        "title": "  Electricity   bill  ",
        "doc_type": "INVOICE",
        "correspondent": "Stadtwerke",
        "confidence": "0.9",
    })
    assert result.date == "20240317"
    assert result.title == "Electricity bill"
    assert result.doc_type == "invoice"
    assert result.confidence == 0.9


def test_normalize_analysis_rejects_junk():
    result = normalize_analysis({
        "date": "unknown",
        "title": None,
        "doc_type": "banana",
        "correspondent": "N/A",
        "confidence": "high",
    })
    assert result.date == ""
    assert result.title == ""
    assert result.doc_type == "other"
    assert result.correspondent == ""
    assert result.confidence == 0.0


def test_heuristic_uses_first_real_line_and_date():
    text = "***\n\nStadtwerke Munich invoice\nDated 17.03.2024\n"
    result = heuristic(text, "IMG_0042.pdf")
    assert result.title == "Stadtwerke Munich invoice"
    assert result.date == "20240317"
    assert result.source == "heuristic"


def test_heuristic_falls_back_to_filename():
    result = heuristic("", "tax-return-2023.pdf")
    assert result.title == "tax-return-2023"
