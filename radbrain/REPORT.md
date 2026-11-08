# RadBrain — build report, 08.11.2026 (night)

Branch `radbrain` on vayyavayya/bottedaway (folder `radbrain/`). Live on the 5090 PC since 22:59.

## VERIFIED ON DEVICE (5090 PC unless noted)
| What | Evidence |
|---|---|
| Install | `install.ps1` via `deploy-pc.sh`: Python 3.12, Tesseract + deu (tessdata_best), venv `C:\RadBrain\venv`, windows-capture, bge-m3 pulled, tasks registered |
| Tests on the PC | 45 passed, 3 skipped (Mac-only) in 125 s — synthetic data |
| Citrix capture (Phase 1) | real Citrix session: mss grab works (335 words OCR'd, 5.4 s); PrintWindow/WGC blank; clipboard blocked by Citrix policy → OCR route |
| Hotkey → library → dashboard | `python -m radbrain.capture.e2e` on the PC: dummy PACS window, real Ctrl+Shift+B, mss + Tesseract, anonymise, saved as B1 · CT · Thorax · Lungenembolie in 1.49 s, listed by the dashboard API, 0 image files on disk (demo data dir) |
| Services | tasks `\RadBrain\RadBrain Capture` (hotkeys registered) and `\RadBrain\RadBrain Dashboard` (http://127.0.0.1:8650, /health ok) running; real library empty |
| PC lifeline | sshd reinstalled, Running/Automatic; watchdog task last result 0; SSH from the Mac works |
| Anonymiser (Mac, synthetic) | 0 leaks in 1,040 synthetic texts (half the names held out) + 12/12 hand-written adversarial cases; eponyms intact; ≥ 98 % token precision |
| Miner / engine / eval (Mac + PC tests, synthetic) | 11–12 of 12 planted rules recovered with the right HOUSE/PERSONAL label; Correct/Predict/Ask end to end; LLM rewrite (qwen3.5:9b on the Mac) passed the no-new-findings guard; eval chrF draft→engine B1 96.7→97.9, B2 89.7→96.4, B3 97.4→97.7 (**synthetic**) |

## STATICALLY CHECKED
- Calibration overlay over the real PACS layout (code reviewed; Ajit's first calibration is the live test).
- Ctrl+Shift+B while a **Citrix** window has focus — Citrix may swallow the hotkey; the tray menu has "Capture pair/final" as a fallback.
- Toast notifications (winotify + Tk fallback), restart-on-failure of the tasks, `install.ps1 -Uninstall`.
- Correct mode with qwen3.6:27b on the PC (model present; not exercised on real text).

## BLOCKED / UNTESTED
- Real captures: need `signers.json` filled and Ajit pressing the hotkey on a real comparison view.
- OCR quality on real Citrix report panels (0 umlauts in the probe's whole-screen OCR — the screen may not have shown report text; the first 10 real captures will tell).
- Engine on real data: goes live per brain at ≥ 300 real pairs (dashboard shows it).
- RadCoach ↔ RadBrain coupling (RadCoach asking RadBrain's Predict for a signer) — deliberately not wired until a brain is live.

## Start / stop (PC)
Start-ScheduledTask -TaskPath \RadBrain\ -TaskName "RadBrain Dashboard"   (or "RadBrain Capture")
Stop-ScheduledTask  -TaskPath \RadBrain\ -TaskName "RadBrain Capture"
Redeploy from the Mac: `~/RadBrain/radbrain/deploy-pc.sh`; remove: `install.ps1 -Uninstall` (data dir kept).

## Needs Ajit (updated 08.11.2026 23:20 — signers and calibration are now automatic)
1. Open comparison views in PACS and press Ctrl+Shift+B (single final: Ctrl+Shift+F). If nothing happens while Citrix
   has focus, use the RadBrain tray menu → Capture pair. Only Ajit opens patient cases — never automated.
2. Dashboard tab "Unterzeichner": one click to mark which Oberarzt is B3 (B1/B2 assign themselves when unambiguous).
3. Glance at the Quarantäne tab after the first ~10 captures.
4. BIOS at the next reboot: Wake-on-LAN / "Power On by PCI-E" on, ErP off, "Restore on AC Power Loss" = Power On.
