#!/bin/bash
# Quick script to add wallets to whale tracker

WHALES_FILE="/Users/pterion2910/.openclaw/workspace/skills/whale-tracker/data/whales/whales.json"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <wallet_address> [label] [notes]"
    echo "Example: $0 7yQYZDqR... 'Smart Whale' 'Consistent 10x caller'"
    exit 1
fi

ADDRESS="$1"
LABEL="${2:-}"
NOTES="${3:-}"

python3 /Users/pterion2910/.openclaw/workspace/skills/whale-tracker/scripts/whale_tracker.py \
    --add-wallet "$ADDRESS" \
    --label "$LABEL" \
    --notes "$NOTES"

echo ""
echo "Current watchlist:"
cat "$WHALES_FILE" | python3 -m json.tool
