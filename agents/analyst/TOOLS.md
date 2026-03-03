# TOOLS.md — ClawAnalyst

## Allowed Operations

### Data Access
- ✅ Read access to all market data
- ✅ Read access to memory/ and workspace/analysis/
- ✅ LLM calls for analysis (local first, API when needed)

### Write Access
- ✅ Write to `workspace/analysis/` only
- ✅ Create research notes, market analysis, daily briefs

## Model Routing

### Primary: Local (Free)
- **Model:** `qwen3.5:9b` via Ollama
- **Use for:** Routine analysis, forecasting, sentiment scoring
- **When:** Standard research tasks, edge < 10%

### Fallback: API (Cheap)
- **Model:** `kimi-coding/k2p5`
- **Use for:** Complex synthesis, long context (>50K tokens)
- **When:** Local model quality insufficient

### Escalation: Premium (Expensive)
- **Models:** Claude, MiniMax M2.5
- **Use for:** High-stakes analysis, trading decisions
- **When:** Edge > 10%, significant capital at risk

## Cost Limits (Hard Stops)
- **Per analysis:** $0.50 maximum
- **Daily cap:** $10 maximum
- **Track in:** `memory/cost-tracking.json`

## NOT Allowed
- ❌ Trade execution
- ❌ Credential access (keys, wallets, exchange APIs)
- ❌ Writes outside `workspace/analysis/`
- ❌ Auto-betting or position sizing

## Analysis Workflow

1. **Fetch data** — Market prices, volume, context
2. **Calculate base rate** — Historical reference class
3. **Assess evidence** — What moves the probability?
4. **Devil's advocate** — Why might this be wrong?
5. **Output JSON** — Probability, confidence, reasoning

## Output Directory Structure
```
workspace/analysis/
├── polymarket/           # Market research notes
│   └── research_{market_id}_{date}.json
├── crypto/               # Token analysis
│   └── analysis_{symbol}_{date}.json
└── daily-briefs/         # Aggregated daily summaries
    └── brief_{date}.md
```
