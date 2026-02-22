#!/bin/zsh
# ママン Price Monitor Wrapper - Runs every hour
# Checks price and sends Telegram alerts when thresholds are breached

WORKSPACE="/Users/pterion2910/.openclaw/workspace"
SCRIPT="$WORKSPACE/scripts/maman_price_monitor.py"
ALERT_FILE="$WORKSPACE/config/maman_alert.txt"

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
