#!/usr/bin/env python3
"""
Cielo Finance Integration Module
Real-time wallet tracking and alerts for Solana
Based on Moltbook research - used by CieloSolanaAgent
"""

import os
import json
import requests
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone

class CieloFinance:
    """
    Cielo Finance API wrapper for wallet tracking and alerts.
    Free tier available for basic tracking.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("CIELO_API_KEY", "")
        self.base_url = "https://api.cielo.finance/api/v1"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _request(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated request to Cielo API."""
        try:
            url = f"{self.base_url}/{endpoint}"
            resp = requests.get(url, headers=self.headers, params=params, timeout=30)
            
            if resp.status_code == 200:
                return resp.json()
            else:
                return {
                    "error": f"HTTP {resp.status_code}",
                    "message": resp.text
                }
        except Exception as e:
            return {"error": str(e)}
    
    # === WALLET TRACKING ===
    
    def track_wallet(self, address: str, label: Optional[str] = None) -> Dict:
        """
        Add wallet to tracking list.
        Cielo will monitor for transactions >100 SOL.
        """
        endpoint = "wallets/track"
        payload = {
            "address": address,
            "label": label or f"Wallet_{address[:8]}"
        }
        
        try:
            url = f"{self.base_url}/{endpoint}"
            resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
            return resp.json() if resp.status_code == 200 else {"error": resp.text}
        except Exception as e:
            return {"error": str(e)}
    
    def untrack_wallet(self, address: str) -> Dict:
        """Remove wallet from tracking."""
        endpoint = f"wallets/untrack/{address}"
        
        try:
            url = f"{self.base_url}/{endpoint}"
            resp = requests.delete(url, headers=self.headers, timeout=30)
            return resp.json() if resp.status_code == 200 else {"error": resp.text}
        except Exception as e:
            return {"error": str(e)}
    
    def list_tracked_wallets(self) -> Dict:
        """Get all tracked wallets."""
        return self._request("wallets/list")
    
    # === TRANSACTION ALERTS ===
    
    def get_recent_transactions(
        self, 
        wallets: Optional[List[str]] = None,
        min_amount_sol: float = 100.0,
        limit: int = 50
    ) -> Dict:
        """
        Get recent transactions for tracked wallets.
        
        Args:
            wallets: Specific wallets to check (None = all tracked)
            min_amount_sol: Minimum SOL amount to include
            limit: Max transactions to return
        """
        params = {
            "min_amount": min_amount_sol,
            "limit": limit
        }
        if wallets:
            params["wallets"] = ",".join(wallets)
        
        return self._request("transactions/recent", params)
    
    def get_transaction_details(self, signature: str) -> Dict:
        """Get detailed info about specific transaction."""
        return self._request(f"transactions/{signature}")
    
    # === WHALE INTELLIGENCE ===
    
    def get_whale_wallets(self, min_balance_sol: float = 10000.0) -> Dict:
        """
        Get list of whale wallets (top holders).
        Based on SOL balance.
        """
        return self._request("whales/list", {
            "min_balance": min_balance_sol
        })
    
    def get_whale_activity(
        self, 
        timeframe_hours: int = 24,
        min_amount_sol: float = 500.0
    ) -> Dict:
        """
        Get recent whale activity summary.
        Aggregated view of large transactions.
        """
        return self._request("whales/activity", {
            "hours": timeframe_hours,
            "min_amount": min_amount_sol
        })
    
    def get_token_whale_holders(self, token_address: str) -> Dict:
        """Get whale holders for specific token."""
        return self._request(f"tokens/{token_address}/whales")
    
    # === TOKEN LAUNCH DETECTION ===
    
    def get_new_launches(
        self,
        min_market_cap: float = 50000.0,
        max_market_cap: float = 1000000.0,
        min_holders: int = 50,
        limit: int = 20
    ) -> Dict:
        """
        Detect new token launches on Pump.fun and Raydium.
        
        Filters:
        - Market cap range ($50K - $1M)
        - Minimum holders (50+)
        - Returns top candidates by momentum
        """
        return self._request("launches/new", {
            "min_mc": min_market_cap,
            "max_mc": max_market_cap,
            "min_holders": min_holders,
            "limit": limit
        })
    
    def get_launch_momentum_score(self, token_address: str) -> Dict:
        """
        Calculate hype/momentum score for new launch.
        Score 0-100 based on:
        - Holder growth rate
        - Volume velocity
        - Whale interest
        - Social signals
        """
        return self._request(f"launches/{token_address}/momentum")
    
    # === SMART MONEY SIGNALS ===
    
    def get_smart_money_signals(self, timeframe_hours: int = 24) -> Dict:
        """
        Get smart money buy/sell signals.
        
        Returns:
        - Accumulation signals (multiple whales buying)
        - Distribution signals (whales selling)
        - New position alerts
        """
        return self._request("signals/smart-money", {
            "hours": timeframe_hours
        })
    
    def get_convergence_alerts(self, min_whales: int = 3) -> Dict:
        """
        Detect when multiple whales buy same token.
        Strong bullish signal.
        """
        return self._request("signals/convergence", {
            "min_whales": min_whales
        })
    
    def get_divergence_alerts(self) -> Dict:
        """
        Detect when whales sell while price rises.
        Bearish divergence signal.
        """
        return self._request("signals/divergence")
    
    # === ALERT CONFIGURATION ===
    
    def create_alert(
        self,
        alert_type: str,  # "transaction", "price", "whale"
        conditions: Dict,
        webhook_url: Optional[str] = None
    ) -> Dict:
        """
        Create real-time alert.
        
        Alert types:
        - transaction: Alert on tx > X SOL
        - price: Alert on price change > X%
        - whale: Alert when whale buys/sells
        """
        endpoint = "alerts/create"
        payload = {
            "type": alert_type,
            "conditions": conditions
        }
        if webhook_url:
            payload["webhook"] = webhook_url
        
        try:
            url = f"{self.base_url}/{endpoint}"
            resp = requests.post(url, headers=self.headers, json=payload, timeout=30)
            return resp.json() if resp.status_code == 200 else {"error": resp.text}
        except Exception as e:
            return {"error": str(e)}
    
    def list_alerts(self) -> Dict:
        """Get all configured alerts."""
        return self._request("alerts/list")
    
    def delete_alert(self, alert_id: str) -> Dict:
        """Remove alert by ID."""
        endpoint = f"alerts/{alert_id}"
        
        try:
            url = f"{self.base_url}/{endpoint}"
            resp = requests.delete(url, headers=self.headers, timeout=30)
            return resp.json() if resp.status_code == 200 else {"error": resp.text}
        except Exception as e:
            return {"error": str(e)}
    
    # === MORNING BRIEFING INTEGRATION ===
    
    def generate_briefing_data(self) -> Dict:
        """
        Generate data for morning briefing.
        Combines multiple signals into summary.
        """
        briefing = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "whale_activity_24h": self.get_whale_activity(24),
            "smart_money_signals": self.get_smart_money_signals(24),
            "new_launches": self.get_new_launches(),
            "convergence_alerts": self.get_convergence_alerts(3),
            "tracked_wallets_count": len(self.list_tracked_wallets().get("wallets", []))
        }
        return briefing

