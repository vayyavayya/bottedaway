"""Capture-side tests, runnable on the Mac: cd radbrain && .venv/bin/python -m pytest tests/test_capture.py

All images are synthetic and in memory; nothing here touches a real report.
"""
from __future__ import annotations

import importlib
import json
import shutil
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

HAS_TESSERACT = shutil.which("tesseract") is not None

@pytest.fixture(autouse=True)
def _no_live_autodetect(monkeypatch):
    """Unit tests must not pick up whatever is on this screen; autocal has its own live test."""
    from radbrain.capture import hotkey_app
    monkeypatch.setattr(hotkey_app, "_default_detect", lambda kind: None)



@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "radbrain-data"
    monkeypatch.setenv("RADBRAIN_DATA", str(d))
    from radbrain import config
    config.data_dir()
    return d


def _files(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


# ------------------------------------------------------------------------------------------------ OCR
@pytest.mark.skipif(not HAS_TESSERACT, reason="tesseract binary not installed")
def test_tesseract_reads_synthetic_panel(data_dir):
    from radbrain.capture import bench_ocr, ocr
    text = ("CT Thorax mit KM i.v.:\nV.a. Lungenembolie re., DD Artefakt.\n"
            "Kleiner Pleuraerguss li., ca. 12 mm. Kein Pneumothorax.\nZ.n. Fraktur BWK 12, Größe unverändert.")
    img = bench_ocr.render_panel(text, font=bench_ocr.load_font("Arial", 12, bench_ocr.available_fonts()))
    out = ocr.ocr(img, "tesseract")
    for word in ("Lungenembolie", "Pleuraerguss", "Pneumothorax", "V.a.", "BWK 12", "Größe", "i.v."):
        assert word in out, word
    assert bench_ocr.cer(bench_ocr.norm_lines(out), bench_ocr.norm_lines(text)) < 0.05


@pytest.mark.skipif(not HAS_TESSERACT, reason="tesseract binary not installed")
def test_tesseract_light_on_dark_and_jpeg(data_dir):
    from radbrain.capture import bench_ocr, ocr
    text = "Pleuraerguss re. basal, ca. 15 mm.\nKein Pneumothorax. Dichte 45 HU."
    img = bench_ocr.render_panel(text, font=bench_ocr.load_font("Tahoma", 13, bench_ocr.available_fonts()),
                                 dark=True, compressed=True, jpeg_q=40, blur=0.5)
    out = ocr.ocr_tesseract(img)
    assert "Pleuraerguss" in out and "Pneumothorax" in out


def test_best_backend_reads_settings(data_dir):
    from radbrain.capture import ocr
    assert ocr.best_backend() == "tesseract"
    (data_dir / "settings.json").write_text(json.dumps({"ocr": "ollama", "llm": "x"}), encoding="utf-8")
    assert ocr.best_backend() == "ollama"
    (data_dir / "settings.json").write_text(json.dumps({"ocr": "nonsense"}), encoding="utf-8")
    assert ocr.best_backend() == "tesseract"


def test_clean_model_output_strips_think_and_fences():
    from radbrain.capture.ocr import clean_model_output
    assert clean_model_output("<think>hmm\nlong</think>\nKein Pneumothorax.") == "Kein Pneumothorax."
    assert clean_model_output("```text\nZeile 1\nZeile 2\n```") == "Zeile 1\nZeile 2"
    assert clean_model_output("Größe ca. 5 mm.\r\n\r\n\r\nV.a. Läsion") == "Größe ca. 5 mm.\n\nV.a. Läsion"


def test_ollama_backend_sends_image_in_memory(data_dir, monkeypatch):
    import httpx

    from radbrain.capture import ocr
    seen = {}

    class R:
        status_code = 200
        text = ""

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "<think>x</think>Kein Pneumothorax."}}

    def fake_post(url, json=None, timeout=None):
        seen["url"], seen["body"] = url, json
        return R()

    monkeypatch.setattr(httpx, "post", fake_post)
    out = ocr.ocr_ollama(Image.new("RGB", (300, 80), "white"), model="vis:1", host="http://127.0.0.1:11434")
    assert out == "Kein Pneumothorax."
    assert seen["url"].endswith("/api/chat") and seen["body"]["model"] == "vis:1"
    assert seen["body"]["options"]["temperature"] == 0
    assert _files(data_dir) == set()


