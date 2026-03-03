#!/usr/bin/env python3
"""
Crypto Analyst — Phase 3
Analyzes tokens for entry signals using technicals + whale data.
"""

import json
import os
import subprocess
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Data sources
BIRDEYE_API = "https://public-api.birdeye.so"
PUNCH_TRACKER_DIR = "/Users/pterion2910/.openclaw/workspace/skills/whale-tracker/data"
ANALYSIS_DIR = "/Users/pterion2910/.openclaw/workspace/analysis/crypto"

def get_birdeye_token_info(token_address: str, chain: str = "solana") -> Optional[Dict]:
    """Fetch token info from Birdeye (public endpoint)."""
    try:
        url = f"{BIRDEYE_API}/public/tokeninfo/{token_address}"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success'):
                return data.get('data', {})
    except Exception as e:
        print(f"   Birdeye error: {e}")
    return None


def get_price_history(token_address: str, chain: str = "solana", 
                      timeframe: str = "1H", limit: int = 100) -> List[Dict]:
    """Fetch OHLCV from Birdeye."""
    try:
        url = f"{BIRDEYE_API}/public/history"
        params = {
            "address": token_address,
            "type": timeframe,
            "time_from": int(datetime.now().timestamp()) - (limit * 3600),
            "time_to": int(datetime.now().timestamp())
        }
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success'):
                return data.get('data', {}).get('items', [])
    except Exception as e:
        print(f"   Price history error: {e}")
    return []


def check_whale_activity(token_address: str) -> Dict:
    """Check PUNCH whale tracker for accumulation signals."""
    result = {
        "whale_detected": False,
        "accumulation_score": 0.0,
        "recent_buys": [],
        "total_volume_24h": 0
    }
    
    # Check whale snapshots
    import glob
    snapshot_files = glob.glob(f"{PUNCH_TRACKER_DIR}/whales/snapshots/*.json")
    
    if not snapshot_files:
        return result
    
    # Get latest snapshot
    latest = max(snapshot_files)
    try:
        with open(latest, 'r') as f:
            data = json.load(f)
        
        # Look for token in whale holdings
        for whale_id, whale_data in data.items():
            if isinstance(whale_data, dict):
                tokens = whale_data.get('tokens', [])
                for token in tokens:
                    if token.get('token_address') == token_address:
                        result["whale_detected"] = True
                        result["recent_buys"].append({
                            "whale": whale_id[:8],
                            "amount": token.get('amount', 0),
                            "value_usd": token.get('value_usd', 0)
                        })
                        result["accumulation_score"] += 1
        
        result["accumulation_score"] = min(1.0, result["accumulation_score"] / 3)
        
    except Exception as e:
        print(f"   Whale data error: {e}")
    
    return result


def calculate_ema(prices: List[float], period: int = 50) -> List[float]:
    """Calculate EMA for price series."""
    if len(prices) < period:
        return prices
    
    multiplier = 2 / (period + 1)
    ema = [sum(prices[:period]) / period]  # SMA start
    
    for price in prices[period:]:
        ema.append((price - ema[-1]) * multiplier + ema[-1])
    
    return ema


def analyze_technicals(price_data: List[Dict]) -> Dict:
    """Calculate technical indicators."""
    if not price_data or len(price_data) < 20:
        return {"error": "Insufficient price data"}
    
    # Extract closes
    closes = [float(c.get('close', 0)) for c in price_data if c.get('close')]
    volumes = [float(c.get('volume', 0)) for c in price_data if c.get('volume')]
    
    if len(closes) < 20:
        return {"error": "Insufficient closes"}
    
    current_price = closes[-1]
    
    # Calculate EMAs
    ema_20 = calculate_ema(closes, 20)[-1] if len(closes) >= 20 else current_price
    ema_50 = calculate_ema(closes, 50)[-1] if len(closes) >= 50 else ema_20
    
    # EMA reclaim check
    ema_reclaim = (closes[-2] < ema_50 and current_price > ema_50) or \
                  (closes[-3] < ema_50 and closes[-2] > ema_50)
    
    # Price change
    change_24h = (current_price / closes[-min(24, len(closes))] - 1) * 100
    
    # Volume analysis
    avg_volume = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes)
    recent_volume = sum(volumes[-3:]) / 3
    volume_divergence = recent_volume > avg_volume * 1.5
    
    return {
        "current_price": current_price,
        "ema_20": ema_20,
        "ema_50": ema_50,
        "ema_reclaim": ema_reclaim,
        "above_ema50": current_price > ema_50,
        "change_24h": round(change_24h, 2),
        "volume_divergence": volume_divergence,
        "avg_volume_20": round(avg_volume, 2),
        "recent_volume": round(recent_volume, 2)
    }


