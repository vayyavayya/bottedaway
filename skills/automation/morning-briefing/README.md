# Skill: morning-briefing

## Description
Generates daily 8 AM morning briefing with crypto watchlist status, open positions, system health, and priorities. Based on Nathan's self-healing infrastructure agent pattern.

## When to Use
- Want daily digest of crypto positions and scanner results
- Need automated morning routine
- Want system health summary
- Following multiple coins/time-sensitive positions

## When NOT to Use
- No active watchlist or positions
- Real-time alerts needed (use specific monitors instead)
- Prefer manual checking

## Pattern: Daily 8 AM Briefing

**Inspired by:** Nathan's "Morning Briefing" from awesome-openclaw-usecases

### What It Includes

**Crypto Section:**
- Watchlist summary (coins tracked)
- Active engine signals
- Performance highlights

**Positions:**
- Open trades status
- P&L summary
- Key levels to watch

**System Status:**
- Cron jobs health
- Scanner schedule
- Backup status

**Priorities:**
- Top opportunities
- Action items for day
- Key reminders (risk management)

## Implementation

### Cron Schedule
```
Daily 8:00 AM (before watchlist report)
```

### Output Format
```
📅 Morning Briefing — 2026-02-17 08:00 UTC

## 🪙 Crypto Watchlist
4 coins tracked
Active Signals:
- $PUP: +42%, Engine A
- $LEO: +378%, Engine B+C

## 📉 Open Positions
Fed Trade: -93%, holding to resolution

## ⚙️ System Status
- Scanner: Every 12h ✅
- Watchlist Report: Daily 8 AM ✅
- Git Backup: Every 2h ✅

## 🎯 Today's Priorities
1. Monitor $PUP for entry
2. Watch $LEO for pullback
3. Review scanner at 8 PM

## 💡 Key Reminder
Position sizing: 1-2% max
Stop loss: -15%
```

## Integration

**Before:** `daily-watchlist-8am` (detailed engine analysis)
**After:** `morning-briefing` (quick summary + priorities)

User gets:
- 8:00 AM: Briefing (what to watch)
- 8:00 AM: Watchlist report (detailed analysis)

## Future Enhancements

- Weather API integration
- Calendar API (upcoming events)
- News headlines
- Economic calendar (Fed events, etc.)
- Portfolio P&L tracking
- Custom priority generation

## Negative Examples

1. **Too much info**: Initially considered 20+ data points
   - Fix: Keep it scannable in 60 seconds
   
2. **Static content**: First version had same priorities daily
   - Fix: Dynamic based on market conditions

3. **No actionable items**: Just data, no guidance
   - Fix: Explicit "Today's Priorities" section

## Artifacts

Briefing saved to:
- Console output (immediate)
- `/mnt/data/reports/morning_briefing.txt` (reference)

## Handoff Protocol

When context compacts:
1. Latest briefing saved to reports
2. Briefing history shows pattern of priorities
3. Skill continues running via cron
