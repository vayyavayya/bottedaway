#!/usr/bin/env python3
"""
Unified Smart Money Alert System
Combines multiple onchain intelligence sources:
- Nansen (deep wallet profiling, god mode)
- Cielo Finance (real-time Solana tracking)
- Base Signal Feed (Base L2 smart money)
- Birdeye/DexScreener (price & volume)

Delivers unified alerts via Telegram.
"""

import json
import os
import sys
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

# Import local modules
sys.path.insert(0, '/Users/pterion2910/.openclaw/workspace/scripts')

class UnifiedSmartMoneyMonitor:
    """
    Unified smart money monitoring across multiple chains and sources.
    """
    
    def __init__(self):
        self.workspace = "/Users/pterion2910/.openclaw/workspace"
        self.config_path = f"{self.workspace}/config/smart_money_config.json"
        self.state_path = f"{self.workspace}/config/smart_money_state.json"
        self.alerts_path = f"{self.workspace}/config/smart_money_alerts.txt"
        
        # API Keys
        self.nansen_key = os.getenv("NANSEN_API_KEY", "")
        self.cielo_key = os.getenv("CIELO_API_KEY", "")
        self.base_signal_key = os.getenv("BASE_SIGNAL_API_KEY", "")
        
        # Load config
        self.config = self._load_config()
        self.state = self._load_state()
    
    def _load_config(self) -> Dict:
        """Load monitoring configuration."""
        default_config = {
            "watched_tokens": [],  # From watchlist
            "whale_wallets": [],   # High-value wallets to track
            "alert_thresholds": {
                "min_transaction_usd": 10000,
                "convergence_min_whales": 3,
                "divergence_threshold": 0.05,  # 5% price move opposite to whales
                "exchange_flow_threshold": 500000  # $500K inflow/outflow
            },
            "sources": {
                "nansen": True,
                "cielo": True,
                "base_signal": True,
                "birdeye": True
            },
            "alert_channels": ["telegram"]
        }
        
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    return {**default_config, **json.load(f)}
        except:
            pass
        
        return default_config
    
    def _load_state(self) -> Dict:
        """Load previous monitoring state."""
        try:
            if os.path.exists(self.state_path):
                with open(self.state_path, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {"last_check": None, "alerts_sent": []}
    
    def _save_state(self):
        """Save current state."""
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def _load_watchlist(self) -> List[Dict]:
        """Load watchlist tokens."""
        watchlist_path = f"{self.workspace}/config/memecoin_watchlist.json"
        try:
            with open(watchlist_path, 'r') as f:
                return json.load(f)
        except:
            return []
    
    # === SOURCE: NANSEN ===
    
    def check_nansen_signals(self, token: str) -> Dict:
        """Check Nansen smart money signals for token."""
        if not self.config["sources"]["nansen"] or not self.nansen_key:
            return {"enabled": False}
        
        try:
            # This would call nansen_enhanced.py
            # Simulated for now
            return {
                "source": "nansen",
                "convergence": False,  # Multiple whales buying
                "divergence": False,   # Whales selling while price up
                "exchange_flows": {"in": 0, "out": 0},
                "smart_holder_count": 0
            }
        except Exception as e:
            return {"source": "nansen", "error": str(e)}
    
    # === SOURCE: CIELO FINANCE ===
    
    def check_cielo_signals(self, token: str, chain: str = "solana") -> Dict:
        """Check Cielo Finance signals for token."""
        if not self.config["sources"]["cielo"] or not self.cielo_key:
            return {"enabled": False}
        
        try:
            # This would call cielo_finance.py
            # Simulated for now
            return {
                "source": "cielo",
                "whale_transactions_24h": [],
                "convergence_detected": False,
                "new_whale_holders": 0
            }
        except Exception as e:
            return {"source": "cielo", "error": str(e)}
    
    # === SOURCE: BASE SIGNAL FEED ===
    
    def check_base_signals(self, token: str) -> Dict:
        """Check Base Signal Feed for Base L2 tokens."""
        if not self.config["sources"]["base_signal"] or not self.base_signal_key:
            return {"enabled": False}
        
        try:
            # Call Base Signal Feed API
            url = "https://signals.ulol.li/signals"
            headers = {"Authorization": f"Bearer {self.base_signal_key}"}
            resp = requests.get(url, headers=headers, timeout=30)
            
            if resp.status_code == 200:
                data = resp.json()
                # Filter for our token
                token_signals = [s for s in data.get("signals", []) 
                               if s.get("token", "").lower() == token.lower()]
                return {
                    "source": "base_signal",
                    "signals": token_signals,
                    "count": len(token_signals)
                }
            else:
                return {"source": "base_signal", "error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"source": "base_signal", "error": str(e)}
    
    # === SOURCE: BIRDEYE/DEXSCREENER ===
    
    def check_price_volume(self, token: str, chain: str = "solana") -> Dict:
        """Check price and volume data."""
        if not self.config["sources"]["birdeye"]:
            return {"enabled": False}
        
        try:
            url = f"https://api.dexscreener.com/tokens/v1/{chain}/{token}"
            resp = requests.get(url, timeout=30)
            
            if resp.status_code == 200:
                data = resp.json()
                if data and len(data) > 0:
                    pair = data[0]
                    return {
                        "source": "dexscreener",
                        "price": float(pair.get("priceUsd", 0)),
                        "price_change_24h": pair.get("priceChange", {}).get("h24", 0),
                        "volume_24h": pair.get("volume", {}).get("h24", 0),
                        "market_cap": pair.get("marketCap", 0),
                        "buy_sell_ratio": self._calculate_buy_sell_ratio(pair.get("txns", {}))
                    }
            return {"source": "dexscreener", "error": "No data"}
        except Exception as e:
            return {"source": "dexscreener", "error": str(e)}
    
    def _calculate_buy_sell_ratio(self, txns: Dict) -> float:
        """Calculate buy/sell ratio from transactions."""
        h24 = txns.get("h24", {})
        buys = h24.get("buys", 0)
        sells = h24.get("sells", 0)
        if sells == 0:
            return 1.0
        return buys / sells
    
    # === ALERT GENERATION ===
    
    def generate_alerts(self, token: Dict, signals: Dict) -> List[Dict]:
        """
        Generate unified alerts from multiple sources.
        
        Alert Types:
        1. CONVERGENCE: Multiple whales buying same token
        2. DIVERGENCE: Whales selling while price rises
        3. EXCHANGE FLOW: Large inflow (bearish) or outflow (bullish)
        4. VOLUME ANOMALY: Unusual volume spike
        5. PRICE BREAKOUT: Significant price move with whale confirmation
        """
        alerts = []
        symbol = token.get("symbol", "Unknown")
        
        # Check for convergence (multiple sources confirming)
        convergence_signals = []
        if signals.get("nansen", {}).get("convergence"):
            convergence_signals.append("nansen")
        if signals.get("cielo", {}).get("convergence_detected"):
            convergence_signals.append("cielo")
        if signals.get("base_signal", {}).get("count", 0) > 0:
            convergence_signals.append("base_signal")
        
        if len(convergence_signals) >= 2:  # 2+ sources confirming
            alerts.append({
                "type": "CONVERGENCE",
                "priority": "HIGH",
                "symbol": symbol,
                "message": f"🐋 **WHALE CONVERGENCE DETECTED**\n\n${symbol} is being accumulated by multiple smart money wallets across {', '.join(convergence_signals)}.",
                "sources": convergence_signals
            })
        
        # Check for divergence (bearish)
        if signals.get("nansen", {}).get("divergence"):
            price_data = signals.get("price", {})
            if price_data.get("price_change_24h", 0) > 5:  # Price up 5%+
                alerts.append({
                    "type": "DIVERGENCE",
                    "priority": "MEDIUM",
                    "symbol": symbol,
                    "message": f"⚠️ **SMART MONEY DIVERGENCE**\n\n${symbol}: Whales are selling while price rises (+{price_data.get('price_change_24h', 0):.1f}%). Potential distribution.",
                    "sources": ["nansen"]
                })
        
        # Check volume anomaly
        price_data = signals.get("price", {})
        volume_24h = price_data.get("volume_24h", 0)
        if volume_24h > 500000:  # $500K+ volume
            buy_ratio = price_data.get("buy_sell_ratio", 1.0)
            if buy_ratio > 1.5:  # 50% more buys than sells
                alerts.append({
                    "type": "VOLUME_SPIKE",
                    "priority": "MEDIUM",
                    "symbol": symbol,
                    "message": f"📊 **VOLUME SPIKE + BUY PRESSURE**\n\n${symbol}: ${volume_24h/1000:.0f}K volume with {buy_ratio:.1f}x buy/sell ratio. Strong accumulation signal.",
                    "sources": ["dexscreener"]
                })
        
        return alerts
    
    # === MAIN MONITORING LOOP ===
    
    def run_monitoring_cycle(self) -> List[Dict]:
        """
        Run one full monitoring cycle.
        Check all tokens, generate alerts.
        """
        print("=" * 70)
        print("🔍 UNIFIED SMART MONEY MONITOR")
        print(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        print("=" * 70)
        
        watchlist = self._load_watchlist()
        all_alerts = []
        
        print(f"\nMonitoring {len(watchlist)} tokens...\n")
        
        for token in watchlist:
            symbol = token.get("symbol", "Unknown")
            address = token.get("address")
            chain = token.get("chain", "solana")
            
            print(f"📈 ${symbol} ({address[:8]}...)")
            
            # Gather signals from all sources
            signals = {
                "nansen": self.check_nansen_signals(address),
                "cielo": self.check_cielo_signals(address, chain),
                "base_signal": self.check_base_signals(address) if chain == "base" else {"enabled": False, "chain_mismatch": True},
                "price": self.check_price_volume(address, chain)
            }
            
            # Generate alerts
            alerts = self.generate_alerts(token, signals)
            all_alerts.extend(alerts)
            
            if alerts:
                for alert in alerts:
                    print(f"   🚨 {alert['type']} ({alert['priority']})")
            else:
                print(f"   ✅ No signals")
        
        # Save state
        self.state["last_check"] = datetime.now(timezone.utc).isoformat()
        self.state["alerts_sent"].extend([a["type"] for a in all_alerts])
        self._save_state()
        
        print(f"\n{'=' * 70}")
        print(f"Cycle complete. Alerts generated: {len(all_alerts)}")
        
        return all_alerts
    
    def send_telegram_alerts(self, alerts: List[Dict]):
        """Send alerts to Telegram."""
        if not alerts:
            return
        
        # Write to alert file
        messages = []
        for alert in alerts:
            messages.append(alert["message"])
        
        full_message = "\n\n" + "="*40 + "\n\n".join(messages)
        
        with open(self.alerts_path, 'w') as f:
            f.write(full_message)
        
        print(f"\n📤 Telegram alerts written to: {self.alerts_path}")

def main():
    """Main entry point."""
    monitor = UnifiedSmartMoneyMonitor()
    alerts = monitor.run_monitoring_cycle()
    
    if alerts:
        monitor.send_telegram_alerts(alerts)
        print(f"\n🚨 {len(alerts)} alerts ready for Telegram!")
        sys.exit(42)  # Signal alerts sent
    else:
        print("\n✅ No alerts this cycle.")
        sys.exit(0)

if __name__ == "__main__":
    main()
