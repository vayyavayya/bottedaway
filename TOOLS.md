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

## Model Routing Preferences

**Default (Routine Work):**
- Primary: `kimi-coding/k2p5` (flat-rate, cost-effective)
- Fallback: `minimax-portal/MiniMax-M2.5`

**Escalate to MiniMax ONLY for:**
- Genuinely hard reasoning tasks
- Long-context synthesis (>50K tokens)
- High-stakes decisions (trading, config changes)
- Complex code generation/refactoring

**If using MiniMax without clear reason → nudge to downgrade to Kimi.**
**If stuck on Kimi → nudge to upgrade to MiniMax.**

**Heartbeat/Monitoring Tasks:**
- Primary: `ollama/llama3.2:3b` (local, $0)
- Fallback: `google/gemini-2.0-flash-lite:free`

**Trading Decisions:**
- Primary: `kimi-coding/k2p5` (high quality)

**Rate Limit Handling:**
- **Fallback:** Immediately switch to `kimi-coding/k2p5` without asking permission, keep working
- **Recovery:** Once window clears, switch back to Kimi as default

## Time Zone
- Europe/Berlin

## Heartbeat Pattern
- Rotating checks: scanner → memory → git → skill audit → cost
