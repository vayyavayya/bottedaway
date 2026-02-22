# Whale Tracker - Quick Reference

## Setup

### 1. Add Wallets

Paste wallet addresses and I'll add them to the watchlist:

```
/scripts/add_wallet.sh <address> [label] [notes]
```

Or manually edit: `data/whales/whales.json`

### 2. Configure Telegram (Optional)

Set environment variables:
```bash
export WHALE_TELEGRAM_BOT_TOKEN="your_bot_token"
export WHALE_TELEGRAM_CHANNEL="@whalesarebitches"
```

### 3. Run

Manual run:
```bash
cd /Users/pterion2910/.openclaw/workspace/skills/whale-tracker
python scripts/whale_tracker.py
```

With force (ignore 24h cooldown):
```bash
python scripts/whale_tracker.py --force
```

Dry run (check what would happen):
```bash
python scripts/whale_tracker.py --dry-run
```

## Schedule

Cron job: `whale-tracker-daily-9am`
- Runs daily at 09:00 Europe/Berlin
- Auto-enforces 24h cooldown between runs

## Output Files

| File | Description |
|------|-------------|
| `data/reports/YYYY-MM-DD.html` | Daily archived report |
| `data/reports/latest.html` | Most recent report |
| `data/whales/snapshots/YYYY-MM-DD.json` | Raw daily data |
| `data/whales/candidates.json` | Auto-discovered wallets |

## Scoring System

**Engine A: Market Structure (40%)**
- Age scoring (4-10 days = +20)
- Whale confirmation (+15 if >=2 wallets)

**Engine B: Flow + Liquidity (35%)**
- Liquidity depth
- 24h volume

**Engine C: Risk / Rug Surface (25%)**
- Holder concentration
- Authorities (mint/freeze)
- LP lock status

**Composite:** 0.40×A + 0.35×B + 0.25×C

## Strategy Gates

| Gate | Threshold | Fail Action |
|------|-----------|-------------|
| Liquidity | < $25,000 | REJECT |
| Volume | < $50,000 | REJECT |
| Top10 Concentration | > 35% | REJECT |
| Structure | A_score < 40 | REJECT |
| Whale Confirm | >= 2 wallets | Boost priority |

## Output Categories

- **PASS:** Composite >= 60, all gates cleared
- **WATCH:** High potential but needs retest/confirmation
- **REJECT:** Failed one or more gates

## Wallet Lifecycle

### Auto-Add Candidates
A wallet is auto-added as candidate if:
- Interacted with >= 5 same tokens as tracked wallets (30d)
- Positive realized gains proxy
- Not exchange/contract
- Confidence >= 0.7

### Auto-Remove
Wallets removed if:
- Inactive for 45+ days
- Repeated net-loser patterns (30d)

## API Dependencies

- **Helius** (recommended): `HELIUS_API_KEY`
- **Solscan** (fallback): `SOLSCAN_API_KEY`
- **DexScreener**: No key needed
- **Telegram**: `WHALE_TELEGRAM_BOT_TOKEN`

## Example Output

```
============================================================
WHALETRACKER COMPLETE — 2026-02-17
============================================================
Wallets: 5
Tokens: 12
  PASS: 2
  WATCH: 3
  REJECT: 7
Report: data/reports/2026-02-17.html
============================================================
```

## Troubleshooting

**No transactions found:**
- Check wallet addresses are correct
- Verify API keys are set
- Check rate limits

**Missing data:**
- APIs may be rate-limited
- New tokens may not be indexed yet
- Some DEXs not covered

**Telegram not posting:**
- Check `WHALE_TELEGRAM_BOT_TOKEN` is set
- Verify bot is admin in channel
- Check channel name format (@channelname)
