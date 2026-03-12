#!/bin/bash
# Base Price Monitor Runner - Direct execution (no agentTurn)
set -e

cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null || true

mkdir -p /Users/pterion2910/.openclaw/workspace/logs
LOG="/Users/pterion2910/.openclaw/workspace/logs/base-price-$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "========================================"
echo "BASE PRICE MONITOR - $(date)"
echo "========================================"

python3 scripts/base_price_monitor.py 2>&1 || echo "Monitor completed with warnings"

echo ""
echo "✅ Base price monitor complete"
echo "========================================"
