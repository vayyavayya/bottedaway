#!/usr/bin/env python3
"""
Crypto Analyst - Token Analysis Pipeline

Analyzes a crypto token using:
1. Birdeye API for price/volume/market data
2. Whale tracker for smart money activity
3. LLM analysis for trading signals

Usage:
    python analyze.py PUNCH
    python analyze.py NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump
    python analyze.py TOKEN --chain ethereum --address 0x123...
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

import requests

# Configuration
SCRIPT_DIR = Path(__file__).parent.resolve()
WORKSPACE_DIR = SCRIPT_DIR.parent.parent
OUTPUT_DIR = WORKSPACE_DIR / "analysis" / "crypto"
SCANNER_DIR = WORKSPACE_DIR / "scanner_engines"
WHALE_TRACKER_DIR = WORKSPACE_DIR / "skills" / "whale-tracker"

# Add scanner_engines to path for Birdeye imports
sys.path.insert(0, str(SCANNER_DIR / "src" / "data"))

try:
    from birdeye import (
        fetch_token_market_data_birdeye,
        fetch_token_metadata_birdeye,
        fetch_candles_birdeye,
        BIRDEYE_API_KEY,
    )
except ImportError:
    print("⚠️ Could not import Birdeye module. Using fallback implementation.")
    fetch_token_market_data_birdeye = None
    fetch_token_metadata_birdeye = None
    fetch_candles_birdeye = None
    BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "bb463164ead7429686f982258664fdb9")

# Known token mappings
KNOWN_TOKENS = {
    "PUNCH": {
        "address": "NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump",
        "chain": "solana",
        "symbol": "PUNCH"
    },
    "SOL": {
        "address": "So11111111111111111111111111111111111111112",
        "chain": "solana",
        "symbol": "SOL"
    },
    "USDC": {
        "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "chain": "solana",
        "symbol": "USDC"
    },
    "BONK": {
        "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "chain": "solana",
        "symbol": "BONK"
    },
    "WIF": {
        "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
        "chain": "solana",
        "symbol": "WIF"
    },
    "PEPE": {
        "address": "0x6982508145454Ce325dDbE47a25d4ec3d2311933",
        "chain": "ethereum",
        "symbol": "PEPE"
    },
    "SHIB": {
        "address": "0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce",
        "chain": "ethereum",
        "symbol": "SHIB"
    },
}

# Helius API
HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "")
HELIUS_BASE_URL = "https://mainnet.helius-rpc.com"

# LLM Configuration
OPENCLAW_GATEWAY_URL = os.getenv("OPENCLAW_GATEWAY_URL", "http://localhost:8080")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


def resolve_token(input_str: str) -> Optional[Dict[str, str]]:
    """Resolve token symbol or address to token info."""
    input_upper = input_str.upper()
    
    # Check known tokens by symbol
    if input_upper in KNOWN_TOKENS:
        return KNOWN_TOKENS[input_upper].copy()
    
    # Check if input looks like a Solana address (base58, 32-44 chars)
    if len(input_str) >= 32 and len(input_str) <= 44:
        # Assume Solana by default
        return {
            "address": input_str,
            "chain": "solana",
            "symbol": input_str[:8] + "..." if len(input_str) > 8 else input_str
        }
    
    # Check if input looks like an Ethereum address (0x + 40 hex chars)
    if input_str.startswith("0x") and len(input_str) == 42:
        return {
            "address": input_str,
            "chain": "ethereum",
            "symbol": input_str[:10] + "..."
        }
    
    return None


def fetch_market_data_birdeye_fallback(chain: str, address: str) -> Optional[Dict]:
    """Fallback implementation for fetching market data from Birdeye."""
    url = "https://public-api.birdeye.so/defi/v3/token/market-data"
    params = {"chain": chain, "address": address}
    headers = {
        "accept": "application/json",
        "X-API-KEY": BIRDEYE_API_KEY,
    }
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        data = resp.json()
        
        if data.get("success"):
            return data.get("data", {})
        return None
    except Exception as e:
        print(f"⚠️ Birdeye market data error: {e}")
        return None


def fetch_metadata_birdeye_fallback(chain: str, address: str) -> Optional[Dict]:
    """Fallback implementation for fetching token metadata."""
    url = "https://public-api.birdeye.so/defi/v3/token/meta-data/single"
    params = {"chain": chain, "address": address}
    headers = {
        "accept": "application/json",
        "X-API-KEY": BIRDEYE_API_KEY,
    }
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        data = resp.json()
        
        if data.get("success"):
            return data.get("data", {})
        return None
    except Exception as e:
        print(f"⚠️ Birdeye metadata error: {e}")
        return None


def fetch_candles_birdeye_fallback(chain: str, address: str, timeframe: str = "1H", limit: int = 100) -> List[Dict]:
    """Fallback implementation for fetching OHLCV candles."""
    url = "https://public-api.birdeye.so/defi/ohlcv"
    
    now = int(time.time())
    tf_seconds = {
        "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
        "1H": 3600, "2H": 7200, "4H": 14400, "6H": 21600,
        "8H": 28800, "12H": 43200, "1D": 86400,
        "3D": 259200, "1W": 604800, "1M": 2592000
    }
    
    seconds = tf_seconds.get(timeframe, 3600)
    time_from = now - (limit * seconds)
    
    params = {
        "address": address,
        "type": timeframe,
        "time_from": time_from,
        "time_to": now,
    }
    headers = {
        "accept": "application/json",
        "X-API-KEY": BIRDEYE_API_KEY,
    }
    
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        data = resp.json()
        
        if data.get("success"):
            items = data.get("data", {}).get("items", [])
            candles = []
            for item in items:
                candles.append({
                    "ts": int(item.get("unixTime", 0)),
                    "o": float(item.get("o", 0)),
                    "h": float(item.get("h", 0)),
                    "l": float(item.get("l", 0)),
                    "c": float(item.get("c", 0)),
                    "v": float(item.get("v", 0)),
                })
            return candles
        return []
    except Exception as e:
        print(f"⚠️ Birdeye candles error: {e}")
        return []


def fetch_token_market_data(chain: str, address: str) -> Optional[Dict]:
    """Fetch market data using available method."""
    if fetch_token_market_data_birdeye:
        return fetch_token_market_data_birdeye(chain, address)
    return fetch_market_data_birdeye_fallback(chain, address)


def fetch_token_metadata(chain: str, address: str) -> Optional[Dict]:
    """Fetch token metadata using available method."""
    if fetch_token_metadata_birdeye:
        return fetch_token_metadata_birdeye(chain, address)
    return fetch_metadata_birdeye_fallback(chain, address)


def fetch_token_candles(chain: str, address: str, timeframe: str = "1H", limit: int = 100) -> List[Dict]:
    """Fetch OHLCV candles using available method."""
    if fetch_candles_birdeye:
        return fetch_candles_birdeye(chain, address, timeframe, limit)
    return fetch_candles_birdeye_fallback(chain, address, timeframe, limit)


def fetch_whale_activity(chain: str, address: str, symbol: str) -> Dict:
    """
    Fetch whale activity data from whale tracker.
    Checks recent snapshots for this token and fetches top holders via Helius.
    """
    whale_data = {
        "tracked_by_whales": False,
        "whale_buy_signals": 0,
        "whale_wallets_holding": [],
        "top_holders": [],
        "recent_accumulation": []
    }
    
    # Check whale tracker snapshots
    snapshots_dir = WHALE_TRACKER_DIR / "data" / "whales" / "snapshots"
    if snapshots_dir.exists():
        # Get last 7 days of snapshots
        snapshot_files = sorted(snapshots_dir.glob("*.json"), reverse=True)[:7]
        
        for snapshot_file in snapshot_files:
            try:
                with open(snapshot_file, 'r') as f:
                    snapshot = json.load(f)
                
                for token_data in snapshot.get("tokens", []):
                    token_addr = token_data.get("address", "").lower()
                    if token_addr == address.lower():
                        whale_data["tracked_by_whales"] = True
                        whale_data["whale_buy_signals"] += 1
                        
                        # Track which wallets bought
                        for wallet in token_data.get("buying_wallets", []):
                            if wallet not in whale_data["whale_wallets_holding"]:
                                whale_data["whale_wallets_holding"].append(wallet)
            except Exception:
                pass
    
    # Fetch top holders via Helius (Solana only)
    if chain == "solana" and HELIUS_API_KEY:
        try:
            url = f"{HELIUS_BASE_URL}/?api-key={HELIUS_API_KEY}"
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTokenLargestAccounts",
                "params": [address]
            }
            response = requests.post(url, json=payload, timeout=30)
            data = response.json()
            
            if "result" in data and "value" in data["result"]:
                holders = data["result"]["value"][:10]  # Top 10 holders
                for holder in holders:
                    whale_data["top_holders"].append({
                        "address": holder.get("address", ""),
                        "amount": holder.get("amount", "0"),
                        "decimals": holder.get("decimals", 0)
                    })
        except Exception as e:
            print(f"⚠️ Helius top holders fetch failed: {e}")
    
    return whale_data


def calculate_technical_indicators(candles: List[Dict]) -> Dict:
    """Calculate technical indicators from OHLCV data."""
    if len(candles) < 50:
        return {"error": "Insufficient data for technical analysis"}
    
    # Sort by timestamp
    candles_sorted = sorted(candles, key=lambda x: x["ts"])
    closes = [c["c"] for c in candles_sorted]
    volumes = [c["v"] for c in candles_sorted]
    
    # EMA calculations
    def ema(data: List[float], period: int) -> List[float]:
        multiplier = 2 / (period + 1)
        ema_values = [data[0]]
        for price in data[1:]:
            ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
        return ema_values
    
    ema50 = ema(closes, 50)
    ema20 = ema(closes, 20)
    
    current_price = closes[-1]
    current_ema50 = ema50[-1]
    current_ema20 = ema20[-1]
    
    # EMA Reclaim detection
    ema_reclaim = {
        "setup_present": False,
        "price_above_ema50": current_price > current_ema50,
        "price_above_ema20": current_price > current_ema20,
        "ema50_above_ema20": current_ema50 > current_ema20,
        "current_price": current_price,
        "ema50": current_ema50,
        "ema20": current_ema20
    }
    
    # Check for EMA50 reclaim (price crossed above EMA50 recently)
    if len(closes) >= 5:
        prev_price = closes[-5]
        if prev_price < ema50[-5] and current_price > current_ema50:
            ema_reclaim["setup_present"] = True
            ema_reclaim["reclaim_type"] = "bullish_ema50_reclaim"
    
    # Volume analysis
    avg_volume = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes)
    current_volume = volumes[-1]
    volume_surge = current_volume > avg_volume * 1.5
    
    volume_divergence = {
        "type": "neutral",
        "current_volume": current_volume,
        "avg_volume_20": avg_volume,
        "volume_surge": volume_surge
    }
    
    if volume_surge and current_price > closes[-2]:
        volume_divergence["type"] = "bullish_accumulation"
    elif volume_surge and current_price < closes[-2]:
        volume_divergence["type"] = "bearish_distribution"
    
    # Support/Resistance levels
    recent_lows = [c["l"] for c in candles_sorted[-20:]]
    recent_highs = [c["h"] for c in candles_sorted[-20:]]
    
    support_resistance = {
        "nearest_support": min(recent_lows) if recent_lows else None,
        "nearest_resistance": max(recent_highs) if recent_highs else None,
        "recent_range_low": min(closes[-10:]) if len(closes) >= 10 else min(closes),
        "recent_range_high": max(closes[-10:]) if len(closes) >= 10 else max(closes)
    }
    
    return {
        "ema_reclaim": ema_reclaim,
        "volume_divergence": volume_divergence,
        "support_resistance": support_resistance,
        "price_change_24h_pct": ((closes[-1] - closes[-24]) / closes[-24] * 100) if len(closes) >= 24 else None,
        "price_change_1h_pct": ((closes[-1] - closes[-2]) / closes[-2] * 100) if len(closes) >= 2 else None,
    }


def call_llm_analysis(prompt: str) -> Optional[Dict]:
    """Call LLM for analysis via OpenClaw gateway or OpenRouter fallback."""
    
    # Try OpenClaw gateway first (local models)
    try:
        response = requests.post(
            f"{OPENCLAW_GATEWAY_URL}/v1/chat/completions",
            json={
                "model": "qwen3:30b-a3b-q4_K_M",
                "messages": [
                    {"role": "system", "content": "You are a crypto trading analyst. Respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 1500
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            
            # Try to parse JSON from the content
            try:
                # Handle markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                return json.loads(content)
            except json.JSONDecodeError:
                # Return raw content if JSON parsing fails
                return {"raw_response": content}
    except Exception as e:
        print(f"⚠️ OpenClaw gateway failed: {e}")
    
    # Fallback to OpenRouter
    if OPENROUTER_API_KEY:
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "qwen/qwen3-30b-a3b:free",
                    "messages": [
                        {"role": "system", "content": "You are a crypto trading analyst. Respond with valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 1500
                },
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                try:
                    if "```json" in content:
                        content = content.split("```json")[1].split("```")[0].strip()
                    elif "```" in content:
                        content = content.split("```")[1].split("```")[0].strip()
                    
                    return json.loads(content)
                except json.JSONDecodeError:
                    return {"raw_response": content}
        except Exception as e:
            print(f"⚠️ OpenRouter failed: {e}")
    
    return None


def build_analysis_prompt(
    symbol: str,
    chain: str,
    market_data: Dict,
    whale_data: Dict,
    technical: Dict
) -> str:
    """Build the prompt for LLM analysis."""
    
    price = market_data.get("price", 0)
    price_change_24h = market_data.get("priceChange24h", 0)
    volume_24h = market_data.get("volume24h", 0) or market_data.get("v24hUSD", 0)
    liquidity = market_data.get("liquidity", 0)
    marketcap = market_data.get("marketcap", 0) or market_data.get("marketCap", 0)
    
    ema_reclaim = technical.get("ema_reclaim", {})
    volume_divergence = technical.get("volume_divergence", {})
    
    whale_summary = f"""
