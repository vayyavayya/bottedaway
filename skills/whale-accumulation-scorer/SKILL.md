---
name: whale-accumulation-scorer
description: Token-centric whale accumulation scorer. Analyzes any token for whale buying patterns, produces 0-1 confidence scores, and layers onto Engine A signals for combined Kelly-sized entries. Use when you need dynamic whale discovery (not static watchlist) and real-time signal enrichment.
---

# Whale Accumulation Scorer

Token-centric whale discovery system that analyzes any token for smart money accumulation patterns. Produces normalized 0-1 confidence scores designed to layer onto Engine A (EMA reclaim) signals for combined signal strength and Kelly criterion position sizing.

## New Signal Patterns (March 2026 Update)

### Pattern 7: Dead Coin Revival / CTO Accumulation (+0.25 bonus)
**Historical precedent:** TROLL sat dormant at sub-$25K market cap for 8 months while wallets quietly accumulated (top 100 reached 43% of supply).

**Detection criteria:**
- Token age > 90 days
- Market cap < $500K OR price within 10% of all-time low
- Top 100 holder concentration increasing over last 30 days while price flat

**Why it works:** Catches coins before anyone is paying attention. Requires holder concentration tracking over time.

### Pattern 8: Market Maker / Institutional Entry (+0.20 bonus)
**Historical precedent:** NEIRO saw Wintermute accumulate 53M tokens and GSR Markets buy 4% of circulating supply before the pump.

**Detection:** Known market maker wallets (Wintermute, GSR, DWF Labs, Cumberland, Jump, Amber) accumulating >$50K

**Config:** See `config/market_makers.json` for wallet addresses. Wallets tagged as `label: "market_maker"` in WalletProfile.

### Pattern 9: Fresh Wallet Accumulation Spike (+0.15 bonus, 2x if 3+ wallets)
**Historical precedent:** NEIRO and WIF saw fresh wallets (<7 days old) withdrawing from CEXes and immediately buying.

**Detection:**
- Wallet age < 7 days
- Large purchase > $50K
- Funds sourced from exchange hot wallet
- 3+ fresh wallets in 48h = 2x multiplier

### Pattern 10: Supply Concentration Acceleration (±0.15-0.20 context-dependent)
**Historical precedent:** NEIRO had 4 wallets withdraw 24.2% of supply from exchanges.

**Detection:**
- Top 10 holders collectively increase share by >5% in 7 days
- **Bullish (+0.15):** Price flat/down during concentration (stealth loading)
- **Bearish (-0.20):** Price pumping during concentration (manipulation/rug risk)

## Purpose

Unlike `whale-tracker` (which monitors 5 curated wallets for daily digests), this module:

- **Discovers whales dynamically** per token via Birdeye top holders API
- **Scores accumulation patterns** using 5 components (buy/sell ratio, whale count, velocity, wallet quality, size vs liquidity)
- **Layers onto Engine A** via `enrich_engine_a_signal()` — every token in STALKING phase gets whale score boost
- **Outputs Kelly-ready probabilities** — maps 0-1 score to 0.45-0.65 probability range

## Architecture

```
token_address → WhaleTracker.analyze_token() → WhaleSignal(score, phase)
                                                    ↓
Engine A (EMA reclaim) ───────┬─────────────────────┘
                              ↓
              enrich_engine_a_signal() → combined_score
                              ↓
              kelly_edge_estimate() → probability p
                              ↓
              Kelly sizing: f* = (p*b - q) / b
```

## Quick Start

```python
from whale_tracker import WhaleTracker

tracker = WhaleTracker()

# Analyze a single token
signal = tracker.analyze_token("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
print(f"Score: {signal.score:.2f}, Phase: {signal.phase.value}")

# Layer onto Engine A
ema_score = 0.75  # From Engine A STALKING phase
combined, reason = tracker.enrich_engine_a_signal(token_addr, ema_score)
print(f"Combined: {combined:.2f} — {reason}")

# Get Kelly probability
p = tracker.kelly_edge_estimate(signal)  # 0.45-0.65 range
```

## Signal Flow (Engine A Integration)

In your `signal_engine.py`, for every token in STALKING phase:

```python
# Get Engine A score (EMA reclaim quality)
engine_a_score = engine_a.analyze(token_addr)  # 0-1

# Layer whale accumulation
whale_score, whale_meta = tracker.get_signal_for_engine(token_addr)

# Combined score (60% EMA + 40% whale)
if whale_score > 0:
    combined = (engine_a_score * 0.6) + (whale_score * 0.4)
    # Bonus for convergence
    if engine_a_score > 0.6 and whale_score > 0.6:
        combined = min(combined * 1.15, 1.0)
else:
    combined = engine_a_score * 0.7  # Discount without whale confirmation

# Kelly sizing
if combined > 0.6:
    p = 0.45 + (combined * 0.20)  # Map to 0.45-0.65
    kelly_fraction = (p * 2 - (1 - p)) / 2  # Assuming b=2 (2:1 payoff)
    position_size = kelly_fraction * bankroll
```

