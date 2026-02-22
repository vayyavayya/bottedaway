---
name: whale-tracker
description: Monitor whale wallets, detect new token buys, score them using Engines A/B/C + memecoin strategy filters, generate HTML reports and Telegram alerts. Use when user needs automated whale tracking, smart money signal detection, or daily memecoin buy reports from high-performing wallets.
---

# Whale Tracker

Autonomous whale monitoring system that tracks curated high-performing wallets, detects their new token purchases, scores opportunities using Engines A/B/C, and delivers daily reports.

## Overview

- **Monitors:** Curated wallet addresses with historically consistent trading success
- **Detects:** New token buys within 24h windows
- **Scores:** Engines A (Market Structure), B (Flow + Liquidity), C (Risk/Rug Surface)
- **Filters:** Applies hard strategy gates (liquidity, volume, concentration)
- **Delivers:** Daily HTML reports + Telegram summaries

## Quick Start

1. **Configure wallets:** Edit `data/whales/whales.json`
2. **Set Telegram:** Configure `WHALE_TELEGRAM_BOT_TOKEN` and `WHALE_TELEGRAM_CHANNEL`
3. **Run manually:** `python scripts/whale_tracker.py`
4. **Schedule:** Cron job runs daily at 09:00 Europe/Berlin

## Data Files

### whales.json (canonical watchlist)
```json
{
  "network": "solana",
  "watchlist": [
    {
      "address": "WALLET_ADDRESS",
      "label": "optional_label",
      "added_at": "2026-02-17",
      "source": "manual|auto",
      "confidence": 0.85,
      "notes": "why this wallet matters"
    }
  ]
}
```

### snapshots/YYYY-MM-DD.json (daily raw data)
Aggregated buy events with enrichment data.

### candidates.json (auto-discovered wallets)
Wallets discovered as co-buyers that meet auto-add criteria.

### reports/latest.html & reports/YYYY-MM-DD.html
Generated daily reports.

## Strategy Filters (Hard Gates)

| Gate | Rule | Default |
|------|------|---------|
| Liquidity | >= MIN_LIQUIDITY_USD | $25,000 |
| Volume | >= MIN_VOL_USD | $50,000 |
| Concentration | top10 <= MAX_TOP10_PCT | 35% |
| Structure | Base + retest required | — |
| Whale Confirm | >=2 wallets = boost | — |

## Engine Scoring

**Engine A: Market Structure (40% weight)**
- Trend direction
- EMA50 reclaim/hold on 2h/12h
- Base formation quality
- Breakout + retest quality

**Engine B: Flow + Liquidity (35% weight)**
- Liquidity depth
- 24h volume
- Buy/sell imbalance
- Slippage risk
- Whale clustering

**Engine C: Risk / Rug Surface (25% weight)**
- Holder concentration
- Mint/freeze authorities
- Deployer behavior
- LP lock/burn status
- Contract flags

**Composite:** 0.40×A + 0.35×B + 0.25×C

## Auto-Maintenance

**Auto-add candidates:**
- Interacted with >=5 same tokens as tracked wallets (30d)
- Positive realized gains proxy
- Not exchange/contract
- Confidence >= 0.7

**Auto-remove:**
- Inactive 45+ days
- Repeated net-loser patterns (30d)

## Telegram Output

Posted to @whalesarebitches:
- Date header
- Top 3 PASS tokens (composite + rationale)
- WATCH count
- HTML report link/attachment

## Environment Variables

```bash
WHALE_TELEGRAM_BOT_TOKEN=your_bot_token
WHALE_TELEGRAM_CHANNEL=@whalesarebitches
SOLSCAN_API_KEY=optional_for_rate_limits
HELIUS_API_KEY=optional_for_enhanced_data
```

## Scripts

- `scripts/whale_tracker.py` — Main orchestration
- `scripts/engines.py` — Scoring implementations
- `scripts/report_generator.py` — HTML output
- `scripts/telegram_poster.py` — Telegram delivery

## Cron Setup

Daily at 09:00 Europe/Berlin:
```bash
0 9 * * * cd /path/to/whale-tracker && python scripts/whale_tracker.py
```

## Failure Handling

- API failures: Continue with partial data, mark as "DATA MISSING"
- Missing credentials: Output DRY RUN mode with exact missing vars
- Never block on single failures
