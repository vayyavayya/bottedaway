#!/usr/bin/env python3
"""
Polymarket Research Pipeline — Phase 2
5-step analysis: Forecasting → Resolution → Devil's Advocate → Signal → Validation
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

COST_TRACKING_FILE = "/Users/pterion2910/.openclaw/workspace/memory/cost-tracking.json"
ANALYSIS_DIR = "/Users/pterion2910/.openclaw/workspace/analysis/polymarket"

def track_cost(amount: float):
    """Track API costs."""
    data = {"daily_spent": 0, "last_reset": datetime.now().isoformat()}
    if os.path.exists(COST_TRACKING_FILE):
        with open(COST_TRACKING_FILE, 'r') as f:
            data = json.load(f)
    
    # Reset if new day
    last_reset = datetime.fromisoformat(data.get("last_reset", "2020-01-01"))
    if (datetime.now() - last_reset).days >= 1:
        data = {"daily_spent": 0, "last_reset": datetime.now().isoformat()}
    
    data["daily_spent"] = data.get("daily_spent", 0) + amount
    
    with open(COST_TRACKING_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    return data["daily_spent"]

def check_cost_limit(limit: float = 0.50) -> bool:
    """Check if we're within cost limits."""
    if os.path.exists(COST_TRACKING_FILE):
        with open(COST_TRACKING_FILE, 'r') as f:
            data = json.load(f)
        last_reset = datetime.fromisoformat(data.get("last_reset", "2020-01-01"))
        if (datetime.now() - last_reset).days < 1:
            return data.get("daily_spent", 0) < limit
    return True


def llm_call(prompt: str, model: str = "qwen3.5:9b", max_tokens: int = 2000) -> str:
    """Call local LLM via Ollama."""
    try:
        # Use Ollama for local models
        if model.startswith("qwen") or model.startswith("llama"):
            result = subprocess.run(
                ["ollama", "run", model, prompt],
                capture_output=True,
                text=True,
                timeout=120
            )
            return result.stdout.strip()
        else:
            # API models would go here (Kimi, etc.)
            # For now, fallback to local
            return llm_call(prompt, "qwen3.5:9b")
    except Exception as e:
        return f'{{"error": "LLM call failed: {e}"}}'


def extract_json(text: str) -> Optional[Dict]:
    """Extract JSON from LLM output."""
    try:
        # Find JSON block
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
    except json.JSONDecodeError:
        pass
    return None


# =============================================================================
# STEP 1: FORECASTING
# =============================================================================

def step1_forecasting(market: Dict) -> Dict:
    """
    Estimate P(YES) using:
    - Outside view (base rate, reference class)
    - Inside view (specific evidence)
    """
    prompt = f"""Analyze this Polymarket prediction market:

Question: {market['question']}
Description: {market['description'][:500]}
Current Market Price: {market['mid_price']:.2f} (implied {market['mid_price']*100:.0f}% YES)
End Date: {market['end_date']}

Provide your analysis as JSON:
{{
  "predicted_probability": 0-100 (your best estimate as percentage),
  "base_rate": 0-100 (historical reference class probability),
  "confidence_interval": [low, high] (90% CI),
  "reasoning": "brief explanation of outside view then inside view"
}}

Start with base rate (outside view), then adjust for specific evidence (inside view)."""

    print("  Step 1: Forecasting...")
    response = llm_call(prompt, "qwen3.5:9b")
    result = extract_json(response)
    
    if not result:
        # Fallback
        market_price = market['mid_price'] * 100
        result = {
            "predicted_probability": round(market_price, 1),
            "base_rate": 50.0,
            "confidence_interval": [max(0, market_price - 20), min(100, market_price + 20)],
            "reasoning": "Failed to parse LLM output, using market price as fallback"
        }
    
    return result


# =============================================================================
# STEP 2: RESOLUTION ANALYSIS
# =============================================================================