# ------------------------------------------------------------------------------------------------ grab
def test_is_black():
    from radbrain.capture.grab import is_black
    assert is_black(Image.new("RGB", (400, 300), (0, 0, 0)))
    assert is_black(Image.new("RGB", (400, 300), (5, 5, 5)))
    assert is_black(Image.new("RGB", (400, 300), (240, 240, 240)))          # flat fill = failed capture
    from radbrain.capture import bench_ocr
    panel = bench_ocr.render_panel("Kein Pneumothorax.\nKein Pleuraerguss.",
                                   font=bench_ocr.load_font("Arial", 12, bench_ocr.available_fonts()))
    assert not is_black(panel)
    dark_panel = bench_ocr.render_panel("Kein Pneumothorax.", dark=True,
                                        font=bench_ocr.load_font("Arial", 12, bench_ocr.available_fonts()))
    assert not is_black(dark_panel)


def test_grab_imports_without_windows():
    from radbrain.capture import grab
    assert grab.find_citrix_windows() == [] or sys.platform == "win32"
    assert callable(grab.grab_region)


# ------------------------------------------------------------------------------------------------ calibration
def test_calibration_round_trip(data_dir):
    from radbrain.capture import calibrate
    assert calibrate.get_regions("pair") is None
    rects = {"draft": calibrate.normalise_rect(700, 400, 100, 120),
             "final": {"left": 720, "top": 120, "width": 600, "height": 280}}
    assert rects["draft"] == {"left": 100, "top": 120, "width": 600, "height": 280}
    vs = {"left": -1920, "top": 0, "width": 4480, "height": 1440}
    calibrate.save_regions("pair", rects, virtual_screen=vs, monitors=[vs], dpi_awareness="per_monitor_v2")
    cal = json.loads((data_dir / "calibration.json").read_text(encoding="utf-8"))
    assert cal["virtual_screen"] == vs and cal["pair"]["draft"] == rects["draft"]
    assert calibrate.get_regions("pair") == rects
    assert calibrate.get_regions("final") == {"final": rects["final"]}     # falls back to the pair's right panel
    calibrate.save_regions("final", {"final": {"left": 0, "top": 0, "width": 500, "height": 500}})
    assert calibrate.get_regions("final")["final"]["width"] == 500
    assert calibrate.get_regions("pair") == rects                           # pair block untouched
    with pytest.raises(ValueError):
        calibrate.save_regions("pair", {"draft": rects["draft"]})
    with pytest.raises(ValueError):
        calibrate.save_regions("final", {"final": {"left": 0, "top": 0, "width": 5, "height": 5}})


def test_settings_update_keeps_foreign_keys(data_dir):
    from radbrain.capture import settings
    (data_dir / "settings.json").write_text(json.dumps({"llm": "qwen3.5:9b", "vision": "qwen3-vl:8b"}))
    assert settings.current_route() == "ocr"
    settings.save_json(settings.probe_path(), {"recommended_route": "clipboard"})
    assert settings.current_route() == "clipboard"
    settings.update_settings(route="ocr")
    s = json.loads((data_dir / "settings.json").read_text())
    assert s == {"llm": "qwen3.5:9b", "vision": "qwen3-vl:8b", "route": "ocr"}
    assert settings.current_route() == "ocr"


# ------------------------------------------------------------------------------------------------ capture()
@pytest.fixture()
def no_image_files(monkeypatch):
    """Fail if anything tries to save a PIL image to a path (in-memory BytesIO saves are allowed)."""
    orig = Image.Image.save

    def guarded(self, fp, *a, **k):
        if isinstance(fp, (str, Path)) or hasattr(fp, "name") and isinstance(getattr(fp, "name"), str):
            raise AssertionError(f"image written to disk: {fp}")
        return orig(self, fp, *a, **k)

    monkeypatch.setattr(Image.Image, "save", guarded)


def _calibrated(data_dir):
    from radbrain.capture import calibrate
    calibrate.save_regions("pair", {"draft": {"left": 0, "top": 0, "width": 400, "height": 300},
                                    "final": {"left": 420, "top": 0, "width": 400, "height": 300}})


DRAFT = "Befund: V.a. Lungenembolie re. Kein Pleuraerguss. Entwurf: Dr. Muster"
FINAL = "Befund: Segmentale Lungenembolie re. Kleiner Pleuraerguss. Elektronisch signiert: Dr. Probe"


