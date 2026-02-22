"""Simple state management."""
import json
import os
from typing import Dict, Any

STATE_FILE = "/Users/pterion2910/.openclaw/workspace/scanner_engines/state.json"

def load_state() -> Dict[str, Any]:
    """Load state from file."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"watch": {}, "alerts": {}}

def save_state(state: Dict[str, Any]) -> None:
    """Save state to file."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def cooldown_ok(state: Dict[str, Any], key: str, cooldown_hours: int) -> bool:
    """Check if cooldown has passed."""
    import time
    alerts = state.get("alerts", {})
    last = alerts.get(key, 0)
    return (int(time.time()) - last) >= (cooldown_hours * 3600)

def set_alerted(state: Dict[str, Any], key: str) -> None:
    """Mark key as alerted."""
    import time
    if "alerts" not in state:
        state["alerts"] = {}
    state["alerts"][key] = int(time.time())
    
    # Also update watch entry
    if "watch" in state and key in state["watch"]:
        state["watch"][key]["last_alert_at"] = int(time.time())
