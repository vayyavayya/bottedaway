#!/bin/bash
# daily-maintenance.sh - OpenClaw Daily Maintenance Routine
# Runs at 4:00 AM daily
# Reports to Discord #monitoring channel

set -e  # Exit on error

LOG_FILE="/Users/pterion2910/.openclaw/workspace/logs/daily-maintenance-$(date +%Y%m%d).log"
REPORT_FILE="/tmp/maintenance-report.txt"
DISCORD_WEBHOOK="${DISCORD_MONITORING_WEBHOOK:-}"  # Set via environment or config
mkdir -p "$(dirname "$LOG_FILE")"

exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

echo "========================================"
echo "🔧 OpenClaw Daily Maintenance"
echo "Date: $(date)"
echo "========================================"
echo ""

# Initialize report
REPORT=""
ERRORS=""
UPDATES=""

# Function to send Discord report
send_discord_report() {
    if [ -z "$DISCORD_WEBHOOK" ]; then
        echo "⚠️  Discord webhook not configured. Report saved to: $LOG_FILE"
        return
    fi
    
    local status="$1"
    local message="$2"
    local color="$3"  # decimal color code
    
    curl -s -X POST "$DISCORD_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "{
            \"embeds\": [{
                \"title\": \"OpenClaw Daily Maintenance - $status\",
                \"description\": \"$message\",
                \"color\": $color,
                \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
                \"fields\": [
                    {\"name\": \"Version\", \"value\": \"$VERSION\", \"inline\": true},
                    {\"name\": \"Date\", \"value\": \"$(date)\", \"inline\": true}
                ]
            }]
        }" > /dev/null 2>&1 && echo "✅ Discord report sent" || echo "❌ Failed to send Discord report"
}

# Get current version before update
echo "📋 Checking current version..."
VERSION=$(openclaw --version 2>/dev/null | head -1 || echo "unknown")
echo "Current version: $VERSION"
UPDATES+="• Pre-update version: $VERSION\n"

# Step 1: Update OpenClaw
echo ""
echo "📦 Step 1: Updating OpenClaw..."
echo "--------------------------------"
if openclaw update 2>&1 | tee -a "$LOG_FILE"; then
    echo "✅ OpenClaw update completed"
    UPDATES+="• OpenClaw package updated\n"
else
    ERROR_MSG="OpenClaw update failed"
    echo "❌ $ERROR_MSG"
    ERRORS+="• $ERROR_MSG\n"
    send_discord_report "FAILED" "OpenClaw update failed. Check logs at: $LOG_FILE" 15158332
    exit 1
fi

# Step 2: Update gateway
echo ""
echo "🔄 Step 2: Updating Gateway..."
echo "--------------------------------"
if openclaw gateway update 2>&1 | tee -a "$LOG_FILE"; then
    echo "✅ Gateway update completed"
    UPDATES+="• Gateway updated\n"
else
    ERROR_MSG="Gateway update failed"
    echo "❌ $ERROR_MSG"
    ERRORS+="• $ERROR_MSG\n"
    send_discord_report "FAILED" "Gateway update failed. Try: openclaw gateway restart" 15158332
    exit 1
fi

# Step 3: Update skills
echo ""
echo "📚 Step 3: Updating Skills..."
echo "--------------------------------"
SKILLS_BEFORE=$(openclaw skills list 2>/dev/null | wc -l)
if openclaw skills update --all 2>&1 | tee -a "$LOG_FILE"; then
    SKILLS_AFTER=$(openclaw skills list 2>/dev/null | wc -l)
    echo "✅ Skills update completed ($SKILLS_BEFORE → $SKILLS_AFTER skills)"
    UPDATES+="• Skills updated ($SKILLS_BEFORE → $SKILLS_AFTER)\n"
else
    ERROR_MSG="Skills update failed"
    echo "❌ $ERROR_MSG"
    ERRORS+="• $ERROR_MSG\n"
    send_discord_report "FAILED" "Skills update failed. Try: openclaw skills update --force" 15158332
    exit 1
fi

# Step 4: Update plugins
echo ""
echo "🔌 Step 4: Updating Plugins..."
echo "--------------------------------"
if openclaw plugins update --all 2>&1 | tee -a "$LOG_FILE"; then
    echo "✅ Plugins update completed"
    UPDATES+="• Plugins updated\n"
else
    ERROR_MSG="Plugins update failed"
    echo "❌ $ERROR_MSG"
    ERRORS+="• $ERROR_MSG\n"
    send_discord_report "FAILED" "Plugins update failed. Check plugin compatibility." 15158332
    exit 1
fi

# Step 5: Restart gateway
echo ""
echo "🚀 Step 5: Restarting Gateway..."
echo "--------------------------------"
sleep 2  # Give update processes time to settle
if openclaw gateway restart 2>&1 | tee -a "$LOG_FILE"; then
    echo "✅ Gateway restarted successfully"
    UPDATES+="• Gateway restarted\n"
else
    ERROR_MSG="Gateway restart failed"
    echo "❌ $ERROR_MSG"
    ERRORS+="• $ERROR_MSG\n"
    send_discord_report "FAILED" "Gateway restart failed. Try manual restart: openclaw gateway restart" 15158332
    exit 1
fi

# Get new version after update
echo ""
echo "📋 Checking new version..."
NEW_VERSION=$(openclaw --version 2>/dev/null | head -1 || echo "unknown")
echo "New version: $NEW_VERSION"
UPDATES+="• Post-update version: $NEW_VERSION\n"

# Verify gateway is running
echo ""
echo "✅ Verifying gateway status..."
if openclaw status 2>/dev/null | grep -q "Gateway.*running"; then
    echo "✅ Gateway is running"
    UPDATES+="• Gateway verified running\n"
else
    ERROR_MSG="Gateway not responding after restart"
    echo "❌ $ERROR_MSG"
    ERRORS+="• $ERROR_MSG\n"
    send_discord_report "WARNING" "Gateway restarted but not responding. Check: openclaw status" 16776960
fi

# Generate summary report
echo ""
echo "========================================"
echo "📊 Maintenance Summary"
echo "========================================"

if [ -z "$ERRORS" ]; then
    STATUS="✅ SUCCESS"
    COLOR=3066993  # Green
    REPORT="All updates completed successfully.\n\n**Updates:**\n$UPDATES"
    echo "Status: $STATUS"
    echo "All components updated and gateway restarted."
else
    STATUS="⚠️ COMPLETED WITH WARNINGS"
    COLOR=16776960  # Yellow
    REPORT="Maintenance completed but some issues occurred.\n\n**Updates:**\n$UPDATES\n**Warnings:**\n$ERRORS"
    echo "Status: $STATUS"
    echo "Errors: $ERRORS"
fi

echo ""
echo "Version: $VERSION → $NEW_VERSION"
echo "Log: $LOG_FILE"
echo "========================================"

# Send final report to Discord
send_discord_report "COMPLETED" "$REPORT" $COLOR

echo ""
echo "✅ Daily maintenance complete!"