- Tracked by whale wallets: {'Yes' if whale_data.get('tracked_by_whales') else 'No'}
- Whale buy signals (last 7 days): {whale_data.get('whale_buy_signals', 0)}
- Unique whale wallets holding: {len(whale_data.get('whale_wallets_holding', []))}
- Top holders count: {len(whale_data.get('top_holders', []))}
"""
    
    prompt = f"""Analyze this token for trading opportunity:

TOKEN: {symbol} on {chain}

MARKET DATA:
- Current Price: ${price:.8f}
- 24h Change: {price_change_24h:.2f}%
- 24h Volume: ${volume_24h:,.0f}
- Liquidity: ${liquidity:,.0f}
- Market Cap: ${marketcap:,.0f}

TECHNICAL INDICATORS:
- EMA50 Reclaim Setup: {'YES' if ema_reclaim.get('setup_present') else 'NO'}
  - Price above EMA50: {ema_reclaim.get('price_above_ema50', False)}
  - Price above EMA20: {ema_reclaim.get('price_above_ema20', False)}
  - EMA50: ${ema_reclaim.get('ema50', 0):.8f}
- Volume Pattern: {volume_divergence.get('type', 'neutral')}
  - Current vs Avg: {volume_divergence.get('current_volume', 0):,.0f} vs {volume_divergence.get('avg_volume_20', 0):,.0f}
  - Volume Surge: {'YES' if volume_divergence.get('volume_surge') else 'NO'}

