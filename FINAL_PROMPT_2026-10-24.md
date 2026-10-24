# Final build prompt: RadCoach + RadDesk + the 5090 node (24.10.2026)

Work on this Mac Studio, unattended. Ajit is not available to answer questions. Everything that needs him goes into ONE list at the end.

Before touching anything, read:
- `~/RadCoach-spec` (`git pull origin radcoach`), in this order: MASTER_PLAN.md, UPDATE_2026-10-19.md, PROMPT.md, COACH_PROMPT_v6_live.md.
- `~/raddesk/`: CLAUDE.md, CONTRACTS.md, DECISIONS.md, BACKLOG.md, README.md.

Where documents differ, this file wins.

## 0. Verified state tonight (24.10.2026, 23:00)

**RadCoach** (`~/RadCoach`):
- Phase 1 was built on 10.10 (82 tests) and has never run live.
- Google OAuth was finished tonight as radioshahall@gmail.com: `secrets/google_client.json` and `secrets/google_token.json`, scopes documents + drive, `config/radcoach.toml` account switched.
- Verified tonight: Drive search finds the week docs, and all live/reference docs open.
- The old scratch doc `1ypU4…` is NOT accessible.
- launchd jobs are not loaded.
- `~/.alertd` does not exist. Use `secrets/telegram.json`.
- The OAuth app is in Testing: the refresh token dies after 7 days unless Ajit publishes it (on his list).

**RadDesk** (`~/raddesk`):
- Running: `com.ajit.raddesk` on 127.0.0.1:8586, Funnel public at https://mac-studio-1.tailb2be37.ts.net.
- Last commit 10.10.
- **Its Google-Docs import has been dead since 10.10.** It depends on a Claude-desktop scheduled task („RadDesk: Google Docs → RadDesk“, daily 22:00, Drive connector) that stopped. `~/Desktop/Radiology/gdocs-inbox.nosync/imported.tsv` shows the last imports on 10.10.
- `gdocs.yaml` knows only 5 docs.
- Nothing develops it any more.

**PC** (RTX 5090, Windows 11 Home):
- 192.168.188.184, MAC 10-FF-E0-B4-C3-46.
- SSH key auth over the tailnet; Ollama gateway :11436 (`qwen3.6:27b`, `ajit-general:35b`, both vision; `ajit-medgemma` exists).
- `~/RadCoach/pcworker/{app.py,setup.ps1,window.ps1}` were written on 10.10 and never deployed.
- winget is broken, so download installers directly.
- Never name a PowerShell parameter `$args`.

**Cloud tasks still live (do NOT disable them):**
- „Radiology live coaching (morning)“ and „(afternoon)“, which correct his cases in the week doc.
- „Radiology lessons + Randomthots (every 2 h)“.

## 1. Goal (what all of this serves)

Ajit started radiology on 01.10.2026 as a complete beginner. Targets:
- Dienst-ready by December 2026.
- Röntgen + emergency CT reporting at 4th-year-resident level by about August 2027.

Daily volume:
- Until 31.12: 30 Röntgen + 6 CT reports per working day.
- From January: 40 Röntgen + 12 CT.
- 10 per day go through the coach.

The system measures, per week:
- the major-miss rate against signed reports (target < 5 % Röntgen, < 10 % emergency CT)
- the chief-edit rate
- volume per day

Three parts carry this:
- **RadCoach** corrects and measures.
- **RadDesk** is where everything he learns accumulates, is arranged and is drilled, and it keeps improving itself.
- **The 5090 PC** does the heavy local work on weekdays from 08:00 to 16:00.

## 2. Part A: RadCoach to shadow-ready (tonight)

Do MASTER_PLAN.md §2 „Tonight and Sunday 25.10“ completely:

1. Tests green.
2. Implement UPDATE_2026-10-19 with tests:
   - weekly doc discovery
   - correction order
   - single-writer lock per case
   - insert only at paragraph start
   - requiredRevisionId → targetRevisionId ladder
   - strip the patient line from his Befund + Privacy line
3. Create a new scratch copy of the week doc, owned by radioshahall.
4. Run DoD items 1–8, 10, 12 and 13 against it.
5. Port the cloud-only jobs in shadow (specs to `shadow/`, writes to the scratch copy only):
   - the day block and accelerators
   - End of Day with the Anki lines
   - Textbausteine / CT Standard / Stil-Datenbank sorting
   - the daily-lessons + randomthots module
6. Weekly report skeleton (Friday 16:30) with the §1 yardstick.
7. Set `mode = shadow`; `GO_LIVE` absent. Prove the writer refuses live IDs.
8. Load launchd, send ONE Telegram test message.

## 3. Part B: the 5090 node (tonight, over SSH, fully; not „mark BLOCKED“)

Spec: PROMPT.md §7.

