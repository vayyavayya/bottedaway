#!/usr/bin/env python3
"""
Crypto Analyst - Token analysis pipeline using Birdeye price data + whale tracker activity
Generates structured trading signals via LLM analysis
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import requests

# Add scanner_engines to path for Birdeye provider
sys.path.insert(0, "/Users/pterion2910/.openclaw/workspace/scanner_engines")
from src.data.birdeye import (
    fetch_token_market_data_birdeye,
    fetch_candles_birdeye,
    fetch_token_metadata_birdeye,
)

# Configuration
DATA_DIR = Path("/Users/pterion2910/.openclaw/workspace/analysis/crypto")
WHALE_TRACKER_DIR = Path("/Users/pterion2910/.openclaw/workspace/skills/whale-tracker")

# Ensure output directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Default chain (can be overridden)
DEFAULT_CHAIN = "solana"


@dataclass
class TokenPriceData:
    """Price and market data from Birdeye"""
    price: float
    price_change_24h: float
    price_change_1h: float
    volume_24h: float
    volume_change_24h: float
    liquidity: float
    marketcap: float
    fdv: float
    buy_volume_24h: float
    sell_volume_24h: float
    buys_24h: int
    sells_24h: int
    unique_wallets_24h: int


@dataclass
class WhaleActivity:
    """Whale activity for a token"""
    token_address: str
    symbol: str
    whale_buys_24h: int
    whale_sells_24h: int
    whale_volume_buy_24h: float
    whale_volume_sell_24h: float
    net_whale_flow_24h: float
    top_holders: List[Dict[str, Any]]
    recent_transactions: List[Dict[str, Any]]


@dataclass
class AnalysisResult:
    """Structured analysis result"""
    signal: str  # buy, sell, hold
    confidence: float  # 0-100
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reasoning: str
    key_levels: Dict[str, Any]
    risk_factors: List[str]
    catalysts: List[str]


def load_helius_key() -> str:
    """Load Helius API key from credentials"""
    env_key = os.getenv("HELIUS_API_KEY", "")
    if env_key:
        return env_key
    
    creds_paths = [
        os.path.expanduser("~/.config/helius/credentials.json"),
        "/Users/pterion2910/.config/helius/credentials.json",
    ]
    for creds_file in creds_paths:
        if os.path.exists(creds_file):
            try:
                with open(creds_file, 'r') as f:
                    creds = json.load(f)
                    return creds.get("api_key", "")
            except Exception:
                continue
    return ""


def fetch_price_data(chain: str, address: str) -> Optional[TokenPriceData]:
    """Fetch price and market data from Birdeye"""
    print(f"📊 Fetching price data for {address[:12]}...")
    
    market_data = fetch_token_market_data_birdeye(chain, address, debug=True)
    if not market_data:
        print(f"⚠️ No market data available from Birdeye")
        return None
    
    return TokenPriceData(
        price=float(market_data.get("price", 0) or 0),
        price_change_24h=float(market_data.get("priceChange24h", 0) or 0),
        price_change_1h=float(market_data.get("priceChange1h", 0) or 0),
        volume_24h=float(market_data.get("volume24h", 0) or 0),
        volume_change_24h=float(market_data.get("volumeChange24h", 0) or 0),
        liquidity=float(market_data.get("liquidity", 0) or 0),
        marketcap=float(market_data.get("marketCap", 0) or 0),
        fdv=float(market_data.get("fdv", 0) or 0),
        buy_volume_24h=float(market_data.get("buyVolume24h", 0) or 0),
        sell_volume_24h=float(market_data.get("sellVolume24h", 0) or 0),
        buys_24h=int(market_data.get("buys24h", 0) or 0),
        sells_24h=int(market_data.get("sells24h", 0) or 0),
        unique_wallets_24h=int(market_data.get("uniqueWallet24h", 0) or 0),
    )


def fetch_whale_activity(chain: str, address: str, symbol: str) -> WhaleActivity:
    """Fetch whale activity from whale tracker snapshots"""
    print(f"🐋 Fetching whale activity for {symbol}...")
    
    # Try to load recent whale tracker data
    snapshots_dir = WHALE_TRACKER_DIR / "data" / "whales" / "snapshots"
    recent_activity = {
        "token_address": address,
        "symbol": symbol,
        "whale_buys_24h": 0,
        "whale_sells_24h": 0,
        "whale_volume_buy_24h": 0.0,
        "whale_volume_sell_24h": 0.0,
        "net_whale_flow_24h": 0.0,
        "top_holders": [],
        "recent_transactions": []
    }
    
    # Load most recent snapshot if available
    if snapshots_dir.exists():
        snapshot_files = sorted(snapshots_dir.glob("*.json"), reverse=True)
        if snapshot_files:
            try:
                with open(snapshot_files[0], 'r') as f:
                    snapshot = json.load(f)
                    # Look for this token in the snapshot
                    for token in snapshot.get("tokens", []):
                        if token.get("address") == address:
                            recent_activity["whale_buys_24h"] = token.get("buys", 0)
                            recent_activity["composite_score"] = token.get("composite", 0)
                            recent_activity["status"] = token.get("status", "unknown")
                            break
            except Exception as e:
                print(f"⚠️ Error reading whale snapshot: {e}")
    
    # Try to fetch on-chain holder data via Helius
    helius_key = load_helius_key()
    if helius_key:
        try:
            url = f"https://mainnet.helius-rpc.com/?api-key={helius_key}"
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
                total_supply = sum(int(h.get("amount", 0)) for h in data["result"]["value"])
                
                formatted_holders = []
                for h in holders:
                    amount = int(h.get("amount", 0))
                    pct = (amount / total_supply * 100) if total_supply > 0 else 0
                    formatted_holders.append({
                        "address": h.get("address", "")[:16] + "...",
                        "amount": amount,
                        "percentage": round(pct, 2)
                    })
                recent_activity["top_holders"] = formatted_holders
                print(f"  Found {len(formatted_holders)} top holders")
        except Exception as e:
            print(f"⚠️ Helius holder fetch failed: {e}")
    
    return WhaleActivity(**recent_activity)


def calculate_ema_reclaim_setup(candles: List[Dict]) -> Dict[str, Any]:
    """Check for EMA reclaim setup pattern"""
    if len(candles) < 50:
        return {"setup_present": False, "reason": "Insufficient candle data"}
    
    # Calculate EMA50
    closes = [c["c"] for c in candles]
    ema50 = sum(closes[-50:]) / 50  # Simple SMA for approximation
    
    current_price = closes[-1]
    prev_price = closes[-2] if len(closes) > 1 else current_price
    
    # Check if price just reclaimed EMA50
    was_below = prev_price < ema50
    is_above = current_price > ema50
    
    setup = {
        "setup_present": was_below and is_above,
        "ema50": round(ema50, 6),
        "current_price": round(current_price, 6),
        "distance_from_ema": round((current_price - ema50) / ema50 * 100, 2),
        "trend": "reclaiming" if (was_below and is_above) else "above" if is_above else "below"
    }
    
    return setup


def calculate_volume_divergence(candles: List[Dict]) -> Dict[str, Any]:
    """Check for volume divergence signals"""
    if len(candles) < 20:
        return {"divergence_present": False, "reason": "Insufficient data"}
    
    recent = candles[-10:]
    previous = candles[-20:-10]
    
    recent_avg_price = sum(c["c"] for c in recent) / len(recent)
    prev_avg_price = sum(c["c"] for c in previous) / len(previous)
    
    recent_avg_vol = sum(c["v"] for c in recent) / len(recent)
    prev_avg_vol = sum(c["v"] for c in previous) / len(previous)
    
    price_change = (recent_avg_price - prev_avg_price) / prev_avg_price * 100
    volume_change = (recent_avg_vol - prev_avg_vol) / prev_avg_vol * 100 if prev_avg_vol > 0 else 0
    
    # Bullish divergence: price down, volume up (accumulation)
    # Bearish divergence: price up, volume down (weak momentum)
    divergence = {
        "divergence_present": (price_change < 0 and volume_change > 20) or (price_change > 0 and volume_change < -20),
        "type": "bullish_accumulation" if (price_change < 0 and volume_change > 20) else "bearish_weakness" if (price_change > 0 and volume_change < -20) else "none",
        "price_change_10candles": round(price_change, 2),
        "volume_change_10candles": round(volume_change, 2)
    }
    
    return divergence


def build_llm_prompt(
    symbol: str,
    chain: str,
    price_data: TokenPriceData,
    whale_activity: WhaleActivity,
    candles: List[Dict]
) -> str:
    """Build the prompt for LLM analysis"""
    
    # Calculate technical indicators
    ema_setup = calculate_ema_reclaim_setup(candles)
    vol_divergence = calculate_volume_divergence(candles)
    
    # Format whale activity
    whale_summary = f"""
