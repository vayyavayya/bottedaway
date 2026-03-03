# PolyClaw Memory System

Long-term memory and learning system for prediction market trading. Records market resolutions, extracts lessons, and feeds insights back into the forecasting pipeline.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MEMORY SYSTEM FLOW                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Research → Trade → Track → Resolve → Record → Learn → Improve │
│     ↑                                                        │   │
│     └────────────────────────────────────────────────────────┘   │
│                    (feedback loop)                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### 1. Memory Tracker (`memory_tracker.py`)
**Purpose:** Record market resolutions and maintain historical data

**Features:**
- Records resolution outcomes with prediction vs actual
- Calculates P&L from trades
- Computes category base rates (% that resolve YES)
- Tracks prediction accuracy per category
- Updates MEMORY.md with learnings
- Generates analyst prompt addons

**Usage:**
```bash
# Record a resolution
python memory_tracker.py resolve 0xabc123 YES --pnl 25.50 --lessons "overconfidence,ignored_base_rate"

# View stats
python memory_tracker.py stats
python memory_tracker.py stats --category Politics

# Update prompts manually
python memory_tracker.py update-prompts
```

### 2. Resolution Watcher (`resolution_watcher.py`)
**Purpose:** Monitor tracked markets for automatic resolution detection

**Features:**
- Auto-adds markets to tracking when we trade them
- Checks Polymarket API for resolution status
- Auto-extracts lessons based on prediction vs outcome
- Records to memory when markets resolve
- Runs as part of research cron job

**Usage:**
```bash
# Check all tracked markets
python resolution_watcher.py check

# Check specific market
python resolution_watcher.py check --market-id 0xabc123

# List tracked/resolved markets
python resolution_watcher.py list

# Auto check (for cron)
python resolution_watcher.py auto

# Manual record
python resolution_watcher.py record 0xabc123 YES --pnl -10.00
```

### 3. Memory Files

#### `memory/projects/polyclaw-history.md`
Historical record of all resolved markets:
- Category base rates
- Per-market resolutions
- P&L tracking
- Embedded JSON for programmatic access

#### `MEMORY.md` (PolyClaw Trading Learnings section)
Curated long-term memory:
- Significant outcomes with Brier scores
- Pattern insights
- Category performance
- Warnings and edge confirmations

#### `skills/polyclaw/prompts/memory_context.md`
Auto-generated analyst context:
- Historical base rates per category
- Calibration notes
- Pattern insights
- Forecasting guidance

## Data Flow

```
1. research.py runs 6-step pipeline
   └── Step 7: Portfolio integration
       └── Logs paper trade
       └── Adds market to resolution_watcher tracking

2. cron_research.py runs every 6 hours
   ├── Step 1: resolution_watcher.check_all_tracked()
   │   └── Detects any new resolutions
   │   └── Calls memory_tracker.record_resolution()
   │       └── Updates polyclaw-history.md
   │       └── Updates MEMORY.md with learning
   │       └── Regenerates memory_context.md
   │
   └── Step 2: research_trending_markets()
       └── Loads memory_context.md into prompts
       └── Generates forecast with historical context
```

## Auto-Extracted Lessons

The system automatically extracts lessons based on:

**Directional Correctness:**
- `directional_error` — We were on the wrong side
- `had_edge_despite_low_confidence` — Low confidence but correct
- `high_edge_predicted_correctly` — Large edge materialized

**Confidence Issues:**
- `overconfidence_penalty` — High confidence (>75%) but wrong
- `large_edge_did_not_materialize` — Edge >15% but lost

**Category-Specific:**
- `politics_polls_unreliable` — Political market loss
- `crypto_volatility_unpredictable` — Crypto market loss
- `sports_favorite_bias_check` — Sports market insight
- `very_short_term_timing_difficult` — <1 day markets

## Base Rate Examples

| Category | Sample Base Rate | Meaning |
|----------|-----------------|---------|
| Politics | 55% YES | Political markets slightly favor YES |
| Crypto | 48% YES | Crypto markets roughly balanced |
| Sports | 62% YES | Favorites win more often |

*Actual rates computed from your resolved markets*

## Metrics Tracked

**Per Market:**
- Market question and category
- Our prediction (probability)
- Actual outcome
- P&L from trade
- Confidence at prediction time
- Edge we estimated
- Brier score (calibration)

**Per Category:**
- Total resolved markets
- Prediction accuracy
- Base rate (% YES)
- Average edge when correct/wrong
- Average P&L
- Total P&L

## Calibration Scoring

**Brier Score:** Measures forecast accuracy (lower is better)
- Perfect: 0.0
- Random (50%): 0.25
- Always wrong: 1.0
- Formula: (predicted_prob - actual_outcome)²

**Calibration Insights:**
- Accuracy < 50% → We tend to be overconfident in this category
- Accuracy > 70% → We have genuine edge in this category
- Track over time to see improvement

## Integration with Research Pipeline

The memory context is automatically loaded into the forecasting prompt:

```python
MEMORY_CONTEXT = load_memory_context()

FORECASTING_PROMPT = """...
{memory_context}

YOUR TASK:
1. Determine the BASE RATE...
2. List KEY EVIDENCE...
3. Estimate P(YES)...
"""
```

This ensures every forecast benefits from historical data.

## Files

| File | Purpose |
|------|---------|
| `memory_tracker.py` | Core memory recording and analysis |
| `resolution_watcher.py` | Auto-detection of market resolutions |
| `data/tracked_markets.json` | Markets currently being watched |
| `data/resolved_markets.json` | Markets that have resolved |
| `prompts/memory_context.md` | Analyst prompt addon |
| `../../memory/projects/polyclaw-history.md` | Historical record |
| `../../MEMORY.md` | Curated long-term learnings |

## Cron Integration

The resolution watcher runs automatically with the research cron:

```bash
# Every 6 hours
0 */6 * * * cd ~/.openclaw/workspace/skills/polyclaw && python cron_research.py
```

This ensures:
1. New resolutions are detected quickly
2. Memory is updated continuously
3. Next forecasts include fresh learnings

## Manual Operations

**Add market to tracking (after manual trade):**
```python
from resolution_watcher import add_market_to_tracking
add_market_to_tracking(market_id, market_data, research_data)
```

**Force prompt regeneration:**
```bash
python memory_tracker.py update-prompts
```

**Export all data:**
```bash
python memory_tracker.py export --format json
python memory_tracker.py export --format markdown
```

## Learnings Feed Forward

The system improves forecasts by:

1. **Base Rate Anchoring** — Start with historical frequency
2. **Calibration Warnings** — Flag categories where we're overconfident
3. **Pattern Recognition** — Recurring lessons highlight systematic biases
4. **Edge Validation** — Track which categories actually produce edge

Over time, this creates a self-improving forecasting system.
