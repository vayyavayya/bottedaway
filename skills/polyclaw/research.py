#!/usr/bin/env python3
"""
POLYCLAW Research Pipeline - 6-Step Market Analysis
Generates structured research notes for Polymarket prediction markets.

Usage:
    python research.py <market_id> [--model kimi|minimax]
    python research.py trending [--limit 10]

Cost target: ~$0.30/market (Kimi K2.5 for steps 1-3)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
import math

# Add script dir to path for imports
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
sys.path.insert(0, os.path.join(SCRIPT_DIR, 'scripts'))  # Also check scripts subdir

# Import API client
try:
    from api_client import get_api_client, PolymarketAPIClient
    API_AVAILABLE = True
except ImportError as e:
    API_AVAILABLE = False
    print(f"⚠️  API client not available: {e}")

# Import portfolio tracker and telegram notifier
try:
    sys.path.insert(0, os.path.expanduser('~/.openclaw/workspace/skills/portfolio'))
    from portfolio_tracker import get_portfolio_tracker
    from telegram_notifier import send_trade_alert, send_research_alert
    PORTFOLIO_AVAILABLE = True
except ImportError as e:
    PORTFOLIO_AVAILABLE = False
    print(f"⚠️  Portfolio tracker not available: {e}")

# Paths
ANALYSIS_DIR = os.path.expanduser('~/.openclaw/workspace/analysis/polymarket')
os.makedirs(ANALYSIS_DIR, exist_ok=True)

# ============================================================================
# MEMORY CONTEXT - Load historical base rates and lessons
# ============================================================================

def load_memory_context() -> str:
    """Load historical base rates and lessons from memory tracker"""
    memory_file = os.path.join(SCRIPT_DIR, 'prompts', 'memory_context.md')
    
    if os.path.exists(memory_file):
        with open(memory_file, 'r') as f:
            content = f.read()
            # Only return the substantive parts, not the header
            lines = content.split('\n')
            # Skip "# Auto-generated" header line
            return '\n'.join(lines[1:]) if len(lines) > 1 else content
    
    return "*No historical memory available yet*"


MEMORY_CONTEXT = load_memory_context()

# ============================================================================
# STEP 1: FORECASTING - LLM estimates P(YES) with base rate + evidence
# ============================================================================

FORECASTING_PROMPT = """You are an expert forecaster analyzing a prediction market.

MARKET: {question}
DESCRIPTION: {description}
END DATE: {end_date}

CURRENT ODDS:
- Yes: {yes_odds} (${yes_price:.4f})
- No: {no_odds} (${no_price:.4f})

{memory_context}

YOUR TASK:
1. Determine the BASE RATE - What is the historical frequency of similar events?
2. List KEY EVIDENCE - What specific factors support each outcome?
3. Estimate P(YES) - Your calibrated probability (0-100%)
4. Provide CONFIDENCE - How certain are you in this estimate? (0-100%)
5. List KEY UNCERTAINTIES - What could change this forecast?

Respond in this EXACT JSON format:
{{
  "base_rate": "<historical base rate as percentage with reasoning>",
  "evidence_yes": ["point 1", "point 2", "point 3"],
  "evidence_no": ["point 1", "point 2", "point 3"],
  "p_yes_estimate": 45.5,
  "confidence": 65,
  "key_uncertainties": ["uncertainty 1", "uncertainty 2"],
  "reasoning": "<concise 2-3 sentence reasoning>"
}}"""

# ============================================================================
# STEP 2: RESOLUTION ANALYSIS - Check clarity, ambiguity risks, edge cases
# ============================================================================

RESOLUTION_PROMPT = """You are a resolution analyst examining how this prediction market could resolve.

MARKET: {question}
DESCRIPTION: {description}
RESOLUTION DETAILS: {resolution_details}

YOUR TASK:
1. Assess RESOLUTION CLARITY (0-100%) - How unambiguous is the resolution criteria?
2. Identify AMBIGUITY RISKS - What interpretations could cause disputes?
3. List EDGE CASES - Scenarios where resolution is unclear
4. Evaluate DATA SOURCE RELIABILITY - How trustworthy is the source?
5. Assess RESOLUTION TIMING RISK - Could delays or timing issues occur?

