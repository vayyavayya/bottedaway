# RadCoach: kickoff for the Claude Code session on the Mac Studio

Paste this into the Mac session as the first message:

```
Read radcoach/BUILD.md in the bottedaway repo (branch radcoach-v4) and build Phase 1 exactly as specified. Work in ~/RadCoach (not inside the repo). Build and test everything yourself end to end; do not hand me steps to run. Shadow mode only: nothing is written to the Google Docs until I say go-live. When Phase 1 passes its checklist, give me one report with three sections, VERIFIED ON DEVICE / STATICALLY CHECKED / BLOCKED, and one list of everything that needs me (logins, OAuth consent, opt-ins, anything paid). Ask before anything paid. Keep the Mac awake while you work.
```

## Where things are
- Repo clone on the Mac: wherever the auto-backup job keeps `bottedaway`. If unsure: `git clone --branch radcoach-v4 --depth 1 https://github.com/vayyavayya/bottedaway ~/radcoach-src` and read `~/radcoach-src/radcoach/BUILD.md`.
- Build target: `~/RadCoach/` (code, venv, launchd plists, case record). Keep it out of iCloud.
- Google access: OAuth client for Docs + Drive (scopes `documents`, `drive.file`); the doc IDs are in `reference/coach_prompt_v3.txt`.
- Existing pieces to reuse, not rebuild: `~/.local/bin/anki-bridge.py` and `~/.srs/anki/outbox` (cards), alertd's Telegram sender (alerts), the Studio's Ollama (`qwen3.5:9b`), the PC's gateway at `http://192.168.188.184:11436` (only when awake).
- The PC schedule (wake 07:55, sleep 16:05) is set up from the Mac over the existing tailnet SSH; see "PC schedule and worker" in BUILD.md.

## Order of work (Phase 1)
1. Watcher + queue + writer against a scratch copy of „My Radio findings“ (never the live doc until go-live).
2. Case folders, privacy gate, certainty rule.
3. Claude packet via `claude -p` with `--output-format json --json-schema`; log `total_cost_usd` per run.
4. docimg (image push) with revocation verified.
5. PC worker + schedule.
6. Eval export of the existing cases (08–09.10.2026).
7. Run the Phase 1 checklist; write the report.

## Go-live is a separate step
Ajit disables the two cloud scheduled tasks („Radiology live coaching (morning)“ and „(afternoon)“) only after a clean shadow day. Until then both systems run; only the cloud one writes.
