#!/usr/bin/env python3
"""
Enhanced Nansen CLI Integration Module
Additional endpoints for comprehensive onchain analytics
"""

import os
import json
import subprocess
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta

class NansenEnhanced:
    """Enhanced Nansen CLI wrapper with additional endpoints."""
    
    def __init__(self):
        self.api_key = os.getenv("NANSEN_API_KEY", "")
        self.base_cmd = "nansen"
    
    def _run(self, cmd: str) -> Dict:
        """Execute nansen command and parse output."""
        try:
            result = subprocess.run(
                cmd.split(),
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                try:
                    return json.loads(result.stdout)
                except:
                    return {"output": result.stdout}
            else:
                return {"error": result.stderr}
        except Exception as e:
            return {"error": str(e)}
    
    # === WALLET PROFILING ===
    
    def wallet_god_mode(self, address: str) -> Dict:
        """
        Comprehensive wallet analysis (Nansen God Mode).
        Includes: PnL, token performance, trading history, labels.
        """
        return self._run(f"{self.base_cmd} wallet god-mode {address} --json")
    
    def wallet_pnl(self, address: str, days: int = 30) -> Dict:
        """Wallet PnL analysis over time period."""
        return self._run(f"{self.base_cmd} wallet pnl {address} --days {days} --json")
    
    def wallet_token_performance(self, address: str) -> Dict:
        """Token-by-token performance for wallet."""
        return self._run(f"{self.base_cmd} wallet tokens {address} --performance --json")
    
    def wallet_trading_summary(self, address: str, days: int = 7) -> Dict:
        """Trading activity summary."""
        return self._run(f"{self.base_cmd} wallet trading {address} --days {days} --json")
    
    def wallet_counterparties(self, address: str) -> Dict:
        """Most traded counterparties."""
        return self._run(f"{self.base_cmd} wallet counterparties {address} --json")
    
    # === SMART MONEY INTELLIGENCE ===
    
    def smart_money_leaderboard(self, timeframe: str = "7d") -> Dict:
        """Top performing smart money wallets."""
        return self._run(f"{self.base_cmd} smart-money leaderboard --timeframe {timeframe} --json")
    
    def smart_money_convergence(self, token: str) -> Dict:
        """
        Detect when multiple smart money wallets buy same token.
        Strong bullish signal.
        """
        return self._run(f"{self.base_cmd} smart-money convergence {token} --json")
    
    def smart_money_divergence(self, token: str) -> Dict:
        """
        Detect when smart money is selling while price rises.
        Bearish divergence signal.
        """
        return self._run(f"{self.base_cmd} smart-money divergence {token} --json")
    
    def smart_money_correlation(self, address: str) -> Dict:
        """Find wallets with similar trading patterns (likely same entity)."""
        return self._run(f"{self.base_cmd} smart-money correlate {address} --json")
    
    # === TOKEN INTELLIGENCE ===
    
    def token_god_mode(self, address: str) -> Dict:
        """Comprehensive token analysis."""
        return self._run(f"{self.base_cmd} token god-mode {address} --json")
    
    def token_smart_holders(self, address: str) -> Dict:
        """Smart money holders with entry prices."""
        return self._run(f"{self.base_cmd} token smart-holders {address} --json")
    
    def token_exchange_flows(self, address: str, days: int = 7) -> Dict:
        """Exchange inflows/outflows (predicts volatility)."""
        return self._run(f"{self.base_cmd} token exchanges {address} --days {days} --json")
    
    def token_distribution(self, address: str) -> Dict:
        """Holder concentration analysis."""
        return self._run(f"{self.base_cmd} token distribution {address} --json")
    
    def token_staking(self, address: str) -> Dict:
        """Staking/unstaking flows."""
        return self._run(f"{self.base_cmd} token staking {address} --json")
    
    # === MARKET INTELLIGENCE ===
    
    def market_sectors(self) -> Dict:
        """Sector performance (DeFi, NFT, Gaming, etc.)."""
        return self._run(f"{self.base_cmd} market sectors --json")
    
    def market_nft_signals(self) -> Dict:
        """NFT market smart money signals."""
        return self._run(f"{self.base_cmd} market nft-signals --json")
    
    def market_gas_analysis(self) -> Dict:
        """Gas usage patterns (detects unusual activity)."""
        return self._run(f"{self.base_cmd} market gas --json")
    
    # === ALERTS & MONITORING ===
    
    def create_smart_money_alert(self, token: str, threshold_usd: int = 10000) -> Dict:
        """Alert when smart money moves >$X into token."""
        return self._run(
            f"{self.base_cmd} alert create --token {token} "
            f"--threshold {threshold_usd} --type smart-money"
        )
    
    def create_wallet_cluster_alert(self, address: str) -> Dict:
        """Alert when related wallets (cluster) show activity."""
        return self._run(
            f"{self.base_cmd} alert create --wallet {address} "
            f"--type cluster --include-related"
        )
    
    def create_convergence_alert(self, min_wallets: int = 3) -> Dict:
        """Alert when multiple smart money wallets converge on same token."""
        return self._run(
            f"{self.base_cmd} alert create --type convergence "
            f"--min-wallets {min_wallets}"
        )

# === NEW CLI COMMANDS ===

if __name__ == "__main__":
    import sys
    
    nansen = NansenEnhanced()
    
    if len(sys.argv) < 2:
        print("Usage: python3 nansen_enhanced.py <command> [args]")
        print("\nCommands:")
        print("  wallet-god-mode <address>        - Full wallet analysis")
        print("  wallet-pnl <address> [days]      - PnL over time")
        print("  wallet-tokens <address>          - Token performance")
        print("  wallet-trading <address> [days]  - Trading summary")
        print("  sm-leaderboard [timeframe]       - Top smart money")
        print("  sm-convergence <token>           - Multiple whales buying")
        print("  sm-divergence <token>            - Smart money selling")
        print("  sm-correlate <address>           - Find related wallets")
        print("  token-god-mode <address>         - Full token analysis")
        print("  token-smart-holders <address>    - Smart money positions")
        print("  token-exchanges <address> [days] - Exchange flows")
        print("  market-sectors                   - Sector performance")
        print("  market-nft                       - NFT signals")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "wallet-god-mode" and len(sys.argv) > 2:
        print(json.dumps(nansen.wallet_god_mode(sys.argv[2]), indent=2))
    elif cmd == "wallet-pnl" and len(sys.argv) > 2:
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 30
        print(json.dumps(nansen.wallet_pnl(sys.argv[2], days), indent=2))
    elif cmd == "wallet-tokens" and len(sys.argv) > 2:
        print(json.dumps(nansen.wallet_token_performance(sys.argv[2]), indent=2))
    elif cmd == "wallet-trading" and len(sys.argv) > 2:
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 7
        print(json.dumps(nansen.wallet_trading_summary(sys.argv[2], days), indent=2))
    elif cmd == "sm-leaderboard":
        timeframe = sys.argv[2] if len(sys.argv) > 2 else "7d"
        print(json.dumps(nansen.smart_money_leaderboard(timeframe), indent=2))
    elif cmd == "sm-convergence" and len(sys.argv) > 2:
        print(json.dumps(nansen.smart_money_convergence(sys.argv[2]), indent=2))
    elif cmd == "sm-divergence" and len(sys.argv) > 2:
        print(json.dumps(nansen.smart_money_divergence(sys.argv[2]), indent=2))
    elif cmd == "sm-correlate" and len(sys.argv) > 2:
        print(json.dumps(nansen.smart_money_correlation(sys.argv[2]), indent=2))
    elif cmd == "token-god-mode" and len(sys.argv) > 2:
        print(json.dumps(nansen.token_god_mode(sys.argv[2]), indent=2))
    elif cmd == "token-smart-holders" and len(sys.argv) > 2:
        print(json.dumps(nansen.token_smart_holders(sys.argv[2]), indent=2))
    elif cmd == "token-exchanges" and len(sys.argv) > 2:
        days = int(sys.argv[3]) if len(sys.argv) > 3 else 7
        print(json.dumps(nansen.token_exchange_flows(sys.argv[2], days), indent=2))
    elif cmd == "market-sectors":
        print(json.dumps(nansen.market_sectors(), indent=2))
    elif cmd == "market-nft":
        print(json.dumps(nansen.market_nft_signals(), indent=2))
    else:
        print(f"Unknown command: {cmd}")
