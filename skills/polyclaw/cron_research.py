#!/usr/bin/env python3
"""
POLYCLAW Research Cron Wrapper
Runs scanner → research on top 5 markets → saves aggregated results
Includes resolution watcher to update memory when markets resolve
Cost: ~$1.50 per run (5 markets × $0.30)
"""

import json
import os
import sys
from datetime import datetime

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_DIR = os.path.expanduser("~/.openclaw/workspace")
OUTPUT_DIR = os.path.join(WORKSPACE_DIR, "analysis", "daily-briefs")
LOG_DIR = os.path.join(WORKSPACE_DIR, "logs")

# Ensure directories exist
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Add research.py to path
sys.path.insert(0, SCRIPT_DIR)

def run_resolution_watcher():
    """Check for resolved markets and update memory"""
    try:
        from resolution_watcher import check_all_tracked
        newly_resolved = check_all_tracked()
        return len(newly_resolved)
    except Exception as e:
        return f"error: {e}"

def main():
    timestamp = datetime.now()
    date_str = timestamp.strftime("%Y-%m-%d")
    time_str = timestamp.strftime("%H%M%S")
    timestamp_iso = timestamp.isoformat()
    
    log_file = os.path.join(LOG_DIR, "polyclaw-research.log")
    
    def log(msg):
        print(msg)
        with open(log_file, "a") as f:
            f.write(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")
    
    log("=" * 60)
    log(f"🤖 POLYCLAW RESEARCH CRON - {timestamp.strftime('%Y%m%d_%H%M%S')}")
    log("=" * 60)
    
    # Step 1: Check for resolved markets and update memory
    log("🔍 Step 1: Checking for resolved markets...")
    resolved_count = run_resolution_watcher()
    if isinstance(resolved_count, str) and resolved_count.startswith("error"):
        log(f"   ⚠️ Resolution watcher: {resolved_count}")
    elif resolved_count > 0:
        log(f"   ✅ {resolved_count} markets resolved - memory updated")
    else:
        log("   ⏳ No new resolutions")
    
    # Step 2: Run research on trending markets
    log(f"📡 Step 2: Scanning top 5 trending markets...")
    
    try:
        # Import and run research pipeline
        from research import research_top_markets
        
        results = research_top_markets(top_n=5)
        
        # Build daily brief
        daily_brief = {
            "meta": {
                "version": "1.0",
                "generated_at": timestamp_iso,
                "run_type": "scheduled",
                "markets_analyzed": len(results),
                "estimated_cost_usd": round(len(results) * 0.30, 2),
                "markets_resolved_in_run": resolved_count if isinstance(resolved_count, int) else 0
            },
            "summary": {
                "total": len(results),
                "trade_recommendations": sum(1 for r in results if r.get("recommendation") == "TRADE"),
                "paper_trades": sum(1 for r in results if r.get("recommendation") == "PAPER_TRADE"),
                "pass": sum(1 for r in results if r.get("recommendation") == "PASS"),
                "errors": sum(1 for r in results if "error" in r)
            },
            "markets": results
        }
        
        # Save to daily-briefs directory
        output_file = os.path.join(OUTPUT_DIR, f"polymarket_{date_str}_{time_str}.json")
        with open(output_file, "w") as f:
            json.dump(daily_brief, f, indent=2)
        
        log(f"✅ Research complete!")
        log(f"📄 Output: {output_file}")
        log(f"📊 Results: {daily_brief['summary']['trade_recommendations']} TRADE, "
            f"{daily_brief['summary']['paper_trades']} PAPER, "
            f"{daily_brief['summary']['pass']} PASS")
        log(f"💰 Cost: ~${daily_brief['meta']['estimated_cost_usd']}")
        log("=" * 60)
        
        return 0
        
    except Exception as e:
        log(f"❌ Error: {str(e)}")
        import traceback
        log(traceback.format_exc())
        return 1

if __name__ == "__main__":
    sys.exit(main())
