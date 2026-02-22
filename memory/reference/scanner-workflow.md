# Scanner Workflow

How the multi-source memecoin scanner operates.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   MEMECOIN SCANNER STACK                    │
├─────────────────────────────────────────────────────────────┤
│  DATA SOURCES                                               │
│  ├── CoinGecko (trending)                                   │
│  ├── Birdeye.so (Solana tokens + OHLCV)                    │
│  ├── DexScreener (boosted tokens, multi-chain)             │
│  └── GMGN.ai (web reference for smart money)               │
│                                                             │
│  VERIFICATION                                               │
│  ├── Solscan (Solana contract verification)                │
│  ├── BaseScan (Base L2 verification)                       │
│  └── Bubble Maps (holder distribution)                     │
│                                                             │
│  PATTERN ENGINES (scanner_v3.py)                           │
│  ├── Engine A: 12h EMA50 reclaim                           │
│  ├── Engine B: 4h EMA50 reclaim after dump                 │
│  └── Engine C: 1h EMA50 hold after pump                    │
│                                                             │
│  OUTPUT                                                     │
│  ├── Sweet spot matches ($100K-$500K MC)                   │
│  ├── Other trending (outside range)                        │
│  └── Due diligence checklist                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Cron Schedule

| Job | Schedule | Action |
|-----|----------|--------|
| `memecoin-scanner-720min` | Every 12h (2PM, 2AM) | Run discovery + analysis |
| `diary-telegram-update` | Daily 9AM | Summary to Telegram |

---

## Manual Execution

```bash
# Run full scanner
python3 /Users/pterion2910/.openclaw/workspace/scripts/memecoin-scanner.sh

# Run with pattern engines (watchlist)
cd scanner_engines && python3 scanner_v3.py --all
```

---

## Target Criteria (Hardcoded)

```python
TARGET_MIN_MC = 100_000      # $100K minimum
TARGET_MAX_MC = 500_000      # $500K maximum  
MIN_LIQUIDITY = 10_000       # $10K minimum
```

---

## Output Locations

- **Console:** Real-time results
- **Log:** `memory/archive/scanner-YYYY-MM-DD.log`
- **Telegram:** Alerts sent to configured channel

---

## File Locations

| Component | Path |
|-----------|------|
| Main scanner | `scripts/memecoin-scanner.sh` |
| Pattern engines | `scanner_engines/scanner_v3.py` |
| Birdeye module | `scanner_engines/src/data/birdeye.py` |
| DexScreener module | `scanner_engines/src/data/dexscreener.py` |
| Telegram formatter | `scanner_engines/src/formatters/telegram.py` |

---

*Last updated: 2026-02-14*
