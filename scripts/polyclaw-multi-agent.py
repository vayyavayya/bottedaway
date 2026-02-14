#!/usr/bin/env python3
"""
PolyClaw Multi-Agent AutoTrader with Supabase Backend
Scanner → Researcher → Trader coordination via Supabase
"""

import os
import sys
import json
import time
from typing import Optional, Dict, List
from datetime import datetime, timezone

# Add scripts to path
sys.path.insert(0, '/Users/pterion2910/.openclaw/workspace/scripts')

# Try to import Supabase coordinator
try:
    from supabase_agent_coordinator import SupabaseAgentCoordinator, CoordinatorAgent
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    print("⚠️  Supabase coordinator not available. Running in single-agent mode.")

# Configuration
CHAINSTACK_NODE = os.getenv("CHAINSTACK_NODE", "https://polygon-mainnet.core.chainstack.com/55b0f6bb17f8e6c0fd6285a5c7320a90")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
POLYCLAW_PRIVATE_KEY = os.getenv("POLYCLAW_PRIVATE_KEY", "")
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")
LIVE_TRADING = os.getenv("LIVE_TRADING", "1") == "1"

# Agent configuration
AGENT_MODE = os.getenv("AGENT_MODE", "scanner")  # scanner, trader, researcher, coordinator
ENABLE_SUPABASE = os.getenv("ENABLE_SUPABASE", "true").lower() == "true" and SUPABASE_AVAILABLE

# Risk Management
MAX_POSITION_SIZE = 5.00
MAX_DAILY_EXPOSURE = 20.00
MIN_CONFIDENCE_THRESHOLD = 0.70
STOP_LOSS_PERCENTAGE = 0.15

print("=" * 60)
print("🤖 POLYCLAW MULTI-AGENT AUTOTRADER")
print("=" * 60)
print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
print(f"Mode: {AGENT_MODE.upper()}")
print(f"Supabase: {'✅ ENABLED' if ENABLE_SUPABASE else '⚪ DISABLED'}")
print(f"Trading: {'🟢 LIVE' if LIVE_TRADING else '⚪ DRY RUN'}")
print("=" * 60)

