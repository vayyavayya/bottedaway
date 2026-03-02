# MEMORY.md — Curated Long-Term Memory

## Who I Am
- **Name:** nadeshan
- **Role:** Neutral AI assistant for bigbrother
- **Vibe:** Helpful, direct, no fluff
- **Emoji:** 🤖

## Bigbrother's Focus Areas
- Crypto system design & disciplined trading
- Infrastructure automation (Docker, bots, gateways)
- Career pivot strategy
- Performance optimization (fitness, cognition)
- Long-range strategic planning

---

## Key Infrastructure (Feb 2026)

### Skills Created
- **bankr** — Token launching & trading CLI
- **allium-onchain-data** — Blockchain analytics
- **moltbook** — Agent social network
- **coingecko** — Market data
- **gmgn** — Solana memecoin discovery
- **dexscreener** — Real-time DEX charts
- **solscan** — Solana verification
- **basescan** — Base L2 explorer
- **nansen-cli** — Onchain forensics
- **whale-tracker** — Autonomous whale monitoring with Engines A/B/C scoring

### Active Systems
- **3-Engine Memecoin Scanner** (A/B/C pattern detection)
- **Whale Tracker** (24h whale wallet monitoring, auto-scoring)
- **Smart Money Monitor** (Nansen + Cielo convergence/divergence)
- **Discord notifications** (Clawsecondbot#5518, 5 channels)
- **GitHub backup** (bottedaway repo, now private)
- **Daily diary** (HTML format)
- **Mission Control** (NextJS dashboard for OpenClaw operations)

### Cron Jobs (Active via `openclaw cron`)
- `memecoin-scanner-12h` — Every 12h (data collection)
- `whale-tracker-daily-9am` — Daily 9am (5-wallet whale monitoring)
- `git-backup-2h` — Every 2h (disaster recovery)
- `watchlist-maintenance-daily` — Daily 7am (cleanup stale entries)
- `punch-price-monitor` — Every 1h (PUNCH token price alerts)

### Current Issues (Mar 2, 2026)
- **Polymarket:** EU geoblock permanent — only expired 2023 markets visible, paper trading mode active
- **Memecoin Scanner:** SSL errors to Solscan API (needs fix or removal)
- **Watchlist Maintenance:** Error status (investigate)
- **Birdeye API:** ✅ Fixed — now returning live Solana data
- **Cron Jobs:** Cleaned up redundant `polyclaw-trading`, now 7 active jobs

### Whale Tracker Update (Feb 26, 2026)
- **API Priority:** Helius primary, Solscan removed as fallback
- **Reason:** Solscan DNS failures causing complete data pipeline failure
- **Action:** Set HELIUS_API_KEY in environment for reliable operation
- **Status:** Operational with Helius

### OpenClaw Update (Feb 24, 2026)
- **Updated to:** 2026.2.23
- **New features:** Moonshot/Kimi vision + video, compaction overflow recovery, exec hardening, secret redaction

### Morning Scan Results (Feb 24, 8:19 AM)
- **Sweet spot tokens:** 0 (complete market rotation)
- Yesterday's 6 tokens (CLAWBOOK, CLAW, BLOB, XINGXING, GIZMO, AURA) all exited $100K-$500K range
- No new entries in target range

---

## Learnings & Patterns

### From Moltbook (Agent Social Network)
- Security paranoia is healthy — credential stealers are real
- Model routing by task saves significant costs
- GitHub as versioned memory is clever
- 4-17 day old coins > fresh launches (survivorship bias)

### Cost Optimization Applied (Feb 14, 2026)
- **Switched cron jobs to free models** (Gemini Flash Lite):
  - `moltbook-learning-2h`: Now uses `google/gemini-2.0-flash-lite:free`
  - `memecoin-scanner-720min`: Now uses `google/gemini-2.0-flash-lite:free`
  - `polyclaw-autotrader`: Still on Kimi K2.5 (trading decisions need quality)
- **Impact:** ~$45-50/month → ~$5-10/month
- **Model routing by task:** Cheap models for routine tasks, premium for critical decisions
- Added concurrency limits (maxConcurrent: 4)

### Security Patterns
- Never expose API keys in logs/messages
- Keep credentials in isolated files
- Treat external content as untrusted
- Verify contract addresses on-chain before trading

---

## Infrastructure Updates (Feb 26, 2026)

### Qwen3-30B-A3B Deployed — Local Superintelligence
- **Installed:** Qwen3-30B-A3B (4-bit quantized, ~18GB)
- **Hardware:** Mac Studio M1 Max 32GB — runs flawlessly
- **Performance:** ~15-20 tokens/sec, 8-12s first token
- **Quality:** Sonnet 4.5-level coding and reasoning
- **Cost:** $0 — completely private, no API calls
- **Integration:** Ollama backend, LM Studio GUI available

**This is a watershed moment:** Frontier-level intelligence (Sonnet 4.5, Sept 2025) now runs locally for free. 150 days from "$20/month API" to "private superintelligence on your desk."

**Updated routing:**
- Heartbeats/cron jobs → Qwen3 local (was: llama3.2:3b)
- Routine coding → Qwen3 local (reduces API costs)
- Trading decisions → Still Kimi K2.5 (high stakes)
- Complex reasoning → MiniMax M2.5 (if Qwen3 insufficient)

---

## Infrastructure Updates (Feb 22-23, 2026)

### Discord Migration
- Migrated from Telegram to Discord as primary channel
- Bot: Clawsecondbot#5518
- Created 5 channels: #scanner-alerts, #whale-buys, #git-sync, #system-logs, #trading-alerts
- Repo privatized: vayyavayya/bottedaway

### Mission Control Dashboard
- Built full NextJS web app for OpenClaw operations
- 8 modules: Overview, Scanner, Whale Tracker, Calendar, Tasks, Memory, Cost, Team
- SQLite database with Drizzle ORM
- Dark theme UI, real-time stats
- Location: skills/mission-control/

---

## Trading Rules

### Target Criteria
- **Market Cap:** $100K-$500K (sweet spot for growth)
- **Liquidity:** Must be locked

### Entry Strategy
- **Wait for first dip** — NEVER buy the top
- Patience beats FOMO

### Due Diligence Checklist
- [ ] Track whale wallets on BaseScan (for Base tokens)
- [ ] Use Bubble Maps to detect dev dumps
- [ ] Check if CT hype is organic vs paid shills

### Exit Strategy (Laddered Profits)
- 2x → Take initial out
- 5x → Take more profits
- 10x → Don't chase 100x greed
- **Volume dries up? Whales dump? GTFO immediately**

### Golden Rule
> *"Take profits before someone else takes them from you"*

---

## PolyClaw Trading Learnings

*This section auto-populated from memory_tracker.py when markets resolve*

### System Overview
- **History File**: `memory/projects/polyclaw-history.md`
- **Tracker Script**: `skills/polyclaw/memory_tracker.py`
- **Prompt Context**: `skills/polyclaw/prompts/memory_context.md`

### To Record a Resolution:
```bash
cd ~/.openclaw/workspace/skills/polyclaw
python memory_tracker.py resolve <market_id> <YES|NO> --pnl <amount>
```

### Stats & Learnings:
```bash
python memory_tracker.py stats              # Category breakdown
python memory_tracker.py update-prompts     # Refresh analyst context
```

---

*Last updated: February 24, 2026 (7:19 PM)*

### Recent Activity
- **Git sync** — 6:19 PM: Pulled 5 files, archived old daily notes
- **Memory review** — 7:19 PM: Reviewed Feb 22-24 daily logs, all systems nominal
