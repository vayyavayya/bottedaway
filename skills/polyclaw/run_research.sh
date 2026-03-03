#!/bin/bash
# POLYCLAW RESEARCH CRON - Every 6 hours
# Flow: scanner → top 5 markets → research.py on each → save results
# Cost cap: $2 per run (5 markets × $0.30 = $1.50, with buffer)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$HOME/.openclaw/workspace"
OUTPUT_DIR="$WORKSPACE_DIR/analysis/daily-briefs"
LOG_FILE="$WORKSPACE_DIR/logs/polyclaw-research.log"

# Create directories
mkdir -p "$OUTPUT_DIR"
mkdir -p "$WORKSPACE_DIR/logs"

# Timestamp for this run
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=============================================="
echo "🤖 POLYCLAW RESEARCH CRON - $TIMESTAMP"
echo "=============================================="

# Activate virtual environment and run
cd "$SCRIPT_DIR"
source "$SCRIPT_DIR/.venv/bin/activate"

# Run the cron research wrapper
python3 "$SCRIPT_DIR/cron_research.py"

echo "=============================================="
