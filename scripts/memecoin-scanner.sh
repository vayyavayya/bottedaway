#!/bin/bash
# Memecoin Scanner - Runs every 720 minutes (12 hours)
# Scans for trending/new tokens and filters by NAOMI'S TRADING RULES
#
# NAOMI RULES:
# - Target MC: $100K-$500K (sweet spot)
# - Wait for first dip, NEVER buy top
# - Liquidity must be locked
# - Track whale wallets on BaseScan
# - Use Bubble Maps to detect dev dumps
# - Check organic vs paid CT hype
# - Exit: 2x → 5x → 10x (not 100x greed!)
# - Golden Rule: "Take profits before someone else takes them from you"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
LOG_FILE="/Users/pterion2910/.openclaw/workspace/memory/scanner-$(date +%Y-%m-%d).log"

# NAOMI CRITERIA
NAOMI_MIN_MC=100000      # $100K minimum
NAOMI_MAX_MC=500000      # $500K maximum (sweet spot)
NAOMI_MIN_LIQUIDITY=10000 # $10K minimum liquidity

echo "=== Memecoin Scanner Run: $TIMESTAMP ===" >> $LOG_FILE
echo "NAOMI RULES: Target MC \$100K-\$500K | Min Liquidity \$10K" >> $LOG_FILE

# Query CoinGecko trending coins
echo "Fetching trending coins from CoinGecko..." >> $LOG_FILE

TRENDING=$(curl -s "https://api.coingecko.com/api/v3/search/trending" 2>/dev/null)

if [ $? -eq 0 ] && [ ! -z "$TRENDING" ]; then
    echo "✓ Trending data received" >> $LOG_FILE
    
    # Parse top trending coins with Naomi filters
    echo "" >> $LOG_FILE
    echo "--- TOP TRENDING COINS (NAOMI FILTERED) ---" >> $LOG_FILE
    
    # Extract coin info using Python with Naomi criteria
    python3 << PYEOF
import json, sys, re

def parse_market_cap(mc_str):
    """Parse market cap string to number."""
    if not mc_str or mc_str == 'N/A':
        return 0
    mc_str = str(mc_str).replace('$', '').replace(',', '')
    multipliers = {'K': 1e3, 'M': 1e6, 'B': 1e9, 'T': 1e12}
    for suffix, mult in multipliers.items():
        if suffix in mc_str:
            try:
                return float(mc_str.replace(suffix, '')) * mult
            except:
                return 0
    try:
        return float(mc_str)
    except:
        return 0

def parse_volume(vol_str):
    """Parse volume string to number."""
    if not vol_str or vol_str == 'N/A':
        return 0
    vol_str = str(vol_str).replace('$', '').replace(',', '')
    multipliers = {'K': 1e3, 'M': 1e6, 'B': 1e9}
    for suffix, mult in multipliers.items():
        if suffix in vol_str:
            try:
                return float(vol_str.replace(suffix, '')) * mult
            except:
                return 0
    try:
        return float(vol_str)
    except:
        return 0

