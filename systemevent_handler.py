#!/usr/bin/env python3
"""SystemEvent handler for cron jobs - place this in your main session startup"""

import subprocess
import os

def handle_system_event(event_text):
    """Handle systemEvent triggers from cron jobs"""
    
    handlers = {
        "whale_tracker_run": {
            "script": "~/.openclaw/workspace/skills/whale-tracker/run_direct.sh",
            "description": "Whale Tracker Daily 9am"
        },
        "base_price_run": {
            "script": "~/.openclaw/workspace/skills/whale-tracker/run_base_price.sh", 
            "description": "Base Price Monitor 2h"
        },
        "memecoin_scan_run": {
            "script": "~/.openclaw/workspace/skills/whale-tracker/run_memecoin.sh",
            "description": "Memecoin Scanner 12h"
        },
        "polyclaw_run": {
            "script": "~/.openclaw/workspace/skills/polyclaw/run_direct.sh",
            "description": "Polyclaw Research 6h"
        }
    }
    
    if event_text in handlers:
        config = handlers[event_text]
        script_path = os.path.expanduser(config["script"])
        
        print(f"🔄 Executing {config['description']}...")
        print(f"   Script: {script_path}")
        
        try:
            result = subprocess.run(
                ["bash", script_path],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            print(f"   Exit code: {result.returncode}")
            if result.stdout:
                print(f"   Output:\n{result.stdout[-500:]}")  # Last 500 chars
            if result.stderr:
                print(f"   Errors:\n{result.stderr[-200:]}")
                
            return result.returncode == 0
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return False
    else:
        print(f"⚠️ Unknown system event: {event_text}")
        return False

# Example usage for your main session message handler:
# if message.get("system_event"):
#     handle_system_event(message.get("text"))

if __name__ == "__main__":
    # Test all handlers
    import sys
    if len(sys.argv) > 1:
        handle_system_event(sys.argv[1])
    else:
        print("Testing all handlers...")
        for event in ["whale_tracker_run", "base_price_run", "memecoin_scan_run", "polyclaw_run"]:
            print(f"\n{'='*60}")
            handle_system_event(event)
