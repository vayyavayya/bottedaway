# Skill: memecoin-scanner

## Description
Multi-source memecoin discovery and filtering system. Scans CoinGecko, Birdeye, DexScreener for coins matching specific criteria.

## When to Use
- Looking for new memecoin opportunities in $100K-$500K MC range
- Need coins aged 4-10 days (survivorship bias window)
- Want automated daily/periodic scans
- Filtering out rugs and fresh launches

## When NOT to Use
- Looking for established coins ($1M+ MC) — use coingecko skill
- Need real-time price alerts — use price-monitor skill
- Want social sentiment analysis — use twitter-sentiment skill
- Looking for Base chain only — this scans Solana primarily

## Negative Examples (Failures)

### Scanner Misses (Technical)
1. **Missed $ME coin (Feb 15, 2026)**: Initially only scanned "trending" and "boosted" coins. Missed high-volume non-boosted tokens.
   - Fix: Added "latest pairs" and "top volume" endpoints
   
2. **Age filter too broad**: Initially only had minimum age (4+ days). Included 76-day-old coins like Franklin.
   - Fix: Added maximum age (10 days) — sweet spot is 4-10 days

3. **Birdeye API limit too low**: Only fetched top 50 tokens, missed volume leaders.
   - Fix: Increased to 100 tokens

### Trading Failures ($ME Post-Mortem, Feb 16, 2026)
**What went wrong:**
- Bought $ME at -38% dip → kept dipping to -70%
- No exit strategy, just watched it bleed
- No momentum filter — negative 24h when added
- Held too long without time-based cutoff

**Fixes Applied to Scanner:**
1. **Momentum filter REQUIRED** — Only coins with positive 24h change OR recent pump with consolidation
2. **No deep dip buying** — Skip coins <-20% (falling knives)
3. **Stop loss guidance** — Scanner now suggests stop levels for each pick
4. **Time-based exit** — Flag coins that haven't moved in 48h
5. **Position sizing note** — Reminder: small positions (1-2% max) for memecoins
6. **Trend confirmation** — Require 2+ green candles or EMA reclaim

## Trading Rules (Hardcoded)
```yaml
# Entry Criteria
MIN_24H_CHANGE: -5        # Reject coins <-5% (falling)
MAX_24H_CHANGE: 200       # Reject coins >200% (parabolic top)
PREFERRED_RANGE: 5-100    # Sweet spot: positive but not overheated

# Exit Guidance (added to output)
STOP_LOSS: -15            # Suggested stop: -15% from entry
TIME_STOP: 48h            # If no move in 48h, reconsider
PROFIT_TAKING: "2x->5x->10x"  # Laddered exits

# Risk Management
POSITION_SIZE: "1-2% max" # Never more than 2% portfolio
MAX_CONCURRENT: 5         # Limit simultaneous positions
```

## Dependencies
```bash
# System
python3 >= 3.10
requests

# APIs (env vars)
BIRDEYE_API_KEY  # Optional, has default
```

## Usage
```bash
# Full scan
python3 skills/crypto/memecoin-scanner/scan.py

# Lookup specific token
python3 skills/crypto/memecoin-scanner/scan.py <contract_address> [chain]
```

## Configuration
Edit `config.yaml`:
```yaml
TARGET_MIN_MC: 100000
TARGET_MAX_MC: 500000
MIN_AGE_DAYS: 4
MAX_AGE_DAYS: 10
SOURCES:
  - coingecko
  - birdeye
  - dexscreener_boosted
  - dexscreener_latest
  - dexscreener_volume
```

## Output
- Console: Human-readable table
- Log: `/logs/scanner-YYYY-MM-DD.log`
- Report: `/mnt/data/reports/memecoin_scan_YYYYMMDD_HHMM.html`

## Artifacts
All scan results saved to `/mnt/data/reports/` with timestamp.

## Handoff Protocol
When context compacts:
1. Save last scan report to `/mnt/data/reports/`
2. Update SKILL_MANIFEST with findings
3. Note any watchlist additions in memory
