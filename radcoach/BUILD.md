# RadCoach v4: build brief for Claude Code on the Mac Studio

Supersedes v2 and v3. Read the whole file before writing code. Build phase by phase, test each end to end yourself, and report VERIFIED / STATICALLY CHECKED / BLOCKED per phase. Collect everything that needs Ajit (OAuth consent, logins, dataset registrations, opt‑ins, paid items) into one list at the end of each phase. Ask before anything paid.

## Purpose
Ajit is a first‑month radiology resident. Goal: Dienst‑ready by December 2026, third‑year reporting level in 1–3 months. He trains by writing Befunde on real cases (screenshots from PACS in the Google Doc „My Radio findings“) and on archived cases that already have a signed report, and by having his real RIS drafts checked before he submits them. Seniors judge him on five things; every module below closes a loop on one of them with ground truth:
1. reports that need no edits, in house wording (pre‑sign check + chief‑edit loop + chief‑style fingerprint);
2. never missing the critical finding (don't‑miss engine + blind reads graded against signed reports);
3. the clinical question answered in one sentence, right side, right classification, next step (lint + fingerprint + corrections);
4. speed and gestalt (perceptual trainer, timed drills);
5. presenting a case and asking one sharp question (Befundbesprechung card, Oberarzt question).

Until 09.10.2026 a cloud Claude session polled the doc. Problems this build removes: an LLM polling a 700 KB doc and missing events; no local record, so no ground‑truth loop or statistics; no images in the doc; and a correction that said „Important miss“ for a fracture read from two screenshots. Verdict language is now rule‑bound (see Certainty).

## Bundle
- `reference/coach_prompt_v3.txt`: the complete coaching rules (docs and IDs, # protocol, when to correct, correction format: red strikethrough / yellow / green / bold, never italic; CT Schädel workflow; Start and End of Day; privacy). Becomes the Claude tier's CLAUDE.md; keep its substance.
- `reference/example_correction_spec.json`: a real correction in block format.
- `lib/build2.py`: block spec → Docs batchUpdate (UTF‑16 indexes, per‑tab ranges, styles, clears inherited italic/grey). Tested. Pitfall: `__` parses as grey, so placeholders use „…“.
- `lib/diffmrf.py`, `lib/caseck.py`, `lib/hashscan.py`, `lib/reanchor.py`: paragraph diff, pending‑case detection, open‑# detection, re‑anchoring.
- `reference/docimg_spec.md`: image push into Docs.

## Principles
- **Google Docs is the capture and reading surface, not the database.** It stays because Ajit can reach it from any hospital PC. The record of truth is local: `~/RadCoach/cases/<caseId>/` with `images/` (de‑identified only), `befund.md`, `correction.json`, `signed.md`, `draft.md` + `signed_by_chief.md` (for his own RIS reports), `grades.json`. Eval, retrieval, Anki, Mistake Log, audio and a later RadDesk UI all read from there.
- **Two ground truths.** (a) Archived signed reports for blind reads. (b) The chief's signed version of Ajit's own RIS drafts. (b) is the KPI that matters: chief‑edit rate.
- **Certainty is a rule.** Levels: `CONFIRMED` (signed report, or Ajit says he checked PACS) → „Missed: …“ / „Important miss“ allowed; `SCREENSHOT` (coach's own read) → „On the screenshot I see …; check on PACS before you sign.“; `NOT_ASSESSABLE` → „Not judged on the screenshot.“ The writer rejects any spec with „miss“ wording at level 2 or 3.
- **Local models never diagnose for teaching.** They do privacy OCR, lint, retrieval, card wording, dataset prep, and (after measurement) a private second opinion that can never raise certainty. Ajit's measurements show the 5090 models are weaker at tight German prose; nothing local writes Befund text.
- **The PC is the day‑time inference node.** Ajit's decision (10.10.2026): the 5090 PC stays awake Mon–Fri 08:00–16:00 and does the heavy local work. The Mac stays the orchestrator and record because Start of Day (07:53), End of Day (16:30), the 20:30 drill and the 06:30 audio delivery fall outside the PC window. Every PC call has a 2 s availability check and a Mac fallback (qwen3.5:9b), so a PC outage costs speed, never correctness.
- **Reuse what runs on the Studio.** Host launchd daemons (pattern: alertd, anki‑bridge). Not inside the Hermes sandbox. Telegram via alertd's sender or the Hermes bot.
- **The pipeline stays invisible.** Seniors see his reports and presentations, nothing else.

## Modules

### A. Core correction loop (Phase 1)
Tier 0 (Mac, Python, launchd, no model):
- **watcher**: documents.get on „My Radio findings“ every 15 s, other docs every 60 s; paragraph diff; events `HASH_LINE`, `CASE_DONE` (`#done`, or Befund with Beurteilung unchanged for 2 polls), `IMAGE_ADDED`, `SIGNED_REPORT`, `REF_REPORT`, `PRESIGN` (see B), `CHIEF_EDIT` (see C). System writes recognised by recorded revisionId and ignored.
- **queue**: SQLite, one event in flight per doc, retries with backoff.
- **writer**: build2 → batchUpdate with `requiredRevisionId` from a fresh read; on mismatch re‑read, re‑anchor by paragraph text, retry ≤5×; re‑read and verify placement, strike/yellow/green/bold runs, nothing italic. Enforces Certainty. Pushes images via docimg.
- **scheduler**: Start of Day 07:53, End of Day 16:30 (idempotent), Mon–Fri; Monday week preview; Friday quiz; evening jobs (see Daily rhythm).
- **health**: no successful poll for 5 min, two failed Claude runs, or a verify failure → Telegram. Keep the Mac awake 07:00–22:00 on weekdays.
Tier 1 (local, PC first inside its window, Mac fallback): privacy gate (fixed PACS header crop by default on the Mac before anything is sent anywhere, even to the PC; OCR with Tesseract on the Mac and a second OCR pass on the PC; any name‑like token, date‑of‑birth pattern or ID‑like number → block, one line in the doc asking to crop, log; originals never stored), side‑marker OCR, rule lint (Mac), model lint for German (PC: qwen3.6:27b via the RadCoach worker; fallback Studio Ollama qwen3.5:9b), retrieval embeddings (PC, index stored on the Mac), # triage.
Tier 2 (Claude, headless Claude Code on the Mac, event‑driven): compact case packet (Befund, de‑identified images plus auto‑crops of the region in the Fragestellung, Fragestellung, lint findings, marker, 5 retrieved house reports, his current top errors, signed report if present) → block spec JSON with `certainty` per finding, `errors[]`, optional `annotations[]` (arrows/labels on his slices), optional `anki[]`, optional `concepts[]`. Never the whole doc. Check first whether unattended use on the subscription is allowed and what the limits are; the API alternative is paid and needs Ajit's yes.

### B. Pre‑sign check (Phase 2, build first)
- Input: Ajit pastes a RIS draft (text only, no identifiers) under a line `#check` in the doc, or into a separate doc „Befund‑Check“ polled every 10 s.
- Pipeline: identifier scan (refuse if any) → rule lint → style lint against the fingerprint (D) → one short Claude pass (issues as a numbered list, then the corrected version in house wording with highlights).
- Target ≤30 s. Output goes directly under his line. This is the highest‑leverage module: the chief sees fewer edits from week one.

### C. Chief‑edit loop (Phase 2)
- Input: `#signed` followed by the chief's signed version of a report Ajit drafted (both de‑identified). The system pairs it with the draft from B.
- Output: sentence‑level diff into the doc (what was cut, reworded, added), classified errors into Ajit's ledger, phrases into the fingerprint corpus (D) tagged as the chief's.
- KPI: chief‑edit rate = reports with a substantive change / reports, weekly, by modality.

### D. Chief‑style fingerprint (Phase 2)
- Corpus: the chief's signed reports from the Textbausteine docs, CT Standard „Original“, and C. Colleagues' reports are kept but tagged separately.
- Per modality/region: paragraph order, fixed formulas, hedging vocabulary, what is always mentioned, what is omitted, Beurteilung structure, typical length.
- Used by A, B and C: retrieval of the closest chief sentence with its source report; phrase‑level style lint (flags non‑house wording and offers the house phrase).

### E. Don't‑miss engine and Dienst simulator (Phase 3)
- Per modality a fixed critical‑findings checklist (Rö Thorax, Rö Skelett, CCT, CT Thorax/LAE, CT Abdomen, Polytrauma, Wirbelsäule). Every case records which items Ajit declared (positive or negative); mastery per item = declared correctly in 5 consecutive relevant cases.
- Dienst simulator: timed mixed cases from his own de‑identified archive plus public datasets (F); 3 min per case; the „clinician call“ arrives as a Telegram voice message via Hermes and he answers in one sentence by voice; graded.
- Kritischer‑Befund drill: for every critical finding the correct call‑and‑document sentence.

### F. Perceptual trainer (Phase 3)
- Public labelled datasets, downloaded by Ajit after checking each licence (most allow personal study; Radiopaedia forbids scraping, so link only, never bulk download): MURA (Stanford, registration), RSNA Intracranial Hemorrhage Detection (Kaggle), CQ500 (CC BY‑NC‑SA), RSNA Pneumonia Detection (Kaggle), NIH ChestX‑ray14 (labels are text‑mined, noisy), VinDr‑CXR and VinDr‑SpineXR (PhysioNet, credentialed, radiologist boxes), FracAtlas (CC BY 4.0), RSNA Cervical Spine Fracture, RSNA Abdominal Trauma, RSNA STR Pulmonary Embolism (Kaggle), LIDC‑IDRI (TCIA), MedPix (NLM). Verify licences at download time; my list is from training data and may be outdated.
- The PC converts DICOM → windowed PNG (pydicom; presets per region) in batch at 15:15 and copies the evening's drill batch to the Mac before it sleeps; the Mac runs the 20:30 drill from that batch.
- Drill: image, 20 s timer, answer normal/abnormal + region (tap or key), instant grading, adaptive difficulty, 10 min per evening; tracks sensitivity and specificity per modality over time. The perceptual‑learning‑module literature (Kellman and colleagues, UCLA) is the model.

### G. Commute audio (Phase 2–3)
- Each evening: a 45–90 min lesson script from yesterday's errors + today's topic + concept explainers (Radiopaedia as linked source, not scraped), English narration with German terms, a question every ~10 min with the answer after a pause. TTS on the PC (Kokoro or Piper on the GPU) at 15:00 inside the PC window, so the file is ready long before 06:30; the Mac renders a short addendum (≤5 min, Piper CPU) for errors logged after 16:00; cloud TTS only with Ajit's yes. Delivered to his phone (Telegram file or a Drive folder his car app can play).

### H. Concept pipeline (Phase 2)
- Every `#what is X` → doc answer with an open‑licence image where one fits (insertInlineImage by URL; Wikimedia verified) → a de‑identified concept note in the vault (`06- Full Notes/`, his 1‑3‑5‑7 loop enrols it) → Anki cards via the existing bridge.

### I. Befundbesprechung card (Phase 2)
- Each evening the day's best teaching case → a 60‑second presentation card: finding, DDx, next step, one pearl, one question for the Oberarzt. Written into the doc under End of Day and sent to Telegram.

### J. Local second reader on the PC (Phase 2 for logging, Phase 3 for use)
- MedGemma 27B or qwen3.6:27b vision on the PC reads the de‑identified images of every case **in parallel** with Claude, images + Fragestellung only, structured output: per critical finding yes/no/uncertain with a short reason.
- Independence rule: its result is shown to Claude only in a second stage, after Claude's own read is complete, and only as „another reader disagrees on X, re‑check“. Claude is never anchored on it.
- Phase 2: the PC read is logged and graded against signed reports (coach ledger, by finding type) but changes nothing user‑visible. Phase 3: once its measured precision on the gold set is known, disagreements are surfaced in the correction as „a second reader saw …“ at SCREENSHOT level. It never raises certainty. A paid cloud second opinion from another vendor only with Ajit's yes.

### K. Anatomy tutor on the PC (Phase 4)
- 3D Slicer + TotalSegmentator on the PC (GPU, batch inside the window) on public CT volumes (TCIA) → labelled slices → „name the structure“ drills and labelled answers to „show me the …“ questions. Scope what TotalSegmentator actually labels (organs, bones, vessels, several head/neck subtasks) and do not promise structures it cannot segment.

### L. RadDesk (Phase 4)
- Public web UI (requirement: reachable from any PC in the world, so Cloudflare Tunnel + Access or a small VPS, not tailnet‑only), reading `~/RadCoach/cases/`: case review with highlights and annotated images, ledgers, KPI dashboard, perceptual drill, AMBOSS‑style topic pages as he specified. Eventually replaces Docs for capture and review; Docs keeps working in parallel.

### M. Weekly report (Phase 2)
- Written into the doc each Friday and sent to Telegram: chief‑edit rate; blind‑read accuracy vs signed reports by category; side errors; time per report; don't‑miss mastery; perceptual sensitivity/specificity; the coach's own accuracy („right in X of Y contradicted findings“).

## Model routing and invocation (decided 10.10.2026, „no compromise“; prices verified against the Anthropic docs that day)
List prices per million tokens from the models overview: Fable 5.1 $10 in / $50 out (slower; „when your evals on Opus 5.5 at higher effort still fall short“), Opus 5.5 $4 / $20 (recommended starting point), Sonnet 5.5 $2 / $10 (fast), Haiku 5.5 from $0.10 / $0.50 (classification, extraction, routing). All four accept images.
- **Every image read** (module A corrections, # lines with images, Dienst simulator grading): `claude-fable-5-1` at high effort, blind first (images + Fragestellung + lint facts), then the full packet. Reason: the cost of a wrong read is a wrong lesson; this is where the strongest model belongs. Fable carries extra biology safety layers; radiology reads should not trip them, but verify in the eval and fall back to Opus 5.5 at high effort if they do.
- **Every text that reaches the chief or persists** (pre‑sign check B, concept notes, Anki cards, audio scripts, presentation cards, finding extraction and grading from signed reports): `claude-opus-5-5`. Reason: a wrong fact drilled for months is the worst failure, and a wrongly graded finding corrupts the ledger; the price difference on text is cents. Latency for B is met by keeping the pass short (issues list + corrected text, no essay).
- **Routing only** (# line triage, event classification): `claude-haiku-5-5`.
- **Local models**: privacy OCR, side‑marker OCR, German lint pre‑pass, retrieval embeddings, the PC second reader (J). Nothing else.
- **Second opinion**: never another Claude run. The PC reader (J) always; in addition a different vendor's frontier vision model on the de‑identified images for contradicted critical findings, if Ajit says yes (paid; the images leave the house de‑identified; it never raises certainty).
- **Style fidelity, no retrieval shortcut**: with the 1M context, load the complete chief corpus (fingerprint D, all signed chief reports, the Stil‑Datenbank) into the pre‑sign and correction prompts with prompt caching, and use retrieval only to point at the closest sentences. Measure the cache hit rate; the corpus is rewritten at most once a day so caching holds.
- **Building RadCoach itself**: Opus 5.5 in Claude Code; Fable for design or debugging steps that fail twice.
- **Weekly eval**: rerun the gold set; report finding‑level accuracy and cost per case per model. Downgrade a role (Fable → Opus, Opus → Sonnet) only when the gold set shows no measurable loss over two consecutive weeks.

Invocation (from the headless docs): `claude -p` with `--output-format json --json-schema <spec schema>` so the block spec returns as validated JSON in `structured_output`; `--permission-prompts none` for unattended runs; `--allowedTools "Read"` only; `--append-system-prompt-file` with the coaching rules; `/model` and `/effort` accepted as arguments in `-p`. Do **not** use `--bare`: it never reads the subscription login and would need an API key. The JSON result carries `total_cost_usd` and a per‑model breakdown: log it per case.

Billing (verified 10.10.2026 against the Anthropic support articles): Ajit is on **Claude Max 20x (€200/month)**. Usage limits apply across claude.ai and Claude Code, reset every five hours, and there are weekly limits, with a separate weekly limit for Fable. Opus uses meaningfully more of the quota than Sonnet, and Fable more again. **Usage credits** can be enabled on Max: once the included limits are used up, requests switch to pay‑as‑you‑go at standard API rates and keep working, with a monthly spend cap and alerts. So:
- The whole system runs on the subscription via plain `-p`. No API key.
- **Fable pacing**: escalation cases (contradicted critical finding, PC reader disagrees, low certainty, `#hard`) always go to Fable. Routine image reads go to Fable until the day's share of the weekly Fable allowance is used, then to Opus 5.5 at high effort. The daily share is set from the shadow‑day measurement (watch Settings → Usage) and adjusted weekly. The daemon detects limit errors in the stream (`api_retry` with `error: rate_limit`) and falls back Fable → Opus → Sonnet for the rest of that five‑hour window instead of stopping; every fallback is logged and shown in the Friday report.
- **Ajit's own interactive use** (chat, Claude Code sessions) draws on the same windows; the daemon must never leave him without quota during work hours, so it stops starting new Fable runs when the five‑hour window is above 80 % and lets Opus carry the rest.
- **Overflow decision for Ajit**: enabling usage credits with a monthly cap (for example €50) means nothing ever stops and every read can stay on Fable; without it, reads degrade to Opus when limits bind. Paid, so his call, with the shadow‑day numbers in hand. List‑price reference if credits are used: about $0.60–0.70 per Fable image case, about $0.08 per Opus pre‑sign check.

## Ground truth and ledgers
- On `SIGNED_REPORT` and `CHIEF_EDIT`: extract findings from the signed text, Ajit's read and the coach's read; grade hit / miss / false positive; write `grades.json`.
- **Ajit's ledger**: one row per error (date, case, category: side, Kopfzeile, question not answered, missed finding, false positive, implant naming, comparison missing, measurement, grammar; severity; confirmed?). Drives End‑of‑Day top 3, Monday weak‑spot drill, the Oberarzt question, lint emphasis, audio topics, the perceptual trainer's weighting.
- **Coach's ledger**: precision/recall of SCREENSHOT‑level claims against signed reports by finding type; reported in M.
- **Vault**: confirmed errors appended, de‑identified, to `06- Full Notes/_Mistake Log.md` (day‑5 gap‑fill reads it). Never scan the iCloud vault from a daemon loop; write through local disk as the existing bridge does.
- **Anki**: card files into `~/.srs/anki/outbox` in the format `~/.local/bin/anki-bridge.py` expects (read it first); deck `Radiology::Befund`; fronts as questions, backs with German terms. No AnkiConnect.

## PC schedule and worker (Phase 1, done from the Mac over the existing tailnet SSH with key auth)
- **Window**: awake Mon–Fri 08:00–16:00. 07:55 wake by a Task Scheduler task with „Wake the computer to run this task“ (wake timers allowed via powercfg) **and** a Wake‑on‑LAN magic packet from the Mac to the PC's MAC 10‑FF‑E0‑B4‑C3‑46 at 07:55 as backup. 16:05 (or 16:35 if Ajit wants the second reader through End of Day): the worker drains its queue, then the PC **sleeps** (never shuts down; WoL from a fast‑startup shutdown is unreliable).
- **Keep‑awake**: the worker holds a continuous system power request (SetThreadExecutionState ES_SYSTEM_REQUIRED) while the window is open; standby timeout set to never inside the window and restored at 16:05.
- **Services**: Ollama, the existing gateway (port 11436) and the new RadCoach worker run as Windows services (NSSM or Task Scheduler „run whether user is logged on or not“) so they come up after any reboot with the screen locked; no auto‑login. Firewall rules scoped to LAN + tailnet (100.64.0.0/10). GPU stays on the persistent 450 W cap.
- **Worker API** (http://192.168.188.184:8790, LAN + tailnet only, token in header): `/health`, `/ocr`, `/marker`, `/lint`, `/embed`, `/read` (vision second reader), `/tts`, `/dicom-prep`, `/segment`. The Mac checks `/health` with a 2 s timeout before every call and falls back to its own models on failure; batch jobs are queued on the Mac and dispatched only while the PC reports healthy.
- **Order inside the window**: live requests first (OCR, marker, lint, read), batch jobs 14:00–15:45 (TTS for tomorrow, drill batch, DICOM conversion, segmentation), so everything is finished before sleep.
- **Energy**: about 1 kWh per working day (idle plus bursts), roughly €10 a month; mention it once to Ajit, no more.
- **Health**: the Mac alerts via Telegram if the PC is not healthy by 08:10 on a weekday.

## Images (docimg)
As in `reference/docimg_spec.md`. The image must be publicly fetchable for the seconds Google needs: Drive file with a temporary `anyone/reader` permission, or a Tailscale Funnel path with a one‑time token. Revoke right after the insert is verified; Docs keeps its own copy. Only de‑identified images ever leave the Mac.

## Daily rhythm (scheduler)
- 06:30 commute audio ready (G; rendered on the PC the previous afternoon). 07:55 PC wakes. 07:53 Start of Day. Work hours: pre‑sign checks (B) within 30 s, case corrections (A) within 3 min, # answers within 90 s. 16:30 End of Day + Befundbesprechung card (I). 20:30 his existing 1‑3‑5‑7 session, then a 10‑min perceptual drill (F). Friday 16:30 timed quiz + weekly report (M). Monday 07:53 week preview + weak‑spot drill.

## KPIs (targets, not promises)
- Chief‑edit rate falling week over week; aim: under 20 % substantive edits by the end of month 2.
- Side errors: 0 after week 2.
- Blind‑read accuracy vs signed reports by category, trending up; don't‑miss items mastered before Dienst.
- Time per routine report trending down; perceptual sensitivity/specificity trending up.

## Privacy and conduct rules (from the prompt, do not weaken)
- No patient identifiers (name, date of birth, patient ID, accession, exam date) in any doc, file, log, prompt, upload or audio; age only as a decade.
- Never write the chief's name in the docs.
- Never delete or overwrite Ajit's text; only add and mark.
- Answer every # line in the same doc, directly below his line, starting with bold „Answer:“.
- Chat language English. In the docs: explanations in English; Befund text, Textbausteine and medical terms in German.

## Phasing
- **Phase 1 (weekend 10–11.10.)**: module A, case folders, privacy gate, Certainty, eval export, docimg, the PC schedule and worker (health, ocr, marker, lint, embed, read for logging only). One shadow day (specs to `~/RadCoach/shadow/`, nothing written to the docs; compare with the cloud coach). The cloud scheduled tasks „Radiology live coaching (morning)“ and „(afternoon)“ keep running until shadow passes; Ajit disables them at go‑live.
- **Phase 2 (from 12.10.)**: B first, then C, D, H, I, M, G, ledgers, vault and Anki integration.
- **Phase 3 (from 19.10.)**: E, F, J.
- **Phase 4 (November)**: K, L.
- Start a new findings doc each month; the local record keeps everything.

## Go‑live checklist (Phase 1)
1. # line → answer in the doc within 90 s.
2. `#done` → full‑format correction within 3 min, verified by re‑reading.
3. Typing in the doc during a write → re‑anchored, nothing misplaced.
4. A test image with a fake name in the header is cropped or blocked; nothing leaves the Mac.
5. A wrong side in a test Befund is caught by lint and appears in the correction.
6. A spec with „Important miss“ at SCREENSHOT level is rejected by the writer.
7. A pasted signed report produces `grades.json` and ledger rows for Ajit and for the coach.
8. An image push lands and its public access is revoked.
9. Killing the watcher triggers the Telegram alert.
10. End of Day is written once at 16:30; a card file appears in the Anki outbox and reaches AnkiMobile after sync.
11. The PC wakes at 07:55 (verify both the timer and the WoL path separately), reports healthy by 08:00, stays awake under load, and sleeps at 16:05 with an empty queue; with the PC unplugged from the network, a case correction still completes via the Mac fallback.
12. The PC's parallel read is logged for a test case and does not appear in Claude's packet before Claude's own read is complete.

## Acceptance for Phase 2
- `#check` with a draft → numbered issues and corrected house‑wording version within 30 s.
- `#signed` → diff in the doc, ledger rows, fingerprint corpus updated, chief‑edit rate in the Friday report.
- `#what is X` → answer with image in the doc, concept note in the vault, Anki card queued.
