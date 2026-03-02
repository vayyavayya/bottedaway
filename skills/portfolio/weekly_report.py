#!/usr/bin/env python3
"""
Weekly Performance Report - Run via cron every Sunday at 9am
Generates and sends performance report to Telegram.
"""

import sys
import os

# Add workspace to path
sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace'))

from skills.portfolio.performance import get_tracker, check_drift


def send_telegram_message(message: str) -> bool:
    """Send message to Telegram via openclaw message tool."""
    import subprocess
    
    # Use openclaw CLI to send message
    cmd = [
        'openclaw', 'message', 'send',
        '--channel', 'telegram',
        '--message', message
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")
        return False


def main():
    tracker = get_tracker()
    
    # Generate weekly report
    report = tracker.get_weekly_report()
    
    # Send report
    success = send_telegram_message(report)
    
    if success:
        print("Weekly report sent successfully.")
    else:
        print("Failed to send weekly report.")
        # Fallback: print to stdout for logging
        print(report)
    
    # Check for drift and send alert if needed
    drift_alert = tracker.get_drift_alert()
    if drift_alert:
        print("Drift detected, sending alert...")
        send_telegram_message(drift_alert['message'])


if __name__ == "__main__":
    main()
