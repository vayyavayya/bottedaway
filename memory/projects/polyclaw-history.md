# PolyClaw Trading History

Historical record of prediction market resolutions, outcomes, and learnings.
Auto-generated from memory tracker system.

---

## 📊 Category Base Rates

*No resolved markets yet - waiting for first real resolutions*

---

## 🎯 Resolved Markets

### Legend
- **Prediction**: Our estimated probability (0-100%)
- **Outcome**: What actually happened
- **✅/❌**: Whether our prediction was directionally correct
- **P&L**: Profit/loss from trading this market

*No markets resolved yet. Use `python memory_tracker.py resolve <market_id> <outcome>` to record resolutions.*

---

## 📝 How to Record Resolutions

### After a market resolves:

```bash
cd ~/.openclaw/workspace/skills/polyclaw

# Basic resolution record (auto-loads from research note)
python memory_tracker.py resolve <market_id> YES --pnl 25.50

# With lessons learned
python memory_tracker.py resolve <market_id> NO \
  --pnl -15.00 \
  --lessons "ignored base rate,overconfident on timing"
```

### Check stats:

```bash
# All categories
python memory_tracker.py stats

# Specific category
python memory_tracker.py stats --category Politics
```

### Update ClawAnalyst prompts with learnings:

```bash
python memory_tracker.py update-prompts
```

---

## 🔄 Memory System Flow

```
Research → Trade → Resolve → Record → Learn → Improve Forecasts
```

1. **research.py** generates forecast with memory context
2. **Trade** (real or paper) based on recommendation
3. **Market resolves** with actual outcome
4. **memory_tracker.py** records the resolution
5. **MEMORY.md** updated with learnings
6. **prompts/memory_context.md** regenerated with new insights
7. **Next forecast** benefits from historical data

---

*Last updated: 2026-03-02 - System initialized*
