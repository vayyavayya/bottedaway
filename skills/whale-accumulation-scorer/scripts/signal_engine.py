"""
signal_engine.py — ClawBot Signal Pipeline
===========================================

Combines Engine A (EMA reclaim) with Whale Accumulation Scorer
for unified signal strength and Kelly-sized position entries.

Flow:
1. Engine A analyzes tokens for EMA50 reclaim patterns
2. Tokens in STALKING phase get whale accumulation layer
3. Combined score feeds Kelly criterion sizing
4. Execution layer places trades

Usage:
    from signal_engine import SignalEngine
    
    engine = SignalEngine()
    signals = engine.scan_for_opportunities()
    
    for signal in signals:
        if signal.combined_score > 0.7:
            size = engine.kelly_size(signal)
            print(f"Enter {signal.token}: {size:.2%} of bankroll")
"""

import os
import sys
from dataclasses import dataclass
from typing import List, Optional, Tuple
from pathlib import Path

# Add paths for imports
SKILL_DIR = Path(__file__).parent.parent
WORKSPACE_DIR = SKILL_DIR.parent.parent.parent  # Up to workspace root
sys.path.insert(0, str(SKILL_DIR / "scripts"))
sys.path.insert(0, str(WORKSPACE_DIR))

from whale_tracker import WhaleTracker, WhaleSignal, AccumulationPhase

# Import Engine A from scanner_engines
try:
    from scanner_engines.src.patterns.engine_a import EngineA, EngineAConfig, SetupState
    ENGINE_A_AVAILABLE = True
except ImportError:
    ENGINE_A_AVAILABLE = False
    print("Warning: Engine A not available at scanner_engines.src.patterns.engine_a")


@dataclass
class Signal:
    """Unified signal from Engine A + Whale accumulation."""
    token_address: str
    token_symbol: str
    engine_a_score: float           # 0-1 EMA reclaim quality
    whale_score: float              # 0-1 accumulation score
    whale_phase: str                # "none", "early", "active", "heavy", "distribution"
    combined_score: float           # 0-1 weighted combination
    kelly_probability: float        # 0.45-0.65 for sizing
    position_size_pct: float        # % of bankroll to deploy
    rationale: str                  # Human-readable reasoning
    action: str                     # "ENTER", "STALK", "PASS"


