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

### Active Systems
- **3-Engine Memecoin Scanner** (A/B/C pattern detection)
- **Telegram notifications** (paired with @sasimestri)
- **GitHub backup** (bottedaway repo)
- **Daily diary** (HTML format)

### Cron Jobs
- `memecoin-scanner-720min` — Every 12h (data collection)
- `diary-telegram-update` — Daily 9am (user notification)

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

## Preferences
- **Model for heartbeat checks:** google/gemini-2.0-flash-lite:free (cost efficiency)
- **Heartbeat pattern:** Rotating checks (scanner → memory → git → skill audit → cost)
- **Time zone:** Europe/Berlin

---

*Last updated: February 14, 2026*
