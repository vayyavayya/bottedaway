#!/usr/bin/env python3
"""
POLYCLAW Resolution Watcher
Monitors tracked markets for resolution and auto-records outcomes to memory.

Usage:
    python resolution_watcher.py check              # Check all tracked markets
    python resolution_watcher.py check --market-id  # Check specific market
    python resolution_watcher.py list               # List tracked markets
    python resolution_watcher.py auto               # Run auto-resolution check (for cron)
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path

# Paths
WORKSPACE = os.path.expanduser('~/.openclaw/workspace')
ANALYSIS_DIR = os.path.join(WORKSPACE, 'analysis', 'polymarket')
DAILY_BRIEFS_DIR = os.path.join(WORKSPACE, 'analysis', 'daily-briefs')
TRACKED_MARKETS_FILE = os.path.join(WORKSPACE, 'skills', 'polyclaw', 'data', 'tracked_markets.json')
RESOLVED_MARKETS_FILE = os.path.join(WORKSPACE, 'skills', 'polyclaw', 'data', 'resolved_markets.json')

sys.path.insert(0, os.path.join(WORKSPACE, 'skills', 'polyclaw'))

# Import memory tracker
try:
    from memory_tracker import PolyclawMemory, MarketResolution
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False
    print("⚠️  Memory tracker not available")

# Import API client
try:
    from api_client import get_api_client
    API_AVAILABLE = True
except ImportError:
    API_AVAILABLE = False
    print("⚠️  API client not available")


def load_tracked_markets() -> Dict[str, Dict]:
    """Load list of markets we're tracking for resolution"""
    if not os.path.exists(TRACKED_MARKETS_FILE):
        return {}
    
    try:
        with open(TRACKED_MARKETS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}


def save_tracked_markets(markets: Dict[str, Dict]):
    """Save tracked markets list"""
    os.makedirs(os.path.dirname(TRACKED_MARKETS_FILE), exist_ok=True)
    with open(TRACKED_MARKETS_FILE, 'w') as f:
        json.dump(markets, f, indent=2, default=str)


def load_resolved_markets() -> Dict[str, Dict]:
    """Load list of already resolved markets"""
    if not os.path.exists(RESOLVED_MARKETS_FILE):
        return {}
    
    try:
        with open(RESOLVED_MARKETS_FILE, 'r') as f:
            return json.load(f)
    except:
        return {}


def save_resolved_markets(markets: Dict[str, Dict]):
    """Save resolved markets list"""
    os.makedirs(os.path.dirname(RESOLVED_MARKETS_FILE), exist_ok=True)
    with open(RESOLVED_MARKETS_FILE, 'w') as f:
        json.dump(markets, f, indent=2, default=str)


def add_market_to_tracking(market_id: str, market_data: Dict, research_data: Dict):
    """Add a market to the tracking list after we trade/research it"""
    tracked = load_tracked_markets()
    
    tracked[market_id] = {
        'market_id': market_id,
        'question': market_data.get('question', 'Unknown'),
        'category': market_data.get('category', 'Uncategorized'),
        'end_date': market_data.get('end_date'),
        'added_at': datetime.now().isoformat(),
        'research_file': research_data.get('research_file'),
        'our_prediction': research_data.get('step1_forecasting', {}).get('p_yes_estimate', 50),
        'our_confidence': research_data.get('step1_forecasting', {}).get('confidence', 50),
        'edge_percent': research_data.get('step4_signals', {}).get('edge_percent', 0),
        'recommended_side': research_data.get('step4_signals', {}).get('recommended_side', 'YES'),
        'status': 'tracking'
    }
    
    save_tracked_markets(tracked)
    return tracked[market_id]


