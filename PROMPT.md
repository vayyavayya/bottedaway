# FachCoach: build prompt for Claude Code on the Mac Studio

You are building FachCoach on this Mac Studio: an oral‑exam coach for Cashmy, a gynaecologist preparing for the Facharztprüfung Frauenheilkunde und Geburtshilfe at the Bezirksärztekammer Nordwürttemberg. Read this whole file before you touch anything. RadCoach (`~/RadCoach`, spec in `~/RadCoach-spec/PROMPT.md`) already exists on this Mac; reuse its library code where this file says so, and keep FachCoach's state, secrets and daemons completely separate.

## 0. How to work on this
- **Who it is for:** Cashmy Joy, 36, completes her 60 months of Weiterbildung on 31.10.2026; the oral exam will be scheduled by the Kammer after the logbook is signed, expected late January to March 2027. She works in a Praxis Mon 11:00–19:30, Tue 08:00–12:00, Wed 08:00–15:30, Fri 08:00–17:30; Thursday is free; three children at home; Urlaub 21.12.2026–10.01.2027 is her intensive block. Realistic study time: about 12 hours a week. She reads textbooks as PDFs in Notability on the iPad and highlights with the Apple Pencil, and she reads AMBOSS.
- **Who commissions it:** Ajit, her husband, who runs this Mac. Talk to him in English. Talk to her, through the bot and the doc, in **German** (the exam language), unless she writes to the bot in English.
- **You do the work.** Build and test everything end to end yourself. Collect everything that needs a human (logins, consent clicks, bot token creation, anything paid) into one list per phase. Ask Ajit before anything paid. Report per phase in three sections: **VERIFIED ON DEVICE / STATICALLY CHECKED / BLOCKED**.
- **Dates** as calendar dates, never calendar‑week numbers.

## 1. Non‑negotiable rules
1. **No patient identifiers anywhere.** She will mention cases from her Praxis and her Logbuch. The privacy gate (reuse `~/RadCoach/radcoach/privacy.py` or its equivalent) runs on every text and image before storage or any model call: name, date of birth, patient ID, exact dates of care → refuse and ask her to rephrase. Age only as a decade.
2. **Her own words are the gold.** Questions, cards and summaries are built from her highlights, her handwritten margin notes and her own takeaways. The model may explain and grade; it never invents a "fact" into her card deck without a guideline citation.
3. **Guidelines are the ground truth.** Grading of her answers cites the guideline and section (AWMF/DGGG S2k/S3 Leitlinien, G‑BA Mutterschafts‑Richtlinien, Krebsfrüherkennungs‑Richtlinie, STIKO where relevant). A grade without a citation is not a grade.
4. **AMBOSS is never automated.** No scraping, no login automation. She reads AMBOSS herself and sends takeaways by message.
5. **Textbooks stay private.** Highlight extraction is for her personal study only; store extracted snippets, never whole pages or chapters; never upload the PDFs anywhere.
6. **Nothing runs in the Hermes Docker sandbox, nothing scans iCloud from a daemon loop.** Host launchd daemons, like RadCoach.
7. **Separate from RadCoach:** own folder `~/FachCoach`, own SQLite, own secrets (mode 600), own launchd labels `com.ajit.fachcoach-*`, own Telegram bot. Import RadCoach modules as a library; never modify RadCoach files.
8. **Model budget:** this runs on Ajit's Claude Max 20x subscription alongside RadCoach. FachCoach uses `claude-opus-5-5` for grading, question generation and summaries, `claude-haiku-5-5` for classification and routing, and never Fable. Use `claude -p` with `--output-format json --json-schema`, `--permission-prompts none`, no `--bare` (reuse RadCoach's runner, `~/RadCoach/radcoach/claude_runner.py` or equivalent, including its cost logging and rate‑limit fallback). Keep FachCoach's share small: batch question generation once a day at 15:00 inside the PC window, grade on demand.

