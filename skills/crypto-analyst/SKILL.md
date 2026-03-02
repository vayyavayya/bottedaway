---
name: crypto-analyst
description: Analyze a crypto token using Birdeye price data + whale tracker activity. Generates structured trading signals with entry/exit levels via LLM analysis.
---

# Crypto Analyst

Token analysis pipeline that fetches price data from Birdeye, whale activity from the PUNCH tracker, and generates structured trading signals via LLM analysis.

## Usage

```bash
# Analyze by symbol (known tokens)
python skills/crypto-analyst/analyze.py PUNCH

# Analyze by address
python skills/crypto-analyst/analyze.py NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump

# Analyze on different chain
python skills/crypto-analyst/analyze.py TOKEN --chain ethereum

# Specify address explicitly
python skills/crypto-analyst/analyze.py MYTOKEN --address 0x1234...
```

## Pipeline

1. **Fetch Price Data** (Birdeye API)
   - Current price, 24h change, 1h change
   - Volume (24h) and volume change
   - Liquidity, market cap, FDV
   - Buy/sell ratio and unique wallet count

2. **Fetch Whale Activity** (PUNCH Tracker + Helius)
   - Top holder concentration
   - Recent whale transactions
   - Accumulation/distribution patterns

3. **Technical Analysis**
   - EMA50 reclaim setup detection
   - Volume divergence calculation
   - Support/resistance identification

4. **LLM Analysis** (ClawAnalyst)
   - Sends structured prompt to local Qwen3 or API fallback
   - Returns: signal (buy/sell/hold), confidence, entry/stop/target
   - Includes reasoning, risk factors, catalysts

5. **Save Results**
   - JSON output: `workspace/analysis/crypto/analysis_{SYMBOL}_{DATE}.json`

## Output Format

```json
{
  "meta": {
    "symbol": "PUNCH",
    "address": "NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump",
    "chain": "solana",
    "timestamp": "2026-03-02T21:45:00",
    "analyst_version": "1.0.0"
  },
  "market_data": {
    "price": 0.000123,
    "price_change_24h": 15.5,
    "price_change_1h": 2.3,
    "volume_24h": 500000,
    ...
  },
  "whale_activity": {
    "top_holders": [...],
    "holder_count": 10
  },
  "technical": {
    "ema_reclaim": {"setup_present": true, ...},
    "volume_divergence": {"type": "bullish_accumulation", ...}
  },
  "analysis": {
    "signal": "buy",
    "confidence": 75,
    "entry_price": 0.00012,
    "stop_loss": 0.00010,
    "take_profit": 0.00018,
    "reasoning": "EMA50 reclaim with strong volume...",
    "key_levels": {...},
    "risk_factors": [...],
    "catalysts": [...]
  }
}
```

## Known Token Mappings

| Symbol | Address |
|--------|---------|
| PUNCH | NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump |
| SOL | So11111111111111111111111111111111111111112 |
| USDC | EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v |
| BONK | DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263 |
| WIF | EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm |

## Dependencies

- Birdeye API (via `scanner_engines/src/data/birdeye.py`)
- Helius API key (for whale holder data)
- OpenClaw gateway or OpenRouter API key (for LLM analysis)
- Whale tracker snapshots (optional, for enhanced whale data)

## Environment Variables

```bash
# Required for whale holder data
HELIUS_API_KEY=your_helius_key

# Required for LLM fallback (optional if using local models)
OPENROUTER_API_KEY=your_openrouter_key

# Local model gateway (default: http://localhost:8080)
OPENCLAW_GATEWAY_URL=http://localhost:8080
```

## Files

- `analyze.py` - Main analysis script
- `workspace/analysis/crypto/` - Output directory for JSON results
