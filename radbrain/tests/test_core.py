"""Core tests — synthetic data only. Run: pytest -q (from the radbrain folder)."""
from __future__ import annotations

import json
import random
import re

import pytest

from radbrain import anonymise as A
from radbrain import config, diff, engine, evaluate, library, miner, pipeline, synth, taxonomy


@pytest.fixture()
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("RADBRAIN_DATA", str(tmp_path))
    monkeypatch.setenv("RADBRAIN_OLLAMA", "http://127.0.0.1:9")      # no model: rules-only, trigram retrieval
    synth.write_test_signers(tmp_path / "signers.json")
    return tmp_path


def _leaks(ident: list[str], out: str) -> list[str]:
    return [i for i in ident if re.search(r"(?<![\wÄÖÜäöüß])" + re.escape(i) + r"(?![\wÄÖÜäöüß])", out)]


# ------------------------------------------------------------------------------------------- Phase 3
def test_anonymiser_recall_100_percent_on_synthetic(data):
    """>= 200 synthetic reports with planted identifiers: nothing may reach the library (ok=True output)."""
    docs = synth.corpus(260, seed=101) + synth.corpus(260, seed=202)
    texts = leaks = quarantined = 0
    for d in docs:
        for t in (d.draft, d.final):
            if not t:
                continue
            texts += 1
            r = A.anonymise(t)
            out = r.text + "\n" + r.exam
            bad = _leaks(d.identifiers, out)
            if r.ok:
                leaks += len(bad)
                assert not bad, (bad, d.entity)
            else:
                quarantined += 1
    assert texts >= 600 and leaks == 0
    assert quarantined / texts < 0.05          # fail-closed must not starve the library on clean text


ADVERSARIAL = [
    # (raw text, identifiers that must not survive in an ok=True output)
    ("Befund:\nVergleich mit der Voraufnahme vom 3.2.2024 und 17.11.23.\nBeurteilung:\nKonstant.",
     ["3.2.2024", "17.11.23"]),
    ("Befund:\nBefund am 12. Januar 2025 um 7.45 Uhr an OÄ Dr. Szczypiorska durchgegeben.\nBeurteilung:\nSiehe oben.",
     ["12. Januar 2025", "7.45", "Szczypiorska"]),
    ("Befund:\nRücksprache mit Herrn Abernathy-Kühn, Durchwahl 4471.\nBeurteilung:\nKein Pneumothorax.",
     ["Abernathy-Kühn", "4471"]),
    ("Befund:\nDer 83jährige Pat. stürzte zu Hause.\nBeurteilung:\nKeine Fraktur.", ["83"]),
    ("Befund:\nPatient: MÖLLENKAMP^GERTRAUD wurde nachuntersucht.\nBeurteilung:\nRegelrecht.",
     ["MÖLLENKAMP", "GERTRAUD"]),
    ("Befund:\nZ.n. Hemikolektomie 2017 (Klinikum Mitte, Station 7B).\nBeurteilung:\nKein Rezidiv.",
     ["2017", "7B"]),
    ("Befund:\nVoraufnahmen aus 03/2022 liegen vor. Aktenzeichen RAD-998877.\nBeurteilung:\nStationär.",
     ["03/2022", "998877"]),
    ("Befund:\nHausarzt Dr. med. Feodora Iwaszkiewicz, Hauptstraße 12, 12345 Musterstadt informiert.\n"
     "Beurteilung:\nWie oben.", ["Feodora", "Iwaszkiewicz", "Hauptstraße 12", "12345"]),
    ("Befund:\nTelefonisch an Wohlgemuth übermittelt, Tel. 0123 456-2210.\nBeurteilung:\nLungenembolie.",
     ["Wohlgemuth", "456-2210"]),
    ("Befund:\nGeburtsdatum 01.02.1944, Fallnr 2025004411.\nBeurteilung:\nUnauffällig.", ["01.02.1944", "2025004411"]),
    ("Befund:\nSchmerzen seit dem 4. Mai.\nBeurteilung:\nKein Erguss.", ["4. Mai"]),
    ("Befund:\nBefund mit der Kollegin Okeke-Brandt (Unfallchirurgie) besprochen.\nBeurteilung:\nFraktur.",
     ["Okeke-Brandt"]),
]