# === CLI INTERFACE ===

if __name__ == "__main__":
    import sys
    
    cielo = CieloFinance()
    
    if len(sys.argv) < 2:
        print("Cielo Finance Integration")
        print("\nUsage: python3 cielo_finance.py <command> [args]")
        print("\nWallet Commands:")
        print("  track <address> [label]       - Track wallet")
        print("  untrack <address>             - Stop tracking")
        print("  list                          - List tracked wallets")
        print("  transactions [min_sol]        - Recent transactions")
        print("\nWhale Commands:")
        print("  whales [min_balance]          - List whale wallets")
        print("  whale-activity [hours]        - Whale activity summary")
        print("  token-whales <token>          - Whale holders for token")
        print("\nLaunch Commands:")
        print("  new-launches                  - New token launches")
        print("  momentum <token>              - Launch momentum score")
        print("\nSignal Commands:")
        print("  smart-signals                 - Smart money signals")
        print("  convergence [min_whales]      - Whale convergence")
        print("  divergence                    - Whale divergence alerts")
        print("\nAlert Commands:")
        print("  create-alert <type>          - Create alert")
        print("  list-alerts                   - List alerts")
        print("  delete-alert <id>            - Delete alert")
        print("\nBriefing:")
        print("  briefing                      - Generate morning briefing data")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    # Wallet commands
    if cmd == "track" and len(sys.argv) > 2:
        label = sys.argv[3] if len(sys.argv) > 3 else None
        print(json.dumps(cielo.track_wallet(sys.argv[2], label), indent=2))
    elif cmd == "untrack" and len(sys.argv) > 2:
        print(json.dumps(cielo.untrack_wallet(sys.argv[2]), indent=2))
    elif cmd == "list":
        print(json.dumps(cielo.list_tracked_wallets(), indent=2))
    elif cmd == "transactions":
        min_sol = float(sys.argv[2]) if len(sys.argv) > 2 else 100.0
        print(json.dumps(cielo.get_recent_transactions(min_amount_sol=min_sol), indent=2))
    
    # Whale commands
    elif cmd == "whales":
        min_bal = float(sys.argv[2]) if len(sys.argv) > 2 else 10000.0
        print(json.dumps(cielo.get_whale_wallets(min_bal), indent=2))
    elif cmd == "whale-activity":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        print(json.dumps(cielo.get_whale_activity(hours), indent=2))
    elif cmd == "token-whales" and len(sys.argv) > 2:
        print(json.dumps(cielo.get_token_whale_holders(sys.argv[2]), indent=2))
    
    # Launch commands
    elif cmd == "new-launches":
        print(json.dumps(cielo.get_new_launches(), indent=2))
    elif cmd == "momentum" and len(sys.argv) > 2:
        print(json.dumps(cielo.get_launch_momentum_score(sys.argv[2]), indent=2))
    
    # Signal commands
    elif cmd == "smart-signals":
        print(json.dumps(cielo.get_smart_money_signals(), indent=2))
    elif cmd == "convergence":
        min_whales = int(sys.argv[2]) if len(sys.argv) > 2 else 3
        print(json.dumps(cielo.get_convergence_alerts(min_whales), indent=2))
    elif cmd == "divergence":
        print(json.dumps(cielo.get_divergence_alerts(), indent=2))
    
    # Alert commands
    elif cmd == "list-alerts":
        print(json.dumps(cielo.list_alerts(), indent=2))
    elif cmd == "delete-alert" and len(sys.argv) > 2:
        print(json.dumps(cielo.delete_alert(sys.argv[2]), indent=2))
    
    # Briefing
    elif cmd == "briefing":
        print(json.dumps(cielo.generate_briefing_data(), indent=2))
    
    else:
        print(f"Unknown command: {cmd}")
