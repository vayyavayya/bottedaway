# PolyClaw Memory System - Build Summary

## Overview

Created a complete long-term memory and learning system for prediction market trading. The system automatically:

1. **Records market resolutions** with predictions, outcomes, and P&L
2. **Computes category base rates** (e.g., "politics markets resolve YES 55%")
3. **Extracts lessons learned** automatically based on prediction vs outcome
4. **Updates MEMORY.md** with curated long-term learnings
5. **Feeds insights back** into ClawAnalyst's prompts for better forecasts

---

## Files Created

### Core System Files

| File | Purpose | Lines |
|------|---------|-------|
| `resolution_watcher.py` | Monitors tracked markets for resolution, auto-records outcomes | 433 |
| `MEMORY_SYSTEM.md` | Comprehensive documentation for the memory system | 232 |
| Updated `memory_tracker.py` | Enhanced with auto-learning extraction, Brier scores, pattern analysis | +50 |
| Updated `cron_research.py` | Integrated resolution watcher into research pipeline | +15 |
| Updated `research.py` | Auto-adds markets to tracking after trade | +12 |

### Data Files (Auto-Created)

| File | Purpose |
|------|---------|
| `data/tracked_markets.json` | Markets currently being watched for resolution |
| `data/resolved_markets.json` | Markets that have resolved |
| `prompts/memory_context.md` | Auto-generated analyst prompt addon |
| `memory/projects/polyclaw-history.md` | Historical resolution record |

---

## How It Works

### The Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Research   │────▶│    Trade     │────▶│  Add to Tracking│
│  Pipeline   │     │  (paper)     │     │                 │
└─────────────┘     └──────────────┘     └─────────────────┘
                                                    │
                         ┌──────────────────────────┘
                         ▼
              ┌─────────────────────┐
              │ Resolution Watcher  │ (runs every 6h)
              │  Checks tracked     │
              │  markets for        │
              │  resolution         │
              └─────────────────────┘
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
   ┌──────────────┐ ┌──────────┐ ┌─────────────┐
   │Record to     │ │Update    │ │Regenerate   │
   │polyclaw-     │ │MEMORY.md │ │memory_      │
   │history.md    │ │          │ │context.md   │
   └──────────────┘ └──────────┘ └─────────────┘
           │             │             │
           └─────────────┴─────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │ Next forecast uses  │
              │ updated context     │
              │ (base rates +       │
              │  lessons)           │
              └─────────────────────┘
```

### Auto-Extracted Lessons

The system automatically generates lesson tags based on:

| Scenario | Lesson Tag |
|----------|------------|
| High confidence (>75%) but wrong | `overconfidence_penalty` |
| Large edge (>15%) didn't materialize | `large_edge_did_not_materialize` |
| Low confidence but correct | `had_edge_despite_low_confidence` |
| Wrong side entirely | `directional_error` |
| Political market loss | `politics_polls_unreliable` |
| Crypto market loss | `crypto_volatility_unpredictable` |
| Very short-term market | `very_short_term_timing_difficult` |

---

## Commands

### Manual Resolution Recording
```bash
cd ~/.openclaw/workspace/skills/polyclaw

# Record a resolution
python memory_tracker.py resolve <market_id> YES --pnl 25.50 --lessons "overconfidence"

# View stats
python memory_tracker.py stats
python memory_tracker.py stats --category Politics

# Check tracked markets
python resolution_watcher.py list

# Check for new resolutions
python resolution_watcher.py check

# Manual record via resolution watcher
python resolution_watcher.py record <market_id> YES --pnl -10.00
```

### Auto-Run (via Cron)
```bash
# Runs every 6 hours via cron:
python cron_research.py
# 1. Checks for resolved markets
# 2. Updates memory if any found
# 3. Runs research on trending markets
```

---

## Integration Points

### 1. Research Pipeline (`research.py`)
```python
# After logging trade:
if RESOLUTION_AVAILABLE:
    add_market_to_tracking(market_id, market_data, research_data)
```

### 2. Cron Job (`cron_research.py`)
```python
# Step 1: Check resolutions
resolved_count = run_resolution_watcher()

# Step 2: Run research (with updated memory context)
results = research_trending_markets()
```

### 3. Memory Context in Prompts
```python
MEMORY_CONTEXT = load_memory_context()  # Loads memory_context.md

FORECASTING_PROMPT = """
{memory_context}  # Includes base rates + lessons

Estimate P(YES): ...
"""
```

---

## Example Memory Context Output

When the system runs, `memory_context.md` is auto-generated:

```markdown
# Auto-generated from PolyClaw Memory Tracker
# Updated: 2026-03-03 01:42

### Historical Base Rates (from PolyClaw memory):
- **Politics**: 55% resolve YES (n=12, 58% prediction accuracy)
- **Crypto**: 48% resolve YES (n=8, 75% prediction accuracy)
- **Sports**: 62% resolve YES (n=5, 40% prediction accuracy)

### Calibration Notes:
- **Sports**: We tend to be OVERCONFIDENT (only 40% accuracy)
- **Crypto**: We have EDGE in this category (75% accuracy)

### Pattern Insights:
- ⚠️ 'overconfidence_penalty' appears when we fail
- ⚠️ 'politics_polls_unreliable' appears when we fail

### Forecasting Guidance:
1. Start with base rate
2. Adjust for edge
3. Confidence calibration
4. Avoid overconfidence
5. Record predictions
```

---

## Metrics Tracked

### Per Market
- Market question, category
- Our prediction (probability 0-100%)
- Actual outcome (YES/NO)
- P&L from trade
- Confidence at prediction time
- Edge we estimated
- Brier score (calibration metric)
- Lessons learned

### Per Category
- Total resolved markets
- Prediction accuracy
- Base rate (% YES)
- Average edge when correct/wrong
- Average and total P&L

---

## MEMORY.md Section

The system auto-updates MEMORY.md with:

```markdown
## PolyClaw Trading Learnings

### 2026-03-03 - Politics: Will X happen...
- **Outcome**: YES (✅ Correct)
- **Our Prediction**: 65.0% | **Actual**: YES (Brier: 0.122)
- **P&L**: $+25.50
- **Lessons**: overconfidence_penalty; ignored_base_rate
- **✅ Edge Confirmed**: Politics accuracy 72% — we have genuine edge here
```

---

## Cost

The memory system adds minimal cost:
- **Resolution checks:** Free (API calls only)
- **Memory recording:** Free (local operations)
- **Prompt regeneration:** Free (local file writes)

Total overhead: **$0** — pure local operations.

---

## Status

✅ **Complete and operational**

- [x] Resolution watcher created
- [x] Auto-learning extraction implemented
- [x] Category base rates computed
- [x] MEMORY.md integration working
- [x] Prompt regeneration active
- [x] Research pipeline integration
- [x] Cron job integration
- [x] Documentation complete
- [x] Tested with sample resolution

---

## Next Steps

1. **Monitor first real resolutions** — The system will auto-detect and record
2. **Review base rates weekly** — Watch for category patterns
3. **Check calibration** — Track Brier scores over time
4. **Refine lessons** — Add domain-specific lesson extractors as needed
