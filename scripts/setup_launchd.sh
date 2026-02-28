#!/bin/bash
# Automated LaunchAgent Setup for Memecoin Signals
# Run this once - it installs and activates the LaunchAgent

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LAUNCHD_DIR="$REPO_DIR/launchd"
PLIST_NAME="com.clawbot.memecoin-signals.plist"
PLIST_SOURCE="$LAUNCHD_DIR/$PLIST_NAME"
PLIST_DEST="$HOME/Library/LaunchAgents/$PLIST_NAME"
LOGS_DIR="$REPO_DIR/logs"

echo "🚀 Setting up Memecoin Signal Engine LaunchAgent..."
echo ""

# Create logs directory
mkdir -p "$LOGS_DIR"
echo "✅ Created logs directory: $LOGS_DIR"

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$HOME/Library/LaunchAgents"
echo "✅ Ensured LaunchAgents directory exists"

# Check if plist exists
if [ ! -f "$PLIST_SOURCE" ]; then
    echo "❌ Error: $PLIST_SOURCE not found"
    exit 1
fi

# Copy plist to LaunchAgents
cp "$PLIST_SOURCE" "$PLIST_DEST"
echo "✅ Copied $PLIST_NAME to LaunchAgents"

# Set proper permissions
chmod 644 "$PLIST_DEST"
echo "✅ Set permissions on plist"

# Unload if already loaded (to refresh)
launchctl unload "$PLIST_DEST" 2>/dev/null || true

# Load the LaunchAgent
if launchctl load "$PLIST_DEST" 2>/dev/null; then
    echo "✅ LaunchAgent loaded successfully"
else
    echo "⚠️  LaunchAgent will auto-load on next login"
fi

# Verify
if launchctl list | grep -q "com.clawbot.memecoin-signals"; then
    echo "✅ Verified: Job is loaded and active"
else
    echo "ℹ️  Job will be active after login/reboot"
fi

echo ""
echo "========================================"
echo "📅 Schedule: Twice daily at 8am & 8pm"
echo "📝 Logs: $LOGS_DIR"
echo "🔧 Status: launchctl list | grep memecoin"
echo "========================================"
echo ""
echo "Setup complete! The memecoin signal engine will run automatically."
