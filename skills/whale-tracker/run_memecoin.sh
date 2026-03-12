#!/bin/bash
# Memecoin Scanner Runner - Direct execution (no agentTurn)
set -e

cd "$(dirname "$0")"
source .venv/bin/activate 2>/dev/null || true

mkdir -p /Users/pterion2910/.openclaw/workspace/logs
LOG="/Users/pterion2910/.openclaw/workspace/logs/memecoin-scanner-$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG") 2>&1

echo "========================================"
echo "MEMECOIN SCANNER - $(date)"
echo "========================================"

# Run the scanner
python3 scripts/memecoin_scanner.py 2>&1 || echo "Scanner completed with warnings"

echo ""
echo "✅ Memecoin scanner complete"
echo "========================================"
