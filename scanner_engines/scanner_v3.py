"""
Memecoin Scanner V3 - DexScreener + Birdeye + 3 Pattern Engines + Naomi Rules

DexScreener: Real-time pair discovery
Birdeye: Historical OHLCV data for pattern detection
Pattern Engines: A (12h), B (4h), C (1h) EMA analysis

NAOMI RULES INTEGRATED:
- Target MC: $100K-$500K (sweet spot)
- Wait for first dip, never buy top (Pattern B captures this)
- Liquidity must be locked (check in discovery)
- Track whale wallets on BaseScan
- Use Bubble Maps for dev dump detection
- Check organic vs paid CT hype
- Exit: 2x -> 5x -> 10x (laddered)
- Golden Rule: "Take profits before someone else takes them from you"
"""
import sys
import os
sys.path.insert(0, '/Users/pterion2910/.openclaw/workspace/scanner_engines')

# NAOMI'S TARGET CRITERIA
NAOMI_MIN_MC = 100_000   # $100K minimum
NAOMI_MAX_MC = 500_000   # $500K maximum (sweet spot)
NAOMI_MIN_LIQUIDITY = 10_000  # Minimum $10K liquidity

from src.patterns.engine_a import run_pattern_a
from src.patterns.engine_b import run_pattern_b  
from src.patterns.engine_c import run_pattern_c
from src.data.dexscreener import (
    dex_get_token_pairs, 
    dex_get_boosted_tokens,
    find_best_pair_for_token,
    scan_memecoins_dexscreener,
)
from src.data.birdeye import (
    fetch_candles_birdeye,
    fetch_token_market_data_birdeye,
    scan_tokens_birdeye,
)
from src.state.manager import load_state, save_state, cooldown_ok, set_alerted
from src.formatters.telegram import alert_to_telegram_text
from src.telegram.sender import send_telegram

# Watchlist - tokens to monitor with specific engines
WATCHLIST = {
    # Example: "bonk": {"chain": "solana", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "engines": ["A", "B", "C"]},
}

