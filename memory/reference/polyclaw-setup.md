# PolyClaw - Polymarket Trading Skill

Prediction market trading integration for OpenClaw.

## Overview

**PolyClaw** enables autonomous trading on Polymarket prediction markets:
- Browse trending markets
- Execute trades (YES/NO positions)
- Track positions with live P&L
- Discover hedging opportunities via LLM analysis

## Installation Status

- [ ] Clone repository
- [ ] Install dependencies (uv)
- [ ] Configure environment
- [ ] Set wallet approvals
- [ ] Test first trade

## Required Credentials

### 1. Chainstack Node (Polygon RPC)
- **Purpose**: Blockchain connection for trades
- **Get**: https://console.chainstack.com (free tier)
- **Format**: `https://polygon-mainnet.core.chainstack.com/YOUR_KEY`

### 2. OpenRouter API Key
- **Purpose**: LLM analysis for hedge discovery
- **Get**: https://openrouter.ai/settings/keys
- **Format**: `sk-or-v1-...`

### 3. Trading Wallet
- **Purpose**: Execute trades on Polygon
- **⚠️ WARNING**: Use small amounts only, withdraw regularly
- **Needs**: POL for gas, USDC.e for trading

## Configuration

Add to `~/.openclaw/openclaw.json`:

```json
{
  "skills": {
    "entries": {
      "polyclaw": {
        "enabled": true,
        "env": {
          "CHAINSTACK_NODE": "https://polygon-mainnet.core.chainstack.com/YOUR_KEY",
          "POLYCLAW_PRIVATE_KEY": "0x...",
          "OPENROUTER_API_KEY": "sk-or-v1-..."
        }
      }
    }
  }
}
```

## Commands

### Market Browsing
```bash
polyclaw markets trending          # Top markets by 24h volume
polyclaw markets search "election" # Search by keyword
polyclaw market <id>               # Market details
```

### Trading
```bash
polyclaw wallet status             # Check balances
polyclaw wallet approve            # One-time approvals
polyclaw buy <id> YES 50          # Buy $50 YES position
polyclaw buy <id> NO 50           # Buy $50 NO position
```

### Position Tracking
```bash
polyclaw positions                 # List open positions
polyclaw position <id>             # Detailed view
```

### Hedge Discovery
```bash
polyclaw hedge scan                # Scan for opportunities
polyclaw hedge scan --query "topic"
polyclaw hedge analyze <id1> <id2>
```

## Trading Flow

1. **One-time setup**: `polyclaw wallet approve` (6 approvals, ~0.01 POL)
2. **Browse**: Find markets with edge
3. **Execute**: Split + CLOB (buy YES, auto-sell NO)
4. **Track**: Monitor positions
5. **Exit**: Sell early or hold to resolution

## Hedge Discovery Logic

Uses LLM-powered **contrapositive analysis**:
- Only logically necessary implications (not correlations)
- Coverage tiers:
  - T1: ≥95% coverage
  - T2: 90-95% coverage
  - T3: 85-90% coverage

Example: If Market A (Trump wins) → Market B (Republican president), then YES on A + NO on B = hedge.

## Risk Management

- Trade only what you can afford to lose
- Small position sizes ($25-100)
- Diversify across markets
- Monitor correlation decay
- Withdraw profits regularly

## Files

- `SKILL.md` - OpenClaw manifest
- `scripts/polyclaw.py` - CLI dispatcher
- `scripts/trade.py` - Split + CLOB execution
- `scripts/hedge.py` - LLM hedge discovery
- `~/.openclaw/polyclaw/positions.json` - Position storage

## Links

- GitHub: https://github.com/chainstacklabs/polyclaw
- Polymarket: https://polymarket.com
- Chainstack: https://chainstack.com

---

**Status**: Ready to install
**Next Action**: Run `bash scripts/install-polyclaw.sh`
