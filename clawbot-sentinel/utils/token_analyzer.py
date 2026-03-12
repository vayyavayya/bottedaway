"""
Token Analyzer - Core Analysis Pipeline
5-layer model routing: Qwen → Perplexity → MiniMax → Kimi → Claude
"""
import json
import os
import sys
from typing import Dict, Optional
from datetime import datetime

# Add whale tracker to path
sys.path.insert(0, os.path.expanduser("~/.openclaw/workspace/skills/whale-accumulation-scorer/scripts"))

class TokenAnalyzer:
    """Orchestrates 5-layer analysis pipeline for any Solana token"""
    
    def __init__(self):
        self.workspace_dir = os.path.expanduser("~/.openclaw/workspace")
        self.birdeye_key = self._load_birdeye_key()
        self.helius_key = self._load_helius_key()
        
    def _load_birdeye_key(self) -> str:
        try:
            with open(os.path.expanduser("~/.config/birdeye/credentials.json")) as f:
                return json.load(f).get("api_key", "")
        except:
            return ""
    
    def _load_helius_key(self) -> str:
        try:
            with open(os.path.expanduser("~/.config/helius/credentials.json")) as f:
                return json.load(f).get("api_key", "")
        except:
            return ""
    
    async def analyze_token(self, address: str) -> Dict:
        """
        Full 5-layer analysis pipeline
        Returns: {
            "token": {...},      # Metadata
            "perplexity": {...}, # Narrative research
            "whale": {...},      # Whale scoring
            "engines": {...},    # A/B/C engine results
            "verdict": {...}     # BUY/STALK/PASS
        }
        """
        # Layer 1: Qwen - Fetch on-chain data
        token_data = await self._fetch_onchain_data(address)
        
        # Check filters first
        if token_data.get("age_days", 0) < 4:
            return self._skip_response(token_data, "Too new (< 4 days)")
        
        if self._is_dino_coin(token_data):
            return self._skip_response(token_data, "Dino coin (established/CEX listed)")
        
        # Layer 2: Perplexity - Real-time narrative research
        narrative = await self._research_narrative(address, token_data.get("symbol", ""))
        
        # Layer 3: MiniMax - Automated pipeline (whale + engines)
        whale_data = await self._run_whale_analysis(address, token_data)
        engines_data = await self._run_engines(address, token_data)
        
        # Layer 4: Kimi - Deep research (conditional)
        deep_research = None
        if self._needs_deep_research(whale_data, engines_data):
            deep_research = await self._deep_research(address, token_data, narrative)
        
        # Layer 5: Claude - Final verdict
        verdict = self._synthesize_verdict(
            token_data, whale_data, engines_data, narrative, deep_research
        )
        
        return {
            "token": token_data,
            "perplexity": narrative,
            "whale": whale_data,
            "engines": engines_data,
            "verdict": verdict
        }
    
    async def _fetch_onchain_data(self, address: str) -> Dict:
        """Layer 1: Qwen - Fetch metadata from Birdeye/DexScreener"""
        import requests
        
        # Try Birdeye first
        try:
            resp = requests.get(
                "https://public-api.birdeye.so/defi/v3/token/overview",
                headers={"X-API-KEY": self.birdeye_key, "x-chain": "solana"},
                params={"address": address},
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return {
                    "address": address,
                    "symbol": data.get("symbol", "???"),
                    "name": data.get("name", "Unknown"),
                    "price": float(data.get("price", 0)),
                    "market_cap": float(data.get("market_cap", 0)),
                    "liquidity": float(data.get("liquidity", 0)),
                    "volume_24h": float(data.get("volume_24h", 0)),
                    "age_days": data.get("token_age_days", 0),
                    "source": "birdeye"
                }
        except Exception as e:
            print(f"Birdeye error: {e}")
        
        # Fallback to DexScreener
        try:
            resp = requests.get(
                f"https://api.dexscreener.com/latest/dex/tokens/{address}",
                timeout=10
            )
            if resp.status_code == 200:
                pairs = resp.json().get("pairs", [])
                if pairs:
                    top = max(pairs, key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0))
                    base = top.get("baseToken", {})
                    return {
                        "address": address,
                        "symbol": base.get("symbol", "???"),
                        "name": base.get("name", "Unknown"),
                        "price": float(top.get("priceUsd", 0)),
                        "market_cap": 0,  # Not provided by DexScreener
                        "liquidity": float(top.get("liquidity", {}).get("usd", 0)),
                        "volume_24h": float(top.get("volume", {}).get("h24", 0)),
                        "age_days": 0,  # Would need separate lookup
                        "source": "dexscreener"
                    }
        except Exception as e:
            print(f"DexScreener error: {e}")
        
        return {"address": address, "symbol": "???", "name": "Unknown", "source": "none"}
    
    async def _research_narrative(self, address: str, symbol: str) -> Dict:
        """Layer 2: Perplexity - Real-time narrative research"""
        # Placeholder - would call Perplexity API
        return {
            "trending": False,
            "sentiment": "neutral",
            "red_flags": [],
            "catalysts": [],
            "source": "perplexity_placeholder"
        }
    
    async def _run_whale_analysis(self, address: str, token_data: Dict) -> Dict:
        """Layer 3: MiniMax - Whale scoring"""
        try:
            from whale_tracker import WhaleTracker
            tracker = WhaleTracker()
            signal = tracker.analyze_token(address)
            
            return {
                "score": signal.score,
                "phase": signal.phase.value,
                "buy_sell_ratio": signal.buy_sell_ratio,
                "velocity": signal.accumulation_velocity,
                "tags": signal.signal_tags,
                "actionable": signal.is_actionable
            }
        except Exception as e:
            print(f"Whale analysis error: {e}")
            return {"score": 0, "phase": "error", "tags": []}
    
    async def _run_engines(self, address: str, token_data: Dict) -> Dict:
        """Layer 3: MiniMax - Engines A/B/C"""
        # Placeholder - would call engine implementations
        return {
            "A": {"phase": "N/A", "confirmed_candles": 0},
            "B": {"phase": "N/A", "retest_status": "N/A"},
            "C": {"phase": "N/A", "trend": "N/A"}
        }
    
    def _needs_deep_research(self, whale: Dict, engines: Dict) -> bool:
        """Check if token needs Kimi deep research"""
        # Trigger if promising but ambiguous
        whale_score = whale.get("score", 0)
        whale_actionable = whale.get("actionable", False)
        
        # If whale is accumulating but engines not clear
        if whale_score > 0.4 and not whale_actionable:
            return True
        
        return False
    
    async def _deep_research(self, address: str, token: Dict, narrative: Dict) -> Dict:
        """Layer 4: Kimi - Deep research for ambiguous tokens"""
        return {"analysis": "placeholder", "confidence": 0.5}
    
    def _synthesize_verdict(self, token: Dict, whale: Dict, engines: Dict, 
                           narrative: Dict, deep_research: Optional[Dict]) -> Dict:
        """Layer 5: Claude - Final BUY/STALK/PASS verdict"""
        
        whale_score = whale.get("score", 0)
        whale_phase = whale.get("phase", "none")
        whale_actionable = whale.get("actionable", False)
        
        # Simple logic for now - full Claude integration later
        if whale_score >= 0.6 and whale_actionable:
            return {
                "action": "BUY",
                "reason": f"Strong whale accumulation (score: {whale_score:.2f}) + {whale_phase}",
                "position_size": 1000,  # Would calculate Kelly sizing
                "confidence": 0.8
            }
        elif whale_score >= 0.4:
            return {
                "action": "STALK",
                "reason": f"Whale activity present but waiting for confirmation (score: {whale_score:.2f})",
                "missing": "Stronger accumulation signal or engine confirmation",
                "confidence": 0.5
            }
        else:
            return {
                "action": "PASS",
                "reason": f"No significant whale accumulation (score: {whale_score:.2f})",
                "confidence": 0.7
            }
    
    def _is_dino_coin(self, token: Dict) -> bool:
        """Check if token is a 'dino' (established coin to skip)"""
        age = token.get("age_days", 0)
        mc = token.get("market_cap", 0)
        
        # Dino criteria: > 365 days old OR market cap > $1B
        if age > 365:
            return True
        if mc > 1_000_000_000:
            return True
        
        return False
    
    def _skip_response(self, token: Dict, reason: str) -> Dict:
        """Return skip response for filtered tokens"""
        return {
            "token": token,
            "perplexity": {},
            "whale": {"score": 0, "phase": "filtered"},
            "engines": {},
            "verdict": {
                "action": "PASS",
                "reason": reason,
                "confidence": 1.0
            }
        }


if __name__ == "__main__":
    import asyncio
    
    async def test():
        analyzer = TokenAnalyzer()
        result = await analyzer.analyze_token("NV2RYH954cTJ3ckFUpvfqaQXU4ARqqDH3562nFSpump")
        print(json.dumps(result, indent=2))
    
    asyncio.run(test())