def step2_resolution(market: Dict) -> Dict:
    """Analyze resolution criteria clarity and risks."""
    prompt = f"""Analyze the resolution criteria for this prediction market:

Question: {market['question']}
Description: {market['description'][:800]}

Evaluate as JSON:
{{
  "clarity_score": 0-1 (how clear are resolution criteria),
  "ambiguity_risks": ["list of potential ambiguities"],
  "edge_cases": ["scenarios that might confuse resolution"],
  "resolution_confidence": 0-1 (how confident that criteria are unambiguous)
}}

Focus on: What could go wrong with resolution? Are edge cases covered?"""

    print("  Step 2: Resolution Analysis...")
    response = llm_call(prompt, "qwen3.5:9b")
    result = extract_json(response)
    
    if not result:
        result = {
            "clarity_score": 0.5,
            "ambiguity_risks": ["Failed to analyze"],
            "edge_cases": ["Unknown"],
            "resolution_confidence": 0.5
        }
    
    return result


# =============================================================================
# STEP 3: DEVIL'S ADVOCATE
# =============================================================================

def step3_devils_advocate(market: Dict, forecast: Dict) -> Dict:
    """Challenge the thesis, steelman opposing case."""
    prompt = f"""You are a skeptical analyst challenging this prediction:

Question: {market['question']}
Our Predicted Probability: {forecast.get('predicted_probability', 50)}%
Market Price: {market['mid_price']*100:.0f}%

Challenge our analysis. Be the devil's advocate. Return JSON:
{{
  "bear_case": "strongest argument against our prediction",
  "bull_case": "strongest argument supporting our prediction", 
  "assumption_risks": ["key assumptions that might be wrong"],
  "severity": 0-1 (how dangerous are these risks),
  "recommendation": "proceed/reduce/abort"
}}

Be ruthless. Find what we're missing."""

    print("  Step 3: Devil's Advocate...")
    response = llm_call(prompt, "qwen3.5:9b")
    result = extract_json(response)
    
    if not result:
        result = {
            "bear_case": "Failed to generate",
            "bull_case": "Failed to generate",
            "assumption_risks": ["Unknown"],
            "severity": 0.5,
            "recommendation": "reduce"
        }
    
    return result


# =============================================================================
# STEP 4: SIGNAL GENERATION (Local Computation)
# =============================================================================

def step4_signal(market: Dict, forecast: Dict) -> Dict:
    """Compute edge, Kelly fraction, and position size."""
    market_price = market['mid_price']
    model_prob = forecast.get('predicted_probability', 50) / 100
    
    # Edge calculation
    edge = abs(model_prob - market_price)
    
    # Kelly criterion (quarter Kelly for safety)
    odds = market.get('odds', 2.0)
    if odds > 1:
        kelly_full = ((odds * model_prob) - (1 - model_prob)) / odds
        kelly_fraction = max(0, kelly_full * 0.25)  # Quarter Kelly
    else:
        kelly_fraction = 0
    
    # Position size (capped at $100)
    max_size = 100
    suggested_size = min(max_size, kelly_fraction * 1000)  # $1000 bankroll assumption
    
    return {
        "edge": round(edge, 4),
        "edge_percent": round(edge * 100, 2),
        "model_probability": round(model_prob, 3),
        "market_price": round(market_price, 3),
        "odds": odds,
        "kelly_fraction": round(kelly_fraction, 4),
        "suggested_size_usd": round(suggested_size, 2),
        "direction": "YES" if model_prob > market_price else "NO"
    }


# =============================================================================
# STEP 5: VALIDATION GATE
# =============================================================================

