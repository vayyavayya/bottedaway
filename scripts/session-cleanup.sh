#!/bin/bash
# session-cleanup.sh — Delete bloated session files every 72 hours
# Preserves last 7 days of active sessions, removes old/bloated ones

SESSION_DIR="/Users/pterion2910/.openclaw/agents/main/sessions"
LOG_FILE="/Users/pterion2910/.openclaw/workspace/logs/session-cleanup.log"
CUTOFF_DAYS=7
MAX_SIZE_MB=50  # Remove individual files > 50MB

mkdir -p "$(dirname "$LOG_FILE")"

echo "========================================" | tee -a "$LOG_FILE"
echo "🧹 Session Cleanup — $(date)" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"

# Count before
BEFORE_COUNT=$(find "$SESSION_DIR" -name "*.jsonl" -type f 2>/dev/null | wc -l)
BEFORE_SIZE=$(du -sh "$SESSION_DIR" 2>/dev/null | cut -f1)
echo "📊 Before: $BEFORE_COUNT files, $BEFORE_SIZE" | tee -a "$LOG_FILE"

# Delete files older than CUTOFF_DAYS
OLD_DELETED=$(find "$SESSION_DIR" -name "*.jsonl" -type f -mtime +$CUTOFF_DAYS -print -delete 2>/dev/null | wc -l)
echo "🗑️ Deleted $OLD_DELETED files older than $CUTOFF_DAYS days" | tee -a "$LOG_FILE"

# Delete files larger than MAX_SIZE_MB (bloated sessions)
LARGE_DELETED=$(find "$SESSION_DIR" -name "*.jsonl" -type f -size +${MAX_SIZE_MB}M -print -delete 2>/dev/null | wc -l)
echo "🗑️ Deleted $LARGE_DELETED files >${MAX_SIZE_MB}MB" | tee -a "$LOG_FILE"

# Count after
AFTER_COUNT=$(find "$SESSION_DIR" -name "*.jsonl" -type f 2>/dev/null | wc -l)
AFTER_SIZE=$(du -sh "$SESSION_DIR" 2>/dev/null | cut -f1)
echo "📊 After: $AFTER_COUNT files, $AFTER_SIZE" | tee -a "$LOG_FILE"

FREED=$(echo "$BEFORE_COUNT - $AFTER_COUNT" | bc)
echo "✅ Freed space: $FREED sessions removed" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
