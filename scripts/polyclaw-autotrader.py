#!/usr/bin/env python3
"""
PolyClaw AutoTrader - Autonomous Prediction Market Trading
Monitors markets, researches opportunities, executes trades, manages risk.
"""

import os
import sys
import json
import time
import random
import requests
from typing import Optional, Dict, List, Tuple
from datetime import datetime, timezone

# Config
CHAINSTACK_NODE = os.getenv("CHAINSTACK_NODE", "https://polygon-mainnet.core.chainstack.com/55b0f6bb17f8e6c0fd6285a5c7320a90")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
POLYCLAW_PRIVATE_KEY = os.getenv("POLYCLAW_PRIVATE_KEY", "0x0970feda196583fd5359efc9a15e2b5d32ba1e3c0d7853c27087baa33e6b18f0")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "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")

# RISK MANAGEMENT
MAX_POSITION_SIZE = 5.00  # Maximum $ per trade - HEDGE POSITIONS ALSO CAPPED AT $5
MAX_DAILY_EXPOSURE = 20.00  # Maximum daily trading volume
MIN_CONFIDENCE_THRESHOLD = 0.70  # 70% minimum confidence
MIN_MARKET_VOLUME = 500000  # $500K minimum volume
MAX_SLIPPAGE = 0.05  # 5% max price deviation from research
STOP_LOSS_PERCENTAGE = 0.15  # 15% stop loss on positions

# HEDGE DISCOVERY
ENABLE_HEDGE_DISCOVERY = True  # Enable LLM-powered hedge scanning
HEDGE_MIN_COVERAGE = 0.90  # Minimum 90% coverage for hedge trades
HEDGE_SCAN_LIMIT = 10  # Number of markets to scan for hedges

# SMART MONEY TRACKING
ENABLE_SMART_MONEY = True  # Enable whale wallet tracking
SMART_MONEY_MIN_CONFIDENCE = 0.75  # Min confidence to copy whale trades
SMART_MONEY_MAX_POSITION = 3.00  # Smaller size for copy trades

# LIVE TRADING MODE
LIVE_TRADING = os.getenv("LIVE_TRADING", "1") == "1"  # Set to 0 for dry run

print(f"[MODE] {'🟢 LIVE TRADING' if LIVE_TRADING else '⚪ DRY RUN (set LIVE_TRADING=1 for live)'}")
print(f"[RISK] Stop loss: {STOP_LOSS_PERCENTAGE:.0%}, Position size: ${MAX_POSITION_SIZE}")
print(f"[HEDGE] Discovery: {'ENABLED' if ENABLE_HEDGE_DISCOVERY else 'DISABLED'}")
print(f"[WHALE] Smart Money: {'ENABLED' if ENABLE_SMART_MONEY else 'DISABLED'}")

# Trade log
TRADE_LOG = "/Users/pterion2910/.openclaw/workspace/memory/polyclaw-trades.json"

def log_trade(trade: Dict):
    """Log trade to file."""
    trades = []
    if os.path.exists(TRADE_LOG):
        with open(TRADE_LOG, 'r') as f:
            trades = json.load(f)
    trades.append({
        **trade,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    with open(TRADE_LOG, 'w') as f:
        json.dump(trades, f, indent=2)

def get_daily_exposure() -> float:
    """Calculate today's trading volume."""
    if not os.path.exists(TRADE_LOG):
        return 0.0
    with open(TRADE_LOG, 'r') as f:
        trades = json.load(f)
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    return sum(t['amount'] for t in trades if t['timestamp'].startswith(today))

def perplexity_research(query: str) -> Optional[Dict]:
    """Run Perplexity research query."""
    try:
        resp = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "sonar-pro",
                "messages": [
                    {"role": "system", "content": "You are a prediction market analyst. Analyze the question objectively. Provide: 1) Probability estimate (0-100%), 2) Key factors, 3) Risk factors, 4) Confidence level (high/medium/low). Be concise."},
                    {"role": "user", "content": query}
                ],
                "temperature": 0.2,
                "max_tokens": 1000
            },
            timeout=45
        )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        
        # Extract probability from response
        prob = 0.5
        if "%" in content:
            # Try to find percentage
            import re
            matches = re.findall(r'(\d+)%', content)
            if matches:
                prob = int(matches[0]) / 100
        
        return {
            "analysis": content,
            "probability": prob,
            "citations": data.get("citations", [])
        }
    except Exception as e:
        print(f"[Research Error] {e}")
        return None

