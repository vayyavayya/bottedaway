# Skill: scanner-watchlist-bridge

## Description
Connects memecoin scanner output to daily watchlist. Automatically adds sweet spot matches (4-10 days, $100K-$500K MC) to the watchlist for engine analysis.

## When to Use
- Want scanner findings automatically tracked
- Don't want to manually copy addresses to watchlist
- Need continuous watchlist updates from market scans

## When NOT to Use
- Want manual control over watchlist (don't use auto-add)
- Scanner is disabled
- Watchlist is at capacity (manage size separately)

## Negative Examples (Failures)
1. **Duplicate entries**: Initially didn't check for existing addresses.
   - Fix: Added address deduplication check

2. **Missing addresses**: Some scanner outputs lacked solscan URLs.
   - Fix: Skip coins without extractable addresses

3. **Watchlist bloat**: Could grow indefinitely.
   - Fix: Age filter (4-10 days) limits additions

## Dependencies
```bash
# System
python3 >= 3.10

# Skills (this skill depends on)
- crypto/memecoin-scanner
- /config/memecoin_watchlist.json
```

## Usage
```bash
# Manual run
python3 skills/automation/scanner-watchlist-bridge/bridge.py

# Cron schedule (runs after scanner)
0 */12 * * *  # Every 12 hours
```

## Configuration
None. Reads scanner output and writes to watchlist file directly.

## Output
- Console: Added/skipped coins
- File: Updates /config/memecoin_watchlist.json

## Artifacts
None (updates state file only).

## Handoff Protocol
When context compacts:
1. Watchlist is saved to git (committed regularly)
2. No special backup needed
