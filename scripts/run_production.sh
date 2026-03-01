#!/bin/bash
# POLYCLAW Production Trading Runner
# Properly loads credentials from keys.env

set -e

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load credentials from keys.env
if [ -f "$SCRIPT_DIR/keys.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/keys.env" | xargs)
    echo "✅ Loaded credentials from keys.env"
else
    echo "❌ Error: keys.env not found at $SCRIPT_DIR/keys.env"
    exit 1
fi

# Verify POLYMARKET_PK is set
if [ -z "$POLYMARKET_PK" ]; then
    echo "❌ Error: POLYMARKET_PK not set in keys.env"
    exit 1
fi

echo "🔑 Private key configured: ${POLYMARKET_PK:0:10}...${POLYMARKET_PK: -6}"

# Change to script directory
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -f "$REPO_DIR/skills/polyclaw/venv/bin/activate" ]; then
    source "$REPO_DIR/skills/polyclaw/venv/bin/activate"
    echo "✅ Activated virtual environment"
fi

# Run the trading script
echo "🚀 Starting POLYCLAW trading cycle..."
echo ""

python3 polymarket_integration.py

# Deactivate venv if activated
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
fi

echo ""
echo "✅ Trading cycle complete"
