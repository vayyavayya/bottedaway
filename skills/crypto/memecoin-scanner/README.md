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
1. **Missed $ME coin (Feb 15, 2026)**: Initially only scanned "trending" and "boosted" coins. Missed high-volume non-boosted tokens.
   - Fix: Added "latest pairs" and "top volume" endpoints
   
2. **Age filter too broad**: Initially only had minimum age (4+ days). Included 76-day-old coins like Franklin.
   - Fix: Added maximum age (10 days) — sweet spot is 4-10 days

3. **Birdeye API limit too low**: Only fetched top 50 tokens, missed volume leaders.
   - Fix: Increased to 100 tokens

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