def scan_opportunities() -> List[Dict]:
    """
    Scan Polymarket for trading opportunities.
    Returns list of potential trades.
    """
    print("🔍 Scanning Polymarket for opportunities...")
    
    # This would call PolyClaw markets API
    # For now, return empty - implement with actual API call
    return []

def evaluate_trade(market: Dict) -> Optional[Dict]:
    """
    Evaluate a market for trading opportunity.
    Returns trade details or None if no edge.
    """
    question = market.get('question', '')
    yes_price = market.get('yes_price', 0)
    volume = market.get('volume', 0)
    
    # Skip low volume markets
    if volume < MIN_MARKET_VOLUME:
        return None
    
    # Research the market
    research_query = f"""Analyze this prediction market for trading:

Question: "{question}"
Current YES price: ${yes_price}
24h Volume: ${volume:,.0f}

Provide probability estimate (0-100%), key factors, confidence level.
Should we buy YES or NO based on edge vs current price?"""

    research = perplexity_research(research_query)
    if not research:
        return None
    
    true_prob = research['probability']
    
    # Calculate edge
    edge = true_prob - yes_price
    
    # Only trade if significant edge
    if abs(edge) < 0.10:  # Need 10%+ edge
        return None
    
    # Determine direction
    side = "YES" if edge > 0 else "NO"
    target_price = true_prob if edge > 0 else (1 - true_prob)
    
    # Calculate position size based on edge and confidence
    confidence = 0.5
    if "high confidence" in research['analysis'].lower():
        confidence = 0.8
    elif "medium confidence" in research['analysis'].lower():
        confidence = 0.6
    
    position_size = min(
        MAX_POSITION_SIZE,
        MAX_POSITION_SIZE * abs(edge) * confidence
    )
    
    return {
        "market_id": market.get('id'),
        "question": question,
        "side": side,
        "current_price": yes_price if side == "YES" else (1 - yes_price),
        "target_price": target_price,
        "edge": abs(edge),
        "confidence": confidence,
        "amount": round(position_size, 2),
        "research": research['analysis'],
        "volume": volume
    }

def execute_trade(trade: Dict) -> bool:
    """
    Execute trade via PolyClaw CLI.
    Returns success status.
    """
    print(f"🎯 Executing: {trade['side']} ${trade['amount']} on '{trade['question'][:50]}...'")
    
    # Build PolyClaw command
    cmd = f"cd ~/.openclaw/skills/polyclaw && uv run python scripts/polyclaw.py buy {trade['market_id']} {trade['side']} {trade['amount']}"
    
    if not LIVE_TRADING:
        print(f"[DRY RUN] Command: {cmd}")
        print("[Set LIVE_TRADING=1 to execute real trades]")
        log_trade({
            **trade,
            "status": "dry_run",
            "executed": False
        })
        return True
    
    # LIVE TRADING MODE
    print(f"🟢 LIVE: {cmd}")
    
    import subprocess
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print("✅ Trade executed successfully!")
            print(result.stdout)
            log_trade({
                **trade,
                "status": "executed",
                "executed": True,
                "tx_output": result.stdout
            })
            return True
        else:
            print(f"❌ Trade failed: {result.stderr}")
            log_trade({
                **trade,
                "status": "failed",
                "executed": False,
                "error": result.stderr
            })
            return False
            
    except Exception as e:
        print(f"❌ Exception: {e}")
        log_trade({
            **trade,
            "status": "error",
            "executed": False,
            "error": str(e)
        })
        return False

