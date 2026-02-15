# Skill: cron-manager

## Description
OpenClaw cron job management and monitoring. Lists, adds, updates, removes scheduled tasks.

## When to Use
- Setting up recurring tasks (scans, monitors, reports)
- Need to check what jobs are running
- Want to pause/resume scheduled tasks
- Debugging why a job didn't run

## When NOT to Use
- One-time tasks — just run the script directly
- Need precise timing (down to seconds) — cron is minute-level
- Want event-driven triggers — use webhooks instead

## Negative Examples (Failures)
1. **Model mismatch**: Initially used expensive models (Kimi K2.5) for routine cron jobs.
   - Fix: Switched to Gemini Flash Lite (free) for routine tasks
   - Savings: $45/month → $5/month

2. **Overlapping jobs**: Scanner took >12h initially, next run would overlap.
   - Fix: Added runtime estimates and adjusted frequencies

3. **No delivery config**: Jobs ran but user didn't get notified.
   - Fix: Always specify delivery.channel and delivery.to

## Dependencies
```bash
# Built-in OpenClaw tool
openclaw cron

# Or direct API
 GATEWAY_URL and GATEWAY_TOKEN env vars
```

## Usage
```bash
# List all jobs
openclaw cron list

# Add job (use skill helper)
python3 skills/automation/cron-manager/add.py --name "my-job" --schedule "0 */4 * * *" --script "./scan.py"

# Check job runs
openclaw cron runs --job-id <job_id>
```

## Configuration
Jobs defined in `/config/cron-jobs.yaml`:
```yaml
jobs:
  - name: memecoin-scanner
    schedule: "0 */12 * * *"  # Every 12 hours
    script: "skills/crypto/memecoin-scanner/scan.py"
    model: "google/gemini-2.0-flash-lite:free"
    delivery:
      channel: telegram
      to: "@sasimestri"
```

## Output
- Job ID (save this!)
- Next run timestamp
- Run history

## Artifacts
None (scheduling only).

## Handoff Protocol
When context compacts:
1. Export job list: `openclaw cron list > /mnt/data/backups/cron-jobs.json`
2. Document any job failures in SKILL_MANIFEST
