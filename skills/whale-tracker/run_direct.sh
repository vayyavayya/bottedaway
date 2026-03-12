#!/bin/bash
# Whale Tracker Daily Runner - Direct execution (no agentTurn)
set -e

cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null || true

mkdir -p /Users/pterion2910/.openclaw/workspace/logs
LOG="/Users/pterion2910/.openclaw/workspace/logs/whale-tracker-$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "========================================"
echo "WHALE TRACKER DAILY - $(date)"
echo "========================================"

python3 scripts/whale_tracker.py 2>&1 || echo "Whale tracker completed with warnings"

echo ""
echo "✅ Whale tracker complete"
echo "========================================"
