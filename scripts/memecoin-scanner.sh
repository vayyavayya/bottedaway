#!/bin/bash
# Memecoin Scanner - Runs every 720 minutes (12 hours)
# Scans for trending/new tokens and filters by criteria

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_FILE="/Users/pterion2910/.openclaw/workspace/memory/scanner-$(date +%Y-%m-%d).log"

echo "=== Memecoin Scanner Run: $TIMESTAMP ===" >> $LOG_FILE

# Query CoinGecko trending coins
echo "Fetching trending coins from CoinGecko..." >> $LOG_FILE

TRENDING=$(curl -s "https://api.coingecko.com/api/v3/search/trending" 2>/dev/null)

if [ $? -eq 0 ] && [ ! -z "$TRENDING" ]; then
    echo "✓ Trending data received" >> $LOG_FILE
    
    # Parse top 5 trending coins
    echo "" >> $LOG_FILE
    echo "--- TOP TRENDING COINS ---" >> $LOG_FILE
    
    # Extract coin info using Python
    python3 << 'PYEOF'
import json, sys

try:
    data = json.loads('''$TRENDING''')
    coins = data.get('coins', [])[:5]
    
    print("\n🚀 TRENDING MEMECOIN SCANNER RESULTS\n")
    print(f"Scan Time: $(date -u +"%Y-%m-%d %H:%M UTC")")
    print("=" * 60)
    
    for i, coin in enumerate(coins, 1):
        item = coin.get('item', {})
        name = item.get('name', 'Unknown')
        symbol = item.get('symbol', '???')
        price = item.get('data', {}).get('price', 'N/A')
        change_24h = item.get('data', {}).get('price_change_percentage_24h', {}).get('usd', 0)
        market_cap = item.get('data', {}).get('market_cap', 'N/A')
        volume = item.get('data', {}).get('total_volume', 'N/A')
        
        # Color coding for changes
        change_str = f"{change_24h:+.1f}%" if change_24h else "N/A"
        
        print(f"\n{i}. {name} (${symbol})")
        print(f"   Price: {price}")
        print(f"   24h Change: {change_str}")
        print(f"   Market Cap: {market_cap}")
        print(f"   Volume: {volume}")
        
        # Filter criteria check
        print(f"   ✓ Trending rank: #{item.get('score', 'N/A')}")
        
except Exception as e:
    print(f"Error parsing data: {e}")
PYEOF

else
    echo "✗ Failed to fetch trending data" >> $LOG_FILE
fi

echo "" >> $LOG_FILE
echo "=== Scanner Complete ===" >> $LOG_FILE
echo "" >> $LOG_FILE