class SignalEngine:
    """
    Combines Engine A (EMA reclaim) with whale accumulation scoring.
    
    For every token in Engine A's STALKING phase:
    - Get whale accumulation score
    - Combine weighted: 60% EMA + 40% whale
    - Apply 15% bonus if both signals agree (>0.6 each)
    - Discount 30% if no whale confirmation
    - Map to Kelly probability (0.45-0.65)
    - Size position accordingly
    """

    def __init__(self, bankroll_usd: float = 10000.0, kelly_fraction: float = 0.25,
                 engine_a_config: Optional[EngineAConfig] = None):
        """
        Args:
            bankroll_usd: Total capital available for deployment
            kelly_fraction: Fraction of full Kelly to use (0.25 = quarter Kelly)
            engine_a_config: Optional Engine A configuration
        """
        self.bankroll = bankroll_usd
        self.kelly_fraction = kelly_fraction
        self.whale_tracker = WhaleTracker()
        
        # Initialize Engine A if available
        if ENGINE_A_AVAILABLE:
            config = engine_a_config or EngineAConfig()
            self.engine_a = EngineA(config)
        else:
            self.engine_a = None
        
        # Thresholds
        self.ENTER_THRESHOLD = 0.70      # Combined score to enter
        self.STALK_THRESHOLD = 0.55      # Combined score to watch
        self.WHALE_MIN_SCORE = 0.40      # Minimum whale score for confirmation

    def scan_for_opportunities(self, token_candidates: List[dict]) -> List[Signal]:
        """
        Main entry point. Scan tokens and return actionable signals.
        
        Args:
            token_candidates: List of dicts with token info from discovery
                [{"address": "...", "symbol": "...", "price": 0.001, ...}]
        
        Returns:
            List of Signal objects sorted by combined_score
        """
        signals = []
        
        for token in token_candidates:
            try:
                signal = self.analyze_token(token)
                if signal.action in ("ENTER", "STALK"):
                    signals.append(signal)
            except Exception as e:
                print(f"Error analyzing {token.get('symbol', '???')}: {e}")
                continue
        
        # Sort by combined score descending
        signals.sort(key=lambda x: x.combined_score, reverse=True)
        return signals

    def analyze_token(self, token: dict) -> Signal:
        """
        Analyze a single token through the full pipeline.
        
        Args:
            token: Token dict with at least "address" and "symbol"
        
        Returns:
            Signal object with scores and recommendation
        """
        token_addr = token["address"]
        token_symbol = token.get("symbol", "???")
        
        # Step 1: Engine A — EMA reclaim analysis
        engine_a_score = self._engine_a_analyze(token)
        
        # Step 2: Whale accumulation layer
        whale_signal = self.whale_tracker.analyze_token(token_addr)
        
        # Step 3: Combine scores
        combined_score, rationale = self._combine_scores(
            token_addr, token_symbol, engine_a_score, whale_signal
        )
        
        # Step 4: Kelly sizing
        kelly_p = self._to_kelly_probability(combined_score)
        position_size = self._kelly_size(kelly_p)
        
        # Step 5: Determine action
        if combined_score >= self.ENTER_THRESHOLD:
            action = "ENTER"
        elif combined_score >= self.STALK_THRESHOLD:
            action = "STALK"
        else:
            action = "PASS"
        
        return Signal(
            token_address=token_addr,
            token_symbol=token_symbol,
            engine_a_score=engine_a_score,
            whale_score=whale_signal.score,
            whale_phase=whale_signal.phase.value,
            combined_score=combined_score,
            kelly_probability=kelly_p,
            position_size_pct=position_size,
            rationale=rationale,
            action=action
        )

    def _engine_a_analyze(self, token: dict) -> float:
        """
        Engine A: EMA reclaim analysis.
        
        Returns confidence score (0-1) for tokens in STALKING or TRIGGER phase.
        Returns 0.0 for tokens in BASING phase (skip — too early).
        
        Args:
            token: Token dict with at least "address" and "symbol"
                  Optionally includes "candles" or "price_data" for analysis
        
        Returns:
            0-1 confidence score, or 0.0 if not in actionable phase
        """
        if not ENGINE_A_AVAILABLE or not self.engine_a:
            # Fallback: return mock score for demo/testing
            import random
            return random.uniform(0.3, 0.9)
        
        token_addr = token["address"]
        token_symbol = token.get("symbol", "UNKNOWN")
        
        # Check if token is already a candidate in Engine A
        if token_addr not in self.engine_a.candidates:
            # Add as candidate with provided data
            chain = token.get("chain", "solana")
            self.engine_a.add_candidate(token_addr, chain, token)
        
        # Get current state from Engine A's candidate tracking
        candidate = self.engine_a.candidates.get(token_addr, {})
        current_state = candidate.get('last_state', SetupState.BASING)
        
        # Only score tokens in STALKING or TRIGGER phase
        # Skip BASING (WATCHLIST) and HOLDING (already in position)
        if current_state == SetupState.BASING:
            # Token still basing below EMA — too early
            return 0.0
        
        if current_state not in (SetupState.STALKING, SetupState.TRIGGER):
            # HOLDING or other states — not actionable for new entry
            return 0.0
        
        # Calculate confidence based on setup quality
        # For STALKING: distance to EMA determines confidence
        # For TRIGGER: higher confidence on successful reclaim
        
        setup_data = candidate.get('setup', {})
        price = setup_data.get('price', 0)
        ema50 = setup_data.get('ema50', 0)
        
        if price <= 0 or ema50 <= 0:
            # No price data, use default mid-range score
            base_confidence = 0.5
        else:
            distance = abs((price - ema50) / ema50)
            
            if current_state == SetupState.TRIGGER:
                # Just triggered — high confidence
                base_confidence = 0.75 + (0.15 * (1 - min(distance * 10, 1)))
            else:
                # STALKING — confidence inversely proportional to distance
                # Closer to EMA = higher confidence (more likely to reclaim)
                base_confidence = 0.55 + (0.20 * (1 - min(distance * 20, 1)))
        
        # Adjust based on volume if available
        volume = setup_data.get('volume_24h', 0)
        if volume > 100000:
            base_confidence += 0.10
        elif volume > 50000:
            base_confidence += 0.05
        
        # Cap at 0.95 (never claim certainty)
        return min(base_confidence, 0.95)

    def _combine_scores(
        self, 
        token_addr: str, 
        token_symbol: str,
        engine_a_score: float, 
        whale_signal: WhaleSignal
    ) -> Tuple[float, str]:
        """
        Combine Engine A and whale scores with weighting logic.
        
        Rules:
        - Whale actionable (score >= 0.4, active/heavy phase): 60% EMA + 40% whale
        - Whale not actionable: 70% EMA only (30% discount for no confirmation)
        - Both strong (>0.6): 15% bonus for convergence
        - Distribution phase: Skip (strong penalty)
        """
        
        # Check for distribution (avoid)
        if whale_signal.phase == AccumulationPhase.DISTRIBUTION:
            combined = engine_a_score * 0.3  # Heavy penalty
            rationale = (
                f"DISTRIBUTION phase detected — whales selling. "
                f"EMA({engine_a_score:.2f}) heavily discounted to {combined:.2f}. SKIP."
            )
            return combined, rationale
        
        # Use enrich_engine_a_signal logic
        if whale_signal.is_actionable:
            # Weighted: 60% EMA + 40% whale
            combined = (engine_a_score * 0.6) + (whale_signal.score * 0.4)
            
            # Bonus for convergence
            if engine_a_score > 0.6 and whale_signal.score > 0.6:
                combined = min(combined * 1.15, 1.0)
                rationale = (
                    f"🎯 CONVERGENCE: EMA({engine_a_score:.2f}) + Whale({whale_signal.score:.2f}) = {combined:.2f}. "
                    f"{whale_signal.num_whales_accumulating} whales accumulating."
                )
            else:
                rationale = (
                    f"EMA({engine_a_score:.2f}) + Whale({whale_signal.score:.2f}) = {combined:.2f}. "
                    f"{whale_signal.details}"
                )
        else:
            # No whale confirmation — discount EMA score
            combined = engine_a_score * 0.7
            rationale = (
                f"EMA only ({engine_a_score:.2f} → {combined:.2f}) — "
                f"no whale confirmation ({whale_signal.phase.value}, {whale_signal.score:.2f})"
            )
        
        return combined, rationale

    def _to_kelly_probability(self, combined_score: float) -> float:
        """
        Map combined 0-1 score to Kelly probability range (0.45-0.65).
        
        Conservative mapping — never claim >65% edge even with perfect signals.
        """
        # Linear map: 0 → 0.45, 1 → 0.65
        return 0.45 + (combined_score * 0.20)

    def _kelly_size(self, probability: float, payoff_ratio: float = 2.0) -> float:
        """
        Calculate Kelly criterion position size.
        
        Formula: f* = (p*b - q) / b
        Where:
        - p = probability of win
        - q = probability of loss (1-p)
        - b = payoff ratio (average win / average loss)
        
        Args:
            probability: 0.45-0.65 range from signal
            payoff_ratio: Expected win/loss ratio (default 2:1)
        
        Returns:
            Position size as % of bankroll (already scaled by kelly_fraction)
        """
        q = 1 - probability
        kelly_full = ((probability * payoff_ratio) - q) / payoff_ratio
        
        # Apply fractional Kelly for safety
        kelly_position = kelly_full * self.kelly_fraction
        
        # Clamp to reasonable range (1% - 25% of bankroll per trade)
        return max(0.01, min(0.25, kelly_position))

    def execute_signal(self, signal: Signal) -> dict:
        """
        Translate signal to execution parameters.
        
        IMPORTANT: PASS signals result in ZERO position size (action: SKIP).
        This is enforced at the execution layer, regardless of raw Kelly calculation.
        
        Returns dict with:
        - action: "BUY", "WATCH", or "SKIP" (for PASS)
        - size_usd: Dollar amount to deploy ($0 for PASS)
        - stop_loss: Recommended stop price
        - take_profit: Recommended target
        - rationale: Full reasoning
        """
        if signal.action == "PASS":
            # PASS signals get ZERO allocation - enforced at execution layer
            return {"action": "SKIP", "rationale": signal.rationale}
        
        size_usd = self.bankroll * signal.position_size_pct
        
        return {
            "action": "BUY" if signal.action == "ENTER" else "WATCH",
            "token_address": signal.token_address,
            "token_symbol": signal.token_symbol,
            "size_usd": round(size_usd, 2),
            "size_pct": round(signal.position_size_pct * 100, 2),
            "combined_score": round(signal.combined_score, 2),
            "engine_a": round(signal.engine_a_score, 2),
            "whale": round(signal.whale_score, 2),
            "whale_phase": signal.whale_phase,
            "kelly_p": round(signal.kelly_probability, 3),
            "rationale": signal.rationale
        }