1. **Reachability:** SSH; Wake-on-LAN from the Mac if it is asleep. Test WoL.
2. **Services** that survive a reboot with the screen locked (NSSM or Task Scheduler „run whether user is logged on or not“; no auto-login):
   - Ollama
   - the gateway :11436
   - the RadCoach worker :8790, FastAPI, with a bearer token kept in the Mac's `secrets/`
   - Firewall: LAN + 100.64.0.0/10 only.
3. **Worker endpoints**, each tested from the Mac with de-identified input:
   - /health, /ocr, /marker, /lint, /embed
   - /read: the vision second reader. Logged only; it never enters Claude's packet before Claude's own read.
   - /tts: Kokoro or Piper on the GPU
   - /dicom-prep, /segment
4. **Window Mon–Fri:**
   - 07:55 wake by a Task Scheduler wake timer (enable wake timers via powercfg), plus a WoL packet from the Mac as backup.
   - Awake until 16:00: ES_SYSTEM_REQUIRED|ES_CONTINUOUS, standby set to never.
   - 16:05: drain the queue, restore standby, then SLEEP (never shut down).
   - Batch jobs 14:00–15:45.
   - Persistent 450 W GPU cap.
5. **Mac side:**
   - /health with a 2 s timeout before every call.
   - Fallback to the Studio's Ollama (`qwen3.5:9b`, `qwen3-vl:8b`) and `~/.local/bin/visionocr`.
   - Telegram alert if the PC is not healthy by 08:10 on a weekday.
   - RadDesk uses the PC by the same rule (2 s health check, never wakes it itself; RadCoach owns the schedule).
6. **Prove DoD item 11:**
   - timer wake and WoL tested separately
   - healthy within 5 min of waking
   - awake under a 10-min load
   - 16:05 sleep with an empty queue (simulate the time)
   - with the PC off the network, a correction on the scratch doc still completes through the Mac
7. Mention the energy cost (about 1 kWh per working day) once in the report.

## 4. Part C: RadDesk revived, auto-update, auto-arrangement, auto-dev

### C1. Revive (first)
- Check the service, a login through the public Funnel URL, `raddesk selftest`, pytest and Playwright E2E.
- Fix whatever is red.
- Find out exactly why the import stopped and write it into DECISIONS.md.

### C2. Auto-update: RadDesk fills itself, no desktop task any more

**Sync job:**
- New launchd job `com.ajit.raddesk-sync`, every 15 min from 07:00 to 23:00, plus one run at 06:00.
- Uses the radioshahall OAuth token. Give RadDesk its own copy in `~/raddesk/secrets/` (mode 600) or read RadCoach's read-only; decide and record it.
- Exports changed docs into the drop folder.
- Detect change by revisionId + content hash, never by Drive `modifiedTime` alone (it lags).
- The existing import (skip tabs, PHI filter, accuracy gate, „KI-Text is never a Beleg“) stays exactly as it is.