Respond in this EXACT JSON format:
{{
  "clarity_score": 75,
  "ambiguity_risks": ["risk 1", "risk 2"],
  "edge_cases": ["edge case 1", "edge case 2"],
  "data_source_reliability": "<assessment of data source>",
  "resolution_timing_risk": "<low/medium/high with explanation>",
  "severity_score": 30,
  "recommendation": "<proceed with caution / clear to trade / avoid>"
}}"""

# ============================================================================
# STEP 3: DEVIL'S ADVOCATE - Steelman opposing case, challenge assumptions
# ============================================================================

DEVILS_ADVOCATE_PROMPT = """You are a skeptical analyst challenging the consensus view on this prediction market.

MARKET: {question}

FORECAST SUMMARY:
- Current market odds: Yes {yes_odds}, No {no_odds}
- Estimated P(Yes): {p_yes_estimate}%

YOUR TASK:
Play devil's advocate and challenge the assumptions:
1. What if the market is WRONG? List reasons why the current odds could be mispriced.
2. What BIASES might be affecting market participants?
3. What INFORMATION might the market be MISSING?
4. Steelman the OPPOSITE CASE - What's the strongest argument against the consensus?
5. What would make you CHANGE your mind?

Respond in this EXACT JSON format:
{{
  "why_market_might_be_wrong": ["reason 1", "reason 2", "reason 3"],
  "participant_biases": ["bias 1", "bias 2"],
  "missing_information": ["info gap 1", "info gap 2"],
  "steelmanned_opposite": "<strongest argument for opposite outcome>",
  "mind_change_triggers": ["trigger 1", "trigger 2"],
  "alternative_scenario": "<brief description of alternative outcome>"
}}"""

# ============================================================================
# LLM Client (OpenRouter API)
# ============================================================================

def get_openrouter_key() -> Optional[str]:
    """Get OpenRouter API key from environment or config."""
    # Try environment first
    key = os.environ.get('OPENROUTER_API_KEY')
    if key:
        return key
    
    # Try common config locations
    config_paths = [
        os.path.expanduser('~/.config/openclaw/credentials.json'),
        os.path.expanduser('~/.openclaw/credentials.json'),
    ]
    
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    creds = json.load(f)
                    return creds.get('openrouter', {}).get('api_key')
            except:
                pass
    
    return None


def call_llm(prompt: str, model: str = "kimi-coding/k2p5") -> Dict:
    """
    Call LLM via OpenRouter API.
    Cost target: Kimi K2.5 (~$0.10/call, 3 calls = $0.30 per market)
    """
    api_key = get_openrouter_key()
    
    if not api_key:
        return {
            "error": "No OpenRouter API key found. Set OPENROUTER_API_KEY environment variable.",
            "parse_error": True
        }
    
    # Map model aliases to full names
    model_map = {
        "kimi": "kimi-coding/k2p5",
        "minimax": "minimax-portal/MiniMax-M2.5",
        "gemini": "google/gemini-2.0-flash-lite:free",
    }
    model = model_map.get(model, model)
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://openclaw.local",
        "X-Title": "PolyClaw Research"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a precise forecasting assistant. Always respond with valid JSON only. No markdown formatting, no explanations outside JSON."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.3,
        "max_tokens": 1500
    }
    
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            response_data = json.loads(resp.read().decode())
        
        # Extract content from response
        content = response_data.get('choices', [{}])[0].get('message', {}).get('content', '')
        
        # Try to extract JSON from content
        json_str = content
        
        # Remove markdown code blocks if present
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        
        # Try parsing
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Return raw response wrapped if JSON fails
            return {
                "raw_response": content[:500],
                "parse_error": True
            }
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return {
            "error": f"HTTP {e.code}: {error_body[:200]}",
            "parse_error": True
        }
    except Exception as e:
        return {
            "error": str(e),
            "parse_error": True
        }


# ============================================================================
# STEP 4: SIGNAL GENERATION - Compute edge, Kelly, EV, size locally
# ============================================================================

def compute_kelly_criterion(p_win: float, odds: float, fraction: float = 0.25) -> float:
    """
    Calculate Kelly Criterion position size.
    
    f* = (bp - q) / b
    where: b = odds - 1, p = probability of win, q = probability of loss
    
    Returns fraction of bankroll to bet (uses half-Kelly by default for safety).
    """
    if odds <= 1 or p_win <= 0 or p_win >= 1:
        return 0.0
    
    b = odds - 1  # net odds received
    q = 1 - p_win
    
    kelly = (b * p_win - q) / b
    
    # Apply fractional Kelly for safety
    return max(0, kelly * fraction)


def compute_expected_value(p_win: float, odds: float, stake: float = 1.0) -> float:
    """
    Calculate Expected Value of a bet.
    EV = (p_win * profit) - (p_loss * stake)
    """
    if odds <= 1:
        return 0.0
    
    p_loss = 1 - p_win
    profit = stake * (odds - 1)
    
    ev = (p_win * profit) - (p_loss * stake)
    return ev


def compute_edge(market_prob: float, estimated_prob: float) -> float:
    """
    Calculate edge as difference between estimated and market probability.
    Positive edge means market underestimates the probability.
    """
    return estimated_prob - market_prob


def generate_signals(
    market_data: Dict,
    forecast: Dict,
    resolution: Dict,
    bankroll: float = 1000.0
) -> Dict:
    """
    Generate trading signals from analysis.
    All calculations done locally (no LLM cost).
    """
    # Extract probabilities
    market_yes_prob = market_data.get('yes_price', 0.5)
    estimated_yes_prob = forecast.get('p_yes_estimate', 50) / 100
    
    # Compute edge for YES side
    edge_yes = compute_edge(market_yes_prob, estimated_yes_prob)
    
    # Compute edge for NO side
    estimated_no_prob = 1 - estimated_yes_prob
    market_no_prob = market_data.get('no_price', 0.5)
    edge_no = compute_edge(market_no_prob, estimated_no_prob)
    
    # Determine which side has edge
    if edge_yes > edge_no:
        recommended_side = "YES"
        edge = edge_yes
        market_prob = market_yes_prob
        our_prob = estimated_yes_prob
        market_odds = 1 / market_yes_prob if market_yes_prob > 0 else 1
    else:
        recommended_side = "NO"
        edge = edge_no
        market_prob = market_no_prob
        our_prob = estimated_no_prob
        market_odds = 1 / market_no_prob if market_no_prob > 0 else 1
    
    # Kelly criterion sizing
    kelly_fraction = compute_kelly_criterion(our_prob, market_odds, fraction=0.25)
    kelly_size = bankroll * kelly_fraction
    
    # Cap position size
    max_position = min(bankroll * 0.10, 100)  # Max 10% of bankroll or $100
    recommended_size = min(kelly_size, max_position)
    
    # Expected value
    ev = compute_expected_value(our_prob, market_odds, recommended_size)
    
    # Risk-adjusted return
    confidence = forecast.get('confidence', 50) / 100
    risk_score = resolution.get('severity_score', 50) / 100
    risk_adjusted_edge = edge * confidence * (1 - risk_score)
    
    return {
        "recommended_side": recommended_side,
        "market_probability": round(market_prob, 4),
        "our_probability": round(our_prob, 4),
        "edge_percent": round(edge * 100, 2),
        "confidence": forecast.get('confidence', 50),
        "kelly_fraction": round(kelly_fraction, 4),
        "kelly_size": round(kelly_size, 2),
        "recommended_size": round(recommended_size, 2),
        "expected_value": round(ev, 2),
        "risk_adjusted_edge": round(risk_adjusted_edge * 100, 2),
        "annualized_return_estimate": round(edge * confidence * 365 / max(1, days_to_resolution(market_data)), 2) if days_to_resolution(market_data) else None
    }


def days_to_resolution(market_data: Dict) -> Optional[int]:
    """Calculate days until market resolution."""
    try:
        end_date = market_data.get('end_date_iso') or market_data.get('end_date')
        if not end_date:
            return None
        
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        now = datetime.now(end.tzinfo)
        delta = (end - now).days
        return max(0, delta)
    except:
        return None


# ============================================================================
# STEP 5: VALIDATION GATE - Check all thresholds
# ============================================================================

VALIDATION_THRESHOLDS = {
    "min_edge_percent": 5.0,           # edge ≥ 5%
    "min_confidence": 60,              # confidence ≥ 60%
    "min_clarity": 50,                 # clarity ≥ 50%
    "max_severity": 80,                # severity < 80%
    "min_liquidity": 100.0,            # liquidity > $100
    "max_position_size": 100.0,        # max $100 per trade
}


def validate_signals(
    signals: Dict,
    forecast: Dict,
    resolution: Dict,
    market_data: Dict
) -> Dict:
    """
    Validate if trade passes all gates.
    Returns detailed validation report.
    """
    checks = []
    
    # Check 1: Edge threshold
    edge_pass = signals.get('edge_percent', 0) >= VALIDATION_THRESHOLDS['min_edge_percent']
    checks.append({
        "check": "Edge ≥ 5%",
        "value": f"{signals.get('edge_percent', 0):.1f}%",
        "threshold": "≥ 5%",
        "passed": edge_pass
    })
    
    # Check 2: Confidence threshold
    conf_pass = forecast.get('confidence', 0) >= VALIDATION_THRESHOLDS['min_confidence']
    checks.append({
        "check": "Confidence ≥ 60%",
        "value": f"{forecast.get('confidence', 0)}%",
        "threshold": "≥ 60%",
        "passed": conf_pass
    })
    
    # Check 3: Clarity threshold
    clarity_pass = resolution.get('clarity_score', 0) >= VALIDATION_THRESHOLDS['min_clarity']
    checks.append({
        "check": "Clarity ≥ 50%",
        "value": f"{resolution.get('clarity_score', 0)}%",
        "threshold": "≥ 50%",
        "passed": clarity_pass
    })
    
    # Check 4: Severity threshold
    sev_pass = resolution.get('severity_score', 100) < VALIDATION_THRESHOLDS['max_severity']
    checks.append({
        "check": "Severity < 80%",
        "value": f"{resolution.get('severity_score', 100)}%",
        "threshold": "< 80%",
        "passed": sev_pass
    })
    
    # Check 5: Liquidity threshold
    liq = market_data.get('liquidity', 0)
    liq_pass = liq > VALIDATION_THRESHOLDS['min_liquidity']
    checks.append({
        "check": "Liquidity > $100",
        "value": f"${liq:,.2f}",
        "threshold": "> $100",
        "passed": liq_pass
    })
    
    # Overall validation
    all_passed = all(c['passed'] for c in checks)
    
    # Determine recommendation
    if all_passed:
        recommendation = "TRADE"
        action = f"Buy {signals.get('recommended_side')} ${signals.get('recommended_size', 0):.2f}"
    elif edge_pass and conf_pass:
        recommendation = "PAPER_TRADE"
        action = f"Paper trade {signals.get('recommended_side')} ${signals.get('recommended_size', 0):.2f}"
    else:
        recommendation = "PASS"
        action = "No trade - insufficient edge or confidence"
    
    return {
        "overall_valid": all_passed,
        "recommendation": recommendation,
        "recommended_action": action,
        "checks": checks,
        "passed_count": sum(c['passed'] for c in checks),
        "total_checks": len(checks)
    }


# ============================================================================
# STEP 6: SAVE RESEARCH NOTE
# ============================================================================

def save_research_note(
    market_id: str,
    market_data: Dict,
    forecast: Dict,
    resolution: Dict,
    devil: Dict,
    signals: Dict,
    validation: Dict
) -> str:
    """
    Save full research note to workspace/analysis/polymarket/
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    date_str = datetime.now().strftime('%Y-%m-%d')
    
    research_note = {
        "meta": {
            "version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "market_id": market_id,
            "pipeline_steps": ["forecasting", "resolution", "devils_advocate", "signals", "validation"]
        },
        "market": {
            "id": market_id,
            "question": market_data.get('question'),
            "slug": market_data.get('slug'),
            "category": market_data.get('category'),
            "end_date": market_data.get('end_date'),
            "yes_price": market_data.get('yes_price'),
            "no_price": market_data.get('no_price'),
            "volume_24h": market_data.get('volume_24h'),
            "liquidity": market_data.get('liquidity')
        },
        "step1_forecasting": forecast,
        "step2_resolution": resolution,
        "step3_devils_advocate": devil,
        "step4_signals": signals,
        "step5_validation": validation,
        "step6_output": {
            "recommendation": validation.get('recommendation'),
            "action": validation.get('recommended_action'),
            "edge_percent": signals.get('edge_percent'),
            "confidence": forecast.get('confidence'),
            "clarity": resolution.get('clarity_score'),
            "severity": resolution.get('severity_score')
        }
    }
    
    filename = f"research_{market_id}_{date_str}.json"
    filepath = os.path.join(ANALYSIS_DIR, filename)
    
    with open(filepath, 'w') as f:
        json.dump(research_note, f, indent=2)
    
    return filepath