- Whale tracker status: {whale_activity.recent_transactions if whale_activity.recent_transactions else 'No recent whale data'}
- Top holders concentration: {len(whale_activity.top_holders)} major holders tracked
"""
    
    if whale_activity.top_holders:
        top3 = whale_activity.top_holders[:3]
        whale_summary += f"- Largest holder: {top3[0]['percentage']:.2f}% of supply\n"
    
    prompt = f"""Analyze this crypto token for a short-to-medium term trade setup:

TOKEN: {symbol} on {chain}
CURRENT PRICE: ${price_data.price:.8f}

MARKET DATA (24h):
- Price change: {price_data.price_change_24h:+.2f}%
- 1h change: {price_data.price_change_1h:+.2f}%
- Volume 24h: ${price_data.volume_24h:,.2f}
- Volume change: {price_data.volume_change_24h:+.2f}%
- Liquidity: ${price_data.liquidity:,.2f}
- Market Cap: ${price_data.marketcap:,.2f}
- Buy/Sell Ratio: {price_data.buys_24h} buys / {price_data.sells_24h} sells
- Buy Volume: ${price_data.buy_volume_24h:,.2f} vs Sell Volume: ${price_data.sell_volume_24h:,.2f}
- Unique wallets 24h: {price_data.unique_wallets_24h}