def analyze_token_with_engines(
    chain: str, 
    address: str, 
    symbol: str, 
    engines: list, 
    cooldown_hours: int = 72, 
    debug: bool = False,
    enforce_naomi_rules: bool = True  # NEW: Apply Naomi's criteria
):
    """Run all enabled engines for a token using Birdeye OHLCV data."""
    state = load_state()
    key = f"{chain}:{address}"
    
    # Check cooldown
    if not cooldown_ok(state, key, cooldown_hours):
        if debug:
            print(f"[Scanner] {key} in cooldown, skipping")
        return []
    
    alerts = []
    
    # Get current market data from Birdeye
    market_data = fetch_token_market_data_birdeye(chain, address, debug)
    if not market_data:
        if debug:
            print(f"[Scanner] No market data for {key}")
        return []
    
    current_price = float(market_data.get("price", 0))
    marketcap = float(market_data.get("marketCap", 0) or 0)
    liquidity = float(market_data.get("liquidity", 0) or 0)
    
    # NAOMI RULE: Target MC $100K-$500K
    if enforce_naomi_rules:
        if marketcap < NAOMI_MIN_MC or marketcap > NAOMI_MAX_MC:
            if debug:
                print(f"[Scanner] {symbol}: MC ${marketcap:,.0f} outside Naomi range (${NAOMI_MIN_MC/1000:.0f}K-${NAOMI_MAX_MC/1000:.0f}K), skipping")
            return []
        if liquidity < NAOMI_MIN_LIQUIDITY:
            if debug:
                print(f"[Scanner] {symbol}: Liquidity ${liquidity:,.0f} < ${NAOMI_MIN_LIQUIDITY:,.0f}, skipping")
            return []
    
    if debug:
        print(f"[Scanner] {symbol}: Price=${current_price:.6f}, MC=${marketcap:,.0f}, Liq=${liquidity:,.0f}")
        if enforce_naomi_rules:
            print(f"[Scanner] ✅ {symbol} passes Naomi criteria (${NAOMI_MIN_MC/1000:.0f}K-${NAOMI_MAX_MC/1000:.0f}K MC)")
    
    # Engine A - 12h EMA50 reclaim
    if "A" in engines:
        print(f"[Engine A] Checking {symbol} (12h)...")
        candles = fetch_candles_birdeye(chain, address, timeframe="12H", limit=100, debug=debug)
        
        if candles and len(candles) >= 52:
            alert = run_pattern_a(chain, address, candles)
            if alert:
                alert["symbol"] = symbol
                alert["marketcap"] = marketcap
                alerts.append(alert)
                print(f"[Engine A] 🚨 ALERT: {symbol} triggered EMA50 reclaim!")
        else:
            if debug:
                print(f"[Engine A] Insufficient 12h candles for {symbol}: {len(candles) if candles else 0}")
    
    # Engine B - 4h EMA50 reclaim after dump
    if "B" in engines and not alerts:
        print(f"[Engine B] Checking {symbol} (4h)...")
        candles = fetch_candles_birdeye(chain, address, timeframe="4H", limit=100, debug=debug)
        
        if candles and len(candles) >= 60:
            alert = run_pattern_b(chain, address, candles)
            if alert:
                alert["symbol"] = symbol
                alert["marketcap"] = marketcap
                alerts.append(alert)
                print(f"[Engine B] 🚨 ALERT: {symbol} triggered 4h reclaim!")
        else:
            if debug:
                print(f"[Engine B] Insufficient 4h candles for {symbol}")
    
    # Engine C - 1h EMA50 hold, MC >= 300k
    if "C" in engines and not alerts:
        print(f"[Engine C] Checking {symbol} (1h)...")
        
        # Check MC requirement first
        if marketcap >= 300_000:
            candles = fetch_candles_birdeye(chain, address, timeframe="1H", limit=100, debug=debug)
            
            if candles and len(candles) >= 50:
                # Inject marketcap into candles for pattern_c
                for c in candles:
                    c["marketcap"] = marketcap
                
                alert = run_pattern_c(chain, address, candles)
                if alert:
                    alert["symbol"] = symbol
                    alerts.append(alert)
                    print(f"[Engine C] 🚀 ALERT: {symbol} triggered 1h EMA hold!")
            else:
                if debug:
                    print(f"[Engine C] Insufficient 1h candles for {symbol}")
        else:
            if debug:
                print(f"[Engine C] MC too low for {symbol}: ${marketcap:,.0f} < $300k")
    
    # Send alerts
    for alert in alerts:
        text = alert_to_telegram_text(alert)
        send_telegram(text)
        set_alerted(state, key)
        print(f"[Scanner] ✅ Alert sent for {symbol}")
    
    save_state(state)
    return alerts

def discover_via_dexscreener(min_liquidity: float = NAOMI_MIN_LIQUIDITY, enforce_naomi_mc: bool = True, debug: bool = False):
    """Discover tokens via DexScreener boosted tokens. Applies Naomi rules."""
    print("=" * 60)
    print("🔍 DISCOVERING TOKENS VIA DEXSCREENER (Naomi Rules)")
    print(f"   Target MC: ${NAOMI_MIN_MC/1000:.0f}K-${NAOMI_MAX_MC/1000:.0f}K | Min Liquidity: ${min_liquidity:,.0f}")
    print("=" * 60)
    
    opportunities = scan_memecoins_dexscreener(
        chains=["solana", "ethereum", "base"],
        min_liquidity=min_liquidity,
        max_age_hours=72,
        debug=debug
    )
    
    # Apply Naomi MC filter
    if enforce_naomi_mc:
        opportunities = [
            opp for opp in opportunities 
            if NAOMI_MIN_MC <= opp.get('marketcap', 0) <= NAOMI_MAX_MC
        ]
    
    print(f"\n📊 Found {len(opportunities)} opportunities matching Naomi criteria")
    
    # Sort by volume
    opportunities.sort(key=lambda x: x.get("volume_24h", 0), reverse=True)
    
    # Show top 10 with NAOMI DUE DILIGENCE NOTES
    for i, opp in enumerate(opportunities[:10], 1):
        print(f"\n{i}. {opp['symbol']} ({opp['chain']})")
        print(f"   💰 Price: ${opp['price']:.8f}")
        print(f"   💧 Liquidity: ${opp['liquidity']:,.0f}")
        print(f"   📊 Volume 24h: ${opp['volume_24h']:,.0f}")
        print(f"   🏦 Market Cap: ${opp['marketcap']:,.0f}")
        print(f"   📈 Change 24h: {opp['price_change_24h']:+.1f}%")
        # NAOMI DUE DILIGENCE LINKS
        if opp['chain'] == 'base':
            print(f"   🔍 BaseScan: https://basescan.org/token/{opp['address']}")
        elif opp['chain'] == 'solana':
            print(f"   🔍 Solscan: https://solscan.io/token/{opp['address']}")
        print(f"   📊 Bubble Maps: https://app.bubblemaps.io/{opp['chain']}/token/{opp['address']}")
    
    if opportunities:
        print("\n" + "=" * 60)
        print("⚠️ NAOMI DUE DILIGENCE CHECKLIST:")
        print("   ☐ Liquidity locked? (check DexScreener lock icon)")
        print("   ☐ Track whale wallets on BaseScan (for Base tokens)")
        print("   ☐ Use Bubble Maps to detect dev dumps")
        print("   ☐ Check if CT hype is organic vs paid shills")
        print("   ☐ Wait for first dip - NEVER buy the top!")
        print("   💡 Exit plan: 2x → 5x → 10x (not 100x greed)")
        print("   🚨 Volume dries up? Whales dump? GTFO immediately")
        print("=" * 60)
    
    return opportunities

