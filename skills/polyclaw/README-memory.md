# PolyClaw Memory System

Long-term memory system for tracking prediction market outcomes, updating base rates, and feeding learnings back into the trading pipeline.

## Overview

The memory system consists of:

1. **Memory Tracker** (`memory_tracker.py`) - CLI tool for recording resolutions
2. **History File** (`memory/projects/polyclaw-history.md`) - Markdown record of all resolutions
3. **Prompt Context** (`prompts/memory_context.md`) - Auto-generated context for ClawAnalyst
4. **MEMORY.md Integration** - Key learnings synced to long-term memory

## Quick Start

### Record a Market Resolution

After a market resolves, record the outcome:

```bash
cd ~/.openclaw/workspace/skills/polyclaw

# Basic resolution (auto-loads from research note)
python memory_tracker.py resolve <market_id> YES --pnl 25.50

# With lessons learned
python memory_tracker.py resolve <market_id> NO \
  --pnl -15.00 \
  --lessons "ignored base rate,overconfident on timing"

# Manual entry (no research note found)
python memory_tracker.py resolve <market_id> YES \
  --pnl 10.00 \
  --category Politics
```

### View Statistics

```bash
# All category stats
python memory_tracker.py stats

# Specific category
python memory_tracker.py stats --category Politics
```

Sample output:
```
📊 Category Statistics
------------------------------------------------------------
Politics:
   Resolved: 12 | Accuracy: 67.0%
   Base Rate YES: 58.3%
   Avg P&L: $5.42 | Total: $65.04

Crypto:
   Resolved: 8 | Accuracy: 75.0%
   Base Rate YES: 37.5%
   Avg P&L: $12.30 | Total: $98.40
```

### Update ClawAnalyst Prompts

Regenerate the prompt context file with latest learnings:

```bash
python memory_tracker.py update-prompts
```

This updates `prompts/memory_context.md` which is automatically loaded into the forecasting prompt.

## Data Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Market Resolves │────▶│ memory_tracker.py │────▶│ polyclaw-history │
└─────────────────┘     └──────────────────┘     │      .md         │
                                                 └─────────────────┘
                                                           │
                                                           ▼
                                                  ┌─────────────────┐
                                                  │ Category Stats  │
                                                  │ - Base rates    │
                                                  │ - Accuracy      │
                                                  │ - P&L          │
                                                  └─────────────────┘
                                                           │
                                                           ▼
         ┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
         │ research.py gets │◀────│ memory_context.md │◀────│ Prompt Generator │
         │ base rate context│     │ (auto-generated)  │     └─────────────────┘
         └─────────────────┘     └──────────────────┘              │
                  │                                                │
                  ▼                                                │
         ┌─────────────────┐                                       │
         │ Forecasting     │───────────────────────────────────────┘
         │ Prompt Includes │              (feedback loop)
         │ Historical Data │
         └─────────────────┘
```

## File Structure

```
skills/polyclaw/
├── memory_tracker.py          # Main CLI tool
├── prompts/
│   └── memory_context.md      # Auto-generated prompt addon
└── README-memory.md           # This file

memory/projects/
└── polyclaw-history.md        # Historical resolutions

MEMORY.md                      # Long-term memory (learnings appended)
```

## History File Format

`polyclaw-history.md` is human-readable markdown with embedded JSON:

```markdown
### Politics

**Will X happen by Y date?**
- Date: 2026-03-02
- Our Prediction: 65.0% | Outcome: YES ✅
- Edge: 15.0% | Confidence: 75%
- P&L: $25.50
- Lessons: ignored early signals, right direction but wrong timing

```json
{
  "market_id": "...",
  "question": "Will X happen by Y date?",
  "category": "Politics",
  "prediction": 65.0,
  "outcome": "YES",
  "pnl": 25.50,
  ...
}
```
```

## Prompt Context Format

`memory_context.md` is injected into the forecasting prompt:

```markdown
### Historical Base Rates (from PolyClaw memory):

- **Politics**: 58.3% resolve YES (n=12, 67% prediction accuracy)
- **Crypto**: 37.5% resolve YES (n=8, 75% prediction accuracy)

### Recent Lessons:

- Don't ignore base rates in political markets
- Crypto markets mean-revert faster than expected
- High confidence > 80% often signals overconfidence

### Calibration Notes:

- **Politics**: We tend to be OVERCONFIDENT (only 67% accuracy). Consider adjusting estimates down by 10-15%.
- **Crypto**: We have EDGE in this category (75% accuracy). Trust our process.
```

## Integration with Research Pipeline

The `research.py` pipeline automatically loads memory context:

1. At startup, `load_memory_context()` reads `prompts/memory_context.md`
2. The `FORECASTING_PROMPT` includes `{memory_context}` placeholder
3. Each research run injects current base rates and lessons

This creates a feedback loop where past learnings improve future forecasts.

## Categories

Common categories tracked:

- **Politics** - Elections, policy decisions, political events
- **Crypto** - Token prices, protocol launches, regulatory news
- **Sports** - Game outcomes, player performance
- **Technology** - Product launches, company decisions
- **Entertainment** - Awards, releases, celebrity events

## Export

Export data for analysis:

```bash
# JSON format
python memory_tracker.py export --format json > polyclaw_data.json

# Markdown format  
python memory_tracker.py export --format markdown > export.md
```

## Automation Ideas

Future enhancements:

1. **Auto-resolution checking** - Poll Polymarket API for resolved markets
2. **P&L sync** - Connect to portfolio tracker for automatic P&L
3. **Weekly reviews** - Cron job to analyze patterns and update prompts
4. **Edge detection** - Alert when new category patterns emerge

## Maintenance

- History file grows over time — no pruning needed (text is cheap)
- Prompt context auto-truncates to last 5 lessons to prevent bloat
- Category stats computed on-the-fly from full history
- Update prompts after every 3-5 new resolutions for fresh context