TECHNICAL PATTERNS:
- EMA50 Reclaim Setup: {"YES - " + ema_setup.get('trend', 'unknown') if ema_setup.get('setup_present') else "No - " + ema_setup.get('reason', 'Insufficient data')} {"(price $" + f"{ema_setup.get('current_price', 0):.8f}" + " vs EMA50 $" + f"{ema_setup.get('ema50', 0):.8f}" + ", " + f"{ema_setup.get('distance_from_ema', 0):+.2f}" + "% distance)" if ema_setup.get('setup_present') else ""}
- Volume Divergence: {vol_divergence.get('type', 'none').upper() if vol_divergence.get('divergence_present') else "None detected"} {"(price " + f"{vol_divergence.get('price_change_10candles', 0):+.2f}" + "%, volume " + f"{vol_divergence.get('volume_change_10candles', 0):+.2f}" + "%)" if vol_divergence.get('divergence_present') else ""}

WHALE ACTIVITY:
{whale_summary}

TASK: Generate a structured trading analysis. Consider:
1. EMA reclaim setup - is price reclaiming key EMA with volume?
2. Volume divergence - any accumulation/distribution patterns?
3. Whale accumulation pattern - are smart money wallets buying?
4. Social/retail sentiment - buy/sell ratio and wallet activity

Return ONLY a JSON object with this exact structure:
{{
  "signal": "buy" or "sell" or "hold",
  "confidence": 0-100,
  "entry_price": number or null,
  "stop_loss": number or null,
  "take_profit": number or null,
  "reasoning": "2-3 sentences explaining the setup and conviction",
  "key_levels": {{
    "support": [price1, price2],
    "resistance": [price1, price2]
  }},
  "risk_factors": ["risk1", "risk2"],
  "catalysts": ["catalyst1", "catalyst2"]
}}