def discover_via_birdeye(min_liquidity: float = 10000, limit: int = 50, debug: bool = False):
    """Discover tokens via Birdeye scan."""
    print("=" * 60)
    print("🔍 DISCOVERING TOKENS VIA BIRDEYE")
    print("=" * 60)
    
    tokens = scan_tokens_birdeye(
        chain="solana",
        sort_by="v24hUSD",
        limit=limit,
        min_liquidity=min_liquidity,
        debug=debug
    )
    
    print(f"\n📊 Found {len(tokens)} Solana tokens")
    
    # Show top 10
    for i, token in enumerate(tokens[:10], 1):
        print(f"\n{i}. {token['symbol']} ({token['chain']})")
        print(f"   💰 Price: ${token['price']:.8f}")
        print(f"   💧 Liquidity: ${token['liquidity']:,.0f}")
        print(f"   📊 Volume 24h: ${token['volume_24h']:,.0f}")
        print(f"   🏦 Market Cap: ${token['marketcap']:,.0f}")
        print(f"   📈 Change 24h: {token['price_change_24h']:+.1f}%")
    
    return tokens

def scan_watchlist(debug: bool = False):
    """Scan configured watchlist with pattern engines."""
    print("\n" + "=" * 60)
    print("🎯 SCANNING WATCHLIST WITH PATTERN ENGINES")
    print("=" * 60)
    
    if not WATCHLIST:
        print("\n⚠️  WATCHLIST is empty!")
        print("Add tokens to WATCHLIST in scanner_v3.py")
        print("\nExample:")
        print('  "bonk": {')
        print('      "chain": "solana",')
        print('      "address": "DezXAZ8z7Pnr...",')
        print('      "engines": ["A", "B", "C"]')
        print('  },')
        return
    
    total_alerts = 0
    
    for symbol, config in WATCHLIST.items():
        chain = config.get("chain", "solana")
        address = config.get("address", "")
        engines = config.get("engines", ["A"])
        
        if not address:
            print(f"⚠️  Skipping {symbol}: no address")
            continue
        
        print(f"\n📊 Checking {symbol.upper()}...")
        alerts = analyze_token_with_engines(chain, address, symbol, engines, debug=debug)
        total_alerts += len(alerts)
    
    print(f"\n✅ Scan complete! {total_alerts} alerts triggered.")

def main():
    """Main scanner loop."""
    import argparse
    parser = argparse.ArgumentParser(description="Memecoin Scanner V3 - DexScreener + Birdeye + Pattern Engines")
    parser.add_argument("--discover-dex", action="store_true", help="Discover via DexScreener")
    parser.add_argument("--discover-birdeye", action="store_true", help="Discover via Birdeye (Solana)")
    parser.add_argument("--scan", action="store_true", help="Scan watchlist with pattern engines")
    parser.add_argument("--all", action="store_true", help="Run everything")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    args = parser.parse_args()
    
    if args.all or (not args.discover_dex and not args.discover_birdeye and not args.scan):
        args.discover_dex = True
        args.discover_birdeye = True
        args.scan = True
    
    if args.discover_dex:
        discover_via_dexscreener(debug=args.debug)
    
    if args.discover_birdeye:
        discover_via_birdeye(debug=args.debug)
    
    if args.scan:
        scan_watchlist(debug=args.debug)

if __name__ == "__main__":
    main()