try:
    data = json.loads('''$TRENDING''')
    coins = data.get('coins', [])
    
    NAOMI_MIN_MC = 100000
    NAOMI_MAX_MC = 500000
    
    print("\n🚀 MEMECOIN SCANNER RESULTS (NAOMI RULES)")
    print("=" * 70)
    print(f"📅 Scan Time: $(date -u +"%Y-%m-%d %H:%M UTC")")
    print(f"🎯 Target: \${NAOMI_MIN_MC/1000:.0f}K-\${NAOMI_MAX_MC/1000:.0f}K Market Cap")
    print("=" * 70)
    
    naomi_matches = []
    other_coins = []
    
    for coin in coins:
        item = coin.get('item', {})
        name = item.get('name', 'Unknown')
        symbol = item.get('symbol', '???')
        
        data = item.get('data', {})
        price = data.get('price', 'N/A')
        change_24h = data.get('price_change_percentage_24h', {}).get('usd', 0) or 0
        market_cap_str = data.get('market_cap', 'N/A')
        volume_str = data.get('total_volume', 'N/A')
        
        market_cap = parse_market_cap(market_cap_str)
        volume = parse_volume(volume_str)
        
        coin_data = {
            'name': name,
            'symbol': symbol,
            'price': price,
            'change_24h': change_24h,
            'market_cap': market_cap,
            'market_cap_str': market_cap_str,
            'volume': volume,
            'volume_str': volume_str,
            'score': item.get('score', 'N/A'),
            'platform': item.get('platform_id', 'unknown'),
            'contract': item.get('contract_address', '')
        }
        
        # Check Naomi criteria
        if NAOMI_MIN_MC <= market_cap <= NAOMI_MAX_MC:
            naomi_matches.append(coin_data)
        else:
            other_coins.append(coin_data)
    
    # Print NAOMI SWEET SPOT coins first
    if naomi_matches:
        print(f"\n✅ NAOMI SWEET SPOT MATCHES ({len(naomi_matches)} coins)")
        print("-" * 70)
        
        for i, coin in enumerate(naomi_matches[:5], 1):
            change_str = f"{coin['change_24h']:+.1f}%"
            change_emoji = "🚀" if coin['change_24h'] > 50 else "📈" if coin['change_24h'] > 0 else "📉"
            
            print(f"\n{i}. {coin['name']} (${coin['symbol']}) {change_emoji}")
            print(f"   💰 Price: {coin['price']}")
            print(f"   📊 24h Change: {change_str}")
            print(f"   🏦 Market Cap: {coin['market_cap_str']} (✅ IN RANGE)")
            print(f"   📈 Volume: {coin['volume_str']}")
            
            # Due diligence links
            if coin['contract']:
                if coin['platform'] == 'solana':
                    print(f"   🔍 Solscan: https://solscan.io/token/{coin['contract']}")
                elif coin['platform'] == 'base':
                    print(f"   🔍 BaseScan: https://basescan.org/token/{coin['contract']}")
                print(f"   📊 Bubble Maps: https://app.bubblemaps.io/{coin['platform']}/token/{coin['contract']}")
            
            # Flag high movers
            if coin['change_24h'] > 50:
                print(f"   ⚠️ FLAG: High volatility (+{coin['change_24h']:.1f}%) - Wait for dip!")
            elif coin['change_24h'] > 20:
                print(f"   💡 Notable gains - Monitor for entry")
    else:
        print("\n❌ No coins in Naomi sweet spot (\$100K-\$500K MC)")
    
    # Print other trending coins
    if other_coins:
        print(f"\n📋 OTHER TRENDING COINS ({len(other_coins)} outside range)")
        print("-" * 70)
        
        for coin in other_coins[:3]:
            status = "Below min" if coin['market_cap'] < NAOMI_MIN_MC else "Above max"
            print(f"• {coin['name']} (${coin['symbol']}): {coin['market_cap_str']} ({status})")
    
    # NAOMI DUE DILIGENCE CHECKLIST
    print("\n" + "=" * 70)
    print("⚠️ NAOMI DUE DILIGENCE CHECKLIST:")
    print("=" * 70)
    print("   ☐ Liquidity locked? (check DexScreener/DexTools)")
    print("   ☐ Track whale wallets on BaseScan (for Base tokens)")
    print("   ☐ Use Bubble Maps to detect dev dumps")
    print("   ☐ Check if CT hype is organic vs paid shills")
    print("   ☐ Wait for first dip - NEVER buy the top!")
    print("")
    print("💡 EXIT STRATEGY:")
    print("   • 2x → Take initial out")
    print("   • 5x → Take more profits")  
    print("   • 10x → Don't chase 100x greed")
    print("")
    print("🚨 RED FLAGS (GTFO immediately):")
    print("   • Volume dries up suddenly")
    print("   • Whales start dumping")
    print("")
    print("🎯 GOLDEN RULE:")
    print('   "Take profits before someone else takes them from you"')
    print("=" * 70)
        
except Exception as e:
    print(f"Error parsing data: {e}")
    import traceback
    traceback.print_exc()
PYEOF

else
    echo "✗ Failed to fetch trending data" >> $LOG_FILE
fi

echo "" >> $LOG_FILE
echo "=== Scanner Complete ===" >> $LOG_FILE
echo "" >> $LOG_FILE