def step5_validation(signal: Dict, resolution: Dict, da: Dict) -> Dict:
    """Check all criteria before trading."""
    checks = {
        "edge_ok": signal.get("edge_percent", 0) >= 5.0,
        "confidence_ok": resolution.get("resolution_confidence", 0) >= 0.50,
        "clarity_ok": resolution.get("clarity_score", 0) >= 0.50,
        "severity_ok": da.get("severity", 1.0) < 0.80,
        "liquidity_ok": signal.get("suggested_size_usd", 0) > 0
    }
    
    all_pass = all(checks.values())
    
    return {
        "decision": "TRADE" if all_pass else "SKIP",
        "checks": checks,
        "failed_checks": [k for k, v in checks.items() if not v]
    }


# =============================================================================
# MAIN RESEARCH FUNCTION
# =============================================================================

def research_market(market: Dict) -> Dict:
    """Run full 5-step pipeline on a single market."""
    print(f"\n🔬 Researching: {market['question'][:60]}...")
    
    # Check cost limits
    if not check_cost_limit(0.50):
        print("  ⚠️ Cost limit reached, skipping LLM calls")
        return None
    
    # Run pipeline
    forecast = step1_forecasting(market)
    resolution = step2_resolution(market)
    da = step3_devils_advocate(market, forecast)
    signal = step4_signal(market, forecast)
    validation = step5_validation(signal, resolution, da)
    
    # Compile full research note
    research = {
        "market_id": market['market_id'],
        "question": market['question'],
        "slug": market['slug'],
        "research_date": datetime.now(timezone.utc).isoformat(),
        "market_data": {
            "volume_24h": market.get('volume_24h'),
            "liquidity": market.get('liquidity'),
            "mid_price": market.get('mid_price'),
            "spread": market.get('spread'),
            "end_date": market.get('end_date')
        },
        "forecasting": forecast,
        "resolution_analysis": resolution,
        "devils_advocate": da,
        "signal": signal,
        "validation": validation
    }
    
    # Save
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"{ANALYSIS_DIR}/research_{market['market_id']}_{date_str}.json"
    
    with open(filename, 'w') as f:
        json.dump(research, f, indent=2)
    
    print(f"  💾 Saved: {filename}")
    print(f"  📊 Decision: {validation['decision']} | Edge: {signal['edge_percent']:.1f}%")
    
    return research


def research_top_markets(scan_file: str = None, top_n: int = 5):
    """Research top N markets from scan file."""
    if scan_file is None:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        scan_file = f"{ANALYSIS_DIR}/scan_{date_str}.json"
    
    # Load scan results
    with open(scan_file, 'r') as f:
        scan = json.load(f)
    
    markets = scan.get('markets', [])[:top_n]
    
    results = []
    total_cost = 0
    
    for market in markets:
        result = research_market(market)
        if result:
            results.append(result)
            total_cost += 0.10  # Approximate per-market cost
        
        # Hard stop at $2
        if total_cost >= 2.0:
            print(f"\n⛔ Cost limit ($2) reached, stopping")
            break
    
    # Save daily brief
    brief = {
        "date": datetime.now(timezone.utc).isoformat(),
        "markets_researched": len(results),
        "total_cost": round(total_cost, 2),
        "trades": [r for r in results if r['validation']['decision'] == 'TRADE'],
        "skips": [r for r in results if r['validation']['decision'] == 'SKIP'],
        "all_research": results
    }
    
    brief_file = f"/Users/pterion2910/.openclaw/workspace/analysis/daily-briefs/polymarket_{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H%M')}.json"
    with open(brief_file, 'w') as f:
        json.dump(brief, f, indent=2)
    
    print(f"\n📋 Daily brief saved: {brief_file}")
    print(f"💰 Total cost: ${total_cost:.2f}")
    
    return brief


if __name__ == "__main__":
    import sys
    
    # Can run standalone with market JSON
    if len(sys.argv) > 1:
        market = json.loads(sys.argv[1])
        research_market(market)
    else:
        # Run full pipeline
        print("=" * 80)
        print("🔬 POLYMARKET RESEARCH PIPELINE")
        print("=" * 80)
        research_top_markets()