**Doc list is discovered, not hard-coded:**
- all „Befunde * week“ docs (newest first, plus every older week once)
- „My Radio findings“
- the three Textbausteine docs
- „CT Standard“ (Sortiert tab only)
- „CT Schädel in house textform“ (Sortiert only)
- „CT Becken-Bein Textbausteine“
- „CT Angio Carotis Schädel Textbausteine“ (created on 20.10 by the cloud coach; if not visible to radioshahall, put it on Ajit's list)
- „Radiology daily lessons“
- „randomthots“: only the Answer: paragraphs that are radiology lessons, never his personal notes

Raw „Original“ tabs, Trainingsplan and Stil-Datenbank stay skipped as before.

**RadCoach → RadDesk feed:**
- From `~/RadCoach/cases/` (already de-identified): every correction, signed report, grade and ledger row.
- These become case-review pages, mistake-log lines and links on the matching topic pages.
- One-way contract, documented in CONTRACTS.md: RadDesk never writes into `~/RadCoach`.

**Backfill:** import everything from 10.10 to now once, idempotently.

**Health:**
- No successful sync for 2 h inside 07–23 → Telegram alert.
- RadDesk down, or the Funnel URL not answering from outside → restart once, then alert.
- Ajit's list: delete the old desktop scheduled task.

### C3. Auto-arrangement: RadDesk sorts itself

- **Classify** every imported unit into the existing `taxonomy.yaml`, mapped to the WBO: a Baustein sentence, a lesson, a correction's Merke, a signed-report sentence, an End-of-Day Anki line, a case. Classify by modality → region → Krankheitsbild / Fragestellung. Use rules first, the local model second.
- **Merge into the existing topic page;** never create a duplicate. Use embedding similarity with a threshold you measure and record.
- **New topics** get a page in the fixed AMBOSS section order, badged „KI-Text, ungeprüft“ until he marks it reviewed.
- **Bausteine pages** are grouped by Krankheitsbild, like the docs' „Nach Krankheitsbild“ tabs, and each group gets its Normalbefund and pathological template.
- **Case reviews** are linked from their topic.
- **Low-confidence classifications** go to an „Einordnen“ queue: one tap to confirm or re-file. Show the count on the home page.
- **The coverage map** (WBO tree with empty nodes visible) and the „Today“ page update automatically. The „Today“ page shows: due cards, today's cases and corrections, today's lessons, the weak-spot drill.
- **Never rewrite his own notes.** Every move is logged and reversible (Undo).
- **One owner per output, no duplicates:** RadDesk's `anki_auto` already turns lesson tables and Merke into cards. Make it also own the End-of-Day Anki lines, and stop RadCoach from writing those cards itself. Record this in DECISIONS.md.

### C4. Auto-dev: RadDesk keeps developing itself every night

**Job:** launchd `com.ajit.raddesk-autodev`, nightly at 01:00.

**Inputs, in this order:**
1. Red tests or errors from the day's logs.
2. Ajit's feedback:
   - a „Feedback“ box on every RadDesk page, stored in `.raddesk/feedback.jsonl`
   - any line in „randomthots“ or the week doc starting with `#raddesk`
3. Gaps named in RadCoach's weekly report.
4. BACKLOG.md, top down. Already queued there:
   - Phase 2: caption_suggest, highlighter, mistake_log, anki_from_topic
   - Phase 3: audio_lessons (see C5) and video_transcripts

**Run:**
- Headless Claude Code (`claude -p`, subscription login, never `--bare`, no API key).
- Working directory: a git worktree on branch `auto/<date>`.
- Allowed tools limited to Read, Edit, Write, Glob, Grep and Bash restricted to the repo, its venv and its tests.
- At most 2 items per night.
- Stop if the Claude 5-hour window is above 60 % used, so Ajit's day keeps its quota.

**Gate:**
- Merge to main and restart the service only if pytest + `raddesk selftest` + Playwright E2E pass AND a post-restart health check (local and through Funnel) passes.
- Otherwise: no merge, keep the branch, revert to the last good build.

**Hard limits for auto-dev:**
- Never touches vault note bodies, secrets, live Google Docs, other launchd jobs, Hermes, Docbox (8484) or Bottega (8585).
- Never installs anything paid.
- Never weakens the PHI filter or the accuracy gate. Any diff touching `phi.py`, `ocrguard.py`, `factcheck.py` or `verify.py` is held for Ajit's review instead of merged.

**Morning Telegram at 06:30:** „Built last night: … / Held for you: … / Failed: …“, plus a CHANGELOG.md entry.

**Pause:** a toggle in RadDesk settings, or the file `~/raddesk/AUTODEV_PAUSED`.

Apply the same nightly loop to `~/RadCoach`, with the same gates, and only after go-live (until then RadCoach changes are made by hand). RadCoach's writer, certainty rule and privacy gate are always held for review, never auto-merged.

### C5. Shared pieces (one implementation each)

**Commute audio:**
- Build RadDesk's `audio_lessons` and feed it from RadCoach.
- Content: the day's errors and the next topic, plus due notes.
- English narration with German terms; a recall question about every 10 min, then a pause, then the answer.
- TTS on the PC during 14:00–15:45, on the Mac otherwise.
- Private podcast RSS with a secret token in the URL; „today's 90 minutes“ ready by 06:30.
- Radiopaedia is used for topic choice only, never scraped.

**KPI dashboard page in RadDesk:** the §1 yardstick, read from RadCoach's ledgers.

## 5. Order and timing

**Tonight → Sunday 25.10:** A, B, C1, C2 (with backfill), C3, C4 (install and run one supervised night by hand first, then arm the schedule).

**Monday 26.10:** shadow day.
- The cloud coach still writes live.
- RadCoach writes to the scratch copy and `shadow/`.
- RadDesk syncs live (read-only on the docs).
- 16:45: `~/RadCoach/shadow/2026-10-26.md` compares RadCoach with the cloud coach per event, with latency and cost.

**Tuesday 27.10:** Ajit decides „go live“.

**Afterwards:** MASTER_PLAN.md §2 dates for Phase 2–4. The Dienst simulator must be usable by 01.12.

## 6. Non-negotiables

- No writes to live docs until GO_LIVE.
- No patient identifiers in any file, log, prompt, commit, Telegram message or audio.
- Never delete or overwrite his text.
- Never write the chief's name.
- Account radioshahall only; never Ajit's private account.
- Nothing in the Hermes Docker sandbox; no daemon scanning the iCloud vault on a hot path. Walks run in a thread with a timeout.
- Ask before anything paid.
- Never ask Ajit to run steps and report back.

## 7. Final report

Write `~/RadCoach/REPORT_2026-10-25.md` and `~/raddesk/REPORT_2026-10-25.md`. Each has three sections:
- VERIFIED ON DEVICE: you ran it and saw the result from the other side.
- STATICALLY CHECKED
- BLOCKED

Then ONE list for Ajit. It is expected to contain at least:
- publish the OAuth app (Branding page)
- delete the old desktop sync task
- delete his duplicate „Befunde Third week“ doc
- anything at the PC that truly needs hands

Send a Telegram summary (no identifiers).