@pytest.mark.parametrize("raw,ident", ADVERSARIAL)
def test_anonymiser_adversarial(data, raw, ident):
    r = A.anonymise(raw)
    if r.ok:
        assert not _leaks(ident, r.text + r.exam), r.text


def test_header_is_dropped_and_no_heading_quarantines(data):
    r = A.anonymise("Mustermann, Erika\n* 01.01.1950\nPID 12345678\nBefund:\nKein Erguss.\nBeurteilung:\nNormal.")
    assert "Mustermann" not in r.text and "12345678" not in r.text
    assert not A.anonymise("Mustermann Erika 01.01.1950 kein Erguss").ok


EPONYM_TEXT = ("Befund:\nMorbus Crohn mit Stenose im terminalen Ileum. Knöcherne Bankart-Läsion und Hill-Sachs-Delle. "
               "Monteggia-Fraktur links. Außenknöchelfraktur Weber B. Baker-Zyste. Fleischner-Kriterien.\n"
               "Beurteilung:\nZ.n. Luxation, V.a. Bankart-Läsion. DD Morbus Bechterew.")


def test_eponyms_and_medical_text_survive(data):
    r = A.anonymise(EPONYM_TEXT)
    for w in ("Morbus Crohn", "Bankart-Läsion", "Hill-Sachs-Delle", "Monteggia-Fraktur", "Weber B", "Baker-Zyste",
              "Fleischner", "Bechterew", "V.a.", "DD", "Z.n."):
        assert w in r.text, w
    assert r.ok, r.reasons


def test_precision_on_clean_text(data):
    """Clean synthetic sections (no identifiers) come through >= 98 % token-identical."""
    rng = random.Random(5)
    kept = total = 0
    for _ in range(150):
        d = synth.make(rng, plant=False)
        clean = "Befund:\n" + d.clean_final["befund"] + "\nBeurteilung:\n" + d.clean_final["beurteilung"]
        r = A.anonymise(clean)
        a = diff.tokens(d.clean_final["befund"] + " " + d.clean_final["beurteilung"])
        b = diff.tokens(r.sections.get("befund", "") + " " + r.sections.get("beurteilung", ""))
        total += len(a)
        kept += sum(1 for x, y in zip(a, b) if x == y)
    assert kept / total >= 0.98


def test_signer_and_author_detection(data):
    rng = random.Random(9)
    for _ in range(40):
        d = synth.make(rng)
        assert A.anonymise(d.final).signer == d.signer
        assert A.anonymise(d.draft).author_is_me == d.author_is_me


# ------------------------------------------------------------------------------------------- Phase 4 / pipeline
def test_pipeline_saves_quarantines_dedupes(data):
    d = synth.make(random.Random(3), signer="B2")
    r1 = pipeline.ingest("pair", d.draft, d.final, synthetic=True)
    assert r1["status"] == "saved" and r1["signer"] == "B2" and r1["pathologies"]
    assert pipeline.ingest("pair", d.draft, d.final, synthetic=True)["status"] == "duplicate"
    q = pipeline.ingest("final", None, "kein Abschnitt Mustermann 01.01.1950")
    assert q["status"] == "quarantined"
    assert pipeline.quarantine_list() and (data / "quarantine").glob("*.json")
    pipeline.quarantine_discard(q["quarantine_id"])
    assert not pipeline.quarantine_list()
    with library.db() as con:
        row = con.execute("SELECT * FROM captures").fetchone()
        assert "TT" not in (row["exam"] or "") and not re.search(r"\d{1,2}\.\d{1,2}\.\d{2,4}", " ".join(
            str(row[k] or "") for k in row.keys() if k not in ("diff",)))


