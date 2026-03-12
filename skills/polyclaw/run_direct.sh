#!/bin/bash
# POLYCLAW Direct Runner - Bypasses agentTurn to avoid tools schema bug
# Runs research pipeline directly without LLM agent wrapper

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate venv
source .venv/bin/activate

# Create log directory
mkdir -p /Users/pterion2910/.openclaw/workspace/logs
LOG_FILE="/Users/pterion2910/.openclaw/workspace/logs/polyclaw-direct-$(date +%Y%m%d_%H%M%S).log"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "========================================"
echo "POLYCLAW DIRECT RUNNER - $(date)"
echo "========================================"

# Step 1: Run scanner
echo ""
echo "📊 Step 1: Scanning markets..."
python3 scanner.py

# Step 2: Run research on top markets
echo ""
echo "🔬 Step 2: Researching top markets..."
python3 cron_research.py

echo ""
echo "✅ Complete! Log: $LOG_FILE"
echo "========================================"