# ─── Example Usage ─────────────────────────────────────────────────────────────
def main():
    """Demo the signal engine with mock tokens."""
    
    # Mock discovery results (replace with actual Birdeye/DexScreener discovery)
    mock_tokens = [
        {"address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "symbol": "USDC"},
        {"address": "So11111111111111111111111111111111111111112", "symbol": "SOL"},
        {"address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263", "symbol": "BONK"},
    ]
    
    # Initialize engine
    engine = SignalEngine(bankroll_usd=10000.0, kelly_fraction=0.25)
    
    print("="*70)
    print("ClawBot Signal Engine — Engine A + Whale Accumulation")
    print("="*70)
    print()
    
    # Scan for opportunities
    signals = engine.scan_for_opportunities(mock_tokens)
    
    # Print results
    for signal in signals:
        exec_params = engine.execute_signal(signal)
        
        print(f"🪙 {signal.token_symbol} ({signal.token_address[:16]}...)")
        print(f"   Action: {exec_params['action']}")
        print(f"   Score: {signal.combined_score:.2f} (EMA: {signal.engine_a_score:.2f}, Whale: {signal.whale_score:.2f})")
        print(f"   Phase: {signal.whale_phase}")
        print(f"   Size: ${exec_params['size_usd']:.0f} ({exec_params['size_pct']:.1f}% of bankroll)")
        print(f"   Kelly p: {signal.kelly_probability:.3f}")
        print(f"   Rationale: {signal.rationale[:100]}...")
        print()
    
    print("="*70)
    print(f"Scanned: {len(mock_tokens)} | Actionable: {len(signals)}")
    print("="*70)


if __name__ == "__main__":
    main()