def test_release_teaches_allowlist(data):
    raw = "Befund:\nKleiner Zwulpex im Unterlappen rechts.\nBeurteilung:\nZwulpex."
    q = pipeline.ingest("final", None, raw)
    assert q["status"] == "quarantined"
    prev = pipeline.quarantine_preview(q["quarantine_id"])
    assert "Zwulpex" in prev["unknown_words"]
    r = pipeline.quarantine_release(q["quarantine_id"], ["Zwulpex"])
    assert r["status"] == "saved"
    assert A.known("Zwulpex")


# ------------------------------------------------------------------------------------------- Phase 5
@pytest.fixture()
def library_600(data):
    con = library.connect()
    for d in synth.corpus(600, seed=5):
        pipeline.ingest(d.kind, d.draft, d.final, synthetic=True, con=con, remine=False)
    miner.mine(con)
    yield con
    con.close()


def test_miner_recovers_ground_truth_rules(library_600):
    con = library_600
    want = {("B1", "del", "es zeigt sich", "HOUSE"), ("B2", "del", "es zeigt sich", "HOUSE"),
            ("B3", "del", "es zeigt sich", "HOUSE"), ("B1", "ins", "kein pneumothorax .", "HOUSE"),
            ("B3", "ins", "kein pneumothorax .", "HOUSE"), ("B2", "sub", "eher", "HOUSE"),
            ("B3", "sub", "eher", "HOUSE"), ("B1", "number", "", "PERSONAL"), ("B1", "sub", "am ehesten", "PERSONAL"),
            ("B2", "ins", "klinische korrelation empfohlen .", "PERSONAL"), ("B2", "sub", "beidseits", "PERSONAL"),
            ("B3", "sub", "regelrecht", "PERSONAL"), ("B3", "reorder", "", "PERSONAL")}
    got = set()
    for s in config.CODES:
        for r in miner.rules_for(con, s):
            phrase = r["before"] if r["op"] in ("sub", "del") else r["after"]
            got.add((s, r["op"], phrase, r["scope"].split()[0]))
    missing = want - got
    assert len(missing) <= 1, missing
    assert (config.data_dir() / "rulebooks" / "rulebook_B1.md").exists()


def test_remine_triggers_every_25_pairs(data):
    con = library.connect()
    n = 0
    for d in synth.corpus(80, seed=8, kind_mix=1.0):
        if pipeline.ingest("pair", d.draft, d.final, synthetic=True, con=con)["status"] == "saved":
            n += 1
    runs = con.execute("SELECT COUNT(*) FROM mine_runs WHERE synthetic=1").fetchone()[0]
    assert runs >= n // 25 >= 2


# ------------------------------------------------------------------------------------------- Phase 7
def test_correct_applies_rules_with_explanations(library_600):
    draft = ("Befund:\nEs zeigt sich eine fleckige Verschattung im Unterfeld rechts, möglicherweise einem Infiltrat "
             "entsprechend.\nRandwinkel beidseits frei.\n\nBeurteilung:\nAm ehesten pneumonisches Infiltrat im "
             "Unterfeld rechts.\nKein Pleuraerguss.")
    r = engine.correct(draft, "B1", use_llm=False, con=library_600)
    out = r["sections_out"]
    assert not out["befund"].startswith("Es zeigt sich")
    assert "Kein Pneumothorax." in out["befund"]
    assert out["beurteilung"].startswith("1. ")
    assert all(e["source"].startswith("R") for e in r["explanations"])
    assert '<mark class="a">' in r["html"]["befund"] and '<del class="d">' in r["html"]["befund"]


