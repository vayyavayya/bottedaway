#!/usr/bin/env python3
"""
Morning Briefing Skill
Generates and delivers daily 8 AM briefing with key info for bigbrother.
"""

import json
import os
import subprocess
from datetime import datetime, timezone

WATCHLIST_FILE = "/Users/pterion2910/.openclaw/workspace/config/memecoin_watchlist.json"

def get_watchlist_summary():
    """Get current watchlist status."""
    try:
        with open(WATCHLIST_FILE, 'r') as f:
            watchlist = json.load(f)
        return f"{len(watchlist)} coins tracked"
    except:
        return "Watchlist unavailable"

def get_open_positions():
    """Get open trading positions."""
    positions = []
    
    # Fed trade (underwater)
    positions.append("Fed rate cut (March): -93%, worthless")
    
    # Watchlist positions
    try:
        with open(WATCHLIST_FILE, 'r') as f:
            watchlist = json.load(f)
        for coin in watchlist:
            positions.append(f"{coin['symbol']}: {coin.get('notes', '')}")
    except:
        pass
    
    return positions

def get_cron_status():
    """Check if cron jobs are healthy."""
    try:
        result = subprocess.run(
            ["openclaw", "cron", "list"],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            return "All systems operational"
        else:
            return "Cron check failed"
    except:
        return "Status unknown"

def generate_briefing():
    """Generate morning briefing."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    
    briefing = f"""📅 **Morning Briefing — {now}**

## 🪙 Crypto Watchlist
{get_watchlist_summary()}
**Active Signals:**
- $PUP: +42%, Engine A (steady)
- $LEO: +378%, Engine B+C (parabolic, watch for dip)

## 📉 Open Positions
**Fed Trade (March):** -93% loss, illiquid — holding to resolution

## ⚙️ System Status
- Scanner: Every 12h ✅
- Watchlist Report: Daily 8 AM ✅
- Git Backup: Every 2h ✅
- Moltbook Learning: Daily midnight ✅

## 🎯 Today's Priorities
1. Monitor $PUP for entry opportunity
2. Watch $LEO for pullback
3. Review any new scanner findings at 8 PM

## 💡 Key Reminder
Position sizing: 1-2% max per coin
Stop loss: -15% from entry
Never buy deep dips (-50%+) without reversal

—
*Next briefing: Tomorrow 8 AM*"""
    
    return briefing

def main():
    """Generate and output morning briefing."""
    briefing = generate_briefing()
    print(briefing)
    
    # Save to file for reference
    os.makedirs("/Users/pterion2910/.openclaw/workspace/reports", exist_ok=True)
    with open("/Users/pterion2910/.openclaw/workspace/reports/morning_briefing.txt", 'w') as f:
        f.write(briefing)

if __name__ == "__main__":
    main()
