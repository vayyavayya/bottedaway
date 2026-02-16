# Skill: git-backup

## Description
Automated Git backup of OpenClaw workspace to GitHub. Ensures full memory/state recovery if server dies or needs migration.

## When to Use
- Want disaster recovery for OpenClaw setup
- Moving to new machine
- Corruption protection
- Team collaboration on agent setup

## When NOT to Use
- Repository is private and contains secrets (use .gitignore carefully)
- GitHub rate limits exceeded
- Working on sensitive data that shouldn't leave machine

## Pattern: Backup Every 2 Hours

**From Moltbook/Twitter:**
> "My OpenClaw backs itself up to GitHub every 2 hours. Server dies? Spin up a new one. Full memory restored."

**Why 2 hours?**
- Frequent enough to minimize data loss
- Not so frequent to hit GitHub rate limits
- Captures skill changes, memory updates, configs
- Allows recovery from corruption/failures

## Implementation

### Option 1: Cron Job (Recommended)

```bash
# Add to crontab or OpenClaw cron
0 */2 * * * cd /path/to/workspace && git add -A && git commit -m "Auto-backup $(date -u +%Y-%m-%d-%H:%M)" && git push
```

### Option 2: Heartbeat Batch

Add to `HEARTBEAT.md` checks:
```bash
git_sync: Every 2h → Auto-commit and push
```

### Option 3: Skill Trigger

```python
# skills/system/git-backup/backup.py
import subprocess
from datetime import datetime

def backup():
    timestamp = datetime.utcnow().strftime("%Y-%m-%d-%H%M")
    subprocess.run(["git", "add", "-A"], cwd="/workspace")
    subprocess.run(["git", "commit", "-m", f"Auto-backup {timestamp}"])
    subprocess.run(["git", "push"])
```

## What Gets Backed Up

**Included:**
- All skills (code, READMEs, configs)
- Memory files (daily/, projects/, reference/)
- SKILL_MANIFEST.md
- Cron job configs
- Reports and artifacts

**Excluded (via .gitignore):**
- State files (*_state.json)
- Logs (*.log)
- __pycache__/
- .env files

## Recovery Process

**If server dies:**

```bash
# On new machine
git clone https://github.com/user/openclaw-workspace.git
cd openclaw-workspace
openclaw gateway config.patch  # Restore config
# Full memory and skills restored
```

## Negative Examples (Failures)

1. **Committed secrets**: Accidentally committed .env with API keys
   - Fix: Use .gitignore, rotate keys, use environment variables

2. **Merge conflicts**: Edited on two machines without pulling
   - Fix: Always pull before push, use branches if needed

3. **Repo too big**: Committed large binary files
   - Fix: Use .gitignore for large files, use releases for binaries

## Artifacts

Backups stored in GitHub repo. No local artifacts.

## Handoff Protocol

When context compacts:
1. Ensure latest changes committed
2. Note repo URL in SKILL_MANIFEST
3. Document any uncommitted changes
