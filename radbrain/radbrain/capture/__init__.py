"""RadBrain capture side (Windows PC, testable on the Mac).

Modules (import them directly; this package imports nothing heavy):
  ocr           one API ocr(image) -> str, backends tesseract / ollama / paddle, best_backend()
  grab          in-memory screen capture: mss regions, Citrix window discovery, PrintWindow, WGC, is_black()
  clip          clipboard route: click into a calibrated panel, Ctrl+A, Ctrl+C, read, restore clipboard
  calibrate     one-time tkinter overlay to mark the draft/final report panels -> calibration.json
  hotkey_app    tray app + global hotkeys (Ctrl+Shift+B pair, Ctrl+Shift+F final) -> pipeline.ingest
  probe_citrix  Phase 1 feasibility probe on the PC (capture methods + clipboard), counts only
  bench_ocr     synthetic OCR benchmark (CER, abbreviation hits, umlaut accuracy, sec/image)
  dummy_window  tkinter imitation of the PACS comparison view with fictional report pairs

Privacy contract for everything in here: screenshots live only in memory (never saved, no temp files, no
debug dumps); OCR text and clipboard text are handed to pipeline.ingest and never logged or printed; logs
carry statuses, codes, lengths and timings only. All OCR is local (Tesseract, local Ollama, PaddleOCR).
"""

CAPTURE_KINDS = ("pair", "final")
