# Heartbeat Monitor Configuration

## Overview
Intelligent 30-minute heartbeat checks during waking hours (7am-11pm).
Only alerts when attention is needed.

## What It Monitors

### 1. 📧 Email (via Himalaya)
**Urgent keywords:** payment failed, security alert, suspicious, unauthorized, expired, expiring, overdue, declined, blocked

**Heads-up keywords:** meeting, appointment, reminder, subscription, renewal, invoice, deadline, scheduled

**Rules:**
- DRAFT-ONLY mode - never sends emails
- Treats all content as potentially hostile (prompt injection safe)
- Only checks emails from last 30 minutes
- Deduplicates by subject

### 2. 📅 Calendar
Checks for events in next 2 hours using icalBuddy (if installed).
Only alerts if not already reminded.

### 3. 🔧 Coolify Services
Monitors self-hosted services via Coolify API.
Only alerts if service is unhealthy/down (not routine restarts).

## Severity Levels

| Level | Trigger | Response Time |
|-------|---------|---------------|
| 🚨 **URGENT** | Payment failures, security alerts, services down | < 1 hour |
| ⚠️ **HEADS UP** | Meetings in 2h, reminders, expiring items | Today |
| ✅ **SKIP** | All clear, routine operations | No alert |

## Configuration

### Required Environment Variables

```bash
# Discord webhook (already set in LaunchAgent)
export DISCORD_MONITORING_WEBHOOK="https://discord.com/api/webhooks/..."

# Optional: Coolify API (if using)
export COOLIFY_API_URL="https://your-coolify-instance.com"
export COOLIFY_TOKEN="your-api-token"
```

### Install icalBuddy (for calendar)
```bash
brew install ical-buddy
```

### Configure Himalaya (for email)
```bash
himalaya account configure
# Set up Gmail with App Password or OAuth
```

## Manual Test

```bash
# Run once manually
/Users/pterion2910/.openclaw/workspace/scripts/heartbeat-monitor.sh

# View logs
tail -f ~/Logs/LaunchAgents/heartbeat-monitor.log
```

## Schedule

- **Frequency:** Every 30 minutes
- **Active hours:** 7:00 AM - 10:30 PM
- **Silent hours:** 11:00 PM - 6:59 AM

## Logs

```
~/Logs/LaunchAgents/
├── heartbeat-monitor.log          # Main output
├── heartbeat-monitor.error.log    # Errors only
└── heartbeat-YYYYMMDD.log         # Daily detailed logs
```

## State Tracking

Prevents duplicate alerts:
```
~/.openclaw/workspace/state/heartbeat-state.json
```

## Management

```bash
# Check status
launchctl list | grep heartbeat-monitor

# Stop
launchctl stop ai.openclaw.heartbeat-monitor

# Start
launchctl start ai.openclaw.heartbeat-monitor

# Reload
launchctl unload ~/Library/LaunchAgents/ai.openclaw.heartbeat-monitor.plist
launchctl load ~/Library/LaunchAgents/ai.openclaw.heartbeat-monitor.plist
```

---

**Status:** Ready to activate