## 2. Her surfaces
- **Telegram bot** (default; Ajit creates the bot with @BotFather and gives you the token; she installs Telegram): the daily drill, voice mock exams, `#` messages (takeaways, questions, "pause", "mehr Geburtshilfe"), weekly report. Voice in both directions. Optional later: the same flows through the existing Hermes WhatsApp profile `cashmy`, only as a delivery channel.
- **Google Doc „Cashmy – Facharztprüfung“** (create it in Ajit's Drive, share with her as editor): the study plan, the topic map with her mastery per topic, weekly reports, and her concept notes. Write it with RadCoach's Docs writer module (OAuth token in FachCoach's own secrets, same Google client); reuse its revision‑guard and verify‑by‑re‑read logic.
- **Notability backups** in Google Drive: she enables Notability → Auto‑backup → Google Drive, PDF. The folder is the input of the highlight pipeline.

## 3. Architecture
### Tier 0: Mac, Python, launchd, no model
- **Drive watcher** (every 10 min): lists the Notability backup folder through the Drive API (`drive.readonly` scope on FachCoach's own token), downloads new or changed PDFs to `~/FachCoach/inbox/` (local disk, never iCloud), records file id, md5 and modified time in SQLite.
- **Highlight extractor**: for each changed PDF, render pages at 150 dpi (PyMuPDF), detect highlighter colour masks (Notability's translucent yellow, pink, green, blue, orange; HSV thresholds, morphological closing, connected components → bounding boxes), extract the text under each box from the PDF text layer (`page.get_text("words")`, clipped), and OCR the box with Apple Vision (pyobjc) when there is no text layer. Handwritten margin notes (Pencil ink that is not highlighter colour): OCR with Apple Vision handwriting recognition and store as her notes. Only changed pages are reprocessed (page image hash). Output: `knowledge units` (book, chapter if detectable, page, highlight text, her note, colour, timestamp) in SQLite.
- **Queue, scheduler, health, alerts**: as in RadCoach (reuse). Health alert to Ajit's alertd Telegram if the Drive watcher or the bot is down for 15 min.
- **Record**: `~/FachCoach/{inbox, units, questions, sessions, ledger, reports}`; everything de‑identified.

### Tier 1: local, deterministic first
- Privacy gate on all incoming text, voice transcripts and images.
- **Guideline corpus**: download the current AWMF guideline PDFs for Gynäkologie und Geburtshilfe (register 015‑xxx), the Mutterschafts‑Richtlinien and the Krebsfrüherkennungs‑Richtlinie into `~/FachCoach/guidelines/` (public documents; record version and date), split into sections, build a local embedding index (PC `/embed` when awake, else Studio Ollama). Refresh monthly.
- **Topic map** (the Prüfungskatalog, stored as data so Ajit or she can edit it): Geburtshilfe‑Notfälle (Schulterdystokie, postpartale Blutung, Präeklampsie/Eklampsie/HELLP, vorzeitiger Blasensprung, Frühgeburt und Lungenreife, CTG‑Beurteilung, Beckenendlage, Sectio‑Indikationen, Uterusruptur), Schwangerenvorsorge und Pränataldiagnostik (Mutterschafts‑Richtlinien, Ersttrimester‑Screening, Gestationsdiabetes, Rhesus, Infektionen in der Schwangerschaft), Gynäkologische Onkologie (Mamma, Zervix, Endometrium, Ovar, Vulva: Früherkennung, Staging, leitliniengerechte Therapie, Nachsorge), Endokrinologie und Reproduktion (Zyklusstörungen, PCOS, Amenorrhoe, Kinderwunsch, Kontrazeption, Klimakterium/HRT), Urogynäkologie (Inkontinenz, Deszensus), Infektionen und Sexualmedizin (STI, HPV, Vaginose, Impfungen), Operative Gynäkologie und Komplikationen, Mamma‑Diagnostik, Notfälle (Extrauteringravidität, Ovarialtorsion, akutes Abdomen), Recht und Ethik (§218 StGB, Mutterschutz, Aufklärung), Kinder‑ und Jugendgynäkologie. Each knowledge unit and each question is classified into one topic (Haiku, or the local model).
- **Voice**: transcription with faster‑whisper large‑v3 in German on the PC when awake (Ajit planned this on the PC), else the Studio; TTS with Piper German voice (`de_DE-thorsten-high` or similar) for spoken questions.

### Tier 2: Claude (Opus), event‑driven
- **Question generation** (daily batch, 15:00): from new knowledge units → 3–8 questions per unit cluster in exam style ("Eine 32‑jährige Zweitgebärende in der 38. SSW… Wie gehen Sie vor?"), each with model answer and guideline citation, graded difficulty, mapped to the topic map. Stored, never sent before review by the scheduler.
- **Daily drill** (20:30, 10 questions, text, ~15 min): spaced repetition over her units; "Nochmal" and "Verstanden" buttons; wrong answers re‑enter after 1, 3, 7, 14 days (reuse the 1‑3‑5‑7 idea Ajit uses; keep it simple).
- **Mock Fachgespräch** (on demand with `/prüfung <Thema>` or scheduled Tue 15:00, Thu 10:00, Sat 10:00; 20 min): the bot asks by voice, she answers by voice, transcription → grading against the guideline (content, structure Anamnese → Diagnostik → Therapie → Aufklärung, completeness, red flags named), then the examiner's follow‑up question, up to three rounds; ends with a scorecard and the cited guideline passages. Later in the plan: mixed topics, three‑examiner style, full 45 minutes.
- **Takeaways** (`#amboss …`, `#merke …`, or any plain message): stored as her note, acknowledged in one line, turned into questions in the next batch.
- **Concept notes** in the doc: per topic a one‑page German summary built from her highlights and the guideline, with her gaps marked.
- **Ledger and weekly report** (Sunday 18:00, bot + doc): score per topic, repeated gaps, time per answer, mastery (a topic is mastered after 5 consecutive correct answers in drills and one mock exam above 80 %), next week's two topics.

## 4. Study plan (write it into the doc at setup, in German, and keep it current)
- Week of 13.10.2026: ingestion, baseline quiz (30 questions across all topics, voice), weak‑spot map.
- 20.10.–30.11.2026, two topics per week in this order: Geburtshilfe‑Notfälle; Schwangerenvorsorge/Pränatal; Mamma; Zervix/Endometrium/Ovar/Vulva; Endokrinologie/Reproduktion/Kontrazeption; Urogynäkologie + Infektionen; operative Gynäkologie + Notfälle; Recht/Ethik + Kinder‑ und Jugendgynäkologie. Per week: her reading and highlights, daily drills, one mock exam per topic.
- December and the Urlaub block 21.12.2026–10.01.2027: mixed mock exams three times a week, daily during the Urlaub; Prüfungsprotokolle (she collects them from colleagues; she pastes or photographs them, text only, no names) are ingested as extra question sources; her Logbuch procedures rehearsed as "Berichten Sie über …" questions.
- January 2027 until the exam date: a full mock exam every second day, weekly report, final gap list.
- The plan rescales automatically when the exam date is entered (`/termin 2027‑02‑12`).

## 5. Engineering
- Python 3.12 in `~/FachCoach/.venv`; python‑telegram‑bot, PyMuPDF, Pillow, numpy, pyobjc (Vision), google‑api‑python‑client; RadCoach imported by path.
- `fachcoachctl`: `status`, `ingest-now`, `drill-now`, `exam <topic>`, `report`, `pause`, `resume`, `termin <date>`.
- launchd: `com.ajit.fachcoach-bot`, `-drive-watcher`, `-scheduler`; KeepAlive; hung‑poll self‑kill.
- Tests: highlight detection on a synthetic PDF with coloured boxes over known text; OCR fallback; privacy gate; question schema; drill scheduling; mock‑exam state machine; doc write verified by re‑read.
- No secrets or extracted textbook text in git; `~/FachCoach` is its own repo.

## 6. Phases
- **Phase 1 (this weekend):** Drive watcher, highlight extractor, topic map, guideline corpus and index, question generation, Telegram drill, the doc with the plan, health. Test with one real Notability backup of hers (ask Ajit to confirm she has enabled the backup).
- **Phase 2 (week of 13.10.):** voice mock exams, ledger, weekly report, concept notes, takeaways.
- **Phase 3 (November):** mixed exams, Prüfungsprotokolle ingestion, Logbuch rehearsal, three‑examiner mode.

## 7. Definition of done, Phase 1
1. A new Notability backup appears in Drive → within 10 min its highlights are in SQLite with page numbers and the correct text.
2. A page with highlights over a scanned (no text layer) page yields correct text via OCR.
3. A takeaway containing a fake patient name is refused and nothing is stored.
4. The daily drill arrives on Telegram at 20:30 with questions built from her highlights, each with a guideline citation.
5. The study plan and topic map are in the doc; a re‑read verifies them.
6. Killing the bot triggers the alert within 15 min.
7. A one‑page needs‑human list: bot token, Drive consent for FachCoach's own token, Notability backup enabled, her Telegram ID, exam date when known.