def extract_resolution_from_api(market_data: Dict) -> Optional[str]:
    """
    Extract resolution outcome from Polymarket API data.
    Returns: 'YES', 'NO', 'CANCELLED', 'UNRESOLVED', or None if still open
    """
    # Check various fields that indicate resolution
    outcome = market_data.get('outcome')
    resolution = market_data.get('resolution')
    resolved = market_data.get('resolved', False)
    active = market_data.get('active', True)
    closed = market_data.get('closed', False)
    
    # If not resolved/closed, still open
    if not resolved and not closed and active:
        return None
    
    # Check outcome field (usually 'Yes', 'No', or numeric)
    if outcome:
        outcome_str = str(outcome).upper()
        if outcome_str in ['YES', 'Y', '1', 'TRUE']:
            return 'YES'
        elif outcome_str in ['NO', 'N', '0', 'FALSE']:
            return 'NO'
        elif outcome_str in ['CANCELLED', 'CANCEL', 'VOID', 'INVALID']:
            return 'CANCELLED'
    
    # Check resolution field
    if resolution:
        resolution_str = str(resolution).upper()
        if resolution_str in ['YES', 'Y', '1', 'TRUE']:
            return 'YES'
        elif resolution_str in ['NO', 'N', '0', 'FALSE']:
            return 'NO'
        elif resolution_str in ['CANCELLED', 'CANCEL', 'VOID', 'INVALID']:
            return 'CANCELLED'
    
    # Market closed but no clear outcome - check price
    if closed or not active:
        yes_price = market_data.get('yes_price', 0.5)
        # If price is near 1 or 0, market likely resolved
        if yes_price > 0.95:
            return 'YES'
        elif yes_price < 0.05:
            return 'NO'
        return 'UNRESOLVED'
    
    return None


def check_market_resolution(market_id: str) -> Optional[Dict]:
    """
    Check if a specific market has resolved.
    Returns resolution data or None if still open.
    """
    if not API_AVAILABLE:
        print("❌ API client not available")
        return None
    
    api = get_api_client()
    market = api.get_market(market_id)
    
    if not market:
        return {
            'market_id': market_id,
            'status': 'error',
            'error': 'Market not found'
        }
    
    outcome = extract_resolution_from_api(market)
    
    if outcome is None:
        return None  # Still open
    
    return {
        'market_id': market_id,
        'status': 'resolved',
        'outcome': outcome,
        'question': market.get('question', 'Unknown'),
        'resolved_at': datetime.now().isoformat(),
        'final_yes_price': market.get('yesPrice', market.get('yes_price', 0.5)),
        'final_no_price': market.get('noPrice', market.get('no_price', 0.5)),
        'resolution_source': market.get('resolutionSource', 'Unknown')
    }


def calculate_pnl(tracked: Dict, outcome: str) -> Optional[float]:
    """
    Calculate P&L based on tracked position and outcome.
    This is simplified - real implementation would use actual trade logs.
    """
    recommended_side = tracked.get('recommended_side', 'YES')
    
    # For paper trading simulation
    # Assume $1 position for simplicity
    position_size = 1.0
    
    if recommended_side == 'YES':
        if outcome == 'YES':
            return position_size * 0.9  # Won, minus fees ~10%
        else:
            return -position_size  # Lost full position
    else:  # NO side
        if outcome == 'NO':
            return position_size * 0.9  # Won, minus fees
        else:
            return -position_size  # Lost full position


def extract_lessons(tracked: Dict, outcome: str) -> List[str]:
    """
    Auto-extract lessons from a resolved trade.
    Uses prediction vs outcome to generate learning points.
    """
    lessons = []
    
    our_pred = tracked.get('our_prediction', 50)
    our_side = tracked.get('recommended_side', 'YES')
    confidence = tracked.get('our_confidence', 50)
    edge = tracked.get('edge_percent', 0)
    
    # Directional correctness
    predicted_yes = our_pred > 50
    actual_yes = outcome == 'YES'
    was_correct = predicted_yes == actual_yes
    
    if was_correct:
        if confidence < 60:
            lessons.append("had_edge_despite_low_confidence")
        if edge > 10:
            lessons.append("high_edge_predicted_correctly")
    else:
        # We were wrong - figure out why
        if confidence > 75:
            lessons.append("overconfidence_penalty")
        if edge > 15:
            lessons.append("large_edge_did_not_materialize")
        
        # Check if we were on the wrong side entirely
        if (our_side == 'YES' and outcome == 'NO') or (our_side == 'NO' and outcome == 'YES'):
            lessons.append("directional_error")
    
    # Market-specific lessons based on category
    category = tracked.get('category', '').lower()
    if 'politic' in category:
        if not was_correct:
            lessons.append("politics_polls_unreliable")
    elif 'crypto' in category or 'bitcoin' in category:
        if not was_correct:
            lessons.append("crypto_volatility_unpredictable")
    elif 'sports' in category:
        lessons.append("sports_favorite_bias_check")
    
    # Time-based lessons
    end_date = tracked.get('end_date')
    if end_date:
        try:
            from datetime import datetime
            end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            days_to_resolve = (end - datetime.now(end.tzinfo)).days
            if days_to_resolve < 1:
                lessons.append("very_short_term_timing_difficult")
        except:
            pass
    
    return lessons


