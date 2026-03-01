#!/bin/bash
# PolyClaw Trading Skill - Cron Entry Point
# Executes the autonomous prediction market trading bot

set -e

echo "🤖 PolyClaw AutoTrader - $(date)"
echo "================================"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Load credentials from keys.env
if [ -f "$SCRIPT_DIR/keys.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/keys.env" | xargs)
    echo "✅ Loaded credentials from keys.env"
else
    echo "⚠️ Warning: keys.env not found"
fi

# Verify POLYMARKET_PK is set
if [ -z "$POLYMARKET_PK" ]; then
    echo "⚠️ Warning: POLYMARKET_PK not set - some features may not work"
else
    echo "🔑 Private key configured: ${POLYMARKET_PK:0:10}...${POLYMARKET_PK: -6}"
fi

# Activate virtual environment
source "$SCRIPT_DIR/.venv/bin/activate"

# Run the autotrader
python3 "$SCRIPT_DIR/scripts/polyclaw.py" markets trending

echo "================================"
echo "✅ Run complete - $(date)"
