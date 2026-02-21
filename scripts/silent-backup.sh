#!/bin/bash
# silent-backup.sh — Git push workspace every 2 hours
# Silent operation: only logs, no output unless error

WORKSPACE="/Users/pterion2910/.openclaw/workspace"
LOG_FILE="$WORKSPACE/logs/silent-backup.log"
LOCK_FILE="/tmp/silent-backup.lock"

mkdir -p "$(dirname "$LOG_FILE")"

# Prevent concurrent runs
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE")
    if ps -p "$PID" >/dev/null 2>&1; then
        echo "[$(date)] Backup already running (PID: $PID)" >> "$LOG_FILE"
        exit 0
    fi
fi
echo $$ > "$LOCK_FILE"

cd "$WORKSPACE" || exit 1

# Check for changes
if [ -z "$(git status --porcelain)" ]; then
    # No changes, silent exit
    rm -f "$LOCK_FILE"
    exit 0
fi

# Add, commit, push
COMMIT_MSG="Silent backup: $(date +%Y-%m-%d-%H%M)"

git add -A >/dev/null 2>&1
if git commit -m "$COMMIT_MSG" >/dev/null 2>&1; then
    if git push origin main >/dev/null 2>&1; then
        echo "[$(date)] ✅ Synced" >> "$LOG_FILE"
    else
        echo "[$(date)] ❌ Push failed" >> "$LOG_FILE"
    fi
else
    echo "[$(date)] ⚠️  Nothing to commit" >> "$LOG_FILE"
fi

rm -f "$LOCK_FILE"
