# PLAN.md — Cost-Optimized Architecture

> "If you don't use a PLAN.md, you're just burning cash in a chat box."

## Architecture: 2-Agent Rule

**Killed the 9-agent fleet ($100/night money pit). Now running 2 agents:**

| Agent | Role | Model | Cost |
|-------|------|-------|------|
| **coder** | Code generation, refactoring, heavy lifting | Kimi K2.5 (flat-rate) | ~$20/mo |
| **ops** | Monitoring, heartbeats, routine checks | Llama 3.2 (local) | $0 |

---

## Cost Optimizations Implemented

### 1. Flat-Rate Loophole ✅
- **Heavy lifting** (code, trading decisions): Kimi K2.5 flat-rate coding plan
- **Stopped**: Paying per token for large context operations
- **Impact**: Unlimited coding tasks at fixed cost

### 2. Local Heartbeats ✅
- **48×/day OpenClaw pings** → Route to local Llama 3.2 via Ollama
- **Cost**: $0
- **Setup**: `ollama run llama3.2:3b` for heartbeat responses
- **Falls back to**: Gemini Flash Lite if local model fails

### 3. Model Routing by Task

| Task | Model | Cost |
|------|-------|------|
| Heartbeats | Llama 3.2 (local) | $0 |
| Routine cron jobs | Gemini Flash Lite | $0 |
| Trading decisions | Kimi K2.5 | Flat rate |
| Code generation | Kimi K2.5 | Flat rate |
| Urgent alerts | MiniMax M2.5 | ~$0.001/run |

---

## Active Cron Jobs (Cost-Optimized)

| Job | Frequency | Model | Monthly Cost |
|-----|-----------|-------|--------------|
| `memecoin-scanner-720min` | Every 12h | Gemini Flash Lite | $0 |
| `smart-money-monitor-2h` | Every 2h | Gemini Flash Lite | $0 |
| `ema50-crossing-alerts-4h` | Every 4h | Gemini Flash Lite | $0 |
| `watchlist-maintenance-daily` | Daily 7am | Gemini Flash Lite | $0 |
| `git-auto-backup-2h` | Every 2h | Gemini Flash Lite | $0 |
| `morning-briefing-8am` | Daily 8am | Gemini Flash Lite | $0 |
| `daily-watchlist-8am` | Daily 8am | Gemini Flash Lite | $0 |
| `moltbook-learning-24h` | Daily midnight | Gemini Flash Lite | $0 |
| `memory-grooming-nightly` | Daily 3am | Gemini Flash Lite | $0 |
| `diary-telegram-update` | Daily 9am | Gemini Flash Lite | $0 |

**Total Monthly**: ~$5-10 (was ~$45-50 before optimization)

---

## Decision Tree

```
User Request
├── Heartbeat check? ──→ Llama 3.2 (local) ──→ $0
├── Routine cron? ──→ Gemini Flash Lite ──→ $0
├── Code task? ──→ Kimi K2.5 (flat-rate) ──→ Fixed
├── Trading decision? ──→ Kimi K2.5 (flat-rate) ──→ Fixed
└── Urgent alert? ──→ MiniMax M2.5 ──→ Minimal
```

---

## Local Ollama Setup

```bash
# Pull the model
ollama pull llama3.2:3b

# Test it works
ollama run llama3.2:3b "Hello, respond with just: HEARTBEAT_OK"

# OpenClaw config will route heartbeats here
```

---

## Backups & Fallbacks

1. **Local Llama fails** → Falls back to Gemini Flash Lite
2. **Flat-rate limit hit** → Falls back to MiniMax M2.5
3. **All APIs down** → Queue for retry, log locally

---

Last updated: 2026-02-21
