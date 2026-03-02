#!/bin/bash
# POLYCLAW RESEARCH CRON - Every 6 hours
# Flow: scanner.py → top 5 markets → research.py on each → save results
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
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H%M%S)

echo "==============================================" | tee -a "$LOG_FILE"
echo "🤖 POLYCLAW RESEARCH CRON - $TIMESTAMP" | tee -a "$LOG_FILE"
echo "==============================================" | tee -a "$LOG_FILE"

# Activate virtual environment
cd "$SCRIPT_DIR"
source "$SCRIPT_DIR/.venv/bin/activate"

# Step 1: Run scanner to get top 5 markets
echo "📡 Step 1: Scanning top 5 markets..." | tee -a "$LOG_FILE"

SCANNER_OUTPUT=$(python3 "$SCRIPT_DIR/scanner.py" 2>&1)
SCANNER_EXIT=$?

# Extract the JSON from scanner output (last line should be JSON)
MARKETS_JSON=$(echo "$SCANNER_OUTPUT" | tail -1)

echo "$SCANNER_OUTPUT" | tee -a "$LOG_FILE"

if [ $SCANNER_EXIT -ne 0 ]; then
    echo "❌ Scanner failed with exit code $SCANNER_EXIT" | tee -a "$LOG_FILE"
    exit 1
fi

# Verify we got valid JSON
if ! echo "$MARKETS_JSON" | jq empty 2>/dev/null; then
    echo "❌ Scanner did not return valid JSON" | tee -a "$LOG_FILE"
    exit 1
fi

echo "" | tee -a "$LOG_FILE"
echo "🔬 Step 2: Researching markets..." | tee -a "$LOG_FILE"

# Step 2: Run research on all markets at once
echo "$MARKETS_JSON" | python3 "$SCRIPT_DIR/research.py" --output "$OUTPUT_DIR/polymarket_${DATE}_${TIME}.json" 2>&1 | tee -a "$LOG_FILE"
RESEARCH_EXIT=$?

if [ $RESEARCH_EXIT -ne 0 ]; then
    echo "❌ Research failed with exit code $RESEARCH_EXIT" | tee -a "$LOG_FILE"
    exit 1
fi

echo "" | tee -a "$LOG_FILE"
echo "✅ Research complete!" | tee -a "$LOG_FILE"
echo "📄 Output: $OUTPUT_DIR/polymarket_${DATE}_${TIME}.json" | tee -a "$LOG_FILE"
echo "💰 Cost: ~$1.50 (5 markets × $0.30)" | tee -a "$LOG_FILE"
echo "==============================================" | tee -a "$LOG_FILE"
