# Memecoin Trading Rules

Systematic rules for memecoin trading and risk management.

---

## Target Criteria

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| **Market Cap** | $100K - $500K | Sweet spot for growth potential |
| **Liquidity** | $10K minimum | Must be locked |
| **Chain** | Solana, Base, Ethereum | Established DEX liquidity |

---

## Entry Strategy

- **Wait for first dip** — NEVER buy the top
- FOMO is the enemy of profit
- Patience beats speed

---

## Due Diligence Checklist

Before entering any position:

- [ ] **Liquidity locked?** Check DexScreener/DexTools for lock icon
- [ ] **Track whale wallets** on BaseScan (Base) or Solscan (Solana)
- [ ] **Use Bubble Maps** to detect dev dumps
- [ ] **Check CT hype** — organic vs paid shills
- [ ] **Verify contract** on-chain
- [ ] **Check holder distribution** — avoid 90%+ concentrated tokens

---

## Exit Strategy (Laddered Profits)

| Multiple | Action | Rationale |
|----------|--------|-----------|
| **2x** | Take initial out | Remove risk, play with house money |
| **5x** | Take more profits | Secure gains |
| **10x** | Consider full exit | Don't chase 100x greed |

### Red Flags (GTFO Immediately)

- ⚠️ Volume dries up suddenly
- ⚠️ Whales start dumping
- ⚠️ Dev wallet selling chunks
- ⚠️ Liquidity unlocks
- ⚠️ Social sentiment turns negative

---

## Golden Rule

> **"Take profits before someone else takes them from you."**

---

## Scanner Integration

These rules are hardcoded in:
- `scripts/memecoin-scanner.sh` — Discovery filter
- `scanner_engines/scanner_v3.py` — Pattern engine filter
- `scanner_engines/src/formatters/telegram.py` — Alert output

### Constants

```python
TARGET_MIN_MC = 100_000      # $100K minimum
TARGET_MAX_MC = 500_000      # $500K maximum
MIN_LIQUIDITY = 10_000       # $10K minimum
```

---

*Last updated: 2026-02-14*