def get_open_positions() -> List[Dict]:
    """Fetch open positions from PolyClaw."""
    try:
        import subprocess
        result = subprocess.run(
            "cd ~/.openclaw/skills/polyclaw && uv run python scripts/polyclaw.py positions",
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            # Parse the output - this is a simple parser
            lines = result.stdout.strip().split('\n')
            positions = []
            for line in lines[2:]:  # Skip header lines
                if line.strip() and not line.startswith('-') and not line.startswith('Total'):
                    parts = line.split()
                    if len(parts) >= 6:
                        positions.append({
                            'id': parts[0],
                            'side': parts[1],
                            'entry': float(parts[2].replace('$', '')),
                            'current': float(parts[3].replace('$', '')),
                            'pnl': float(parts[4].replace('$', '').replace('+', '')),
                            'market': ' '.join(parts[5:])
                        })
            return positions
    except Exception as e:
        print(f"[Positions Error] {e}")
    return []

def check_stop_loss(positions: List[Dict]) -> List[Dict]:
    """Check positions against stop loss threshold."""
    stop_loss_triggered = []
    for pos in positions:
        entry = pos['entry']
        current = pos['current']
        if entry > 0:
            loss_pct = (current - entry) / entry
            if loss_pct <= -STOP_LOSS_PERCENTAGE:
                stop_loss_triggered.append(pos)
                print(f"🛑 STOP LOSS TRIGGERED: {pos['market'][:40]}...")
                print(f"   Entry: ${entry:.2f} | Current: ${current:.2f} | Loss: {loss_pct:.1%}")
    return stop_loss_triggered

def execute_stop_loss(position: Dict) -> bool:
    """Sell position at market to stop loss."""
    print(f"🚨 EXECUTING STOP LOSS: {position['id']}")
    
    # For now, we sell the opposite side of what we bought
    # If we bought YES, we sell YES tokens
    side_to_sell = position['side']
    
    cmd = f"cd ~/.openclaw/skills/polyclaw && uv run python scripts/polyclaw.py sell {position['id']} {side_to_sell}"
    
    if not LIVE_TRADING:
        print(f"[DRY RUN] Would execute: {cmd}")
        return True
    
    print(f"🟢 LIVE STOP LOSS: {cmd}")
    
    import subprocess
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print("✅ Stop loss executed!")
            log_trade({
                "type": "stop_loss",
                "position_id": position['id'],
                "market": position['market'],
                "side": position['side'],
                "entry": position['entry'],
                "exit": position['current'],
                "pnl": position['pnl'],
                "status": "executed"
            })
            return True
        else:
            print(f"❌ Stop loss failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Stop loss exception: {e}")
        return False

def scan_hedge_opportunities() -> List[Dict]:
    """
    Scan for hedge opportunities using PolyClaw hedge scan.
    Returns list of hedge trade pairs.
    """
    if not ENABLE_HEDGE_DISCOVERY:
        return []
    
    print("\n🔍 Scanning for hedge opportunities...")
    
    try:
        import subprocess
        result = subprocess.run(
            f"cd ~/.openclaw/skills/polyclaw && uv run python scripts/polyclaw.py hedge scan --limit {HEDGE_SCAN_LIMIT}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # Hedge scan can take a few minutes
        )
        
        if result.returncode != 0:
            print(f"[Hedge Scan Error] {result.stderr}")
            return []
        
        # Parse hedge scan output
        # Look for T1/T2/T3 coverage tiers
        hedges = []
        lines = result.stdout.split('\n')
        
        for line in lines:
            # Look for coverage indicators (T1 >=95%, T2 90-95%, T3 85-90%)
            if 'T1' in line or 'T2' in line:
                # Extract market IDs and coverage info
                # This is a simplified parser - actual format may vary
                if 'coverage' in line.lower() or '%' in line:
                    # Parse the hedge opportunity
                    hedges.append({
                        'raw_line': line,
                        'output': result.stdout
                    })
        
        print(f"Found {len(hedges)} potential hedge opportunities")
        return hedges
        
    except Exception as e:
        print(f"[Hedge Scan Exception] {e}")
        return []

def analyze_hedge_pair(market1_id: str, market2_id: str) -> Optional[Dict]:
    """
    Analyze a specific pair for hedging opportunity.
    Returns hedge trade details or None.
    """
    try:
        import subprocess
        result = subprocess.run(
            f"cd ~/.openclaw/skills/polyclaw && uv run python scripts/polyclaw.py hedge analyze {market1_id} {market2_id}",
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            return None
        
        # Parse the analysis for coverage percentage
        output = result.stdout
        
        # Look for coverage info
        coverage = 0.0
        if 'T1' in output:
            coverage = 0.95  # T1 = 95%+
        elif 'T2' in output:
            coverage = 0.92  # T2 = 90-95%
        elif 'T3' in output:
            coverage = 0.87  # T3 = 85-90%
        
        if coverage >= HEDGE_MIN_COVERAGE:
            return {
                'market1_id': market1_id,
                'market2_id': market2_id,
                'coverage': coverage,
                'analysis': output,
                'type': 'hedge'
            }
        
        return None
        
    except Exception as e:
        print(f"[Hedge Analysis Error] {e}")
        return None

def execute_hedge_trade(hedge: Dict, daily_exposure: float) -> Tuple[bool, float]:
    """
    Execute a hedge trade (buy YES on one, NO on other).
    Returns (success, amount_spent).
    """
    print(f"🎯 Executing hedge trade: {hedge['market1_id']} + {hedge['market2_id']}")
    print(f"   Coverage: {hedge['coverage']:.0%}")
    
    # For hedges, we split the position size between both legs
    # Each leg gets MAX_POSITION_SIZE / 2
    leg_size = min(MAX_POSITION_SIZE / 2, (MAX_DAILY_EXPOSURE - daily_exposure) / 2)
    
    if leg_size < 1.0:
        print("   ⏭️  Insufficient funds for hedge")
        return False, 0.0
    
    # Execute both legs
    success_count = 0
    total_spent = 0.0
    
    for market_id, side in [(hedge['market1_id'], 'YES'), (hedge['market2_id'], 'NO')]:
        cmd = f"cd ~/.openclaw/skills/polyclaw && uv run python scripts/polyclaw.py buy {market_id} {side} {leg_size:.2f}"
        
        if not LIVE_TRADING:
            print(f"   [DRY RUN] {cmd}")
            success_count += 1
            total_spent += leg_size
            continue
        
        print(f"   🟢 LIVE: {cmd}")
        
        import subprocess
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                print(f"   ✅ Leg executed: {market_id} {side}")
                success_count += 1
                total_spent += leg_size
                log_trade({
                    'type': 'hedge_leg',
                    'market_id': market_id,
                    'side': side,
                    'amount': leg_size,
                    'hedge_pair': f"{hedge['market1_id']}-{hedge['market2_id']}",
                    'coverage': hedge['coverage'],
                    'status': 'executed'
                })
            else:
                print(f"   ❌ Leg failed: {result.stderr}")
                
        except Exception as e:
            print(f"   ❌ Leg exception: {e}")
    
    # Both legs must succeed for hedge to work
    if success_count == 2:
        print(f"   ✅ Hedge complete! Total: ${total_spent:.2f}")
        return True, total_spent
    else:
        print(f"   ⚠️  Hedge incomplete ({success_count}/2 legs)")
        return False, total_spent

# ==================== SMART MONEY TRACKING ====================

def load_performance_data() -> List[Dict]:
    """Load recent trade performance."""
    perf_file = "/Users/pterion2910/.openclaw/workspace/memory/polyclaw-performance.json"
    if os.path.exists(perf_file):
        with open(perf_file, 'r') as f:
            return json.load(f)
    return []

def calculate_strategy_adjustment() -> Dict:
    """
    Analyze recent performance and suggest strategy adjustments.
    Like Clawdia - adapt when losing, capitalize when winning.
    """
    performance = load_performance_data()
    
    if len(performance) < 5:
        return {
            'adjustment': 0,
            'message': 'Building performance baseline...',
            'min_edge': 0.10,
            'max_position': MAX_POSITION_SIZE,
            'stop_loss': STOP_LOSS_PERCENTAGE
        }
    
    # Last 10 trades
    recent = performance[-10:]
    wins = sum(1 for p in recent if p.get('pnl', 0) > 0)
    win_rate = wins / len(recent)
    total_pnl = sum(p.get('pnl', 0) for p in recent)
    
    print(f"📊 Recent Performance: {win_rate:.0%} win rate, ${total_pnl:+.2f} P&L")
    
    # Adaptive strategy
    if win_rate < 0.4 or total_pnl < -30:
        # Losing streak - tighten up like Clawdia did
        return {
            'adjustment': -1,
            'message': f'🛡️ LOSING STREAK: Tightening risk (WR: {win_rate:.0%})',
            'min_edge': 0.15,  # Need 15% edge (vs 10%)
            'max_position': 3.00,  # Reduce to $3 (vs $5)
            'stop_loss': 0.10,  # Tighter 10% stop
            'action': 'conservative'
        }
    elif win_rate > 0.6 and total_pnl > 50:
        # Winning streak - maintain but don't get greedy
        return {
            'adjustment': 1,
            'message': f'🔥 HOT STREAK: Capitalizing (WR: {win_rate:.0%}, +${total_pnl:.0f})',
            'min_edge': 0.08,  # Can take 8% edge
            'max_position': MAX_POSITION_SIZE,  # Full $5
            'stop_loss': STOP_LOSS_PERCENTAGE,
            'action': 'aggressive'
        }
    else:
        # Neutral - standard strategy
        return {
            'adjustment': 0,
            'message': f'⚖️ NEUTRAL: Standard strategy (WR: {win_rate:.0%})',
            'min_edge': 0.10,
            'max_position': MAX_POSITION_SIZE,
            'stop_loss': STOP_LOSS_PERCENTAGE,
            'action': 'standard'
        }

def get_smart_money_signals() -> List[Dict]:
    """
    Get copy-trade signals from whale wallets.
    Integration with polyclaw-smart-money.py
    """
    if not ENABLE_SMART_MONEY:
        return []
    
    print("\n🐋 Checking smart money signals...")
    
    try:
        # Run the smart money tracker
        import subprocess
        result = subprocess.run(
            "cd ~/.openclaw/skills/polyclaw && uv run python scripts/polyclaw-smart-money.py",
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # For now, return empty (full implementation needs Polymarket data source)
        # In production, this would parse the output and return structured signals
        print("   Smart money tracker run (data integration pending)")
        return []
        
    except Exception as e:
        print(f"   [Smart Money Error] {e}")
        return []

def execute_smart_money_trade(signal: Dict, daily_exposure: float) -> Tuple[bool, float]:
    """
    Execute a copy trade based on whale signal.
    Uses smaller position size than edge trades.
    """
    confidence = signal.get('confidence', 0)
    
    if confidence < SMART_MONEY_MIN_CONFIDENCE:
        print(f"   ⏭️  Whale confidence too low ({confidence:.0%})")
        return False, 0.0
    
    # Smaller position for copy trades
    position_size = min(SMART_MONEY_MAX_POSITION, (MAX_DAILY_EXPOSURE - daily_exposure))
    
    if position_size < 1.0:
        print("   ⏭️  Insufficient funds for copy trade")
        return False, 0.0
    
    market_id = signal.get('market_id')
    side = signal.get('side')
    whale = signal.get('whale_address', 'unknown')[:12]
    
    print(f"🐋 Copying whale {whale}...")
    print(f"   Market: {market_id} | Side: {side}")
    print(f"   Size: ${position_size:.2f} | Confidence: {confidence:.0%}")
    
    cmd = f"cd ~/.openclaw/skills/polyclaw && uv run python scripts/polyclaw.py buy {market_id} {side} {position_size:.2f}"
    
    if not LIVE_TRADING:
        print(f"   [DRY RUN] {cmd}")
        return True, position_size
    
    print(f"   🟢 LIVE: {cmd}")
    
    import subprocess
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print("   ✅ Copy trade executed!")
            log_trade({
                'type': 'smart_money',
                'market_id': market_id,
                'side': side,
                'amount': position_size,
                'whale': signal.get('whale_address'),
                'whale_score': signal.get('whale_score'),
                'confidence': confidence,
                'status': 'executed'
            })
            return True, position_size
        else:
            print(f"   ❌ Copy trade failed: {result.stderr}")
            return False, 0.0
            
    except Exception as e:
        print(f"   ❌ Copy trade exception: {e}")
        return False, 0.0

def main():
    """Main autotrader loop."""
    print("=" * 60)
    print("🤖 POLYCLAW AUTOTRADER")
    print("=" * 60)
    print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    
    # STEP 1: CHECK STOP LOSS ON EXISTING POSITIONS
    print("\n📊 Checking existing positions for stop loss...")
    open_positions = get_open_positions()
    if open_positions:
        print(f"Found {len(open_positions)} open positions")
        stop_loss_positions = check_stop_loss(open_positions)
        if stop_loss_positions:
            print(f"\n🛑 {len(stop_loss_positions)} position(s) hit stop loss (-{STOP_LOSS_PERCENTAGE:.0%})")
            for pos in stop_loss_positions:
                execute_stop_loss(pos)
        else:
            print("✅ All positions within risk limits")
    else:
        print("No open positions")
    
    # STEP 2: CHECK DAILY EXPOSURE FOR NEW TRADES
    print("\n💰 Checking daily exposure...")
    daily_exposure = get_daily_exposure()
    print(f"Daily exposure: ${daily_exposure:.2f} / ${MAX_DAILY_EXPOSURE:.2f}")
    
    if daily_exposure >= MAX_DAILY_EXPOSURE:
        print("⚠️  Daily exposure limit reached. No new trades today.")
        return
    
    # STEP 3: STRATEGY ADAPTATION (like Clawdia - adapt to performance)
    print("\n🧠 Adapting strategy based on performance...")
    strategy_adj = calculate_strategy_adjustment()
    print(f"   {strategy_adj['message']}")
    
    # Update dynamic thresholds based on performance
    dynamic_min_edge = strategy_adj.get('min_edge', 0.10)
    dynamic_max_position = strategy_adj.get('max_position', MAX_POSITION_SIZE)
    print(f"   Settings: {dynamic_min_edge:.0%} min edge, ${dynamic_max_position} max position")
    
    # STEP 4: SMART MONEY COPY TRADING
    if ENABLE_SMART_MONEY and daily_exposure < MAX_DAILY_EXPOSURE:
        print("\n🐋 Checking smart money signals...")
        smart_signals = get_smart_money_signals()
        
        if smart_signals:
            print(f"   Found {len(smart_signals)} whale signals")
            for signal in smart_signals[:2]:  # Limit to 2 copy trades per run
                if daily_exposure + SMART_MONEY_MAX_POSITION <= MAX_DAILY_EXPOSURE:
                    success, spent = execute_smart_money_trade(signal, daily_exposure)
                    if success:
                        daily_exposure += spent
        else:
            print("   No smart money signals this cycle")
    
    # STEP 5: HEDGE DISCOVERY (if enabled)
    if ENABLE_HEDGE_DISCOVERY and daily_exposure < MAX_DAILY_EXPOSURE:
        print("\n🔍 Running hedge discovery...")
        hedge_opportunities = scan_hedge_opportunities()
        
        if hedge_opportunities:
            print(f"Found {len(hedge_opportunities)} hedge candidates")
            # Execute hedges (simplified - would need full parsing logic)
            # For now, just log that hedges were found
            for hedge in hedge_opportunities[:2]:  # Limit to 2 hedges per run
                if daily_exposure + MAX_POSITION_SIZE <= MAX_DAILY_EXPOSURE:
                    # Note: Full hedge execution requires parsing the scan output
                    # This is a placeholder for the actual implementation
                    print(f"   [HEDGE FOUND] {hedge.get('raw_line', 'Details in scan output')}")
                    # execute_hedge_trade(hedge, daily_exposure)
        else:
            print("No hedge opportunities found")
    
    # STEP 6: SCAN FOR REGULAR EDGE OPPORTUNITIES
    print("\n🔍 Scanning for edge opportunities...")
    opportunities = scan_opportunities()
    print(f"Found {len(opportunities)} markets to analyze")
    
    # Evaluate each opportunity with dynamic edge threshold
    trades_to_execute = []
    for opp in opportunities:
        trade = evaluate_trade(opp)
        if trade:
            # Apply dynamic edge threshold based on performance
            if trade['edge'] >= dynamic_min_edge:
                # Adjust position size based on strategy mode
                trade['amount'] = min(trade['amount'], dynamic_max_position)
                trades_to_execute.append(trade)
                print(f"✅ Trade signal: {trade['side']} ${trade['amount']} (edge: {trade['edge']:.1%})")
            else:
                print(f"⏭️  Edge {trade['edge']:.1%} < threshold {dynamic_min_edge:.0%}")
    
    # Execute best trades
    executed = 0
    for trade in sorted(trades_to_execute, key=lambda x: x['edge'], reverse=True):
        if daily_exposure + trade['amount'] <= MAX_DAILY_EXPOSURE:
            if execute_trade(trade):
                executed += 1
                daily_exposure += trade['amount']
        else:
            print(f"⏭️  Skipping trade - would exceed daily limit")
    
    print(f"\n{'='*60}")
    print(f"✅ AUTOTRADER COMPLETE")
    print(f"   Mode: {strategy_adj.get('action', 'standard').upper()}")
    print(f"   Stop loss checks: {len(stop_loss_positions) if 'stop_loss_positions' in dir() else 0} triggered")
    print(f"   Smart money: {len(smart_signals) if 'smart_signals' in dir() else 0} signals")
    print(f"   Edge trades: {executed} executed")
    print(f"   Daily exposure: ${daily_exposure:.2f} / ${MAX_DAILY_EXPOSURE:.2f}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
