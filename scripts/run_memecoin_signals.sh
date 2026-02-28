#!/bin/bash
# Memecoin Signal Engine - Twice Daily Run
# Runs at 8am and 8pm CET

set -e

REPO_DIR="$HOME/.openclaw/workspace/bottedaway"
LOG_DIR="$REPO_DIR/logs"
LOG_FILE="$LOG_DIR/memecoin-signals-$(date +%Y%m%d-%H%M).log"

# Create log directory
mkdir -p "$LOG_DIR"

# Change to repo directory
cd "$REPO_DIR"

echo "========================================" >> "$LOG_FILE"
echo "Memecoin Signal Engine - $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Run the signal engine
python3 -c "
import sys
sys.path.insert(0, 'skills/memecoin')
sys.path.insert(0, 'skills/polymarket')
sys.path.insert(0, 'scanner_engines/src')

from memecoin_integration import MemecoinSignalEngine
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('$LOG_FILE', mode='a')
    ]
)

print('🚀 Starting Memecoin Signal Engine...')
print('')

engine = MemecoinSignalEngine(paper_mode=True)

# Run discovery
signals = engine.discover_and_trade(chains=['solana', 'base'], min_volume=10000)

if signals:
    print('')
    print('=' * 70)
    print(f'🎯 Generated {len(signals)} signals')
    print('=' * 70)
else:
    print('')
    print('No actionable signals this cycle.')

# Print stats
stats = engine.get_stats()
print('')
print('Engine Stats:')
print(f'  Candidates: {stats.get(\"candidates\", 0)}')
print(f'  Signals Total: {stats.get(\"signals_total\", 0)}')
print(f'  Entry Signals: {stats.get(\"signals_entry\", 0)}')
" 2>&1 | tee -a "$LOG_FILE"

echo "" >> "$LOG_FILE"
echo "Completed at $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Keep only last 30 log files
ls -t "$LOG_DIR"/memecoin-signals-*.log | tail -n +31 | xargs -r rm

echo "✅ Memecoin signal scan complete"