def record_resolution(resolution_data: Dict, tracked: Dict) -> Optional[MarketResolution]:
    """
    Record a market resolution to the memory system.
    """
    if not MEMORY_AVAILABLE:
        print("❌ Memory tracker not available")
        return None
    
    memory = PolyclawMemory()
    
    market_id = resolution_data['market_id']
    outcome = resolution_data['outcome']
    question = tracked.get('question', resolution_data.get('question', 'Unknown'))
    category = tracked.get('category', 'Uncategorized')
    prediction = tracked.get('our_prediction', 50)
    confidence = tracked.get('our_confidence', 50)
    edge = tracked.get('edge_percent', 0)
    
    # Calculate P&L
    pnl = calculate_pnl(tracked, outcome)
    
    # Extract lessons
    lessons = extract_lessons(tracked, outcome)
    
    # Record to memory
    resolution = memory.record_resolution(
        market_id=market_id,
        question=question,
        category=category,
        prediction=prediction,
        outcome=outcome,
        confidence=confidence,
        edge_percent=edge,
        pnl=pnl,
        lessons=lessons
    )
    
    # Update prompt addon
    memory.save_prompt_addon()
    
    # Move from tracked to resolved
    resolved = load_resolved_markets()
    resolved[market_id] = {
        **tracked,
        'outcome': outcome,
        'pnl': pnl,
        'lessons': lessons,
        'resolved_at': datetime.now().isoformat()
    }
    save_resolved_markets(resolved)
    
    # Remove from tracked
    tracked_list = load_tracked_markets()
    if market_id in tracked_list:
        del tracked_list[market_id]
        save_tracked_markets(tracked_list)
    
    return resolution


def check_all_tracked() -> List[Dict]:
    """
    Check all tracked markets for resolution.
    Returns list of newly resolved markets.
    """
    tracked = load_tracked_markets()
    resolved = load_resolved_markets()
    
    newly_resolved = []
    
    print(f"🔍 Checking {len(tracked)} tracked markets for resolution...")
    
    for market_id, tracked_data in tracked.items():
        if market_id in resolved:
            continue  # Already recorded
        
        result = check_market_resolution(market_id)
        
        if result and result.get('status') == 'resolved':
            print(f"\n🎯 Market resolved: {market_id}")
            print(f"   Question: {tracked_data.get('question', 'Unknown')[:60]}...")
            print(f"   Outcome: {result['outcome']}")
            
            # Record to memory
            resolution = record_resolution(result, tracked_data)
            
            if resolution:
                print(f"   {'✅' if resolution.was_correct() else '❌'} Our prediction: {resolution.prediction:.1f}%")
                print(f"   💰 P&L: ${resolution.pnl:+.2f}")
                print(f"   📝 Lessons: {', '.join(resolution.lessons)}")
            
            newly_resolved.append(result)
        
    return newly_resolved


