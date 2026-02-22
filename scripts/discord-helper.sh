#!/bin/bash
# Alternative: Send Discord message using message tool (if Discord channel configured)
# This script can be used if Discord is configured as an OpenClaw channel

CONFIG_FILE="/Users/pterion2910/.openclaw/workspace/config/discord-config.json"

# Check if Discord is configured
if [ -f "$CONFIG_FILE" ]; then
    DISCORD_CHANNEL=$(cat "$CONFIG_FILE" | grep -o '"channel": "[^"]*"' | cut -d'"' -f4)
    echo "Discord channel configured: $DISCORD_CHANNEL"
else
    echo "Discord not configured. Set up via:"
    echo "1. Create Discord webhook in your server #monitoring channel"
    echo "2. Set DISCORD_MONITORING_WEBHOOK environment variable"
    echo "3. Or create config file at: $CONFIG_FILE"
fi
