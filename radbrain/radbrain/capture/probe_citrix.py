"""Phase 1 feasibility probe for the PC: python -m radbrain.capture.probe_citrix [--no-clipboard] [--ocr tesseract]

1. Lists visible Citrix windows (class / process / matched keywords only - titles are NOT printed, a PACS title
   can carry a patient name).
2. Grabs each window in memory via PrintWindow(PW_RENDERFULLCONTENT), mss of the window rect and Windows
   Graphics Capture (if the windows-capture package is installed); per method: blank or not, size, and
   whether OCR finds German text (counts of words / dictionary words / umlauts only).
3. Clipboard route: asks you to click into a report panel within 5 s, sends Ctrl+A, Ctrl+C to the
   foreground window via SendInput, reads CF_UNICODETEXT, reports only length / line count / umlaut presence,
   then clears the clipboard.
4. Writes {"capture": {...}, "clipboard": {...}, "recommended_route": "clipboard"|"ocr"|"none"} to
   data_dir()/logs/probe_citrix.json.

No image and no text is ever printed or stored; images are dropped right after counting.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time

from radbrain.capture.settings import probe_path, save_json

UMLAUTS = set("äöüÄÖÜß")
_WORD = re.compile(r"[A-Za-zÄÖÜäöüß]{3,}")


def text_stats(text: str | None) -> dict:
    """Counts only. The text itself is discarded by the caller."""
    if not text:
        return {"chars": 0, "lines": 0, "words": 0, "german_words": 0, "umlauts": 0, "has_umlauts": False}
    words = _WORD.findall(text)
    try:
        from wordfreq import zipf_frequency
        german = sum(1 for w in words if zipf_frequency(w.lower(), "de") >= 2.5)
    except Exception:
        german = -1
    um = sum(1 for c in text if c in UMLAUTS)
    return {"chars": len(text), "lines": text.count("\n") + 1, "words": len(words), "german_words": german,
            "umlauts": um, "has_umlauts": um > 0}


def looks_german(stats: dict) -> bool:
    return stats.get("words", 0) >= 15 and stats.get("german_words", 0) >= 0.5 * stats.get("words", 1)


def probe_capture(ocr_backend: str = "tesseract") -> dict:
    from radbrain.capture import grab
    from radbrain.capture.ocr import get_backend
    ocr_fn = get_backend(ocr_backend)
    out = {"dpi_awareness": grab.set_dpi_awareness(), "wgc_available": grab.wgc_available(),
           "ocr_backend": ocr_backend, "windows": []}
    wins = grab.find_citrix_windows()
    out["citrix_windows_found"] = len(wins)
    for idx, w in enumerate(wins):
        l, t, r, b = w["rect"]
        entry = {"index": idx, "cls": w["cls"], "exe": w["exe"], "match": w["match"],
                 "title_len": len(w["title"]), "size": [r - l, b - t], "minimised": w["minimised"], "methods": {}}
        for method in ("printwindow", "mss", "wgc"):
            res: dict = {}
            t0 = time.perf_counter()
            img = None
            try:
                img = grab.grab_window(w["hwnd"], method)
                if img is None:
                    res["status"] = "unavailable" if method == "wgc" and not grab.wgc_available() else "failed"
                else:
                    res["size"] = list(img.size)
                    res["black"] = grab.is_black(img)
                    res["grab_sec"] = round(time.perf_counter() - t0, 3)
                    if not res["black"]:
                        t1 = time.perf_counter()
                        txt = ocr_fn(img)
                        res["ocr"] = text_stats(txt)
                        res["ocr_sec"] = round(time.perf_counter() - t1, 2)
                        res["german_text"] = looks_german(res["ocr"])
                        del txt
                    res["status"] = "ok"
            except Exception as e:
                res["status"] = f"error: {type(e).__name__}"
            finally:
                del img
            entry["methods"][method] = res
        out["windows"].append(entry)
    return out


def probe_clipboard(countdown: int = 5) -> dict:
    from radbrain.capture import clip, grab
    be = clip.Win32Backend()
    print(f"\nCLIPBOARD TEST: click into a report text panel inside Citrix NOW. Copying in {countdown} s ...",
          flush=True)
    for i in range(countdown, 0, -1):
        print(f"  {i}", flush=True)
        time.sleep(1)
    fg = grab.foreground_window()
    fg_info = {}
    if fg:
        try:
            d = grab.describe_window(fg)
            fg_info = {"cls": d["cls"], "exe": d["exe"], "citrix": bool(grab.citrix_match(d))}
        except Exception:
            pass
    clip._wait_modifiers_released(be)
    before = be.seq()
    be.ctrl(clip.VK_A)
    time.sleep(0.15)
    be.ctrl(clip.VK_C)
    changed = False
    t_end = time.monotonic() + 3.0
    t0 = time.monotonic()
    while time.monotonic() < t_end:
        if be.seq() != before:
            changed = True
            break
        time.sleep(0.03)
    latency = round(time.monotonic() - t0, 3)
    time.sleep(0.1)
    text = be.get_text() if changed else None
    stats = text_stats(text)
    del text
    cleared = be.clear()
    print("  done - clipboard cleared. (Click once into the panel to drop the selection.)", flush=True)
    return {"foreground": fg_info, "clipboard_changed": changed, "latency_sec": latency if changed else None,
            "length": stats["chars"], "lines": stats["lines"], "has_umlauts": stats["has_umlauts"],
            "words": stats["words"], "german_words": stats["german_words"], "cleared": cleared}


def recommend(capture: dict, clipboard: dict | None) -> str:
    if clipboard and clipboard.get("clipboard_changed") and clipboard.get("length", 0) >= 80 \
            and clipboard.get("lines", 0) >= 2:
        return "clipboard"
    for w in capture.get("windows", []):
        for m in w.get("methods", {}).values():
            if m.get("status") == "ok" and not m.get("black") and m.get("german_text"):
                return "ocr"
    return "none"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="RadBrain Citrix feasibility probe (counts only, no text)")
    ap.add_argument("--no-clipboard", action="store_true", help="skip the interactive clipboard test")
    ap.add_argument("--ocr", default="tesseract", choices=["tesseract", "ollama", "paddle"])
    ap.add_argument("--countdown", type=int, default=5)
    args = ap.parse_args(argv)
    if sys.platform != "win32":
        print("probe_citrix is a Windows-only test (run it on the PC inside the logged-on desktop).")
        return 2
    capture = probe_capture(args.ocr)
    print(json.dumps({"capture": capture}, indent=2, ensure_ascii=False))
    clipboard = None
    if not args.no_clipboard:
        try:
            clipboard = probe_clipboard(args.countdown)
        except Exception as e:
            clipboard = {"error": type(e).__name__}
    verdict = {"probed_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "capture": capture, "clipboard": clipboard,
               "recommended_route": recommend(capture, clipboard)}
    p = save_json(probe_path(), verdict)
    print(json.dumps({"clipboard": clipboard, "recommended_route": verdict["recommended_route"]}, indent=2))
    print(f"\nverdict written to {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
