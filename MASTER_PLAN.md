# RadCoach master plan (state 24.10.2026)

This is the index of the whole advanced plan. Read it first, then the detailed specs:

1. `PROMPT.md`: full build spec (architecture, PC, model routing, modules A–M, phases 1–4).
2. `UPDATE_2026-10-19.md`: overrides PROMPT.md where they differ.
3. `COACH_PROMPT_v6_live.md`: authoritative coaching rules; replaces Appendix A.

Where they differ, the order of precedence is: this file > UPDATE > PROMPT.

## 0. Goal and yardstick

**Goal:** an absolute beginner (first month, since 01.10.2026) speed-runs the reporting learning curve.
- Dienst-ready for December 2026 (the department plans his first Dienste then).
- 4th-year-resident reporting level in Röntgen and emergency CT by about August 2027.
- Long term: the interventional track.

**Volume plan (Ajit's daily targets):**

| | until 31.12.2026 | from January 2027 |
|---|---|---|
| Full Röntgen reports per working day | 30 | 40 |
| CT reports per working day, written blind before the signed report | 6 | 12 |
| Corrected through the coach per working day | 10 | 10 (the hardest) |

- Every other report he compares with the signed report the same day.
- Evening block, Monday to Wednesday: 50 normals in gestalt mode, plus 20 timed 30-second calls.
- Friday: a 10-case quiz plus a blind re-read of his weakest category.

**Yardstick:** progress is measured, not dated. The system must report weekly:
- major-miss rate against signed reports: target < 5 % for Röntgen, < 10 % for emergency CT
- chief-edit rate on Beurteilung
- volume per day

## 1. Inventory: what exists, what is missing

| # | Component | Spec | State 24.10.2026 |
|---|---|---|---|
| 1 | Watcher, queue, writer, privacy gate, lint, side marker, retrieval, `claude -p` runner with schema and cost log, certainty rule, docimg, scheduler, health, CLI, eval export (gold set 08–09.10) | PROMPT §3–6, §11 | **Built 10.10 (82 tests), never run live.** launchd jobs not loaded. |
| 2 | Google OAuth as radioshahall (documents + drive) | UPDATE §1 | **Done 24.10.** Token works; Drive search finds the week docs; all 7 docs open. The app is in Testing, so the token expires after 7 days. Ajit must finish Branding and click „App veröffentlichen“. |
| 3 | Weekly doc discovery, new correction order, single-writer lock, insert-at-paragraph-start assertion, revision ladder, patient-line stripping | UPDATE §2–6 | **Missing.** |
| 4 | Scratch copy owned by radioshahall | UPDATE §7 | **Missing.** The old scratch doc belongs to the old account. |
| 5 | Telegram alerts | PROMPT §3 | `secrets/telegram.json` exists. **~/.alertd does NOT exist on the Mac**, so use RadCoach's own sender with that file. |
| 6 | PC node (RTX 5090): wake 07:55 (timer + WoL), awake 08–16, services (Ollama, gateway :11436, worker :8790), firewall, keep-awake, 16:05 sleep, 450 W cap, /health /ocr /marker /lint /embed /read /tts /dicom-prep /segment, health alert at 08:10, Mac fallback | PROMPT §7 | `pcworker/app.py`, `setup.ps1`, `window.ps1` written 10.10. **Not deployed or verified.** |
| 7 | Model routing (Fable for images with pacing, Opus for persistent text, Haiku for triage, fallback ladder, stop new Fable runs above 80 % of the 5-hour window, prompt-cached chief corpus, weekly eval) | PROMPT §8 | Runner built; pacing and eval **unverified**. |
| 8 | Second reader on the PC: vision model `ajit-general:35b` / `qwen3.6:27b`; also try `ajit-medgemma` | PROMPT §3 Tier 3, §7 | Logged only (Phase 1). Never reaches Claude before Claude's own read. |
| 9 | B. Pre-sign check (`#check` + RIS draft → corrected house version ≤ 30 s) | PROMPT §9 | **Missing.** Highest leverage. |
| 10 | C. Chief-edit loop (`#signed` → sentence diff, ledger, fingerprint corpus; KPI chief-edit rate) | PROMPT §9 | **Missing.** |
| 11 | D. Chief-style fingerprint per modality and region | PROMPT §9 | **Missing.** |
| 12 | Ground-truth grading on signed reports (`grades.json`, extractor validated on 50 hand-graded reports) plus both ledgers (Ajit's errors; coach precision/recall) | PROMPT §9 | Partly (DoD 7). |
| 13 | M. Weekly report, Friday 16:30, doc + Telegram: chief-edit rate, blind-read accuracy by category, side errors, time per report, don't-miss mastery, perceptual sens/spec, coach accuracy, model fallbacks, **plus the volume and miss-rate yardstick of §0** | PROMPT §9 | **Missing.** |
| 14 | H. Concept pipeline (`#what is X` → answer with open-licence image → concept note in vault `06- Full Notes/` written to local disk the way the bridge does → Anki cards via `~/.srs/anki/outbox`, deck `Radiology::Befund`) | PROMPT §9 | **Missing.** The Anki bridge exists (`~/.local/bin/anki-bridge.py`, launchd `com.ajit.anki-bridge`); match its card format. |
| 15 | End-of-Day Anki cards: the 10 „front ‖ back“ lines → Anki outbox, deck `Radiology::Befund` | COACH v6 | **Missing.** The cloud coach writes them to the doc only. |
| 16 | I. Befundbesprechung card each evening (finding, DDx, next step, pearl, Oberarzt question) → doc + Telegram | PROMPT §9 | **Missing.** |
| 17 | G. Commute audio: Ajit wants 90 min/day (PROMPT: 45–90) | PROMPT §9 | **Missing.** Details below. |
| 18 | Daily-lessons module: doc „Radiology daily lessons“ every 2 h 08–16 Mon–Fri; „randomthots“ doc | memory 13.10; cloud task „Radiology lessons + Randomthots“ | **Runs in the cloud only. Port it.** Details below. |
| 19 | Textbausteine and CT Standard maintenance | COACH v6 | **Cloud only. Port it.** Details below. |
| 20 | Day block and accelerators: Start of Day 07:53, Monday week preview + top-3 mistakes + weak-spot drill + Dienst hospitation, daily Evening PACS block (Mon–Wed), Oberarzt question, Friday quiz, End of Day 16:30 | COACH v6 | Scheduler exists; **content per v6 missing.** |
| 21 | E. Don't-miss engine + Dienst simulator: fixed critical-findings checklist per modality, mastery per item, timed simulator with „clinician calls“ as Telegram voice messages through Hermes | PROMPT §9 Phase 3 | **Missing.** Due before the first Dienste in December. |
| 22 | F. Perceptual trainer | PROMPT §9 Phase 3 | **Missing.** Details below. |
| 23 | J. PC second reader surfaced at SCREENSHOT level once its accuracy is measured | PROMPT §9 | Later. |
| 24 | K. Anatomy tutor (3D Slicer + TotalSegmentator on public CT volumes on the PC; promise only structures it actually segments) | PROMPT §9 Phase 4 | Later (November). |
| 25 | L. RadDesk: public web UI reachable from ANY computer in the world | PROMPT §9 Phase 4; memory 01–03.10 | Later (November). Details below. |
| 26 | Optional PC extras planned 15.09: faster-whisper German dictation for spoken-Befund practice; MedGemma as a candidate second reader | memory | Optional, after J. |

Details for the rows marked „Details below“:

- **Row 17, commute audio:**
  - Built from the day's errors and the next topic.
  - English narration with German terms, and a question about every 10 minutes.
  - TTS on the PC (Kokoro or Piper) at 15:00, plus a ≤ 5-minute Mac addendum for errors made later.
  - Delivered by Telegram or a Drive folder by 06:30.
  - Radiopaedia forbids scraping: use it to pick topics only, never as text.
- **Row 18, daily-lessons module:**
  - Highlighted or open lines in „Radiology daily lessons“ get a full lesson below them: Wikimedia image checked by looking at it, what to look for, DDx, why it matters, German Bausteine, Merke.
  - „randomthots“: every `#` or `?` line gets a bold Answer:.
  - Lessons also go to RadDesk once it exists.
- **Row 19, Textbausteine and CT Standard maintenance:**
  - Sort new reference reports into „Nach Krankheitsbild“ / Sortiert, with Best patterns.
  - Sort new CT reports into CT Standard „Sortiert“ groups.
  - Add new formulas to the Stil-Datenbank tab.
  - Copy signed CCT reports into CT Standard „Original“.
  - Never touch his Original text.
- **Row 22, perceptual trainer:**
  - Use public labelled datasets that Ajit downloads himself after checking each licence: MURA, RSNA ICH, CQ500, RSNA Pneumonia, NIH ChestX-ray14, VinDr, FracAtlas, RSNA C-spine, RSNA Abdominal Trauma, RSNA PE, LIDC-IDRI, MedPix.
  - The PC converts DICOM to windowed PNG.
  - 20 s per image; answer normal/abnormal plus region; adaptive; 10 min per evening.
  - Track sensitivity and specificity.
- **Row 25, RadDesk:**
  - Cloudflare Tunnel + Access or a small VPS; tailnet-only is NOT acceptable.
  - Shows: case review with highlights, ledgers, KPI dashboard, drills.
  - AMBOSS-style topic pages: left outline, collapsible sections, term tooltips, a right-hand AI term panel with clickable term buttons, Q&A per topic, a „+“ box to add a topic, per-section image/video by link.
  - Ask Ajit before anything paid.

## 2. Build order with dates

**Tonight and Sunday 25.10 (unattended, shadow mode only):**
1. Rows 3, 4, 5. Run DoD items 1–8, 10, 12 and 13 against the new scratch copy.
2. Row 6: the PC fully over SSH, with DoD 11 proven (timer wake and WoL separately, 08–16 window, 16:05 sleep with an empty queue, Mac fallback with the PC off).
3. Rows 15, 18, 19, 20 in shadow (specs to `shadow/`, writes to the scratch copy only).
4. Row 13 skeleton with the §0 yardstick.
5. `launchd` loaded, `mode = shadow`, `GO_LIVE` absent, one Telegram test message.

**Monday 26.10:** shadow day. The cloud coach still writes live. At 16:45, `shadow/2026-10-26.md` compares RadCoach with the cloud coach for every event, with latency and cost.

**Tuesday 27.10 evening:** Ajit reads the report. If it is clean, he writes „go live“, `GO_LIVE` is created, and he disables the two cloud coach tasks. The lessons task stays until row 18 has run live for one day.

**Week 27.–30.10:** rows 9, 10, 11, 12, then 13 live on Friday 30.10.

**Week 02.–06.11:** rows 14, 16, 17.

**Weeks 09.–20.11:** rows 21 and 22. The Dienst simulator must be usable by 01.12.

**From 23.11:** rows 23, 24, 25, then 26.

## 3. Non-negotiables (all phases)

- Shadow mode until „go live“.
- No patient identifiers anywhere: docs, files, logs, prompts, Telegram, audio, commits.
- Never delete or overwrite his text.
- Never write the chief's name.
- Account radioshahall only.
- Nothing inside the Hermes Docker sandbox; no daemon scanning the iCloud vault.
- Ask before anything paid.
- Ajit is never asked to run steps and report back: everything that needs a human goes into ONE list per phase.
- Every phase ends with a report in three sections: VERIFIED ON DEVICE / STATICALLY CHECKED / BLOCKED.
