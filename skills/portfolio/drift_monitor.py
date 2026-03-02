#!/usr/bin/env python3
"""
Drift Monitor - Check for performance drift and alert if detected.
Can be run as a cron job (e.g., daily) to monitor for degradation.
"""

import sys
import os

# Add workspace to path
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace'))

from skills.portfolio.performance import get_tracker


def send_telegram_alert(message: str) -> bool:
    """Send alert to Telegram via openclaw message tool."""
    import subprocess
    
    cmd = [
        'openclaw', 'message', 'send',
        '--channel', 'telegram',
        '--message', message
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
        return False


def main():
    tracker = get_tracker()
    
    # Check for drift
    drift_alert = tracker.get_drift_alert()
    
    if drift_alert:
        print("Performance drift detected!")
        print(drift_alert['message'])
        
        # Send alert to BigBrother
        success = send_telegram_alert(drift_alert['message'])
        
        if success:
            print("Alert sent successfully.")
        else:
            print("Failed to send alert.")
        
        return 1  # Exit with error code to signal drift
    else:
        print("No drift detected.")
        print(f"Overall win rate: {tracker.metrics.overall_win_rate:.1%}")
        print(f"Recent (20) win rate: {tracker.metrics.recent_20_win_rate:.1%}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
