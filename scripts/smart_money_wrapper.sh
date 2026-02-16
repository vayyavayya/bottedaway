#!/bin/zsh
# Unified Smart Money Monitor Wrapper
# Runs every 2 hours to check for whale signals across all sources

WORKSPACE="/Users/pterion2910/.openclaw/workspace"
SCRIPT="$WORKSPACE/scripts/unified_smart_money_monitor.py"
ALERT_FILE="$WORKSPACE/config/smart_money_alerts.txt"

# Run the monitor
python3 "$SCRIPT"
EXIT_CODE=$?

# If exit code 42, alerts were triggered - send Telegram message
if [ $EXIT_CODE -eq 42 ]; then
    if [ -f "$ALERT_FILE" ]; then
        MESSAGE=$(cat "$ALERT_FILE")
        # Send via OpenClaw message tool to @pumpepump
        cd "$WORKSPACE" && openclaw message send --target "@pumpepump" --message "$MESSAGE" 2>/dev/null || echo "ALERT: $MESSAGE"
        rm -f "$ALERT_FILE"
    fi
fi

exit 0
