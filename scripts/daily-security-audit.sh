#!/bin/bash
# daily-security-audit.sh — Morning security check
# Reports: firewall, SSH, open ports, docker status, fail2ban

REPORT_FILE="/Users/pterion2910/.openclaw/workspace/reports/security-audit-$(date +%Y%m%d).log"
ALERT_FILE="/Users/pterion2910/.openclaw/workspace/reports/security-alerts.log"

mkdir -p "$(dirname "$REPORT_FILE")"

echo "========================================" > "$REPORT_FILE"
echo "🔒 Daily Security Audit — $(date)" >> "$REPORT_FILE"
echo "========================================" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

ALERTS=0

# 1. Firewall Status (macOS)
echo "🧱 Firewall Status:" >> "$REPORT_FILE"
if /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null | grep -q "enabled"; then
    echo "   ✅ Firewall: ENABLED" >> "$REPORT_FILE"
else
    echo "   ⚠️  Firewall: DISABLED" >> "$REPORT_FILE"
    ALERTS=$((ALERTS + 1))
fi
echo "" >> "$REPORT_FILE"

# 2. Open Ports
echo "🚪 Open Ports (TCP):" >> "$REPORT_FILE"
lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | grep -v "^COMMAND" | head -20 >> "$REPORT_FILE" || echo "   No listening ports" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# 3. SSH Status
echo "🔑 SSH Status:" >> "$REPORT_FILE"
if pgrep -q sshd 2>/dev/null; then
    echo "   ⚠️  SSH daemon RUNNING" >> "$REPORT_FILE"
    ALERTS=$((ALERTS + 1))
else
    echo "   ✅ SSH daemon: Not running (good for workstation)" >> "$REPORT_FILE"
fi

# Check SSH config if it exists
if [ -f /etc/ssh/sshd_config ]; then
    if grep -q "^PermitRootLogin yes" /etc/ssh/sshd_config 2>/dev/null; then
        echo "   ⚠️  Root login permitted" >> "$REPORT_FILE"
        ALERTS=$((ALERTS + 1))
    else
        echo "   ✅ Root login disabled" >> "$REPORT_FILE"
    fi
fi
echo "" >> "$REPORT_FILE"

# 4. Docker Status
echo "🐳 Docker Status:" >> "$REPORT_FILE"
if command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1; then
        echo "   ✅ Docker: Running" >> "$REPORT_FILE"
        echo "" >> "$REPORT_FILE"
        echo "📋 Running Containers:" >> "$REPORT_FILE"
        docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" 2>/dev/null >> "$REPORT_FILE"
    else
        echo "   ⚠️  Docker: Not running" >> "$REPORT_FILE"
    fi
else
    echo "   ℹ️  Docker: Not installed" >> "$REPORT_FILE"
fi
echo "" >> "$REPORT_FILE"

# 5. Fail2ban Status (if installed)
echo "🛡️  Fail2ban Status:" >> "$REPORT_FILE"
if command -v fail2ban-client >/dev/null 2>&1; then
    if pgrep -q fail2ban 2>/dev/null; then
        echo "   ✅ Fail2ban: Running" >> "$REPORT_FILE"
        fail2ban-client status 2>/dev/null >> "$REPORT_FILE"
    else
        echo "   ⚠️  Fail2ban: Not running" >> "$REPORT_FILE"
        ALERTS=$((ALERTS + 1))
    fi
else
    echo "   ℹ️  Fail2ban: Not installed" >> "$REPORT_FILE"
fi
echo "" >> "$REPORT_FILE"

# 6. OpenClaw Security Check
echo "🦞 OpenClaw Gateway:" >> "$REPORT_FILE"
if pgrep -q openclaw-gateway 2>/dev/null || curl -s http://localhost:18789/status >/dev/null 2>&1; then
    echo "   ✅ Gateway: Running" >> "$REPORT_FILE"
else
    echo "   ⚠️  Gateway: Not responding" >> "$REPORT_FILE"
    ALERTS=$((ALERTS + 1))
fi
echo "" >> "$REPORT_FILE"

# Summary
echo "========================================" >> "$REPORT_FILE"
if [ $ALERTS -eq 0 ]; then
    echo "✅ All checks passed — no alerts" >> "$REPORT_FILE"
else
    echo "⚠️  $ALERTS alert(s) require attention" >> "$REPORT_FILE"
fi
echo "Report saved: $REPORT_FILE" >> "$REPORT_FILE"
echo "========================================" >> "$REPORT_FILE"

# If alerts, also write to alert log
if [ $ALERTS -gt 0 ]; then
    echo "[$(date)] $ALERTS security alerts — see $REPORT_FILE" >> "$ALERT_FILE"
fi

echo "Audit complete. Report: $REPORT_FILE"