def auto_check():
    """
    Automatic resolution check - meant to be run via cron.
    Checks tracked markets and updates memory if any resolved.
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_file = os.path.join(WORKSPACE, 'logs', 'resolution-watcher.log')
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    def log(msg):
        print(msg)
        with open(log_file, 'a') as f:
            f.write(f"{timestamp} - {msg}\n")
    
    log("=" * 60)
    log(f"🔍 Resolution Watcher - {timestamp}")
    
    if not API_AVAILABLE:
        log("❌ API client not available")
        return 1
    
    if not MEMORY_AVAILABLE:
        log("❌ Memory tracker not available")
        return 1
    
    newly_resolved = check_all_tracked()
    
    if newly_resolved:
        log(f"✅ Recorded {len(newly_resolved)} new resolutions")
        for r in newly_resolved:
            log(f"   - {r['market_id']}: {r['outcome']}")
    else:
        log("⏳ No new resolutions")
    
    log("=" * 60)
    return 0


def list_tracked():
    """List all tracked markets"""
    tracked = load_tracked_markets()
    resolved = load_resolved_markets()
    
    print(f"\n📋 Tracked Markets ({len(tracked)} active, {len(resolved)} resolved)")
    print("=" * 80)
    
    if tracked:
        print("\n🔄 Currently Tracking:")
        for market_id, data in tracked.items():
            print(f"   {market_id}")
            print(f"      {data.get('question', 'Unknown')[:50]}...")
            print(f"      Prediction: {data.get('our_prediction', 'N/A')}% | Side: {data.get('recommended_side', 'N/A')}")
    
    if resolved:
        print(f"\n✅ Recently Resolved:")
        # Show last 5
        recent = sorted(resolved.items(), key=lambda x: x[1].get('resolved_at', ''), reverse=True)[:5]
        for market_id, data in recent:
            outcome = data.get('outcome', 'UNKNOWN')
            pnl = data.get('pnl', 0)
            emoji = "✅" if pnl and pnl > 0 else "❌"
            print(f"   {emoji} {market_id}: {outcome} (${pnl:+.2f})")


def main():
    parser = argparse.ArgumentParser(
        description='POLYCLAW Resolution Watcher - Monitor markets for resolution'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Check command
    check_parser = subparsers.add_parser('check', help='Check markets for resolution')
    check_parser.add_argument('--market-id', help='Check specific market')
    
    # List command
    subparsers.add_parser('list', help='List tracked markets')
    
    # Auto command (for cron)
    subparsers.add_parser('auto', help='Auto check (for cron)')
    
    # Manual record command
    record_parser = subparsers.add_parser('record', help='Manually record a resolution')
    record_parser.add_argument('market_id', help='Market ID')
    record_parser.add_argument('outcome', choices=['YES', 'NO', 'CANCELLED', 'UNRESOLVED'])
    record_parser.add_argument('--pnl', type=float, help='P&L amount')
    record_parser.add_argument('--lessons', help='Comma-separated lessons')
    
    args = parser.parse_args()
    
    if args.command == 'check':
        if args.market_id:
            result = check_market_resolution(args.market_id)
            if result:
                print(json.dumps(result, indent=2))
            else:
                print(f"⏳ Market {args.market_id} is still open")
        else:
            newly_resolved = check_all_tracked()
            if newly_resolved:
                print(f"\n✅ {len(newly_resolved)} markets newly resolved")
            else:
                print("\n⏳ No new resolutions")
    
    elif args.command == 'list':
        list_tracked()
    
    elif args.command == 'auto':
        return auto_check()
    
    elif args.command == 'record':
        # Manual recording - use memory_tracker directly
        tracked = load_tracked_markets()
        tracked_data = tracked.get(args.market_id, {
            'question': input("Market question: "),
            'category': input("Category: "),
            'our_prediction': float(input("Our prediction (0-100): ")),
            'our_confidence': int(input("Confidence (0-100): ")),
            'edge_percent': float(input("Edge %: "))
        })
        
        resolution_data = {
            'market_id': args.market_id,
            'outcome': args.outcome,
            'question': tracked_data.get('question', 'Unknown')
        }
        
        resolution = record_resolution(resolution_data, tracked_data)
        if resolution:
            print(f"\n✅ Resolution recorded")
            print(f"   {'✅' if resolution.was_correct() else '❌'} Prediction: {resolution.prediction:.1f}%")
            print(f"   Outcome: {resolution.outcome}")
            print(f"   P&L: ${resolution.pnl:+.2f}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    sys.exit(main())
