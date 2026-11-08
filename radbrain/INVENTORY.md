# INVENTORY — RadBrain (what exists, where, how to run)

## On the PC (after install.ps1)
| What | Where |
|---|---|
| App code | `C:\RadBrain\app` (copy of this folder), venv `C:\RadBrain\venv` |
| Data dir (everything derived from reports) | `%LOCALAPPDATA%\RadBrain` — `library.sqlite`, `signers.json`, `settings.json`, `calibration.json`, `allowlist.txt`, `quarantine\`, `rulebooks\rulebook_B1..B3.md`, `logs\` |
| Demo data dir (synthetic only) | `%LOCALAPPDATA%\RadBrain-demo` (`python -m radbrain.demo`) |
| Dashboard | http://127.0.0.1:8650 — task `\RadBrain\RadBrain Dashboard` (at logon, interactive) |
| Capture tray app | task `\RadBrain\RadBrain Capture` — Ctrl+Shift+B pair, Ctrl+Shift+F final |
| Models | local Ollama 127.0.0.1:11434: `qwen3.6:27b` (LLM, vision OCR option), `bge-m3` (embeddings) |

Start/stop: `Start-ScheduledTask -TaskPath \RadBrain\ -TaskName "RadBrain Dashboard"` (or "RadBrain Capture"),
`Stop-ScheduledTask …`; remove: `install.ps1 -Uninstall` (keeps the data dir).

## Modules
| File | Phase | Purpose |
|---|---|---|
| radbrain/config.py | – | paths, signers.json, models, targets |
| radbrain/taxonomy.py | 6 | modalities, regions, 43 checklist entities, tagging rules |
| radbrain/names.py, lexicon_med.txt | 3 | name lists, eponyms, titles; medical lexicon |
| radbrain/anonymise.py | 3 | structure → scrub → fail-closed residual check |
| radbrain/synth.py | test | synthetic reports, planted identifiers, ground-truth style rules |
| radbrain/pipeline.py | 2/4 | `ingest()`, quarantine review/release/discard, re-mine every 25 pairs |
| radbrain/library.py | 4 | SQLite schema (no exam date, no raw text) |
| radbrain/diff.py | 5/7 | word diff, reorder/numbering, highlight HTML |
| radbrain/miner.py | 5/6 | rules, HOUSE/PERSONAL, rulebooks, saturation, open-next |
| radbrain/llm.py | 7 | local-only Ollama client (refuses non-local hosts) |
| radbrain/engine.py | 7 | Correct / Predict / Ask + guards + consistency flags |
| radbrain/evaluate.py | 8 | holdout eval: chrF, edit distance, predict recall/precision |
| radbrain/web.py, static/ | 6/7 | dashboard |
| radbrain/demo.py | test | fill the demo data dir |
| tests/ | – | pytest, synthetic only |

## Capture side (`radbrain/capture/`, Windows PC; testable on the Mac)

Privacy contract: screenshots exist only in memory (grab -> OCR -> `del`), Tesseract gets the image through
STDIN (pytesseract's temp-file path is not used), Ollama gets base64 in the request body. OCR/clipboard text
goes only to `pipeline.ingest`; logs carry statuses, signer codes, lengths and timings. Window titles are never
logged (a PACS title can carry a name). Everything is local: no cloud, no telemetry.

| File | Run / API | What it does |
|---|---|---|
| `capture/__init__.py` | - | package doc + `CAPTURE_KINDS` |
| `capture/ocr.py` | `ocr(img) -> str`, `best_backend()`, `available_backends()` | backends `tesseract` (deu, psm 4, grayscale/invert, UI-line stripping, adaptive upscale, light threshold, l/I/\| fixes), `ollama` (config.models().vision, temperature 0, `<think>` stripped), `paddle` (optional) ; settings.json `"ocr"` picks the default |
| `capture/grab.py` | `grab_region`, `grab_rect`, `find_citrix_windows`, `grab_window(hwnd, "printwindow"\|"mss"\|"wgc"\|"auto")`, `is_black` | mss region capture; Win32 EnumWindows + PrintWindow(PW_RENDERFULLCONTENT) + optional Windows Graphics Capture (`windows-capture`); DPI awareness |
| `capture/clip.py` | `copy_regions({"draft": r, "final": r})` | clipboard route: click panel centre, Ctrl+A, Ctrl+C (SendInput, VK + scan code), poll clipboard sequence number, read CF_UNICODETEXT, restore previous clipboard text (or clear) and cursor |
| `capture/calibrate.py` | `python -m radbrain.capture.calibrate --mode pair\|final` | fullscreen semi-transparent topmost Tk overlay over the virtual screen; drag LEFT=draft then RIGHT=final (or one final) -> `calibration.json` (+ virtual screen + monitors + DPI mode) |
| `capture/hotkey_app.py` | `python -m radbrain.capture.hotkey_app [--once pair\|final]` | tray app (pystray, icon drawn in code, tooltip `RadBrain · B1 12/500 · ...` from `pipeline.counts()`), RegisterHotKey Ctrl+Shift+B (pair) / Ctrl+Shift+F (final), route clipboard/OCR with OCR fallback, toast (winotify or Tk), menu: recalibrate, route toggle, dashboard, quarantine, quit. `capture(kind, *, grab=, ocr=, ingest=, copy=, blank=)` is injectable |
| `capture/probe_citrix.py` | `python -m radbrain.capture.probe_citrix` | Phase 1 feasibility: Citrix windows x {PrintWindow, mss, WGC} blank/not + OCR word/umlaut counts; clipboard test (length/lines/umlauts only, then cleared) -> `logs/probe_citrix.json` with `recommended_route` |
| `capture/bench_ocr.py` | `python -m radbrain.capture.bench_ocr --backends tesseract,ollama --ollama-model M --out f.json` | 30 fictional report snippets rendered in memory (11-20 px, light/dark, JPEG+blur); CER, layout-free CER, abbreviation/term hit rate, umlaut/ß accuracy, sec/image |
| `capture/dummy_window.py` | `python -m radbrain.capture.dummy_window [--geometry-out f.json]` | Tk imitation of the PACS comparison view, 3 fictional pairs (Dr. med. Muster / Probe / Beispiel / Test-B3), diffs highlighted yellow, → cycles |
| `capture/settings.py` | `load_settings`, `update_settings`, `current_route` | settings.json read-modify-write (keeps config.models() keys), atomic JSON writes |
| `tests/test_capture.py` | `.venv/bin/python -m pytest tests/test_capture.py` (`RADBRAIN_E2E=1` adds the live dummy-window grab) | 19 tests incl. a guard that fails on any PIL save to a path |
| `install.ps1` | `powershell -ExecutionPolicy Bypass -File install.ps1 [-Uninstall]` | Python 3.12 + Tesseract (winget) + tessdata_best deu, `C:\RadBrain\app` + `C:\RadBrain\venv`, signers template, tasks `\RadBrain\RadBrain Capture` / `RadBrain Dashboard` (At log on, interactive, restart 3x/1 min), `ollama pull bge-m3` |
| `requirements-win.txt` | - | httpx, pillow, pytesseract, mss, pyperclip, pystray, winotify, rapidfuzz, wordfreq (+ optional windows-capture) |

Data-dir files written by the capture side: `calibration.json`, `settings.json` (`route`, `ocr` keys),
`logs/capture.log`, `logs/probe_citrix.json`. Never images, never text.
