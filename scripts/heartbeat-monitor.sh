#!/bin/bash
# heartbeat-monitor.sh - Intelligent 30-min heartbeat checks
# Runs every 30min during waking hours (7am-11pm)
# Only alerts when attention needed

set -e

# Config
COOLIFY_API_URL="${COOLIFY_API_URL:-}"
COOLIFY_TOKEN="${COOLIFY_TOKEN:-}"
DISCORD_WEBHOOK="${DISCORD_MONITORING_WEBHOOK:-}"
LOG_FILE="/Users/pterion2910/.openclaw/workspace/logs/heartbeat-$(date +%Y%m%d).log"
STATE_FILE="/Users/pterion2910/.openclaw/workspace/state/heartbeat-state.json"

mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$STATE_FILE")"

# Severity tracking
URGENT=""
HEADS_UP=""
ALERT_COUNT=0

log() {
    echo "[$(date '+%H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

send_discord() {
    local severity="$1"
    local title="$2"
    local message="$3"
    local color="$4"
    
    if [ -z "$DISCORD_WEBHOOK" ]; then
        log "⚠️ Discord webhook not set"
        return
    fi
    
    curl -s -X POST "$DISCORD_WEBHOOK" \
        -H "Content-Type: application/json" \
        -d "{
            \"embeds\": [{
                \"title\": \"$title\",
                \"description\": \"$message\",
                \"color\": $color,
                \"timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
                \"footer\": {\"text\": \"Heartbeat Check • $(date '+%H:%M')\"}
            }]
        }" > /dev/null 2>&1
    
    log "📤 Discord alert sent: $severity"
}

# ========== EMAIL CHECK ==========
check_email() {
    log "📧 Checking email..."
    
    # Check if Himalaya configured
    if ! command -v himalaya &> /dev/null; then
        log "⚠️ Himalaya not installed"
        return
    fi
    
    if [ ! -f ~/.config/himalaya/config.toml ]; then
        log "⚠️ Himalaya not configured"
        return
    fi
    
    # Get emails from last 30 minutes
    # Himalaya doesn't have time filter, so we check recent and filter
    local recent_emails
    recent_emails=$(himalaya envelope list --page-size 20 --output json 2>/dev/null || echo "[]")
    
    # Keywords for urgency detection
    local urgent_keywords="payment failed|security alert|suspicious|unauthorized|expired|expiring|overdue|declined|blocked"
    local heads_up_keywords="meeting|appointment|reminder|subscription|renewal|invoice|deadline|scheduled"
    
    # Parse and check emails (DRAFT-ONLY mode - never send)
    echo "$recent_emails" | jq -r '.[] | select(.date) | "\(.id)|\(.subject)|\(.from)|\(.date)"' 2>/dev/null | while IFS='|' read -r id subject from date; do
        # Check if email is from last 30 minutes
        local email_time=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$date" +%s 2>/dev/null || date -d "$date" +%s 2>/dev/null || echo 0)
        local thirty_mins_ago=$(($(date +%s) - 1800))
        
        if [ "$email_time" -lt "$thirty_mins_ago" ]; then
            continue
        fi
        
        # Check for urgent patterns
        if echo "$subject $from" | grep -iE "$urgent_keywords" > /dev/null; then
            URGENT="${URGENT}📧 **URGENT EMAIL**\nSubject: $subject\nFrom: $from\nAction needed: Review immediately\n\n"
            ((ALERT_COUNT++))
            log "🚨 URGENT: $subject"
        # Check for heads-up patterns
        elif echo "$subject $from" | grep -iE "$heads_up_keywords" > /dev/null; then
            # Only alert if we haven't seen this subject today
            if ! grep -q "$subject" "$STATE_FILE" 2>/dev/null; then
                HEADS_UP="${HEADS_UP}📧 Meeting/Reminder: $subject\nFrom: $from\n\n"
                echo "{\"subject\": \"$subject\", \"time\": \"$(date)\"}" >> "$STATE_FILE"
                ((ALERT_COUNT++))
                log "⚠️ HEADS UP: $subject"
            fi
        fi
    done
}

