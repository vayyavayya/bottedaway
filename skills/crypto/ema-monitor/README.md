# Skill: ema-monitor

## Description
Technical indicator monitoring for specific tokens. Tracks price vs EMA on configurable timeframe and alerts on breakdown.

## When to Use
- Holding a position and want automated exit signals
- Need 24/7 monitoring without manual chart watching
- Want alerts on key support/resistance breaks
- Managing multiple positions with different timeframes

## When NOT to Use
- Just checking price once — use dexscreener or coingecko
- Need complex multi-indicator signals — use tradingview
- Want predictive analysis — this is reactive, not predictive
- Token has no liquidity or volume — EMA meaningless on illiquid pairs

## Negative Examples (Failures)
1. **API vs Chart Mismatch (Feb 15, 2026)**: Birdeye OHLC calculated EMA50 at $0.000158, but DexScreener TradingView showed $0.00020. Significant difference caused false confidence.
   - Fix: Added MANUAL_EMA50 override config
   - Documented: Always verify API data matches visual chart

2. **Insufficient candle data**: Initially requested 50 candles but API returned fewer. EMA calculation failed silently.
   - Fix: Added candle count validation and fallback

3. **Alert fatigue**: Initially considered alerting every check below EMA.
   - Fix: Added 6-hour cooldown, require 2+ sustained below or new cross

## Dependencies
```bash
# System
python3 >= 3.10
requests

# APIs
BIRDEYE_API_KEY  # For OHLC data
DEXSCREENER  # For current price (no key needed)
```

## Usage
```bash
# Configure token
cp config/example.token.yaml config/tokens/ME.yaml
# Edit: address, chain, timeframe, ema_period

# Run monitor
python3 skills/crypto/ema-monitor/monitor.py --config config/tokens/ME.yaml
```

## Configuration
```yaml
token:
  address: "3wshHmD3aBx3wfHPeGWq2o38BNpVaEf7iFf3gYgRpump"
  chain: "solana"
  symbol: "ME"
  
indicator:
  timeframe: "2h"
  ema_period: 50
  manual_ema: 0.00020  # Override API calculation
  
alerts:
  cooldown_hours: 6
  telegram: true
  threshold_pct: 2.0  # Alert when 2% below EMA
```

## Output
- State: `/state/ema-{token}.json`
- Logs: `/logs/ema-monitor.log`
- Alerts: Telegram message on breakdown

## Artifacts
None (stateful monitoring, not report generation).

## Handoff Protocol
When context compacts:
1. Save state file to `/mnt/data/backups/ema-{token}-state.json`
2. Document current EMA level and position status
3. Note any recent alerts in SKILL_MANIFEST