Be objective. High confidence only when multiple factors align."""
    
    return prompt


def call_llm_analyst(prompt: str) -> Optional[AnalysisResult]:
    """Send prompt to LLM and parse response"""
    print("🧠 Sending to ClawAnalyst for analysis...")
    
    # Try OpenClaw's local model first, then fall back to API
    try:
        # Check if we have OpenClaw gateway for local inference
        gateway_url = os.getenv("OPENCLAW_GATEWAY_URL", "http://localhost:8080")
        
        # Try local Qwen3 model via ollama/OpenClaw
        response = requests.post(
            f"{gateway_url}/v1/chat/completions",
            json={
                "model": "ollama/qwen3:30b-a3b-q4_K_M",
                "messages": [
                    {"role": "system", "content": "You are an expert crypto trader analyst. Provide objective technical analysis with specific entry/exit levels."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 800
            },
            timeout=60
        )
        
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"]
        else:
            raise Exception(f"Local model failed: {response.status_code}")
            
    except Exception as local_error:
        print(f"  Local model unavailable ({local_error}), trying API fallback...")
        
        # Fallback: Use OpenRouter or other configured API
        api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not api_key:
            print("⚠️ No LLM API available - using heuristic analysis")
            return heuristic_analysis(prompt)
        
        try:
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "google/gemini-2.0-flash-lite:free",
                    "messages": [
                        {"role": "system", "content": "You are an expert crypto trader analyst."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3,
                    "max_tokens": 800
                },
                timeout=60
            )
            content = response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"⚠️ API fallback failed: {e}")
            return heuristic_analysis(prompt)
    
    # Parse JSON from response
    try:
        # Extract JSON from response (handle markdown code blocks)
        content_clean = content
        if "```json" in content:
            content_clean = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content_clean = content.split("```")[1].split("```")[0]
        
        result = json.loads(content_clean.strip())
        
        return AnalysisResult(
            signal=result.get("signal", "hold"),
            confidence=float(result.get("confidence", 50)),
            entry_price=result.get("entry_price"),
            stop_loss=result.get("stop_loss"),
            take_profit=result.get("take_profit"),
            reasoning=result.get("reasoning", ""),
            key_levels=result.get("key_levels", {}),
            risk_factors=result.get("risk_factors", []),
            catalysts=result.get("catalysts", [])
        )
    except Exception as e:
        print(f"⚠️ Failed to parse LLM response: {e}")
        print(f"Raw response: {content[:500]}")
        return heuristic_analysis(prompt)


def heuristic_analysis(prompt: str) -> AnalysisResult:
    """Fallback heuristic analysis when LLM is unavailable"""
    print("📊 Running heuristic analysis...")
    
    # Extract key data points from prompt using simple rules
    signal = "hold"
    confidence = 50
    entry = None
    stop = None
    target = None
    reasoning = "Heuristic analysis based on technical patterns"
    
    # Simple rule-based logic
    if "EMA50 Reclaim Setup: YES" in prompt and "bullish_accumulation" in prompt:
        signal = "buy"
        confidence = 70
        reasoning = "EMA50 reclaim with bullish volume divergence detected"
    elif "bearish_weakness" in prompt:
        signal = "sell"
        confidence = 60
        reasoning = "Bearish volume divergence - momentum weakening"
    
    return AnalysisResult(
        signal=signal,
        confidence=confidence,
        entry_price=entry,
        stop_loss=stop,
        take_profit=target,
        reasoning=reasoning,
        key_levels={"support": [], "resistance": []},
        risk_factors=["Heuristic mode - LLM unavailable"],
        catalysts=[]
    )


def analyze_token(address: str, symbol: str, chain: str = DEFAULT_CHAIN) -> Dict[str, Any]:
    """
    Main analysis pipeline for a token
    
    Args:
        address: Token contract address
        symbol: Token symbol/name
        chain: Blockchain (default: solana)
    
    Returns:
        Complete analysis result dictionary
    """
    print(f"\n{'='*60}")
    print(f"🔍 CRYPTO ANALYST: {symbol} on {chain}")
    print(f"   Address: {address}")
    print(f"{'='*60}\n")
    
    # Step 1: Fetch price data from Birdeye
    price_data = fetch_price_data(chain, address)
    if not price_data:
        return {
            "error": "Failed to fetch price data",
            "symbol": symbol,
            "address": address,
            "timestamp": datetime.now().isoformat()
        }
    
    print(f"✅ Price data: ${price_data.price:.8f} ({price_data.price_change_24h:+.2f}%)")
    
    # Step 2: Fetch whale activity
    whale_activity = fetch_whale_activity(chain, address, symbol)
    print(f"✅ Whale data: {len(whale_activity.top_holders)} top holders tracked")
    
    # Step 3: Fetch candle data for technical analysis
    print("📈 Fetching candle data for technical analysis...")
    candles = fetch_candles_birdeye(chain, address, timeframe="1H", limit=100, debug=True)
    if not candles:
        print("⚠️ No candle data available, using limited analysis")
        candles = []
    else:
        print(f"✅ Loaded {len(candles)} candles")
    
    # Step 4: Build LLM prompt and get analysis
    prompt = build_llm_prompt(symbol, chain, price_data, whale_activity, candles)
    analysis = call_llm_analyst(prompt)
    
    if not analysis:
        return {
            "error": "Analysis failed",
            "symbol": symbol,
            "address": address,
            "timestamp": datetime.now().isoformat()
        }
    
    # Step 5: Compile full result
    result = {
        "meta": {
            "symbol": symbol,
            "address": address,
            "chain": chain,
            "timestamp": datetime.now().isoformat(),
            "analyst_version": "1.0.0"
        },
        "market_data": asdict(price_data),
        "whale_activity": {
            "top_holders": whale_activity.top_holders,
            "holder_count": len(whale_activity.top_holders)
        },
        "technical": {
            "ema_reclaim": calculate_ema_reclaim_setup(candles),
            "volume_divergence": calculate_volume_divergence(candles),
            "candles_analyzed": len(candles)
        },
        "analysis": {
            "signal": analysis.signal,
            "confidence": analysis.confidence,
            "entry_price": analysis.entry_price,
            "stop_loss": analysis.stop_loss,
            "take_profit": analysis.take_profit,
            "reasoning": analysis.reasoning,
            "key_levels": analysis.key_levels,
            "risk_factors": analysis.risk_factors,
            "catalysts": analysis.catalysts
        }
    }
    
    # Step 6: Save to file
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_file = DATA_DIR / f"analysis_{symbol}_{date_str}.json"
    
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"✅ ANALYSIS COMPLETE")
    print(f"{'='*60}")
    print(f"Signal: {analysis.signal.upper()} (confidence: {analysis.confidence}%)")
    print(f"Reasoning: {analysis.reasoning[:100]}...")
    print(f"Saved to: {output_file}")
    print(f"{'='*60}\n")
    
    return result


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Crypto Analyst - Token analysis with Birdeye + whale tracker"
    )
    parser.add_argument(
        "token",
        help="Token address or symbol (e.g., 'PUNCH' or 'NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump')"
    )
    parser.add_argument(
        "--chain",
        default=DEFAULT_CHAIN,
        help=f"Blockchain (default: {DEFAULT_CHAIN})"
    )
    parser.add_argument(
        "--address",
        help="Token contract address (if token is a symbol)"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (default: auto-generated)"
    )
    
    args = parser.parse_args()
    
    # Resolve token symbol to address if needed
    symbol = args.token.upper()
    address = args.address
    
    # Common token mappings
    token_mappings = {
        "PUNCH": "NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump",
        "SOL": "So11111111111111111111111111111111111111112",
        "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    }
    
    if not address:
        if args.token in token_mappings:
            address = token_mappings[args.token]
        elif len(args.token) > 30:
            # Looks like an address
            address = args.token
        else:
            print(f"❌ Unknown token symbol: {args.token}")
            print(f"Known symbols: {', '.join(token_mappings.keys())}")
            print(f"Or provide --address with the contract address")
            sys.exit(1)
    
    # Run analysis
    result = analyze_token(address, symbol, args.chain)
    
    if "error" in result:
        print(f"❌ Error: {result['error']}")
        sys.exit(1)
    
    # Print summary
    analysis = result["analysis"]
    print("\n📊 SUMMARY:")
    print(f"  Signal: {analysis['signal'].upper()}")
    print(f"  Confidence: {analysis['confidence']}%")
    if analysis['entry_price']:
        print(f"  Entry: ${analysis['entry_price']:.8f}")
    if analysis['stop_loss']:
        print(f"  Stop Loss: ${analysis['stop_loss']:.8f}")
    if analysis['take_profit']:
        print(f"  Take Profit: ${analysis['take_profit']:.8f}")
    print(f"\n  Reasoning:")
    print(f"    {analysis['reasoning']}")


if __name__ == "__main__":
    main()
