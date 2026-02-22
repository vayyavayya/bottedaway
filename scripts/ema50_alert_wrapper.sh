#!/bin/zsh
# 4h EMA50 Crossing Alert Wrapper
# Runs every 4 hours to check for EMA50 breakouts/breakdowns

WORKSPACE="/Users/pterion2910/.openclaw/workspace"
SCRIPT="$WORKSPACE/scripts/ema50_crossing_alerts.py"
ALERT_FILE="$WORKSPACE/config/ema50_alert.txt"

# Run the monitor
python3 "$SCRIPT"
EXIT_CODE=$?

# If exit code 42, an alert was triggered - send Telegram message
if [ $EXIT_CODE -eq 42 ]; then
    if [ -f "$ALERT_FILE" ]; then
        MESSAGE=$(cat "$ALERT_FILE")
        # Send via OpenClaw message tool
        cd "$WORKSPACE" && openclaw message send --target "@sasimestri" --message "$MESSAGE" 2>/dev/null || echo "ALERT: $MESSAGE"
        rm -f "$ALERT_FILE"
    fi
fi

exit 0