## Accumulation Phases

| Phase | Score Range | Meaning | Action |
|-------|-------------|---------|--------|
| `NONE` | 0.0-0.2 | No whale activity | Skip |
| `EARLY_ACCUMULATION` | 0.2-0.4 | Scattered buys, wallet activation | Watch |
| `ACTIVE_ACCUMULATION` | 0.4-0.7 | Clear pattern, multiple whales | **Consider entry** |
| `HEAVY_ACCUMULATION` | 0.7+ | Aggressive buying | **Strong signal** |
| `DEAD_COIN_REVIVAL` | Any | Dormant token + concentration | **Highest alpha** |
| `INSTITUTIONAL_ENTRY` | Any | Market maker accumulation | **Strong signal** |
| `DISTRIBUTION` | Any | Sellers > buyers | **Avoid/Exit** |

## Scoring Components

| Component | Weight | Description |
|-----------|--------|-------------|
| Buy/Sell Ratio | 25% | Net flow direction (sigmoid mapped) |
| Whale Count | 20% | Distinct independent buyers |
| Velocity | 20% | Acceleration vs deceleration (4h vs 24h rate) |
| Wallet Quality | 15% | Smart money score (dormancy + win rate + hold time + MM bonus) |
| Size vs Liquidity | 20% | Big fish in small pond bonus |

### Bonus Signals (Stackable)

| Bonus | Weight | Trigger |
|-------|--------|---------|
| Dead Coin Revival | +0.25 | Token age >90d, MC <$500K, near ATL, concentration increasing |
| Market Maker Entry | +0.20 | Known MM wallet (Wintermute/GSR/DWF) buying >$50K |
| Fresh Wallet | +0.15 | Wallet age <7d, CEX source, >$50K (2x if 3+ in 48h) |
| Supply Concentration (Bullish) | +0.15 | Top-10 +5% in 7d + price flat/down |
| Supply Concentration (Risk) | -0.20 | Top-10 +5% in 7d + price pumping |
| Dormant Reactivation | +0.15 | 60+ day dormant wallet starts buying |
| Exchange Withdrawal | +0.20 | Wallet received from CEX before buying |

## Credentials

### Secure Storage (Recommended)

Store Helius API key in isolated credentials file (not `.env`):

```bash
mkdir -p ~/.config/helius
cat > ~/.config/helius/credentials.json << 'EOF'
{
  "api_key": "your_helius_key_here"
}
EOF
chmod 600 ~/.config/helius/credentials.json
```

This matches the pattern used by `whale-tracker` and follows credential hygiene best practices.

### Environment Variables (Alternative)

```bash
# REQUIRED: Birdeye API
export BIRDEYE_API_KEY=your_birdeye_key

# OPTIONAL: Helius (if not using credentials file)
export HELIUS_API_KEY=your_helius_key
```

## Dependencies

```bash
pip install websockets aiohttp requests python-dotenv
```

## Real-Time Streaming (Optional)

```python
import asyncio
from whale_tracker import WhaleTracker, WhaleStreamMonitor

tracker = WhaleTracker()
monitor = WhaleStreamMonitor(tracker)

# Register callback
def on_alert(signal):
    print(f"🐋 Whale alert: {signal.token_symbol} score={signal.score:.2f}")

monitor.on_whale_alert(on_alert)

# Start streaming
asyncio.run(monitor.start(["token_addr_1", "token_addr_2"]))
```

## Batch Scanning

```python
# Scan multiple tokens from discovery
tokens = birdeye.discover_ema_candidates("solana")
signals = tracker.batch_scan([t["address"] for t in tokens])

# Filter actionable
actionable = [s for s in signals if s.is_actionable]
```

## Files

- `scripts/whale_tracker.py` — Core tracker with scoring engine
- `scripts/signal_engine.py` — Example Engine A integration (create this)
- `config/market_makers.json` — Known market maker wallet addresses
- `data/` — Runtime cache for wallet profiles

## Difference from whale-tracker

| | `whale-tracker` | `whale-accumulation-scorer` |
|---|---|---|
| **Input** | 5 static curated wallets | Any token address |
| **Discovery** | Monitors known whales | Discovers whales per token |
| **Output** | PASS/WATCH/REJECT with Engine A/B/C | 0-1 score for signal layering |
| **Use case** | Daily "what did my whales buy?" digest | Real-time signal enrichment |
| **Integration** | Standalone reports | Feeds into Kelly-sized execution |

Keep both — they serve different purposes.
