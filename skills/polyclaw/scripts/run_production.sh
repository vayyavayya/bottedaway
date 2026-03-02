#!/bin/bash
# POLYCLAW Production Trading Runner
# Uses direct API calls to bypass EU geoblock

set -e

# Get script directory (resolve symlinks)
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Load credentials from keys.env (in parent directory - polyclaw/)
KEYS_ENV="$(cd "$SCRIPT_DIR/.." && pwd)/keys.env"
if [ -f "$KEYS_ENV" ]; then
    export $(grep -v '^#' "$KEYS_ENV" | xargs)
    echo "✅ Loaded credentials from keys.env"
else
    echo "⚠️ Warning: keys.env not found at $KEYS_ENV (API mode still works)"
fi

# Check for private key (optional for API mode)
if [ -n "$POLYMARKET_PK" ]; then
    echo "🔑 Trading key configured: ${POLYMARKET_PK:0:10}...${POLYMARKET_PK: -6}"
else
    echo "⚠️  No trading key - API mode only (read-only)"
fi

echo ""
echo "🌐 POLYCLAW Trading Interface"
echo "   EU Geoblock Workaround: ACTIVE"
echo "   Data Source: gamma-api.polymarket.com"
echo ""

# Change to script directory
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
VENV_PATH="$(cd "$SCRIPT_DIR/.." && pwd)/.venv/bin/activate"
if [ -f "$VENV_PATH" ]; then
    source "$VENV_PATH"
    echo "✅ Virtual environment active"
else
    echo "⚠️  Using system Python"
fi

echo ""

# Check system status
echo "📊 System Status:"
python3 polyclaw.py status
echo ""

# Fetch trending markets
echo "📈 Fetching Live Markets..."
python3 polyclaw.py markets trending
echo ""

# Show open positions
echo "💼 Open Positions:"
python3 polyclaw.py positions
echo ""

# Deactivate venv if activated
if [ -n "$VIRTUAL_ENV" ]; then
    deactivate
fi

echo "✅ POLYCLAW cycle complete"