# ============================================================================
# STEP 7: PORTFOLIO INTEGRATION - Risk check, log trade, send alerts
# ============================================================================

def process_portfolio_integration(
    market_id: str,
    market_data: Dict,
    forecast: Dict,
    resolution: Dict,
    signals: Dict,
    validation: Dict,
    verbose: bool = True
) -> Optional[Dict]:
    """
    Process portfolio integration after validation gate.
    
    If validation recommends TRADE:
    1. Run portfolio risk check
    2. If approved: log paper trade to portfolio tracker
    3. Send Telegram alert to BigBrother with full details
    
    Returns:
        Portfolio integration result dict or None if not applicable
    """
    if not PORTFOLIO_AVAILABLE:
        if verbose:
            print("   ⚠️  Portfolio tracker not available, skipping integration")
        return None
    
    recommendation = validation.get('recommendation', 'PASS')
    
    # Only process TRADE or PAPER_TRADE recommendations
    if recommendation not in ['TRADE', 'PAPER_TRADE']:
        if verbose:
            print(f"   ⏭️  Recommendation is {recommendation}, skipping portfolio integration")
        return None
    
    # Get portfolio tracker
    tracker = get_portfolio_tracker()
    
    # Extract trade parameters
    side = signals.get('recommended_side', 'YES')
    size = signals.get('recommended_size', 0)
    entry_price = market_data.get('yes_price', 0.5) if side == 'YES' else market_data.get('no_price', 0.5)
    edge_percent = signals.get('edge_percent', 0)
    confidence = forecast.get('confidence', 0)
    clarity = resolution.get('clarity_score', 0)
    severity = resolution.get('severity_score', 0)
    
    if verbose:
        print(f"\n💼 STEP 7: Portfolio Integration...")
        print(f"   Checking risk for {side} ${size:.2f} @ {entry_price:.4f}")
    
    # Run risk check
    risk_check = tracker.check_risk(
        market_id=market_id,
        side=side,
        size=size,
        edge_percent=edge_percent,
        confidence=confidence
    )
    
    if verbose:
        passed = sum(c['passed'] for c in risk_check.get('checks', []))
        total = len(risk_check.get('checks', []))
        status = "✅" if risk_check['approved'] else "❌"
        print(f"   {status} Risk check: {passed}/{total} passed")
        
        if not risk_check['approved']:
            failed = [c['check'] for c in risk_check.get('checks', []) if not c['passed']]
            print(f"   Failed checks: {', '.join(failed)}")
    
    # If risk check fails, don't log trade
    if not risk_check['approved']:
        if verbose:
            print(f"   ❌ Risk check failed - trade NOT logged")
        return {
            "success": False,
            "reason": "risk_check_failed",
            "risk_check": risk_check,
            "trade_logged": None
        }
    
    # Log paper trade (NEVER auto-execute live trades)
    trade = tracker.log_trade(
        market_id=market_id,
        market_question=market_data.get('question', 'Unknown'),
        side=side,
        size=size,
        entry_price=entry_price,
        edge_percent=edge_percent,
        confidence=confidence,
        clarity=clarity,
        severity=severity,
        source="research_pipeline",
        trade_type="PAPER",  # ALWAYS PAPER - never live
        notes=f"Research pipeline recommendation: {recommendation}. Signals: edge={edge_percent:.1f}%, confidence={confidence}%"
    )
    
    if verbose:
        print(f"   ✅ Paper trade logged: {trade['trade_id']}")
    
    # Send Telegram alert
    alert_sent = False
    try:
        alert_sent = send_trade_alert(trade, risk_check)
        if verbose:
            status = "✅" if alert_sent else "⚠️"
            print(f"   {status} Telegram alert sent")
    except Exception as e:
        if verbose:
            print(f"   ⚠️  Telegram alert failed: {e}")
    
    return {
        "success": True,
        "trade": trade,
        "risk_check": risk_check,
        "telegram_alert_sent": alert_sent,
        "trade_type": "PAPER"
    }


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_research_pipeline(market_id: str, model: str = "kimi-coding/k2p5", verbose: bool = True) -> Dict:
    """
    Execute the full 6-step research pipeline on a single market.
    """
    if verbose:
        print(f"\n🔬 POLYCLAW Research Pipeline")
        print(f"   Market ID: {market_id}")
        print(f"   Model: {model}")
        print(f"   Started: {datetime.now().strftime('%H:%M:%S')}")
        print("=" * 60)
    
    # Get market data
    if not API_AVAILABLE:
        return {"error": "API client not available"}
    
    api = get_api_client()
    market = api.get_market(market_id)
    
    if not market:
        return {"error": f"Market {market_id} not found"}
    
    market_data = api.format_market(market)
    
    if verbose:
        print(f"\n📊 Market: {market_data['question'][:60]}...")
        print(f"   Yes: {market_data['yes_odds']} | No: {market_data['no_odds']}")
        print(f"   Volume 24h: ${market_data['volume_24h']:,.0f}")
    
    # ------------------------------------------------------------------------
    # STEP 1: FORECASTING
    # ------------------------------------------------------------------------
    if verbose:
        print(f"\n🎯 STEP 1: Forecasting (LLM call 1/3)...")
    
    prompt_1 = FORECASTING_PROMPT.format(
        question=market_data['question'],
        description=market_data['description'],
        end_date=market_data['end_date'],
        yes_odds=market_data['yes_odds'],
        no_odds=market_data['no_odds'],
        yes_price=market_data['yes_price'],
        no_price=market_data['no_price'],
        memory_context=load_memory_context()
    )
    
    forecast = call_llm(prompt_1, model=model)
    
    if verbose:
        p_yes = forecast.get('p_yes_estimate', 'N/A')
        conf = forecast.get('confidence', 'N/A')
        print(f"   ✓ P(Yes) estimate: {p_yes}% | Confidence: {conf}%")
    
    # ------------------------------------------------------------------------
    # STEP 2: RESOLUTION ANALYSIS
    # ------------------------------------------------------------------------
    if verbose:
        print(f"\n📋 STEP 2: Resolution Analysis (LLM call 2/3)...")
    
    prompt_2 = RESOLUTION_PROMPT.format(
        question=market_data['question'],
        description=market_data['description'],
        resolution_details=market.get('resolutionSource', 'Not specified')
    )
    
    resolution = call_llm(prompt_2, model=model)
    
    if verbose:
        clarity = resolution.get('clarity_score', 'N/A')
        sev = resolution.get('severity_score', 'N/A')
        print(f"   ✓ Clarity: {clarity}% | Severity: {sev}%")
    
    # ------------------------------------------------------------------------
    # STEP 3: DEVIL'S ADVOCATE
    # ------------------------------------------------------------------------
    if verbose:
        print(f"\n👿 STEP 3: Devil's Advocate (LLM call 3/3)...")
    
    prompt_3 = DEVILS_ADVOCATE_PROMPT.format(
        question=market_data['question'],
        yes_odds=market_data['yes_odds'],
        no_odds=market_data['no_odds'],
        p_yes_estimate=forecast.get('p_yes_estimate', 50)
    )
    
    devil = call_llm(prompt_3, model=model)
    
    if verbose:
        biases = devil.get('participant_biases', [])
        print(f"   ✓ Identified {len(biases)} potential biases")
    
    # ------------------------------------------------------------------------
    # STEP 4: SIGNAL GENERATION (Local computation - no LLM cost)
    # ------------------------------------------------------------------------
    if verbose:
        print(f"\n📈 STEP 4: Signal Generation (local)...")
    
    signals = generate_signals(market_data, forecast, resolution)
    
    if verbose:
        print(f"   ✓ Edge: {signals['edge_percent']:.1f}%")
        print(f"   ✓ Recommended: {signals['recommended_side']} ${signals['recommended_size']:.2f}")
    
    # ------------------------------------------------------------------------
    # STEP 5: VALIDATION GATE
    # ------------------------------------------------------------------------
    if verbose:
        print(f"\n🚦 STEP 5: Validation Gate...")
    
    validation = validate_signals(signals, forecast, resolution, market_data)
    
    if verbose:
        rec = validation.get('recommendation', 'UNKNOWN')
        passed = validation.get('passed_count', 0)
        total = validation.get('total_checks', 0)
        
        emoji = "✅" if rec == "TRADE" else ("📝" if rec == "PAPER_TRADE" else "❌")
        print(f"   {emoji} {rec} ({passed}/{total} checks passed)")
    
    # ------------------------------------------------------------------------
    # STEP 6: SAVE RESEARCH NOTE
    # ------------------------------------------------------------------------
    if verbose:
        print(f"\n💾 STEP 6: Saving research note...")
    
    filepath = save_research_note(
        market_id, market_data, forecast, resolution, devil, signals, validation
    )
    
    if verbose:
        print(f"   ✓ Saved to: {filepath}")
    
    # ------------------------------------------------------------------------
    # STEP 7: PORTFOLIO INTEGRATION (Risk check + Paper trade logging)
    # ------------------------------------------------------------------------
    portfolio_result = process_portfolio_integration(
        market_id, market_data, forecast, resolution, signals, validation, verbose=verbose
    )
    
    # Summary
    result = {
        "market_id": market_id,
        "market_question": market_data['question'],
        "recommendation": validation.get('recommendation'),
        "action": validation.get('recommended_action'),
        "edge_percent": signals.get('edge_percent'),
        "confidence": forecast.get('confidence'),
        "clarity": resolution.get('clarity_score'),
        "severity": resolution.get('severity_score'),
        "liquidity": market_data.get('liquidity'),
        "research_file": filepath,
        "portfolio_integration": portfolio_result,
        "timestamp": datetime.now().isoformat()
    }
    
    if verbose:
        print(f"\n{'=' * 60}")
        print(f"🏁 Pipeline Complete")
        print(f"   Recommendation: {result['recommendation']}")
        print(f"   Edge: {result['edge_percent']:.1f}% | Conf: {result['confidence']}%")
        if portfolio_result and portfolio_result.get('success'):
            print(f"   📝 Paper trade logged: {portfolio_result['trade']['trade_id']}")
        print(f"   File: {filepath}")
    
    return result


