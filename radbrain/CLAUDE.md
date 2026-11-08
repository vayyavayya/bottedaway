# RadBrain — working notes for Claude Code

Three style "brains" (B1 = Chefarzt, B2 = Leitender Oberarzt, B3 = Oberarzt) learn how senior radiologists in
Ajit's department correct Befunde, from draft→final pairs he captures in PACS with a hotkey on the 5090 PC.

## Hard rules (never relax)
- Codes only: B1/B2/B3 in code, UI, filenames, logs, commits, docs. The name→code map is `signers.json` in the data
  dir (Ajit fills it, gitignored, never printed or logged).
- No patient data leaves the PC. No cloud API for report text, no telemetry. `radbrain/llm.py` refuses any
  non-localhost Ollama. RadBrain does NOT use Triage (cloud) — see DECISIONS #3.
- Screenshots are never written to disk: memory → OCR → anonymise → discard.
- The anonymiser fails closed: unsure → `quarantine/` in the data dir, reviewed by Ajit in the dashboard.
- Tests use synthetic data only (`radbrain/synth.py`). Real captures only when Ajit presses the hotkey.
- The repo (vayyavayya/bottedaway, public) holds code only. Data dir: `%LOCALAPPDATA%\RadBrain` (PC).
- Ask before anything paid. Free local Ollama models are fine.
- "It ran" is not proof: report VERIFIED ON DEVICE / STATICALLY CHECKED / BLOCKED-UNTESTED.

## Layout
radbrain/config.py      data dir, signers.json, model settings, targets (500 pairs / 1000 finals, live at 300)
radbrain/anonymise.py   Phase 3 (structure → scrub → residual check)
radbrain/synth.py       synthetic reports + planted identifiers + ground-truth style rules
radbrain/pipeline.py    ingest() — the only entry point for captures; quarantine review
radbrain/library.py     SQLite schema
radbrain/diff.py        word-level diff, reorder/numbering, highlight HTML
radbrain/miner.py       Phase 5 rule miner, rulebooks, saturation, open-next
radbrain/engine.py      Phase 7 Correct / Predict / Ask + no-new-findings guards
radbrain/evaluate.py    Phase 8 holdout eval (chrF, edit distance, predict recall/precision)
radbrain/web.py         dashboard on 127.0.0.1:8650 (static/ = page, no external assets)
radbrain/capture/       Phase 1/2 Windows capture tool (hotkeys, tray, calibration, OCR, Citrix probe)
install.ps1             one-click PC install; deploy-pc.sh pushes from the Mac over SSH

## Run
pytest -q                                   # synthetic only
python -m radbrain.web --port 8650          # dashboard
python -m radbrain.capture.hotkey_app       # PC tray app (Ctrl+Shift+B pair, Ctrl+Shift+F final)
python -m radbrain.demo --n 600             # fill a SEPARATE demo data dir with synthetic captures