def test_capture_pair_ocr_route(data_dir, no_image_files):
    from radbrain.capture import hotkey_app
    _calibrated(data_dir)
    before = _files(data_dir)
    grabbed, calls = [], []

    def fake_grab(rect):
        grabbed.append(rect["left"])
        return Image.new("RGB", (rect["width"], rect["height"]), "white")

    def fake_ocr(img):
        return DRAFT if len(grabbed) == 1 else FINAL

    def fake_ingest(kind, draft, final, source="hotkey"):
        calls.append((kind, draft, final, source))
        return {"status": "saved", "id": 7, "signer": "B1", "modality": "CT", "region": "Thorax",
                "pathologies": ["Lungenembolie"], "reason": ""}

    res = hotkey_app.capture("pair", route="ocr", grab=fake_grab, ocr=fake_ocr, ingest=fake_ingest,
                             blank=lambda img: False)
    assert calls == [("pair", DRAFT, FINAL, "hotkey")]
    assert grabbed == [0, 420]                      # draft = left panel first, then final
    assert hotkey_app.toast_text(res) == "Saved — B1 · CT Thorax · Lungenembolie"
    new = _files(data_dir) - before
    assert all(p.endswith((".log", ".json")) for p in new), new
    assert not any(p.lower().endswith((".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp")) for p in
                   _files(data_dir))
    log = (data_dir / "logs" / "capture.log")
    if log.exists():                                # logging only when setup_logging() ran; never text
        assert "Lungenembolie" not in log.read_text(encoding="utf-8")


def test_capture_final_and_logging_has_no_text(data_dir, no_image_files):
    from radbrain.capture import hotkey_app
    hotkey_app.setup_logging()
    _calibrated(data_dir)                           # only a pair calibration: final uses its right panel
    calls = []
    res = hotkey_app.capture(
        "final", route="ocr", grab=lambda r: Image.new("RGB", (10, 10)), ocr=lambda img: FINAL,
        blank=lambda img: False,
        ingest=lambda k, d, f, source="hotkey": calls.append((k, d, f)) or
        {"status": "quarantined", "id": None, "signer": None, "modality": None, "region": None,
         "pathologies": [], "reason": "no signer match"})
    assert calls == [("final", None, FINAL)]
    assert hotkey_app.toast_text(res) == "Quarantined — no signer match"
    for h in hotkey_app.log.handlers:
        h.flush()
    text = (data_dir / "logs" / "capture.log").read_text(encoding="utf-8")
    assert "status=quarantined" in text
    for secret in ("Lungenembolie", "Probe", "Muster", "signiert"):
        assert secret not in text


def test_capture_clipboard_route_with_ocr_fallback(data_dir, no_image_files):
    from radbrain.capture import hotkey_app
    _calibrated(data_dir)
    calls, grabbed = [], []
    res = hotkey_app.capture(
        "pair", route="clipboard",
        copy=lambda regions: {"draft": DRAFT, "final": None},           # final panel did not copy
        grab=lambda r: grabbed.append(r["left"]) or Image.new("RGB", (10, 10)),
        ocr=lambda img: FINAL, blank=lambda img: False,
        ingest=lambda k, d, f, source="hotkey": calls.append((k, d, f)) or {"status": "duplicate"})
    assert calls == [("pair", DRAFT, FINAL)] and grabbed == [420]
    assert hotkey_app.toast_text(res) == "Duplicate — skipped"


def test_capture_errors(data_dir, no_image_files):
    from radbrain.capture import hotkey_app
    never = lambda *a, **k: pytest.fail("ingest must not be called")  # noqa: E731
    assert hotkey_app.capture("pair", route="ocr", ingest=never)["reason"] == "not_calibrated"
    _calibrated(data_dir)
    r = hotkey_app.capture("pair", route="ocr", grab=lambda r: Image.new("RGB", (10, 10)), ocr=lambda i: "x",
                           blank=lambda i: True, ingest=never)
    assert r["status"] == "error" and r["reason"] == "blank_capture:draft"
    r = hotkey_app.capture("pair", route="ocr", grab=lambda r: Image.new("RGB", (10, 10)), ocr=lambda i: "  ",
                           blank=lambda i: False, ingest=never)
    assert r["reason"] == "no_text:draft"
    assert hotkey_app.toast_text(r) == "Capture failed — no_text:draft"


def test_clipboard_copy_logic_with_fake_backend():
    from radbrain.capture import clip

    class Fake:
        def __init__(self):
            self.clip, self.s, self.cursor, self.events, self.focus = "user stuff", 1, (5, 5), [], None
            self.panels = {(200, 150): DRAFT, (620, 150): FINAL}

        def modifiers_down(self):
            return False

        def get_text(self):
            return self.clip

        def has_content(self):
            return self.clip is not None

        def set_text(self, t):
            self.clip, self.s = t, self.s + 1
            return True

        def clear(self):
            self.clip, self.s = None, self.s + 1
            return True

        def seq(self):
            return self.s

        def cursor_pos(self):
            return self.cursor

        def set_cursor(self, x, y):
            self.cursor = (x, y)

        def click(self, x, y):
            self.focus = (x, y)
            self.events.append(("click", x, y))

        def ctrl(self, vk):
            self.events.append(("ctrl", vk))
            if vk == clip.VK_C and self.focus in self.panels:
                self.clip, self.s = self.panels[self.focus], self.s + 1

    f = Fake()
    out = clip.copy_regions({"draft": {"left": 0, "top": 0, "width": 400, "height": 300},
                             "final": {"left": 420, "top": 0, "width": 400, "height": 300},
                             "empty": {"left": 900, "top": 0, "width": 100, "height": 100}},
                            backend=f, settle=0, timeout=0.1)
    assert out == {"draft": DRAFT, "final": FINAL, "empty": None}
    assert f.clip == "user stuff" and f.cursor == (5, 5)            # clipboard + cursor restored
    assert ("ctrl", clip.VK_A) in f.events


