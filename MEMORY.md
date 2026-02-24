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

### Current Issues (Feb 24, 2026)
- **Whale Tracker API blocked** — Needs `HELIUS_API_KEY` (403 error)
- **Watchlist empty** — No tokens being monitored by pattern engines
- **GMGN down** — DNS resolution failure (service may be deprecated)
- **Cron INDEX edit** — Whitespace mismatch in auto-update script

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

*Last updated: February 24, 2026 (9:31 AM)*
