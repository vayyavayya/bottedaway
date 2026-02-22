# HEARTBEAT.md — Rotating Check Pattern

Based on digitalknk's runbook: Single heartbeat rotates through overdue checks instead of separate cron jobs.

## Cost Optimization: Local Model Routing

**NEW**: Heartbeats now route to local Llama 3.2 via Ollama for **$0 cost**.
- 48×/day pings = $0 with local model
- Falls back to Gemini Flash Lite if local model unavailable

---

## Check Rotation

| Check | Cadence | Last Run | Window | Action if Overdue |
|-------|---------|----------|--------|-------------------|
| Scanner Results | 12h | - | Any | Read latest scanner log, flag opportunities |
| Memory Review | 24h | - | Any | Review recent memory files, update MEMORY.md |
| Git Sync | 6h | - | Any | Sync bottedaway repo if changes exist |
| Skill Audit | 7d | - | Any | Review installed skills for security |
| Cost Check | 24h | - | Any | Log API usage, alert if unusual |

## State Tracking

```json
{
  "lastChecks": {
    "scanner_review": 0,
    "memory_review": 0,
    "git_sync": 0,
    "skill_audit": 0,
    "cost_check": 0
  },
  "nextCheck": "scanner_review"
}
```

## Rotation Logic

1. Load `memory/heartbeat-state.json`
2. Calculate which check is most overdue
3. Run that check
4. Update timestamp
5. Save state

## Benefits

- **Batched work** — Multiple checks in one heartbeat
- **Flat costs** — No spike from concurrent cron jobs
- **Flexible timing** — Checks run when most needed, not rigid schedule
- **$0 heartbeats** — Local Llama 3.2 handles 48×/day pings

## Current Cron Jobs (Still Active)

These are user-facing and time-sensitive:

- `memecoin-scanner-720min` — Every 12h (data collection)
- `smart-money-monitor-2h` — Every 2h (whale alerts)
- `ema50-crossing-alerts-4h` — Every 4h (EMA50 signals)
- `watchlist-maintenance-daily` — Daily 7am (cleanup)
- `git-auto-backup-2h` — Every 2h (disaster recovery)
- `diary-telegram-update` — Daily 9am (user digest)
- `morning-briefing-8am` — Daily 8am
- `daily-watchlist-8am` — Daily 8am
- `moltbook-learning-24h` — Daily midnight
- `memory-grooming-nightly` — Daily 3am

---

## Local Model Setup

```bash
# Ensure Llama 3.2 is available
ollama list | grep llama3.2

# If not present:
ollama pull llama3.2:3b
```

Heartbeat responses will use local model first, fall back to Gemini Flash Lite.
