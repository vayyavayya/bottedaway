# HEARTBEAT.md - Rotating Check Pattern

Based on digitalknk's runbook: Single heartbeat rotates through overdue checks instead of separate cron jobs.

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
- **Cheap model** — All checks use `google/gemini-2.0-flash-lite:free`

## Current Cron Jobs (Still Active)

- `memecoin-scanner-720min` — Every 12h (data collection)
- `diary-telegram-update` — Daily 9am (user notification)

These are user-facing and time-sensitive, so they stay as cron jobs.