def research_trending_markets(limit: int = 5, model: str = "kimi-coding/k2p5"):
    """
    Run research pipeline on top trending markets.
    """
    if not API_AVAILABLE:
        print("❌ API client not available")
        return []
    
    api = get_api_client()
    markets = api.get_trending_markets(limit=limit)
    
    print(f"\n🔬 Researching {len(markets)} trending markets...")
    print(f"   Estimated cost: ${len(markets) * 0.30:.2f} ({len(markets)} × $0.30)")
    print("=" * 60)
    
    results = []
    for i, market in enumerate(markets, 1):
        market_id = market.get('id')
        print(f"\n[{i}/{len(markets)}] Researching {market_id}...")
        
        try:
            result = run_research_pipeline(market_id, model=model, verbose=False)
            results.append(result)
            
            rec = result.get('recommendation', 'UNKNOWN')
            edge = result.get('edge_percent', 0)
            emoji = "✅" if rec == "TRADE" else ("📝" if rec == "PAPER_TRADE" else "❌")
            print(f"   {emoji} {rec} | Edge: {edge:.1f}% | {result['market_question'][:40]}...")
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            results.append({"market_id": market_id, "error": str(e)})
    
    # Summary
    print(f"\n{'=' * 60}")
    print(f"📊 RESEARCH SUMMARY")
    print(f"   Total: {len(results)} markets")
    print(f"   TRADE: {sum(1 for r in results if r.get('recommendation') == 'TRADE')}")
    print(f"   PAPER: {sum(1 for r in results if r.get('recommendation') == 'PAPER_TRADE')}")
    print(f"   PASS:  {sum(1 for r in results if r.get('recommendation') == 'PASS')}")
    
    return results


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='POLYCLAW Research Pipeline - 6-Step Market Analysis'
    )
    parser.add_argument(
        'market_id',
        help='Market ID to research (or "trending" for top markets)'
    )
    parser.add_argument(
        '--model',
        default='kimi-coding/k2p5',
        help='LLM model to use (default: kimi-coding/k2p5)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=5,
        help='Number of trending markets to research (default: 5)'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    
    args = parser.parse_args()
    
    if args.market_id == 'trending':
        results = research_trending_markets(limit=args.limit, model=args.model)
        if args.json:
            print(json.dumps(results, indent=2))
    else:
        result = run_research_pipeline(args.market_id, model=args.model, verbose=not args.json)
        if args.json:
            print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