# ------------------------------------------------------------------------------------------------ imports
def test_hotkey_app_imports_on_non_windows(data_dir, monkeypatch):
    import threading
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    mod = importlib.import_module("radbrain.capture.hotkey_app")
    assert callable(mod.capture) and callable(mod.main)
    for name in ("probe_citrix", "calibrate", "clip", "grab", "ocr", "bench_ocr", "dummy_window", "settings"):
        importlib.import_module(f"radbrain.capture.{name}")
    if sys.platform != "win32":
        assert mod.main([]) == 2                                     # tray mode refuses politely
        from radbrain.capture import probe_citrix
        assert probe_citrix.main(["--no-clipboard"]) == 2


def test_counts_tooltip():
    from radbrain.capture.hotkey_app import counts_tooltip
    tip = counts_tooltip({"B1": {"pairs": 12, "finals": 40}, "B2": {"pairs": 3}})
    assert tip == "RadBrain · B1 12/500 · B2 3/500 · B3 0/500"


def test_probe_text_stats_counts_only():
    from radbrain.capture.probe_citrix import recommend, text_stats
    st = text_stats("Kein Pneumothorax.\nGröße ca. 5 mm.")
    assert st["lines"] == 2 and st["has_umlauts"] and set(st) == {
        "chars", "lines", "words", "german_words", "umlauts", "has_umlauts"}
    assert recommend({"windows": []}, {"clipboard_changed": True, "length": 500, "lines": 12}) == "clipboard"
    assert recommend({"windows": [{"methods": {"mss": {"status": "ok", "black": False, "german_text": True}}}]},
                     {"clipboard_changed": False}) == "ocr"
    assert recommend({"windows": []}, None) == "none"


def test_dummy_window_diff_spans():
    from radbrain.capture.dummy_window import PAIRS, changed_spans
    sa, sb = changed_spans(PAIRS[0]["draft"], PAIRS[0]["final"])
    assert sa and sb
    changed_final = {PAIRS[0]["final"][s:e] for s, e in sb}
    assert "Elektronisch" in changed_final and "Thorax" not in changed_final


# ------------------------------------------------------------------------------------------------ live e2e
@pytest.mark.skipif(not (HAS_TESSERACT and __import__("os").environ.get("RADBRAIN_E2E")),
                    reason="set RADBRAIN_E2E=1 (opens a window, needs screen-recording permission)")
def test_e2e_dummy_window_grab_ocr(data_dir, tmp_path, no_image_files):
    """Launch dummy_window, grab its panels with mss in memory, OCR, CER vs the known text, then push the
    pair through capture() with the real grab/OCR and a recording ingest."""
    import json as _json
    import subprocess
    import time

    from radbrain.capture import bench_ocr, calibrate, grab, hotkey_app
    geo = tmp_path / "geo.json"
    proc = subprocess.Popen([sys.executable, "-m", "radbrain.capture.dummy_window", "--geometry-out", str(geo),
                             "--topmost", "--exit-after", "30"], cwd=str(Path(__file__).resolve().parents[1]))
    try:
        t0 = time.time()
        while not geo.exists() and time.time() - t0 < 15:
            time.sleep(0.2)
        time.sleep(1.0)
        d = _json.loads(geo.read_text(encoding="utf-8"))
        img = grab.grab_rect(d["rects"]["final"])
        if grab.is_black(img):
            pytest.skip("BLOCKED: grab is blank (no screen-recording permission?)")
        del img
        calibrate.save_regions("pair", d["rects"])
        seen = []
        res = hotkey_app.capture("pair", route="ocr",
                                 ingest=lambda k, dr, fi, source="hotkey": seen.append((k, dr, fi)) or
                                 {"status": "duplicate"})
        assert res["status"] == "duplicate" and len(seen) == 1
        _, draft, final = seen[0]
        c_draft = bench_ocr.cer(bench_ocr.norm_lines(draft), bench_ocr.norm_lines(d["draft"]))
        c_final = bench_ocr.cer(bench_ocr.norm_lines(final), bench_ocr.norm_lines(d["final"]))
        print(f"E2E CER draft={c_draft:.4f} final={c_final:.4f}")
        assert c_draft < 0.03 and c_final < 0.03
    finally:
        proc.terminate()
