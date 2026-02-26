#!/usr/bin/env python3
"""PUNCH token price monitor - Agent compatible"""
import json
import os
import requests
from datetime import datetime

TOKEN_MINT = "NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump"
TOKEN_SYMBOL = "PUNCH"
DATA_DIR = "/Users/pterion2910/.openclaw/workspace/skills/price-monitor/data"
ALERT_THRESHOLD = 10  # 10% change

def fetch_price():
    try:
        resp = requests.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{TOKEN_MINT}",
            timeout=30
        )
        data = resp.json()
        pair = data.get('pairs', [{}])[0]
        return {
            'price': float(pair.get('priceUsd', 0)),
            'change24h': pair.get('priceChange', {}).get('h24', 0),
            'volume': pair.get('volume', {}).get('h24', 0),
            'liquidity': pair.get('liquidity', {}).get('usd', 0),
            'marketCap': pair.get('marketCap', 0),
            'dex': pair.get('dexId', 'unknown')
        }
    except Exception as e:
        return None

def get_previous_price():
    path = f"{DATA_DIR}/punch_last_price.txt"
    try:
        with open(path) as f:
            return float(f.read().strip())
    except:
        return 0

def save_price(price):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(f"{DATA_DIR}/punch_last_price.txt", 'w') as f:
        f.write(str(price))

def main():
    data = fetch_price()
    if not data:
        print("Failed to fetch price")
        return
    
    prev_price = get_previous_price()
    save_price(data['price'])
    
    change_since_last = 0
    if prev_price > 0:
        change_since_last = ((data['price'] - prev_price) / prev_price) * 100
    
    # Format output
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    output = f"""📊 {TOKEN_SYMBOL} Price Update

💰 Price: ${data['price']:.8f}
📈 24h Change: {data['change24h']}%
💎 Market Cap: ${data['marketCap']:,.0f}
📊 24h Volume: ${data['volume']:,.0f}
💧 Liquidity: ${data['liquidity']:,.0f}
🏦 DEX: {data['dex']}
🕐 {timestamp}
"""
    
    # Alert on significant moves
    if abs(change_since_last) > ALERT_THRESHOLD:
        direction = "📈" if change_since_last > 0 else "📉"
        output = f"🚨 {TOKEN_SYMBOL} ALERT: {direction} {change_since_last:.2f}% in 1h\n\n" + output
    
    print(output)
    
    # Save to log
    with open(f"{DATA_DIR}/punch_monitor.log", 'a') as f:
        f.write(f"[{timestamp}] Price: ${data['price']:.8f} | 24h: {data['change24h']}%\n")

if __name__ == "__main__":
    main()