WHALE ACTIVITY:
{whale_summary}

ANALYSIS CHECKLIST:
1. EMA Reclaim Setup - Is price reclaiming EMA50 with volume?
2. Volume Divergence - Is there bullish accumulation or bearish distribution?
3. Whale Accumulation Pattern - Are smart money wallets accumulating?
4. Risk/Reward - What are key support/resistance levels?

Respond with valid JSON in this exact format:
{{
    "signal": "buy|sell|hold",
    "confidence": 0-100,
    "entry_price": float or null,
    "stop_loss": float or null,
    "take_profit": float or null,
    "reasoning": "concise explanation of the trade thesis",
    "key_levels": {{
        "support": float,
        "resistance": float
    }},
    "risk_factors": ["list", "of", "risks"],
    "catalysts": ["potential", "upcoming", "catalysts"]
}}"""
    
    return prompt


def analyze_token(symbol_or_address: str, chain: Optional[str] = None, address: Optional[str] = None) -> Dict:
    """
    Main analysis function.
    
    Args:
        symbol_or_address: Token symbol (e.g., "PUNCH") or address
        chain: Blockchain (solana, ethereum, etc.)
        address: Explicit token address (overrides symbol lookup)
    
    Returns:
        Complete analysis result dictionary
    """
    print(f"🔍 Analyzing {symbol_or_address}...")
    print("=" * 60)
    
    # Resolve token
    if address:
        token_info = {
            "address": address,
            "chain": chain or "solana",
            "symbol": symbol_or_address.upper()
        }
    else:
        token_info = resolve_token(symbol_or_address)
    
    if not token_info:
        print(f"❌ Could not resolve token: {symbol_or_address}")
        return {"error": f"Could not resolve token: {symbol_or_address}"}
    
    symbol = token_info["symbol"]
    addr = token_info["address"]
    chain = token_info["chain"]
    
    print(f"📋 Token: {symbol}")
    print(f"🔗 Address: {addr}")
    print(f"⛓️  Chain: {chain}")
    print()
    
    # 1. Fetch market data
    print("📊 Fetching market data from Birdeye...")
    market_data = fetch_token_market_data(chain, addr)
    
    if not market_data:
        print("⚠️ No market data available")
        market_data = {}
    else:
        print(f"   Price: ${market_data.get('price', 0):.8f}")
        print(f"   24h Change: {market_data.get('priceChange24h', 0):.2f}%")
        print(f"   24h Volume: ${market_data.get('volume24h', market_data.get('v24hUSD', 0)):,.0f}")
    
    # 2. Fetch whale activity
    print("\n🐋 Fetching whale activity...")
    whale_data = fetch_whale_activity(chain, addr, symbol)
    
    print(f"   Tracked by whales: {'Yes' if whale_data['tracked_by_whales'] else 'No'}")
    print(f"   Whale buy signals: {whale_data['whale_buy_signals']}")
    print(f"   Top holders: {len(whale_data['top_holders'])}")
    
    # 3. Calculate technical indicators
    print("\n📈 Calculating technical indicators...")
    candles = fetch_token_candles(chain, addr, timeframe="1H", limit=100)
    technical = calculate_technical_indicators(candles)
    
    ema_reclaim = technical.get("ema_reclaim", {})
    print(f"   EMA50 Reclaim: {'YES' if ema_reclaim.get('setup_present') else 'NO'}")
    print(f"   Price above EMA50: {ema_reclaim.get('price_above_ema50', False)}")
    
    # 4. LLM Analysis
    print("\n🤖 Sending to LLM for analysis...")
    prompt = build_analysis_prompt(symbol, chain, market_data, whale_data, technical)
    llm_result = call_llm_analysis(prompt)
    
    if llm_result:
        print(f"   Signal: {llm_result.get('signal', 'unknown').upper()}")
        print(f"   Confidence: {llm_result.get('confidence', 0)}%")
        print(f"   Entry: ${llm_result.get('entry_price', 'N/A')}")
    else:
        print("   ⚠️ LLM analysis failed")
        llm_result = {"error": "LLM analysis failed"}
    
    # Build final result
    timestamp = datetime.now().isoformat()
    date_str = datetime.now().strftime("%Y-%m-%d")
    
    result = {
        "meta": {
            "symbol": symbol,
            "address": addr,
            "chain": chain,
            "timestamp": timestamp,
            "analyst_version": "1.0.0"
        },
        "market_data": {
            "price": market_data.get("price", 0),
            "price_change_24h": market_data.get("priceChange24h", 0),
            "price_change_1h": market_data.get("priceChange1h", 0),
            "volume_24h": market_data.get("volume24h", market_data.get("v24hUSD", 0)),
            "liquidity": market_data.get("liquidity", 0),
            "marketcap": market_data.get("marketcap", market_data.get("marketCap", 0)),
            "fdv": market_data.get("fdv", 0),
            "buy_ratio": market_data.get("buyRatio", 0),
            "sell_ratio": market_data.get("sellRatio", 0),
            "unique_wallet_24h": market_data.get("uniqueWallet24h", 0)
        },
        "whale_activity": {
            "tracked_by_whales": whale_data["tracked_by_whales"],
            "whale_buy_signals_7d": whale_data["whale_buy_signals"],
            "whale_wallets_holding": whale_data["whale_wallets_holding"],
            "top_holders_count": len(whale_data["top_holders"]),
            "top_holders": whale_data["top_holders"][:5]  # Top 5 only
        },
        "technical": {
            "ema_reclaim": technical.get("ema_reclaim", {}),
            "volume_divergence": technical.get("volume_divergence", {}),
            "support_resistance": technical.get("support_resistance", {}),
            "price_change_24h_pct": technical.get("price_change_24h_pct"),
            "price_change_1h_pct": technical.get("price_change_1h_pct")
        },
        "analysis": llm_result if not llm_result.get("error") else {
            "signal": "hold",
            "confidence": 0,
            "entry_price": None,
            "stop_loss": None,
            "take_profit": None,
            "reasoning": llm_result.get("error", "Analysis failed"),
            "key_levels": {},
            "risk_factors": [],
            "catalysts": []
        },
        "raw_prompt": prompt  # Include for debugging
    }
    
    # 5. Save to file
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / f"analysis_{symbol}_{date_str}.json"
    
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n💾 Analysis saved to: {output_file}")
    print("=" * 60)
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Crypto Analyst - Token analysis pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python analyze.py PUNCH
    python analyze.py NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump
    python analyze.py MYTOKEN --chain ethereum --address 0x123...
        """
    )
    
    parser.add_argument("token", help="Token symbol (e.g., PUNCH) or address")
    parser.add_argument("--chain", help="Blockchain (solana, ethereum, etc.)", default=None)
    parser.add_argument("--address", help="Explicit token address", default=None)
    parser.add_argument("--json", action="store_true", help="Output raw JSON to stdout")
    
    args = parser.parse_args()
    
    result = analyze_token(args.token, args.chain, args.address)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        # Print summary
        analysis = result.get("analysis", {})
        signal = analysis.get("signal", "unknown").upper()
        confidence = analysis.get("confidence", 0)
        
        print(f"\n📊 ANALYSIS SUMMARY")
        print(f"   Signal: {signal}")
        print(f"   Confidence: {confidence}%")
        
        if analysis.get("entry_price"):
            print(f"   Entry: ${analysis['entry_price']:.8f}")
        if analysis.get("stop_loss"):
            print(f"   Stop: ${analysis['stop_loss']:.8f}")
        if analysis.get("take_profit"):
            print(f"   Target: ${analysis['take_profit']:.8f}")
        
        if analysis.get("reasoning"):
            print(f"\n📝 Reasoning: {analysis['reasoning'][:200]}...")


if __name__ == "__main__":
    main()
