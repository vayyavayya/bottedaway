# PolyClaw Research Pipeline

6-step prediction market analysis pipeline for Polymarket.

## Pipeline Steps

| Step | Name | Method | Cost |
|------|------|--------|------|
| 1 | Forecasting | LLM (Kimi K2.5) | ~$0.10 |
| 2 | Resolution Analysis | LLM (Kimi K2.5) | ~$0.10 |
| 3 | Devil's Advocate | LLM (Kimi K2.5) | ~$0.10 |
| 4 | Signal Generation | Local compute | $0 |
| 5 | Validation Gate | Local compute | $0 |
| 6 | Save Research | File I/O | $0 |

**Total: ~$0.30 per market**

## Usage

```bash
# Research a single market
python3 research.py <market_id>

# Research with JSON output
python3 research.py <market_id> --json

# Research top trending markets
python3 research.py trending --limit 5

# Use different model
python3 research.py <market_id> --model minimax-portal/MiniMax-M2.5
```

## Validation Thresholds

For a TRADE recommendation, ALL must pass:

- Edge ≥ 5%
- Confidence ≥ 60%
- Clarity ≥ 50%
- Severity < 80%
- Liquidity > $100

## Output

Research notes saved to:
```
~/.openclaw/workspace/analysis/polymarket/research_{market_id}_{date}.json
```

## Output Format

```json
{
  "meta": {
    "version": "1.0",
    "generated_at": "2026-03-02T21:45:00",
    "market_id": "...",
    "pipeline_steps": ["forecasting", "resolution", "devils_advocate", "signals", "validation"]
  },
  "market": { /* market data */ },
  "step1_forecasting": {
    "base_rate": "...",
    "evidence_yes": [...],
    "evidence_no": [...],
    "p_yes_estimate": 45.5,
    "confidence": 65,
    "key_uncertainties": [...],
    "reasoning": "..."
  },
  "step2_resolution": {
    "clarity_score": 75,
    "ambiguity_risks": [...],
    "edge_cases": [...],
    "severity_score": 30,
    "recommendation": "proceed with caution"
  },
  "step3_devils_advocate": {
    "why_market_might_be_wrong": [...],
    "participant_biases": [...],
    "steelmanned_opposite": "..."
  },
  "step4_signals": {
    "recommended_side": "YES",
    "edge_percent": 15.0,
    "kelly_size": 25.0,
    "expected_value": 15.5
  },
  "step5_validation": {
    "overall_valid": true,
    "recommendation": "TRADE",
    "checks": [...]
  },
  "step6_output": {
    "recommendation": "TRADE",
    "action": "Buy YES $25.00",
    "edge_percent": 15.0
  }
}
```

## Configuration

Set your OpenRouter API key:

```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

Or add to `~/.config/openclaw/credentials.json`:

```json
{
  "openrouter": {
    "api_key": "sk-or-v1-..."
  }
}
```

## Memory Integration

The research pipeline integrates with the **PolyClaw Memory System** to improve forecasts over time.

### How It Works

1. **Research** → Market analyzed, recommendation generated
2. **Trade** → Position taken (real or paper)
3. **Resolve** → Market outcome determined
4. **Record** → Resolution logged via memory tracker
5. **Learn** → Base rates and lessons feed back into prompts

### Recording Resolutions

After a market resolves, record the outcome:

```bash
python memory_tracker.py resolve <market_id> YES --pnl 25.50
```

This automatically:
- Records resolution in `memory/projects/polyclaw-history.md`
- Updates category base rates
- Appends lessons to MEMORY.md
- Regenerates prompt context for ClawAnalyst

### Memory in Forecasting

The forecasting prompt (Step 1) includes historical context:

```markdown
### Historical Base Rates (from PolyClaw memory):

- **Politics**: 58.3% resolve YES (n=12, 67% prediction accuracy)
- **Crypto**: 37.5% resolve YES (n=8, 75% prediction accuracy)

### Recent Lessons:

- Don't ignore base rates in political markets
- High confidence > 80% often signals overconfidence
```

This creates a **feedback loop**: past predictions improve future accuracy.

### Viewing Stats

```bash
# Category breakdown with base rates
python memory_tracker.py stats

# Specific category
python memory_tracker.py stats --category Politics
```

See [README-memory.md](README-memory.md) for full documentation.
