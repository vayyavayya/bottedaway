#!/bin/bash
# POLYCLAW Production Trading Runner
# Properly loads credentials from keys.env

set -e

# Get script directory (resolve symlinks)
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load credentials from keys.env (in parent directory)
KEYS_ENV="$SCRIPT_DIR/keys.env"
if [ -f "$KEYS_ENV" ]; then
    export $(grep -v '^#' "$KEYS_ENV" | xargs)
    echo "✅ Loaded credentials from keys.env"
else
    echo "❌ Error: keys.env not found at $KEYS_ENV"
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
if [ -f "$REPO_DIR/skills/polyclaw/.venv/bin/activate" ]; then
    source "$REPO_DIR/skills/polyclaw/.venv/bin/activate"
    echo "✅ Activated virtual environment"
else
    echo "⚠️ Warning: Virtual environment not found"
fi

# Run the trading script
echo "🚀 Starting POLYCLAW trading cycle..."
echo ""

python3 polyclaw.py positions

# Deactivate venv if activated
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
fi

echo ""
echo "✅ Trading cycle complete"