# ========== CALENDAR CHECK ==========
check_calendar() {
    log "📅 Checking calendar..."
    
    # Check for events in next 2 hours
    # This would integrate with cal/calendar CLI or Google Calendar API
    # For now, placeholder - user can integrate their preferred calendar
    
    # Example with icalBuddy if installed
    if command -v icalBuddy &> /dev/null; then
        local events
        events=$(icalBuddy -n -nc -ps '|: |' eventsFrom:now to:+2h 2>/dev/null || echo "")
        
        if [ -n "$events" ]; then
            # Check if we've already reminded about this event
            local event_hash=$(echo "$events" | md5)
            if ! grep -q "$event_hash" "$STATE_FILE" 2>/dev/null; then
                HEADS_UP="${HEADS_UP}📅 **Upcoming in next 2 hours:**\n$events\n\n"
                echo "{\"calendar_hash\": \"$event_hash\", \"time\": \"$(date)\"}" >> "$STATE_FILE"
                ((ALERT_COUNT++))
                log "📅 Calendar alert: Event in next 2h"
            fi
        fi
    else
        log "ℹ️ Calendar check skipped (icalBuddy not installed)"
    fi
}

# ========== COOLIFY SERVICES CHECK ==========
check_coolify() {
    log "🔧 Checking Coolify services..."
    
    if [ -z "$COOLIFY_API_URL" ] || [ -z "$COOLIFY_TOKEN" ]; then
        log "⚠️ Coolify not configured (set COOLIFY_API_URL and COOLIFY_TOKEN)"
        return
    fi
    
    # Get services status
    local services
    services=$(curl -s -H "Authorization: Bearer $COOLIFY_TOKEN" \
        "$COOLIFY_API_URL/api/v1/services" 2>/dev/null || echo "[]")
    
    # Check for unhealthy services
    echo "$services" | jq -r '.[] | select(.status != "running" and .status != "stopped") | "\(.name)|\(.status)|\(.health)"' 2>/dev/null | while IFS='|' read -r name status health; do
        # Only alert for unhealthy, not routine restarts
        if [ "$health" = "unhealthy" ] || [ "$status" = "error" ] || [ "$status" = "crashed" ]; then
            URGENT="${URGENT}🚨 **SERVICE DOWN: $name**\nStatus: $status\nHealth: $health\n\n"
            ((ALERT_COUNT++))
            log "🚨 SERVICE DOWN: $name ($status)"
        fi
    done
}

# ========== MAIN ==========
main() {
    log "========================================"
    log "🔍 Heartbeat Check Started"
    log "Time: $(date)"
    log "========================================"
    
    # Check if within waking hours (7am-11pm)
    local hour=$(date +%H)
    if [ "$hour" -lt 7 ] || [ "$hour" -ge 23 ]; then
        log "🌙 Outside waking hours (7am-11pm), skipping"
        exit 0
    fi
    
    # Run checks
    check_email
    check_calendar
    check_coolify
    
    # Send consolidated alert if anything found
    if [ $ALERT_COUNT -gt 0 ]; then
        log "🚨 Found $ALERT_COUNT items needing attention"
        
        local message=""
        local color=""
        local title=""
        
        if [ -n "$URGENT" ]; then
            title="🚨 URGENT: Action needed within 1 hour"
            message="$URGENT"
            color="15158332"  # Red
            
            if [ -n "$HEADS_UP" ]; then
                message="${message}\n---\n\n$HEADS_UP"
            fi
        else
            title="⚠️ Heads Up"
            message="$HEADS_UP"
            color="16776960"  # Yellow
        fi
        
        send_discord "$([ -n "$URGENT" ] && echo "URGENT" || echo "HEADS_UP")" "$title" "$message" "$color"
    else
        log "✅ All clear - no alerts needed"
    fi
    
    log "========================================"
    log "✅ Heartbeat Check Complete"
    log "Alerts: $ALERT_COUNT"
    log "========================================"
}

main "$@"