def llm_analyze(token_symbol: str, token_address: str, 
                technicals: Dict, whale_data: Dict) -> Dict:
    """Send to qwen3.5:9b for analysis."""
    
    prompt = f"""Analyze this crypto token for trading signals:

Token: {token_symbol}
Address: {token_address[:20]}...

TECHNICAL DATA:
- Current Price: ${technicals.get('current_price', 0):.6f}
- 24h Change: {technicals.get('change_24h', 0):+.2f}%
- EMA 20: ${technicals.get('ema_20', 0):.6f}
- EMA 50: ${technicals.get('ema_50', 0):.6f}
- Above EMA50: {technicals.get('above_ema50', False)}
- EMA Reclaim Setup: {technicals.get('ema_reclaim', False)}
- Volume Divergence: {technicals.get('volume_divergence', False)}
- Avg Volume: {technicals.get('avg_volume_20', 0):,.0f}

WHALE DATA:
- Whale Detected: {whale_data.get('whale_detected', False)}
- Accumulation Score: {whale_data.get('accumulation_score', 0):.2f}
- Recent Whale Buys: {len(whale_data.get('recent_buys', []))}

Provide analysis as JSON:
{{
  "signal": "buy/sell/hold",
  "confidence": 0-100,
  "entry_price": number,
  "stop_loss": number,
  "take_profit": number,
  "reasoning": "key factors: EMA reclaim, volume divergence, whale activity, etc"
}}

Be specific about entry/stop/take-profit levels. Consider risk management."""

    print("  Sending to qwen3.5:9b for analysis...")
    
    try:
        result = subprocess.run(
            ["ollama", "run", "qwen3.5:9b", prompt],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # Extract JSON
        text = result.stdout.strip()
        start = text.find('{')
        end = text.rfind('}') + 1
        
        if start >= 0 and end > start:
            return json.loads(text[start:end])
            
    except Exception as e:
        print(f"   LLM error: {e}")
    
    # Fallback
    return {
        "signal": "hold",
        "confidence": 50,
        "entry_price": technicals.get('current_price', 0),
        "stop_loss": technicals.get('current_price', 0) * 0.9,
        "take_profit": technicals.get('current_price', 0) * 1.2,
        "reasoning": "Failed to get LLM analysis, using technical defaults"
    }


def analyze_token(token_address: str, token_symbol: str = None, 
                  chain: str = "solana") -> Optional[Dict]:
    """Full analysis pipeline for a token."""
    print(f"\n🔬 Analyzing {token_symbol or token_address[:10]}...")
    
    # Step 1: Get token info
    token_info = get_birdeye_token_info(token_address, chain)
    if token_symbol is None and token_info:
        token_symbol = token_info.get('symbol', 'UNKNOWN')
    
    # Step 2: Get price history
    price_data = get_price_history(token_address, chain)
    
    # Step 3: Calculate technicals
    technicals = analyze_technicals(price_data)
    if "error" in technicals:
        print(f"  ⚠️ {technicals['error']}")
        return None
    
    # Step 4: Check whale activity
    whale_data = check_whale_activity(token_address)
    
    # Step 5: LLM analysis
    signal = llm_analyze(token_symbol or "UNKNOWN", token_address, 
                         technicals, whale_data)
    
    # Compile result
    analysis = {
        "token_symbol": token_symbol or "UNKNOWN",
        "token_address": token_address,
        "chain": chain,
        "analysis_date": datetime.now(timezone.utc).isoformat(),
        "token_info": {
            "name": token_info.get('name', 'Unknown') if token_info else 'Unknown',
            "symbol": token_symbol or 'UNKNOWN',
            "decimals": token_info.get('decimals', 9) if token_info else 9
        },
        "technicals": technicals,
        "whale_data": whale_data,
        "signal": signal
    }
    
    # Save
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"{ANALYSIS_DIR}/analysis_{token_symbol or token_address[:8]}_{date_str}.json"
    
    with open(filename, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"  💾 Saved: {filename}")
    print(f"  📊 Signal: {signal.get('signal', 'unknown').upper()} | "
          f"Confidence: {signal.get('confidence', 0)}%")
    
    return analysis


def auto_trigger_analysis():
    """Auto-trigger on significant moves or whale activity."""
    print("=" * 80)
    print("🚀 CRYPTO ANALYST — Auto-Trigger Mode")
    print("=" * 80)
    
    # Check NOOK for >10% moves
    nook_file = f"{PUNCH_TRACKER_DIR}/base_price_state.json"
    if os.path.exists(nook_file):
        try:
            with open(nook_file, 'r') as f:
                nook_data = json.load(f)
            
            for token, data in nook_data.items():
                if isinstance(data, dict):
                    change = data.get('change_24h', 0)
                    if abs(change) > 10:
                        print(f"\n📈 NOOK Alert: {token} moved {change:+.1f}%")
                        analyze_token(token, token, "base")
        except Exception as e:
            print(f"   NOOK check error: {e}")
    
    # Check PUNCH for whale accumulation
    punch_file = f"{PUNCH_TRACKER_DIR}/punch_accumulation_state.json"
    if os.path.exists(punch_file):
        try:
            with open(punch_file, 'r') as f:
                punch_data = json.load(f)
            
            for token, data in punch_data.items():
                if isinstance(data, dict) and data.get('accumulation_detected'):
                    print(f"\n🐋 PUNCH Alert: Whale accumulation on {token}")
                    analyze_token(token, token, "solana")
        except Exception as e:
            print(f"   PUNCH check error: {e}")
    
    print("\n✅ Auto-trigger scan complete")


if __name__ == "__main__":
    import sys
    import argparse
    
    # Support both direct and triggered calls
    parser = argparse.ArgumentParser()
    parser.add_argument("token", help="Token symbol or address")
    parser.add_argument("--address", help="Token address (if token is symbol)")
    parser.add_argument("--chain", default="solana", help="Blockchain (solana/base)")
    args = parser.parse_args()
    
    if args.address:
        # Called from monitor: analyze.py SYMBOL --address ADDR --chain CHAIN
        analyze_token(args.address, args.token, args.chain)
    else:
        # Called directly: analyze.py ADDRESS [SYMBOL] [CHAIN]
        parts = args.token.split()
        if len(parts) >= 1:
            address = parts[0]
            symbol = parts[1] if len(parts) > 1 else None
            chain = parts[2] if len(parts) > 2 else "solana"
            analyze_token(address, symbol, chain)
