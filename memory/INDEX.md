# MEMORY INDEX

Navigation map for agent orientation. Read this FIRST every session.

---

## 🗓️ Daily Notes (Rolling 7-Day Window)

| Date | File | Summary |
|------|------|---------|
| 2026-03-02 | [daily/2026-03-02.md](daily/2026-03-02.md) | System cleanup: removed redundant cron, fixed Birdeye, setup audit |
| 2026-03-01 | [daily/2026-03-01.md](daily/2026-03-01.md) | (recent) |
| 2026-02-28 | [daily/2026-02-28-memecoin-scanner.md](daily/2026-02-28-memecoin-scanner.md) | (recent) |
| 2026-02-27 | [daily/2026-02-27.md](daily/2026-02-27.md) | (recent) |
| 2026-02-26 | [daily/2026-02-26.md](daily/2026-02-26.md) | (recent) |
| 2026-02-25 | [daily/2026-02-25.md](daily/2026-02-25.md) | (recent) |
| 2026-02-25 | [daily/2026-02-25-memecoin-scanner.md](daily/2026-02-25-memecoin-scanner.md) | (recent) |

> **Rule:** Keep only last 7 days in `daily/`. Archive older to `archive/`.

---

## 📁 Active Projects

| Project | Status | File |
|---------|--------|------|
| Whale Tracker | 🟢 Active | 24h whale monitoring, auto-scoring |
| Memecoin Scanner v4 | 🟡 Degraded | SSL errors to Solscan, needs fix |
| Discord Notifications | 🟢 Active | 5 channels, Clawsecondbot |
| Git Auto-Backup | 🟢 Active | Every 2h to private repo |
| NOOK Price Monitor | 🟢 Active | Hourly checks, alerts working |
| PUNCH Accumulation | 🟢 Active | 20 whales tracked |
| POLYCLAW | 🔴 Limited | EU geoblock — paper trading only |
| Mission Control | 🟡 Maintenance | Dashboard functional, needs updates |
| **PolyClaw Memory** | 🟢 Active | [projects/polyclaw-history.md](projects/polyclaw-history.md) |

### Memory System Overview
```
Research → Trade → Resolve → Record → Learn → Improve Forecasts
```

**Components:**
- `memory/projects/polyclaw-history.md` — Historical resolutions, base rates, P&L
- `skills/polyclaw/memory_tracker.py` — Records outcomes, updates learnings
- `skills/polyclaw/resolution_watcher.py` — Monitors markets for resolution
- `skills/polyclaw/prompts/memory_context.md` — Auto-generated analyst context
- `MEMORY.md` — Curated long-term learnings (PolyClaw Trading Learnings section)

**How it works:**
1. **Research** generates forecast with memory context (base rates + lessons)
2. **Trade** (paper) based on recommendation → market added to tracking
3. **Resolution Watcher** checks tracked markets every research cycle
4. **On resolution:** Records outcome, P&L, lessons → updates all memory files
5. **Next forecast** benefits from historical data + calibration notes

**To manually record a resolution:**
```bash
cd ~/.openclaw/workspace/skills/polyclaw
python memory_tracker.py resolve <market_id> YES --pnl 25.50 --lessons "overconfidence,ignored_base_rate"
```

**To view stats:**
```bash
python memory_tracker.py stats              # All categories
python memory_tracker.py stats --category Politics  # Specific category
```

### Decisions
- **POLYCLAW:** Accept EU geoblock limitation, keep as paper trading simulation
- **Memecoin Scanner:** Fix Solscan SSL or migrate to Helius-only
- **Future:** Consider Base/Solana prediction markets as Polymarket alternative

---

## 📚 Reference Docs

- **[reference/voice-guide.md](reference/voice-guide.md)** — Writing style and voice patterns
- **[reference/trading-rules.md](reference/trading-rules.md)** — Memecoin trading rules
- **[reference/scanner-workflow.md](reference/scanner-workflow.md)** — How the scanner operates

---

## 📞 Meeting Notes

- **[meetings/agency/](meetings/agency/)** — Client/agency calls
- **[meetings/content/](meetings/content/)** — Content planning/review
- **[meetings/external/](meetings/external/)** — Partners, vendors, investors
- **[meetings/internal/](meetings/internal/)** — Team standups, 1:1s, strategy

---

## 🗄️ Archive

- Old daily notes (>7 days)
- Completed projects
- Historical scanner logs

---

## ⚡ Quick Stats

- **Skills Created:** 10+
- **Cron Jobs:** 10+ active
- **Data Sources:** 6 (CoinGecko, Birdeye, DexScreener, GMGN, Solscan, BaseScan)
- **Discord Channels:** 5
- **Last System Update:** 2026-02-23

---

*This INDEX is updated automatically. Last refreshed: 2026-02-24*