def test_guard_rejects_invented_findings():
    src = "Fleckige Verschattung im Unterfeld rechts von 12 mm."
    assert not engine.guard("befund", src, "Verschattung im Unterfeld rechts von 12 mm.", set())
    assert any("Zahlen" in w for w in engine.guard("befund", src, "Verschattung rechts von 14 mm.", set()))
    assert any("Seiten" in w for w in engine.guard("befund", src, "Verschattung links von 12 mm.", set()))
    assert engine.guard("befund", src, src + " Zusätzlich kleiner Pneumothorax.", set())


def test_consistency_flags():
    f = engine.consistency_flags({"befund": "Regelrechte Belüftung beider Lungen.",
                                  "beurteilung": "Lungenembolie rechts."})
    assert any(x["level"] == "error" for x in f)
    f = engine.consistency_flags({"befund": "Pleuraerguss rechts.", "beurteilung": "Pleuraerguss links."})
    assert any("Seitenwiderspruch" in x["text"] for x in f)


def test_predict_and_ask(library_600):
    p = engine.predict("Befund:\nEs zeigt sich ein Erguss beidseits.\nBeurteilung:\nEher kleiner Erguss.", "B2",
                       con=library_600)
    assert any(h["phrase"] and h["phrase"].lower() == "es zeigt sich" for h in p["hits"])
    a = engine.ask("Wie formuliert B1 eine Lungenembolie?", con=library_600)
    assert a["entity"] == "lungenembolie" and a["by_signer"]["B1"]["examples"]


def test_llm_refuses_non_local_host(data, monkeypatch):
    from radbrain import llm
    monkeypatch.setenv("RADBRAIN_OLLAMA", "https://api.example.com")
    with pytest.raises(RuntimeError):
        llm._base()


# ------------------------------------------------------------------------------------------- Phase 8
def test_eval_end_to_end_synthetic(library_600):
    r = evaluate.run(library_600, llm=False)
    assert r["synthetic"] is True
    for s in config.CODES:
        b = r["by_signer"][s]
        assert b["n_test"] > 0 and b["chrf_engine"] >= b["chrf_draft"] - 0.5
    assert evaluate.chrf("abc def", "abc def") == pytest.approx(100.0)
    assert evaluate.ned("a b c", "a b c") == 0


# ------------------------------------------------------------------------------------------- taxonomy
def test_tagging():
    assert taxonomy.modality("CT Thorax mit KM") == "CT"
    assert taxonomy.modality("MRT Knie nativ") == "MRT"
    assert taxonomy.modality("DSA Becken-Bein links") == "Angio"
    assert taxonomy.pathologies("Nicht dislozierte Rippenfraktur 7 rechts.") == ["rippenfraktur"]
    assert taxonomy.pathologies("Kein Pneumothorax.") == []
    assert len(taxonomy.ENTITIES) >= 40


# ------------------------------------------------------------------------------------------- web
def test_web_localhost_guards(data):
    import threading
    import urllib.request
    from radbrain import web
    srv = web.serve("127.0.0.1", 0)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        assert json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/health").read())["ok"]
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/mine", data=b"{}", method="POST")
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(req)
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/overview", headers={"Host": "evil.example"})
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(req)
        with pytest.raises(SystemExit):
            web.serve("0.0.0.0", 0)
    finally:
        srv.shutdown()


def test_entwurf_signature_line(data):
    import json as _j
    (data / "signers.json").write_text(_j.dumps({"signers": {"B1": ["Probe"]}, "me": ["Muster"], "staff": []}))
    r = A.anonymise("Befund:\nKein Erguss.\n\nBeurteilung:\nUnauffällig.\n\nEntwurf: Dr. med. Muster")
    assert r.author_is_me and "Muster" not in r.text and "Entwurf" not in r.text


def test_ocr_punctuation_noise_is_not_a_rule():
    assert miner.canonical({"op": "sub", "before": "re .", "after": "re ,"}) is None
    assert miner.canonical({"op": "sub", "before": "V.a .", "after": "V.a ,"}) is None
    assert miner.canonical({"op": "sub", "before": "eher", "after": "am ehesten"})["op"] == "sub"
