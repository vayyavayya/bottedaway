"""Send Telegram messages."""
import os
import requests
from typing import Optional

# Default to the paired chat
default_chat_id = os.getenv("TELEGRAM_CHAT_ID", "8492071912")

def send_telegram(message: str, chat_id: Optional[str] = None) -> bool:
    """Send message to Telegram."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "8036658935:AAFMwGJ-EOtGcvT_-a528ONAK0O-cI83qtk")
    chat = chat_id or default_chat_id
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=30)
        return resp.status_code == 200
    except Exception as e:
        print(f"[Telegram] Error sending: {e}")
        return False