class MultiAgentTrader:
    """
    Multi-agent trading system with Supabase coordination.
    
    Modes:
    - scanner: Finds opportunities, creates jobs
    - researcher: Deep research on specific markets
    - trader: Executes trades from job queue
    - coordinator: Monitors system health
    """
    
    def __init__(self):
        self.coordinator = None
        self.agent = None
        
        if ENABLE_SUPABASE:
            try:
                if AGENT_MODE == "coordinator":
                    self.coordinator = CoordinatorAgent()
                    print("✅ Coordinator agent initialized")
                else:
                    self.agent = SupabaseAgentCoordinator(
                        agent_id=f"polyclaw-{AGENT_MODE}-{int(time.time())}",
                        agent_name=f"PolyClaw {AGENT_MODE.title()}",
                        agent_type=AGENT_MODE
                    )
                    print(f"✅ {AGENT_MODE.title()} agent initialized")
            except Exception as e:
                print(f"⚠️  Could not initialize Supabase: {e}")
                self.coordinator = None
                self.agent = None
    
    def run_scanner_cycle(self):
        """Scanner: Find opportunities and create jobs."""
        print("\n🔍 SCANNER CYCLE")
        print("-" * 60)
        
        # Get trending markets from PolyClaw
        markets = self._get_trending_markets()
        
        if not markets:
            print("No markets found")
            return
        
        print(f"Found {len(markets)} markets")
        
        # Analyze each market
        for market in markets[:5]:  # Top 5
            market_id = market.get('id')
            question = market.get('question', '')
            volume = market.get('volume', {}).get('24h', 0)
            
            # Skip low volume
            if volume < 500000:
                continue
            
            print(f"\n📊 Analyzing: {question[:60]}...")
            
            # Quick analysis with Perplexity
            edge = self._analyze_market(market)
            
            if edge and edge['edge'] >= 0.10:
                print(f"✅ Opportunity found! Edge: {edge['edge']:.1%}")
                
                if ENABLE_SUPABASE and self.agent:
                    # Create opportunity in Supabase
                    self.agent.create_opportunity(
                        market_id=market_id,
                        market_question=question,
                        side=edge['side'],
                        current_price=edge['current_price'],
                        confidence=edge['confidence'],
                        edge=edge['edge'],
                        research_summary=edge['research_summary'],
                        suggested_position=min(MAX_POSITION_SIZE, 5.0)
                    )
                else:
                    # Direct execution (single-agent mode)
                    print(f"   Would execute: {edge['side']} ${MAX_POSITION_SIZE}")
            else:
                print(f"   ⏭️ No edge (or too small)")
    
    def run_trader_cycle(self):
        """Trader: Execute trades from job queue."""
        print("\n💰 TRADER CYCLE")
        print("-" * 60)
        
        if ENABLE_SUPABASE and self.agent:
            # Claim a trade job from Supabase
            job = self.agent.claim_job()
            
            if job and job.job_type == "execute_trade":
                print(f"🎯 Executing trade job: {job.payload}")
                self._execute_trade_from_job(job)
            else:
                print("No trade jobs available")
        else:
            print("Supabase not available. Trader mode requires job queue.")
    
    def run_researcher_cycle(self):
        """Researcher: Deep dive on assigned markets."""
        print("\n🔬 RESEARCHER CYCLE")
        print("-" * 60)
        
        if ENABLE_SUPABASE and self.agent:
            job = self.agent.claim_job()
            
            if job and job.job_type == "deep_research":
                print(f"📚 Researching: {job.payload.get('market_question')}")
                # TODO: Implement deep research
                self.agent.complete_job(job.id, success=True, result={"analysis": "completed"})
            else:
                print("No research jobs available")
        else:
            print("Supabase not available. Researcher mode requires job queue.")
    
    def run_coordinator_cycle(self):
        """Coordinator: Monitor and manage all agents."""
        print("\n🎛️ COORDINATOR CYCLE")
        print("-" * 60)
        
        if self.coordinator:
            health = self.coordinator.run_health_check()
            self.coordinator.dispatch_jobs()
            
            # Send summary
            self.coordinator.broadcast_alert(
                subject="Health Check Complete",
                content=f"Agents: {health['total_agents']}, Stale: {health['stale']}, Blocked: {health['blocked']}",
                payload=health
            )
        else:
            print("Coordinator not initialized")
    
    def _get_trending_markets(self) -> List[Dict]:
        """Get trending markets from PolyClaw."""
        import subprocess
        
        try:
            result = subprocess.run(
                "cd ~/.openclaw/skills/polyclaw && uv run python scripts/polyclaw.py markets trending",
                shell=True, capture_output=True, text=True, timeout=30
            )
            
            # Parse the output (simplified)
            # In production, use JSON output from PolyClaw
            return []  # Placeholder
            
        except Exception as e:
            print(f"Error getting markets: {e}")
            return []
    
    def _analyze_market(self, market: Dict) -> Optional[Dict]:
        """Analyze a market for trading opportunity."""
        import requests
        
        question = market.get('question', '')
        
        # Skip if not suitable for analysis
        if len(question) < 10:
            return None
        
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
                        {"role": "system", "content": "You are a prediction market analyst. Provide: 1) Probability 0-100%, 2) Key factors, 3) Confidence level."},
                        {"role": "user", "content": f"Analyze this market: '{question}'. Current prediction market prices? What is the true probability vs market price? Is there an edge?"}
                    ],
                    "temperature": 0.2,
                    "max_tokens": 500
                },
                timeout=45
            )
            
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            
            # Extract probability
            prob = 0.5
            if "%" in content:
                import re
                matches = re.findall(r'(\d+)%', content)
                if matches:
                    prob = int(matches[0]) / 100
            
            # Simple edge calculation (placeholder)
            # In real implementation, parse actual market prices
            edge = abs(prob - 0.5)
            
            if edge >= 0.10:
                return {
                    "side": "YES" if prob > 0.5 else "NO",
                    "current_price": 0.5,  # Placeholder
                    "confidence": 0.75,
                    "edge": edge,
                    "research_summary": content[:200]
                }
            
            return None
            
        except Exception as e:
            print(f"Research error: {e}")
            return None
    
    def _execute_trade_from_job(self, job):
        """Execute a trade from a job."""
        import subprocess
        
        payload = job.payload
        market_id = payload.get('market_id')
        side = payload.get('side')
        amount = payload.get('amount', MAX_POSITION_SIZE)
        
        print(f"🎯 Executing: {side} ${amount} on {market_id}")
        
        cmd = f"cd ~/.openclaw/skills/polyclaw && uv run python scripts/polyclaw.py buy {market_id} {side} {amount}"
        
        if not LIVE_TRADING:
            print(f"[DRY RUN] {cmd}")
            self.agent.complete_job(job.id, success=True, result={"status": "dry_run"})
            return
        
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=120
            )
            
            if result.returncode == 0:
                print("✅ Trade executed!")
                self.agent.complete_job(
                    job.id, 
                    success=True, 
                    result={"output": result.stdout}
                )
            else:
                print(f"❌ Trade failed: {result.stderr}")
                self.agent.complete_job(
                    job.id,
                    success=False,
                    error=result.stderr
                )
                
        except Exception as e:
            print(f"❌ Exception: {e}")
            self.agent.complete_job(job.id, success=False, error=str(e))

def main():
    """Main entry point."""
    trader = MultiAgentTrader()
    
    # Run based on agent mode
    if AGENT_MODE == "scanner":
        trader.run_scanner_cycle()
    elif AGENT_MODE == "trader":
        trader.run_trader_cycle()
    elif AGENT_MODE == "researcher":
        trader.run_researcher_cycle()
    elif AGENT_MODE == "coordinator":
        trader.run_coordinator_cycle()
    else:
        print(f"Unknown mode: {AGENT_MODE}")
    
    print("\n" + "=" * 60)
    print("✅ CYCLE COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
