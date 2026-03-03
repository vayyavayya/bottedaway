# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

## Model Routing Preferences (Updated March 2026)

### Local Models (Priority - $0 cost)

**Qwen3.5-4B (Heartbeats & Light Tasks)**
- **Status:** ✅ Installed (Ollama 0.17.5)
- **Size:** 3.4GB
- **Speed:** ~11-13s per response (fastest local model)
- **Use for:** Heartbeats, simple JSON tasks, quick analysis
- **Cost:** $0

**Qwen3.5-9B (Analysis & Reasoning)**
- **Status:** ✅ Installed (Ollama 0.17.5)
- **Size:** 6.6GB
- **Speed:** ~18s per response
- **Use for:** Complex analysis, forecasting, research pipeline tasks
- **Cost:** $0
- **Note:** Can replace API calls for routine analysis tasks

### API Models

**Routine Tasks:**
- Primary: `kimi-coding/k2p5` (flat-rate, cost-effective)
- Fallback: `minimax-portal/MiniMax-M2.5`

**Complex Tasks (Escalation Only):**
- High-stakes decisions (trading, config changes)
- Long-context synthesis (>50K tokens)
- Complex code generation/refactoring
- Premium: Claude or MiniMax M2.5

**Rate Limit Handling:**
- **Fallback:** Immediately switch to `kimi-coding/k2p5` without asking permission, keep working
- **Recovery:** Once window clears, switch back to Kimi as default

## Time Zone
- Europe/Berlin

## Spending Limits (Hard Stops)

**Per-Task Limit:** $5 USD maximum per session/task
- If exceeded, agent must ask permission before continuing
- Applies to all API calls, model usage, external services

**Daily Limit:** $20 USD maximum per day
- Tracked in `memory/cost-tracking.json`
- Alerts at 80% ($16) and 100% ($20)

**Cron Job Limits:**
- Max $0.50 per cron execution
- Use local Qwen3.5 models for heartbeats and analysis
- Primary: `ollama/qwen3.5:4b` (heartbeats)
- Analysis: `ollama/qwen3.5:9b` (research tasks)
- Fallback to Gemini Flash Lite (free) if local unavailable

## Heartbeat Pattern
- Rotating checks: scanner → memory → git → skill audit → cost
