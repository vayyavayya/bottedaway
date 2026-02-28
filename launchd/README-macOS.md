# macOS LaunchAgent Setup for Memecoin Signals

This directory contains the macOS-native cron alternative (launchd) configuration.

## Files

- `com.clawbot.memecoin-signals.plist` - LaunchAgent configuration
- `README-macOS.md` - This file

## Schedule

Runs twice daily:
- **8:00 AM CET** (08:00)
- **8:00 PM CET** (20:00)

## Installation

### One-time setup:

```bash
# Create LaunchAgents directory if it doesn't exist
mkdir -p ~/Library/LaunchAgents

# Copy the plist file
cp ~/.openclaw/workspace/bottedaway/launchd/com.clawbot.memecoin-signals.plist ~/Library/LaunchAgents/

# Load the job
launchctl load ~/Library/LaunchAgents/com.clawbot.memecoin-signals.plist

# Verify it's loaded
launchctl list | grep clawbot
```

## Management Commands

```bash
# Load (start)
launchctl load ~/Library/LaunchAgents/com.clawbot.memecoin-signals.plist

# Unload (stop)
launchctl unload ~/Library/LaunchAgents/com.clawbot.memecoin-signals.plist

# Check status
launchctl list | grep memecoin

# Run manually (for testing)
launchctl start com.clawbot.memecoin-signals

# View logs
tail -f ~/.openclaw/workspace/bottedaway/logs/memecoin-launchd.log
tail -f ~/.openclaw/workspace/bottedaway/logs/memecoin-launchd.error.log
```

## Troubleshooting

### "Operation not permitted" error
If you get permission errors, the script may need Full Disk Access:
1. System Preferences → Security & Privacy → Privacy → Full Disk Access
2. Add Terminal (or your terminal app)
3. Restart Terminal

### Logs not appearing
Check the log directory exists:
```bash
mkdir -p ~/.openclaw/workspace/bottedaway/logs
```

### Job not running
Check for errors:
```bash
launchctl print gui/$(id - u)/com.clawbot.memecoin-signals
```

## Alternative: Traditional Cron

If you prefer traditional cron instead of launchd:

```bash
# Add to crontab
crontab -e

# Add this line:
0 8,20 * * * bash ~/.openclaw/workspace/bottedaway/scripts/run_memecoin_signals.sh >> ~/.openclaw/workspace/bottedaway/logs/memecoin-cron.log 2>&1
```

**Note:** launchd is recommended on macOS as it's more reliable with sleep/wake cycles.

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.clawbot.memecoin-signals.plist
rm ~/Library/LaunchAgents/com.clawbot.memecoin-signals.plist
```
