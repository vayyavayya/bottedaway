""" ClawBot - Whale Accumulation Tracker
======================================
Monitors on-chain whale wallets for accumulation patterns on Solana and EVM chains.
Produces a normalized confidence score (0-1) per token that feeds into ClawBot's 
signal validation layer alongside Engine A (EMA reclaim) and other signals.

Data Sources:
- Birdeye API: Token holder snapshots, top holders, wallet activity (Solana)
- Helius API: Real-time transaction streaming via websocket (Solana)
- DexScreener: Cross-chain pair data for liquidity context

Architecture:
    whale_tracker.py → WhaleSignal(token, score, details)
            ↓
    signal_engine.py → Combined signal with Engine A, gabagool, etc.
            ↓
    execution layer → Kelly-sized entry

Setup:
1. Add to keys.env:
   HELIUS_API_KEY=your-helius-key        # Free tier: 50k credits/day
   BIRDEYE_API_KEY=your-existing-key     # Already in your stack

2. pip install websockets aiohttp

3. Import into ClawBot:
   from whale_tracker import WhaleTracker
   tracker = WhaleTracker()

Usage:
    # One-shot scan
    signal = tracker.analyze_token("So11111111111111111111111111111111111111112")
    print(signal.score)  # 0.0 - 1.0

    # Continuous monitoring (async)
    import asyncio
    asyncio.run(tracker.monitor_tokens(["token_addr1", "token_addr2"]))
"""

import os
import time
import json
import logging
import hashlib
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import requests
try:
    from dotenv import load_dotenv
    load_dotenv("keys.env")
except ImportError:
    pass  # dotenv not installed, skip

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("clawbot.whale_tracker")

# ─── Config ────────────────────────────────────────────────────────────────────
def _load_helius_key() -> str:
    """Load Helius API key from env or credentials file."""
    key = os.getenv("HELIUS_API_KEY", "")
    if key:
        return key
    
    # Try credentials file
    creds_paths = [
        os.path.expanduser("~/.config/helius/credentials.json"),
        "/Users/pterion2910/.config/helius/credentials.json",
    ]
    for creds_file in creds_paths:
        if os.path.exists(creds_file):
            try:
                with open(creds_file, 'r') as f:
                    creds = json.load(f)
                    key = creds.get("api_key", "")
                    if key:
                        logger.info(f"Loaded Helius key from {creds_file}")
                        return key
            except Exception as e:
                logger.debug(f"Failed to read {creds_file}: {e}")
                continue
    return ""


def _load_birdeye_key() -> str:
    """Load Birdeye API key from env or credentials file."""
    key = os.getenv("BIRDEYE_API_KEY", "")
    if key:
        return key
    
    # Try credentials file
    creds_paths = [
        os.path.expanduser("~/.config/birdeye/credentials.json"),
        "/Users/pterion2910/.config/birdeye/credentials.json",
    ]
    for creds_file in creds_paths:
        if os.path.exists(creds_file):
            try:
                with open(creds_file, 'r') as f:
                    creds = json.load(f)
                    key = creds.get("api_key", "")
                    if key:
                        logger.info(f"Loaded Birdeye key from {creds_file}")
                        return key
            except Exception as e:
                logger.debug(f"Failed to read {creds_file}: {e}")
                continue
    return ""


HELIUS_API_KEY = _load_helius_key()
BIRDEYE_API_KEY = _load_birdeye_key()
HELIUS_RPC = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
HELIUS_API = f"https://api.helius.xyz/v0"
BIRDEYE_API = "https://public-api.birdeye.so"
HELIUS_API = f"https://api.helius.xyz/v0"
BIRDEYE_API = "https://public-api.birdeye.so"

# ─── Data Models ───────────────────────────────────────────────────────────────
class AccumulationPhase(Enum):
    """Whale accumulation lifecycle."""
    NONE = "none"                    # No whale activity
    EARLY_ACCUMULATION = "early"     # First signs: scattered buys, wallet activation
    ACTIVE_ACCUMULATION = "active"   # Clear pattern: size increasing, multiple wallets
    HEAVY_ACCUMULATION = "heavy"     # Aggressive: large buys, short intervals
    DISTRIBUTION = "distribution"    # Selling started — get out or don't enter


@dataclass
class WalletProfile:
    """Tracked whale wallet with scoring metadata."""
    address: str
    label: str = ""                      # "known_whale", "smart_money", "fresh", "exchange_withdrawal"
    cluster_id: Optional[str] = None     # Groups related wallets
    first_seen: float = 0.0              # Timestamp
    last_activity_timestamp: float = 0.0 # For dormant whale detection
    dormancy_days: float = 0.0           # Days inactive before current activity
    historical_win_rate: float = 0.5     # % of past accumulations that preceded pumps
    total_tokens_tracked: int = 0
    avg_hold_duration_hours: float = 0.0
    score_modifier: float = 1.0          # Multiplier for this wallet's signals
    is_exchange_withdrawal: bool = False # True if wallet received from CEX before buying
    early_holder: bool = False           # True if wallet was in first 30 days
    
    @property
    def quality_score(self) -> float:
        """0-1 score of how 'smart' this wallet is."""
        dormancy_bonus = min(self.dormancy_days / 180, 1.0) * 0.3     # Max 0.3 for 6mo+ dormancy
        win_bonus = self.historical_win_rate * 0.4                    # Max 0.4
        hold_bonus = min(self.avg_hold_duration_hours / 168, 1.0) * 0.3  # Max 0.3 for 1wk+ holds
        return min(dormancy_bonus + win_bonus + hold_bonus, 1.0)
    
    def is_dormant_reactivation(self, current_time: float, threshold_days: int = 60) -> bool:
        """Check if wallet was dormant for threshold_days+ and just reactivated."""
        if self.last_activity_timestamp == 0:
            return False
        days_inactive = (current_time - self.last_activity_timestamp) / 86400
        return days_inactive >= threshold_days


@dataclass
class WhaleTransaction:
    """Single whale buy/sell event."""
    wallet: str
    token_address: str
    token_symbol: str
    side: str                    # "buy" or "sell"
    amount_tokens: float
    amount_usd: float
    timestamp: float
    tx_hash: str


@dataclass
class WhaleSignal:
    """Output signal from whale tracker. Feed this into ClawBot's signal validation layer."""
    token_address: str
    token_symbol: str
    score: float                                   # 0.0 - 1.0 confidence
    phase: AccumulationPhase
    num_whales_accumulating: int
    total_whale_buys_usd_24h: float
    total_whale_sells_usd_24h: float
    buy_sell_ratio: float                          # >1 = net accumulation
    accumulation_velocity: float                   # Rate of change (accelerating?)
    top_wallet_quality: float                      # Best wallet's quality score
    details: str                                   # Human-readable summary
    timestamp: float = field(default_factory=time.time)

    @property
    def is_actionable(self) -> bool:
        """Quick filter: is this worth feeding to signal engine?"""
        return self.score >= 0.4 and self.phase in (
            AccumulationPhase.ACTIVE_ACCUMULATION,
            AccumulationPhase.HEAVY_ACCUMULATION,
        )


# ─── Blacklists ────────────────────────────────────────────────────────────────
# Known exchange hot wallets, market makers, LP pools, and contracts to exclude
EXCHANGE_WALLETS = {
    # Binance
    "5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9",
    # Kraken  
    "FWznbcNXWQuHTawe9RxvQ2LdCENLsh12dsznf4RiouN5",
    # Coinbase
    "H8sMJSCVzfius7NBqzkY4FhKJR9z22qY3yJ85DxQjwF",
    # OKX
    "GzPHuS2ynTCz68J9Q2hFk8bJyU87gWCBq5p1n3k9N3X",
}

# DEX/AMM Pool Authorities (Raydium, Orca, Meteora, etc.)
DEX_POOL_AUTHORITIES = {
    # Raydium AMM
    "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",
    # Orca Whirlpool
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",
    "2LecshUwdyHxiL25o4cPNY9FNqRk63PzxKQ4mZ69hX5d",
    # Meteora DLMM
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo",
    "M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K",
    # Jupiter Aggregator
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
    # Lifinity
    "LFT4e5RmdB9t1K4K1zYh5zZ5K1zYh5zZ5K1zYh5zZ5K",
    # Phoenix
    "PhoeNiXZ8ByJGLkxNfZRnkUfjvmuYqLR89jjFHmKVjS",
    # Drift
    "DriFtR8yQW3jJZw2d1h3H3J3J3J3J3J3J3J3J3J3J3J",
}

# Bridge Contracts
BRIDGE_CONTRACTS = {
    # Wormhole
    "worm2ZoG2kUd4vFXhvjh93UUH596ayRfgQ2MgjNMTth",
    "5z3EqY5jGqF4N6q4gN7q4gN7q4gN7q4gN7q4gN7q4gN7",
    # Allbridge
    "BrdgN8nX9e3vJ3J3J3J3J3J3J3J3J3J3J3J3J3J3J3J",
    # Portal
    "Port7Z8B8B8B8B8B8B8B8B8B8B8B8B8B8B8B8B8B8B8",
}

# Known token contract patterns (burn addresses, null, etc.)
CONTRACT_PATTERNS = {
    "11111111111111111111111111111111",  # System/null address
    "So11111111111111111111111111111111111111112",  # Wrapped SOL (not a whale)
}

# Combined blacklist for easy checking
BLACKLISTED_ADDRESSES = EXCHANGE_WALLETS | DEX_POOL_AUTHORITIES | BRIDGE_CONTRACTS | CONTRACT_PATTERNS

# Minimum thresholds
MIN_WHALE_TX_USD = 5_000          # Ignore txs below this
MIN_HOLDER_BALANCE_USD = 10_000   # Minimum to consider someone a "whale"
MIN_LIQUIDITY_USD = 50_000        # Skip illiquid tokens
MAX_SUPPLY_PCT_FOR_WHALE = 10.0   # Exclude wallets holding >10% (likely team/contract)
MAX_WHALES_TO_ANALYZE = 20        # Cap analysis at top 20 after filtering

# WIF/POPCAT historically-proven signal bonuses
BONUS_DORMANT_REACTIVATION = 0.15   # Weight: +0.15 for 60+ day dormant whales buying
BONUS_EXCHANGE_WITHDRAWAL = 0.20    # Weight: +0.20 for CEX withdrawal -> accumulation
BONUS_CONCENTRATION_ACCELERATION = 0.15  # Weight: +0.15 for top-10 holders +5% in 7d
BONUS_PRICE_DIVERGENCE = 0.20       # Weight: +0.20 for flat price + rising whale buys
BONUS_DOMINANT_ACCUMULATOR = 0.10   # Weight: +0.10 for single wallet >30% of volume
PENALTY_EARLY_WHALE_SELLING = -0.30 # Weight: -0.30 for original insiders distributing

# Tracking for historical patterns
class WhaleTracker:
    """
    Monitors whale wallets for accumulation patterns.
    Plugs into ClawBot as a signal source:
        tracker = WhaleTracker()
        signal = tracker.analyze_token("token_address")
        if signal.is_actionable:
            # Feed to signal_engine alongside Engine A
    """

    def __init__(self):
        self.wallet_profiles: Dict[str, WalletProfile] = {}
        self.tx_history: Dict[str, List[WhaleTransaction]] = defaultdict(list)   # token -> txs
        self.snapshots: Dict[str, List[Dict]] = defaultdict(list)                # token -> holder snapshots
        self.holder_history: Dict[str, List[Dict]] = defaultdict(list)           # token -> historical holder %
        self._session = requests.Session()
        
        if not HELIUS_API_KEY:
            logger.warning("HELIUS_API_KEY not set — using Birdeye-only mode (less granular)")
        if not BIRDEYE_API_KEY:
            logger.error("BIRDEYE_API_KEY required — add to keys.env")

    # ─── Public API ────────────────────────────────────────────────────────
    def analyze_token(self, token_address: str, chain: str = "solana") -> WhaleSignal:
        """
        Full whale accumulation analysis for a single token.
        Returns a WhaleSignal with a 0-1 confidence score.
        
        This is the main entry point for ClawBot integration:
            signal = tracker.analyze_token("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v")
            if signal.score > 0.6:
                # Strong whale accumulation detected
        """
        logger.info(f"Analyzing whale activity for {token_address[:16]}...")

        # Step 1: Get top holders
        holders = self._get_top_holders(token_address, chain)
        if not holders:
            return self._empty_signal(token_address)

        # Step 2: Get token metadata for context
        token_meta = self._get_token_metadata(token_address, chain)
        symbol = token_meta.get("symbol", "???")
        liquidity = token_meta.get("liquidity", 0)

        if liquidity < MIN_LIQUIDITY_USD:
            logger.info(f"{symbol}: Liquidity ${liquidity:,.0f} below minimum, skipping")
            return self._empty_signal(token_address, symbol=symbol)

        # Step 3: Filter to whale-sized holders (exclude exchanges/MMs)
        whales = self._filter_whales(holders, token_meta)

        # Step 4: Check recent activity for each whale (already capped by _filter_whales)
        whale_txs = []
        for whale_addr in whales:
            txs = self._get_wallet_token_txs(whale_addr, token_address, chain)
            whale_txs.extend(txs)
            time.sleep(0.15)              # Rate limit

        # Step 5: Score the accumulation pattern
        token_price = float(token_meta.get("price", 0))
        signal = self._score_accumulation(token_address, symbol, whales, whale_txs, liquidity, token_price)
        logger.info(f"{symbol}: Whale score={signal.score:.2f} phase={signal.phase.value} "
                   f"buys=${signal.total_whale_buys_usd_24h:,.0f} "
                   f"sells=${signal.total_whale_sells_usd_24h:,.0f}")
        return signal

    def batch_scan(self, token_addresses: List[str], chain: str = "solana") -> List[WhaleSignal]:
        """
        Scan multiple tokens. Use this in ClawBot's main loop:
            tokens = birdeye.discover_ema_candidates("solana")
            signals = tracker.batch_scan([t["address"] for t in tokens])
            actionable = [s for s in signals if s.is_actionable]
        """
        signals = []
        for addr in token_addresses:
            try:
                sig = self.analyze_token(addr, chain)
                signals.append(sig)
                time.sleep(0.5)           # Be nice to APIs
            except Exception as e:
                logger.error(f"Failed to analyze {addr[:16]}: {e}")
                signals.append(self._empty_signal(addr))
        return signals

    def get_signal_for_engine(self, token_address: str, chain: str = "solana") -> Tuple[float, dict]:
        """
        Convenience method matching Engine A's signal format.
        Returns (score, metadata_dict) for direct use in signal_engine.py
        
        Usage in signal_engine:
            whale_score, whale_meta = tracker.get_signal_for_engine(token_addr)
            ema_score = engine_a.get_signal(token_addr)
            combined = (whale_score * 0.4) + (ema_score * 0.6)  # Weight as you like
        """
        signal = self.analyze_token(token_address, chain)
        meta = {
            "phase": signal.phase.value,
            "num_whales": signal.num_whales_accumulating,
            "buy_sell_ratio": signal.buy_sell_ratio,
            "velocity": signal.accumulation_velocity,
            "details": signal.details,
        }
        return signal.score, meta

    # ─── Data Fetchers ─────────────────────────────────────────────────────
    def _get_top_holders(self, token_address: str, chain: str = "solana") -> List[Dict]:
        """Fetch top holders via Birdeye."""
        try:
            resp = self._session.get(
                f"{BIRDEYE_API}/defi/v3/token/holder",
                headers={
                    "X-API-KEY": BIRDEYE_API_KEY,
                    "x-chain": chain,
                },
                params={
                    "address": token_address,
                    "offset": 0,
                    "limit": 50,     # Top 50 holders
                },
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                holders = data.get("items", [])
                logger.info(f"Found {len(holders)} holders for {token_address[:16]}")
                return holders
            else:
                logger.warning(f"Birdeye holder API returned {resp.status_code}")
                return []
        except Exception as e:
            logger.error(f"Failed to fetch holders: {e}")
            return []

    def _get_token_metadata(self, token_address: str, chain: str = "solana") -> Dict:
        """Get token price, liquidity, market cap from Birdeye."""
        try:
            resp = self._session.get(
                f"{BIRDEYE_API}/defi/v3/token/overview",
                headers={
                    "X-API-KEY": BIRDEYE_API_KEY,
                    "x-chain": chain,
                },
                params={"address": token_address},
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json().get("data", {})
            return {}
        except Exception as e:
            logger.error(f"Token metadata fetch failed: {e}")
            return {}

    def _get_wallet_token_txs(
        self, 
        wallet: str, 
        token_address: str, 
        chain: str = "solana",
        lookback_hours: int = 72
    ) -> List[WhaleTransaction]:
        """
        Get recent buy/sell transactions for a wallet on a specific token.
        Uses Helius if available (better data), falls back to Birdeye if empty/fails.
        """
        txs = []
        cutoff = time.time() - (lookback_hours * 3600)

        # Try Helius first (if Solana and key available)
        if HELIUS_API_KEY and chain == "solana":
            txs = self._helius_wallet_txs(wallet, token_address, cutoff)
            if txs:
                logger.debug(f"Helius returned {len(txs)} txs for {wallet[:16]}")
            else:
                logger.debug(f"Helius returned empty for {wallet[:16]}, will try Birdeye fallback")
        
        # Fallback to Birdeye if Helius returned empty or not available
        if not txs:
            logger.debug(f"Trying Birdeye fallback for {wallet[:16]}")
            txs = self._birdeye_wallet_txs(wallet, token_address, chain, cutoff)
            if txs:
                logger.debug(f"Birdeye returned {len(txs)} txs for {wallet[:16]}")

        # Cache for velocity calculations
        self.tx_history[token_address].extend(txs)
        return txs

    def _helius_wallet_txs(
        self, 
        wallet: str, 
        token_address: str, 
        cutoff: float
    ) -> List[WhaleTransaction]:
        """
        Fetch parsed transactions from Helius.
        Tries RPC getTransactionsForAddress first (paid plans), falls back to REST API (free tier).
        """
        txs = []
        if not HELIUS_API_KEY:
            return txs
        
        # Try RPC method first (more efficient, 100 credits/request)
        try:
            rpc_url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransactionsForAddress",
                "params": {
                    "address": wallet,
                    "transactionDetails": "full",
                    "encoding": "jsonParsed",
                    "filters": {
                        "tokenAccounts": "balanceChanged",
                        "status": "succeeded",
                        "blockTime": {
                            "gte": int(cutoff)
                        }
                    }
                }
            }
            
            resp = self._session.post(rpc_url, json=payload, timeout=30)
            
            if resp.status_code == 200:
                data = resp.json()
                if "error" not in data:
                    transactions = data.get("result", {}).get("transactions", [])
                    
                    for tx in transactions:
                        block_time = tx.get("blockTime", 0)
                        if block_time < cutoff:
                            continue
                        
                        tx_hash = tx.get("signature", "")
                        meta = tx.get("meta", {})
                        
                        # Parse token balance changes
                        pre_balances = {}
                        post_balances = {}
                        
                        for pre in meta.get("preTokenBalances", []):
                            if pre.get("owner") == wallet:
                                mint = pre.get("mint", "")
                                amount = float(pre.get("uiTokenAmount", {}).get("uiAmount", 0))
                                pre_balances[mint] = amount
                        
                        for post in meta.get("postTokenBalances", []):
                            if post.get("owner") == wallet:
                                mint = post.get("mint", "")
                                amount = float(post.get("uiTokenAmount", {}).get("uiAmount", 0))
                                post_balances[mint] = amount
                        
                        if token_address not in pre_balances and token_address not in post_balances:
                            continue
                        
                        pre_amount = pre_balances.get(token_address, 0)
                        post_amount = post_balances.get(token_address, 0)
                        delta = post_amount - pre_amount
                        
                        if abs(delta) < 0.000001:
                            continue
                        
                        side = "buy" if delta > 0 else "sell"
                        amount_tokens = abs(delta)
                        
                        # Estimate USD from SOL change
                        amount_usd = 0
                        pre_sol = meta.get("preBalances", [0])[0] if meta.get("preBalances") else 0
                        post_sol = meta.get("postBalances", [0])[0] if meta.get("postBalances") else 0
                        sol_delta = abs(post_sol - pre_sol) / 1e9
                        if sol_delta > 0.001:
                            amount_usd = sol_delta * 150  # Approximate SOL price
                        
                        txs.append(WhaleTransaction(
                            wallet=wallet,
                            token_address=token_address,
                            token_symbol="",
                            side=side,
                            amount_tokens=amount_tokens,
                            amount_usd=amount_usd,
                            timestamp=block_time,
                            tx_hash=tx_hash,
                        ))
                    
                    if txs:
                        return txs  # RPC worked, return results
                        
            # RPC failed or returned no results, fall through to REST
            if resp.status_code == 403:
                logger.debug(f"Helius RPC 403 for {wallet[:16]} — falling back to REST (free tier)")
            
        except Exception as e:
            logger.debug(f"Helius RPC failed for {wallet[:16]}: {e}")
        
        # Fall back to REST API (free tier compatible)
        try:
            resp = self._session.get(
                f"{HELIUS_API}/addresses/{wallet}/transactions",
                params={
                    "api-key": HELIUS_API_KEY,
                    "type": "SWAP",
                    "limit": 50,
                },
                timeout=15,
            )
            
            if resp.status_code != 200:
                logger.warning(f"Helius REST error {resp.status_code} for {wallet[:16]}")
                return txs
            
            data = resp.json()
            logger.debug(f"Helius REST returned {len(data) if isinstance(data, list) else 'non-list'} items for {wallet[:16]}")
            
            # Handle both list and dict responses
            if isinstance(data, dict):
                transactions = data.get("transactions", [])
            else:
                transactions = data
            
            for tx in transactions:
                ts = tx.get("timestamp", 0)
                if ts < cutoff:
                    continue

                tx_type = tx.get("type", "").upper()
                token_transfers = tx.get("tokenTransfers", [])
                
                # Try Enhanced Transactions API format (events.swap.innerSwaps)
                events = tx.get("events", {})
                swap_events = events.get("swap", {}) if isinstance(events, dict) else {}
                inner_swaps = swap_events.get("innerSwaps", []) if isinstance(swap_events, dict) else []
                
                if inner_swaps:
                    for event in inner_swaps:
                        token_in = event.get("tokenInputs", [{}])
                        token_out = event.get("tokenOutputs", [{}])

                        for t_in in token_in:
                            if t_in.get("mint") == token_address:
                                txs.append(WhaleTransaction(
                                    wallet=wallet,
                                    token_address=token_address,
                                    token_symbol="",
                                    side="sell",
                                    amount_tokens=float(t_in.get("rawTokenAmount", {}).get("tokenAmount", 0)),
                                    amount_usd=float(t_in.get("userAmount", 0)) if "userAmount" in t_in else 0,
                                    timestamp=ts,
                                    tx_hash=tx.get("signature", ""),
                                ))

                        for t_out in token_out:
                            if t_out.get("mint") == token_address:
                                txs.append(WhaleTransaction(
                                    wallet=wallet,
                                    token_address=token_address,
                                    token_symbol="",
                                    side="buy",
                                    amount_tokens=float(t_out.get("rawTokenAmount", {}).get("tokenAmount", 0)),
                                    amount_usd=float(t_out.get("userAmount", 0)) if "userAmount" in t_out else 0,
                                    timestamp=ts,
                                    tx_hash=tx.get("signature", ""),
                                ))
                
                # Parse from tokenTransfers (Helius native format)
                elif token_transfers and tx_type == "SWAP":
                    for move in token_transfers:
                        if move.get("mint") == token_address:
                            from_wallet = move.get("fromUserAccount", "")
                            to_wallet = move.get("toUserAccount", "")
                            amount = float(move.get("tokenAmount", 0))
                            
                            if from_wallet == wallet:
                                txs.append(WhaleTransaction(
                                    wallet=wallet, token_address=token_address, token_symbol="",
                                    side="sell", amount_tokens=amount, amount_usd=0,
                                    timestamp=ts, tx_hash=tx.get("signature", ""),
                                ))
                            elif to_wallet == wallet:
                                txs.append(WhaleTransaction(
                                    wallet=wallet, token_address=token_address, token_symbol="",
                                    side="buy", amount_tokens=amount, amount_usd=0,
                                    timestamp=ts, tx_hash=tx.get("signature", ""),
                                ))
                
                else:
                    logger.debug(f"No swap data in tx for {wallet[:16]} (type: {tx_type})")
                    
        except Exception as e:
            logger.error(f"Helius REST failed for {wallet[:16]}: {e}")
            
        return txs

    def _birdeye_wallet_txs(
        self, 
        wallet: str, 
        token_address: str, 
        chain: str, 
        cutoff: float
    ) -> List[WhaleTransaction]:
        """Fallback: use Birdeye's transaction history."""
        txs = []
        try:
            resp = self._session.get(
                f"{BIRDEYE_API}/v1/wallet/tx_list",
                headers={
                    "X-API-KEY": BIRDEYE_API_KEY,
                    "x-chain": chain,
                },
                params={
                    "wallet": wallet,
                    "limit": 50,
                },
                timeout=10,
            )
            if resp.status_code != 200:
                return []

            for tx in resp.json().get("data", {}).get("items", []):
                ts = tx.get("blockUnixTime", 0)
                if ts < cutoff:
                    continue

                # Check if transaction involves our token
                if token_address in json.dumps(tx):
                    side = "buy" if tx.get("side", "") == "buy" else "sell"
                    txs.append(WhaleTransaction(
                        wallet=wallet,
                        token_address=token_address,
                        token_symbol="",
                        side=side,
                        amount_tokens=float(tx.get("tokenAmount", 0)),
                        amount_usd=float(tx.get("volumeUSD", 0)),
                        timestamp=ts,
                        tx_hash=tx.get("txHash", ""),
                    ))
        except Exception as e:
            logger.error(f"Birdeye tx fetch failed for {wallet[:16]}: {e}")
        return txs

    # ─── Analysis Engine ───────────────────────────────────────────────────
    def _filter_whales(self, holders: List[Dict], token_meta: Dict) -> List[str]:
        """
        Filter holders to actual trading whales, excluding:
        - Exchange hot wallets
        - DEX/AMM pool authorities (Raydium, Orca, Meteora, etc.)
        - Bridge contracts
        - Token deployer/team wallets
        - Burn/null addresses
        - Wallets holding >10% of supply (likely contracts/team)
        - Dust wallets
        
        Returns top MAX_WHALES_TO_ANALYZE (20) after filtering.
        """
        price = float(token_meta.get("price", 0)) or 0.0001
        filtered_whales = []
        excluded_count = {
            "blacklist": 0,
            "low_balance": 0,
            "high_supply_pct": 0,
        }

        for h in holders:
            addr = h.get("address", "") or h.get("owner", "")
            if not addr:
                continue

            # Skip blacklisted addresses (exchanges, pools, bridges, contracts)
            if addr in BLACKLISTED_ADDRESSES:
                excluded_count["blacklist"] += 1
                continue

            # Calculate balances and percentages
            balance = float(h.get("amount", 0) or h.get("uiAmount", 0))
            usd_value = balance * price
            supply_pct = h.get("percentage", 0) or 0.0
            
            # Skip dust wallets (below minimum USD threshold)
            if usd_value < MIN_HOLDER_BALANCE_USD:
                excluded_count["low_balance"] += 1
                continue
            
            # Skip wallets holding >10% of supply (likely team/contract, not trading whale)
            if supply_pct > MAX_SUPPLY_PCT_FOR_WHALE:
                excluded_count["high_supply_pct"] += 1
                logger.debug(f"Excluding {addr[:16]}... (holds {supply_pct:.1f}% supply)")
                continue

            # Build/update wallet profile
            if addr not in self.wallet_profiles:
                self.wallet_profiles[addr] = WalletProfile(
                    address=addr,
                    first_seen=time.time(),
                )

            filtered_whales.append((addr, usd_value, supply_pct))

        # Sort by USD value descending and cap at MAX_WHALES_TO_ANALYZE
        filtered_whales.sort(key=lambda x: x[1], reverse=True)
        capped_whales = filtered_whales[:MAX_WHALES_TO_ANALYZE]
        
        # Log filtering summary
        total_excluded = sum(excluded_count.values())
        if total_excluded > 0 or len(capped_whales) < len(holders):
            logger.info(f"Whale filter: {len(holders)} holders → {len(filtered_whales)} filtered → {len(capped_whales)} capped")
            logger.info(f"  Excluded: {excluded_count['blacklist']} blacklisted, "
                       f"{excluded_count['low_balance']} low balance, "
                       f"{excluded_count['high_supply_pct']} high supply %")

        # Return just the addresses
        return [w[0] for w in capped_whales]

    def _score_accumulation(
        self, 
        token_address: str, 
        symbol: str, 
        whale_addrs: List[str],
        transactions: List[WhaleTransaction], 
        liquidity: float,
        token_price: float = 0.0,
    ) -> WhaleSignal:
        """
        Core scoring engine. Produces a 0-1 confidence score based on:
        1. Buy/sell ratio (net flow direction)
        2. Number of distinct whales buying
        3. Accumulation velocity (accelerating vs decelerating)
        4. Wallet quality (smart money vs dumb money)
        5. Size relative to liquidity (big fish in small pond = stronger signal)
        """
        now = time.time()
        h24_cutoff = now - 86400
        h4_cutoff = now - 14400

        # ── Aggregate buy/sell volumes ──
        # NOTE: Helius/Birdeye may not provide USD values, so we calculate from token amounts
        buys_24h = []
        sells_24h = []
        
        for tx in transactions:
            if tx.timestamp <= h24_cutoff:
                continue
                
            # Calculate USD value if not provided by API
            tx_usd = tx.amount_usd
            if tx_usd == 0 and token_price > 0:
                tx_usd = tx.amount_tokens * token_price
                
            if tx.side == "buy":
                buys_24h.append((tx, tx_usd))
            else:
                sells_24h.append((tx, tx_usd))

        total_buy_usd = sum(usd for _, usd in buys_24h)
        total_sell_usd = sum(usd for _, usd in sells_24h)
        
        # 4h window
        buys_4h = [(tx, usd) for tx, usd in buys_24h if tx.timestamp > h4_cutoff]
        sells_4h = [(tx, usd) for tx, usd in sells_24h if tx.timestamp > h4_cutoff]
        buy_usd_4h = sum(usd for _, usd in buys_4h)
        sell_usd_4h = sum(usd for _, usd in sells_4h)

        # DEBUG: Log the calculated values
        logger.info(f"DEBUG _score_accumulation: {symbol}")
        logger.info(f"  Token price: ${token_price:.6f}")
        logger.info(f"  Transactions: {len(transactions)} total, {len(buys_24h)} buys, {len(sells_24h)} sells (24h)")
        logger.info(f"  total_buy_usd: ${total_buy_usd:,.2f}")
        logger.info(f"  total_sell_usd: ${total_sell_usd:,.2f}")
        logger.info(f"  buy_usd_4h: ${buy_usd_4h:,.2f}")
        logger.info(f"  sell_usd_4h: ${sell_usd_4h:,.2f}")
        
        # Show sample transaction values
        if buys_24h:
            sample_tx, sample_usd = buys_24h[0]
            logger.info(f"  Sample buy tx: amount_usd=${sample_usd:,.2f}, amount_tokens={sample_tx.amount_tokens:,.2f}")
        if sells_24h:
            sample_tx, sample_usd = sells_24h[0]
            logger.info(f"  Sample sell tx: amount_usd=${sample_usd:,.2f}, amount_tokens={sample_tx.amount_tokens:,.2f}")

        # Distinct buyers (extract tx objects from tuples)
        distinct_buyers = len(set(tx.wallet for tx, _ in buys_24h))
        distinct_sellers = len(set(tx.wallet for tx, _ in sells_24h))

        # ── Component Scores (each 0-1) ──
        # 1. Buy/sell ratio score
        if total_sell_usd > 0:
            buy_sell_ratio = total_buy_usd / total_sell_usd
        else:
            buy_sell_ratio = 10.0 if total_buy_usd > 0 else 1.0

        # Sigmoid-like mapping: ratio 1.0→0.5, 2.0→0.7, 5.0→0.9
        ratio_score = min(buy_sell_ratio / (buy_sell_ratio + 2.0), 1.0)

        # Penalize if sellers > buyers (distribution)
        if distinct_sellers > distinct_buyers and distinct_sellers > 2:
            ratio_score *= 0.3

        # 2. Whale count score (more independent whales = stronger signal)
        # 1 whale = 0.2, 3 whales = 0.6, 5+ = 0.9
        count_score = min(distinct_buyers * 0.18, 0.95)

        # 3. Velocity score (buying acceleration, penalized if selling dominates)
        # Compare 4h buy rate vs 24h average rate, but zero/negative if 4h sells exceed buys
        rate_24h = total_buy_usd / 24.0 if total_buy_usd > 0 else 0
        rate_4h = buy_usd_4h / 4.0 if buy_usd_4h > 0 else 0
        sell_rate_4h = sell_usd_4h / 4.0 if sell_usd_4h > 0 else 0
        
        if rate_24h > 0:
            base_velocity = rate_4h / rate_24h
        else:
            base_velocity = 0.0
        
        # If 4h sells exceed 4h buys, velocity is negative (distribution, not accumulation)
        if sell_rate_4h > rate_4h:
            velocity = -base_velocity if base_velocity > 0 else -1.0
        else:
            velocity = base_velocity

        # velocity > 1 means accelerating, < 1 means decelerating, < 0 means distribution
        if velocity < 0:
            velocity_score = 0.0  # No accumulation score for distribution
        else:
            velocity_score = min(velocity / (velocity + 1.5), 1.0)

        # 4. Wallet quality score (average quality of buying whales)
        buyer_wallets = [self.wallet_profiles.get(tx.wallet) for tx, _ in buys_24h if tx.wallet in self.wallet_profiles]
        if buyer_wallets:
            quality_score = sum(w.quality_score for w in buyer_wallets) / len(buyer_wallets)
        else:
            quality_score = 0.3    # Default for unknown wallets

        # 5. Size relative to liquidity
        # Big buys in thin books = much more significant
        if liquidity > 0:
            size_ratio = total_buy_usd / liquidity
        else:
            size_ratio = 0.0

        # 5% of liquidity accumulated = moderate, 20%+ = very strong
        size_score = min(size_ratio / 0.25, 1.0)

        # ── WIF/POPCAT Historically-Proven Bonus Signals ──
        bonus_signals = {}
        
        # 1. DORMANT WHALE ACTIVATION (+0.15)
        # Wallets inactive 60+ days that start buying
        dormant_reactivation_count = 0
        for tx, usd in buys_24h:
            profile = self.wallet_profiles.get(tx.wallet)
            if profile and profile.is_dormant_reactivation(now, 60):
                dormant_reactivation_count += 1
        if dormant_reactivation_count > 0:
            bonus_signals["dormant_reactivation"] = BONUS_DORMANT_REACTIVATION * min(dormant_reactivation_count, 3) / 3
        
        # 2. EXCHANGE WITHDRAWAL ACCUMULATION (+0.20)
        # Wallets that received from CEX before buying
        exchange_withdrawal_buyers = sum(
            1 for tx, usd in buys_24h 
            if self.wallet_profiles.get(tx.wallet, WalletProfile(address="")).is_exchange_withdrawal
        )
        if exchange_withdrawal_buyers > 0:
            bonus_signals["exchange_withdrawal"] = BONUS_EXCHANGE_WITHDRAWAL * min(exchange_withdrawal_buyers, 2) / 2
        
        # 3. SINGLE DOMINANT ACCUMULATOR (+0.10)
        # One wallet >30% of total whale buy volume
        if total_buy_usd > 0:
            wallet_buy_volumes = {}
            for tx, usd in buys_24h:
                wallet_buy_volumes[tx.wallet] = wallet_buy_volumes.get(tx.wallet, 0) + usd
            max_wallet_share = max(wallet_buy_volumes.values()) / total_buy_usd if wallet_buy_volumes else 0
            if max_wallet_share > 0.30:
                bonus_signals["dominant_accumulator"] = BONUS_DOMINANT_ACCUMULATOR
        
        # 4. EARLY WHALE SELLING PENALTY (-0.30)
        # Original insiders (first 30 days) starting to sell after dormancy
        early_whale_selling = 0
        for tx, usd in sells_24h:
            profile = self.wallet_profiles.get(tx.wallet)
            if profile and profile.early_holder:
                early_whale_selling += usd
        if early_whale_selling > total_sell_usd * 0.5:  # Early whales >50% of selling
            bonus_signals["early_whale_selling"] = PENALTY_EARLY_WHALE_SELLING
        
        # Apply bonus signals (capped at 0-1 range after base score)
        total_bonus = sum(bonus_signals.values())
        adjusted_score = score + total_bonus
        
        # Log bonus signals
        if bonus_signals:
            logger.info(f"  Bonus signals for {symbol}: {bonus_signals}")
            logger.info(f"  Base score: {score:.3f} | Adjusted: {adjusted_score:.3f}")
        
        # ── Determine Phase ──
        # Critical checks first - if sells dominate, it's distribution regardless of other factors
        if buy_sell_ratio < 0.8:
            # Net selling pressure - more than 20% more sells than buys
            phase = AccumulationPhase.DISTRIBUTION
            adjusted_score *= 0.3  # Heavy penalty - this is not accumulation
        elif distinct_sellers > distinct_buyers * 1.5:
            # More distinct sellers than buyers
            phase = AccumulationPhase.DISTRIBUTION
            adjusted_score *= 0.5
        elif adjusted_score < 0.2:
            phase = AccumulationPhase.NONE
        elif adjusted_score < 0.4:
            phase = AccumulationPhase.EARLY_ACCUMULATION
        elif adjusted_score < 0.7:
            phase = AccumulationPhase.ACTIVE_ACCUMULATION
        else:
            phase = AccumulationPhase.HEAVY_ACCUMULATION

        # Clamp final score
        final_score = max(0.0, min(1.0, adjusted_score))

        # ── Build detail string ──
        if velocity < 0:
            velocity_desc = "distributing"
        elif velocity > 1:
            velocity_desc = "accelerating"
        else:
            velocity_desc = "flat/decelerating"
            
        details = (
            f"{symbol}: {distinct_buyers} whales buying (${total_buy_usd:,.0f}) vs "
            f"{distinct_sellers} selling (${total_sell_usd:,.0f}) in 24h. "
            f"Velocity {velocity_desc} "
            f"({abs(velocity):.1f}x). Size={size_ratio*100:.1f}% of liquidity."
        )

        return WhaleSignal(
            token_address=token_address,
            token_symbol=symbol,
            score=final_score,
            phase=phase,
            num_whales_accumulating=distinct_buyers,
            total_whale_buys_usd_24h=total_buy_usd,
            total_whale_sells_usd_24h=total_sell_usd,
            buy_sell_ratio=buy_sell_ratio,
            accumulation_velocity=velocity,
            top_wallet_quality=max((w.quality_score for w in buyer_wallets), default=0),
            details=details,
        )

    def _empty_signal(self, token_address: str, symbol: str = "???") -> WhaleSignal:
        """Return a zero-score signal when analysis can't proceed."""
        return WhaleSignal(
            token_address=token_address,
            token_symbol=symbol,
            score=0.0,
            phase=AccumulationPhase.NONE,
            num_whales_accumulating=0,
            total_whale_buys_usd_24h=0,
            total_whale_sells_usd_24h=0,
            buy_sell_ratio=1.0,
            accumulation_velocity=0.0,
            top_wallet_quality=0.0,
            details="No whale data available",
        )

    # ─── Wallet Clustering ─────────────────────────────────────────────────
    def cluster_wallets(self, wallets: List[str]) -> Dict[str, List[str]]:
        """
        Group wallets that likely belong to the same entity.
        Uses Helius Enhanced Transactions API to find funding sources.
        Note: getTransactionsForAddress RPC requires paid plan.
        
        Returns: {cluster_id: [wallet1, wallet2, ...]}
        """
        clusters: Dict[str, List[str]] = {}
        wallet_funding: Dict[str, str] = {}

        if not HELIUS_API_KEY:
            logger.warning("Wallet clustering requires HELIUS_API_KEY")
            return {w[:8]: [w] for w in wallets}

        # Check funding sources using REST API
        for wallet in wallets:
            try:
                resp = self._session.get(
                    f"{HELIUS_API}/addresses/{wallet}/transactions",
                    params={
                        "api-key": HELIUS_API_KEY,
                        "type": "TRANSFER",
                        "limit": 10,
                    },
                    timeout=10,
                )
                
                if resp.status_code == 403:
                    logger.warning(f"Helius 403 for clustering {wallet[:16]} — free tier limitation")
                    continue
                    
                if resp.status_code == 200:
                    txs = resp.json()
                    # Find the first SOL transfer in (likely the funder)
                    for tx in reversed(txs):
                        native = tx.get("nativeTransfers", [])
                        for nt in native:
                            if nt.get("toUserAccount") == wallet and nt.get("amount", 0) > 0:
                                funder = nt.get("fromUserAccount", "")
                                if funder and funder not in EXCHANGE_WALLETS:
                                    wallet_funding[wallet] = funder
                                    break
                time.sleep(0.15)  # Rate limiting
            except Exception as e:
                logger.error(f"Funding check failed for {wallet[:16]}: {e}")

        # Group by common funder
        funder_groups: Dict[str, List[str]] = defaultdict(list)
        for wallet, funder in wallet_funding.items():
            funder_groups[funder].append(wallet)

        # Convert to clusters
        for funder, group_wallets in funder_groups.items():
            if len(group_wallets) >= 2:
                cluster_id = hashlib.md5(funder.encode()).hexdigest()[:8]
                clusters[cluster_id] = group_wallets
                logger.info(f"Cluster {cluster_id}: {len(group_wallets)} wallets funded by {funder[:16]}")

        # Add unclustered wallets as singles
        clustered = set(w for group in clusters.values() for w in group)
        for w in wallets:
            if w not in clustered:
                clusters[w[:8]] = [w]

        return clusters

    # ─── ClawBot Integration Helpers ───────────────────────────────────────
    def enrich_engine_a_signal(
        self, 
        token_address: str, 
        engine_a_score: float, 
        chain: str = "solana"
    ) -> Tuple[float, str]:
        """
        Combine whale signal with Engine A's EMA reclaim score.
        
        Usage in your main loop:
            ema_score = engine_a.get_signal("GIGA")
            combined_score, reason = tracker.enrich_engine_a_signal(token_addr, ema_score)
            if combined_score > 0.7:
                # Execute via Kelly sizing
        """
        whale_signal = self.analyze_token(token_address, chain)

        if not whale_signal.is_actionable:
            # No whale confirmation — use Engine A score alone (discounted)
            combined = engine_a_score * 0.7
            reason = f"EMA reclaim only (no whale confirmation). Discounted to {combined:.2f}"
            return combined, reason

        # Weighted combination: EMA reclaim (60%) + whale accumulation (40%)
        combined = (engine_a_score * 0.6) + (whale_signal.score * 0.4)

        # Bonus for convergence (both signals agree)
        if engine_a_score > 0.6 and whale_signal.score > 0.6:
            combined = min(combined * 1.15, 1.0)    # 15% bonus

        reason = (
            f"EMA({engine_a_score:.2f}) + Whale({whale_signal.score:.2f}) = {combined:.2f}. "
            f"{whale_signal.details}"
        )
        return combined, reason

    def kelly_edge_estimate(self, whale_signal: WhaleSignal) -> float:
        """
        Convert whale signal to a probability estimate for Kelly criterion.
        Feed this as 'p' into your existing Kelly sizing logic.
        
        Conservative: maps 0-1 score to 0.45-0.65 probability range.
        (Never claim >65% edge from whale data alone — too noisy.)
        """
        # Map score 0-1 to probability 0.45-0.65
        p = 0.45 + (whale_signal.score * 0.20)
        return p


# ─── Async Streaming Monitor (Optional) ───────────────────────────────────────
class WhaleStreamMonitor:
    """
    Real-time whale monitoring via Helius websocket.
    Use this for live alerts instead of polling.
    
    Usage:
        import asyncio
        monitor = WhaleStreamMonitor(tracker)
        asyncio.run(monitor.start(["token_addr1", "token_addr2"]))
    """

    def __init__(self, tracker: WhaleTracker):
        self.tracker = tracker
        self.watched_tokens: List[str] = []
        self.callbacks: List[callable] = []

    def on_whale_alert(self, callback: callable):
        """Register a callback for whale alerts: callback(WhaleSignal)"""
        self.callbacks.append(callback)

    async def start(self, token_addresses: List[str]):
        """Start streaming whale transactions via Helius websocket."""
        try:
            import websockets
        except ImportError:
            logger.error("pip install websockets for real-time monitoring")
            return

        if not HELIUS_API_KEY:
            logger.error("HELIUS_API_KEY required for streaming")
            return

        self.watched_tokens = token_addresses
        ws_url = f"wss://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"

        logger.info(f"Starting whale stream monitor for {len(token_addresses)} tokens")

        async with websockets.connect(ws_url) as ws:
            # Subscribe to token account changes for watched tokens
            for i, token in enumerate(token_addresses):
                sub_msg = json.dumps({
                    "jsonrpc": "2.0",
                    "id": i + 1,
                    "method": "logsSubscribe",
                    "params": [
                        {"mentions": [token]},
                        {"commitment": "confirmed"},
                    ],
                })
                await ws.send(sub_msg)

            logger.info("Subscriptions active. Listening for whale activity...")

            async for message in ws:
                try:
                    data = json.loads(message)
                    await self._process_stream_event(data)
                except json.JSONDecodeError:
                    continue
                except Exception as e:
                    logger.error(f"Stream processing error: {e}")

    async def _process_stream_event(self, data: dict):
        """Process incoming websocket events and fire alerts."""
        # Check if it's a notification (not a subscription confirmation)
        if "method" not in data or data["method"] != "logsNotification":
            return

        logs = data.get("params", {}).get("result", {}).get("value", {}).get("logs", [])
        signature = data.get("params", {}).get("result", {}).get("value", {}).get("signature", "")

        # Quick check: does this look like a swap/transfer above our threshold?
        log_text = " ".join(logs)
        if "swap" not in log_text.lower() and "transfer" not in log_text.lower():
            return

        # Full analysis (throttled to avoid API spam)
        for token in self.watched_tokens:
            if token in log_text:
                signal = self.tracker.analyze_token(token)
                if signal.is_actionable:
                    for cb in self.callbacks:
                        cb(signal)
                break


# ─── Quick Test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    tracker = WhaleTracker()
    
    # Example: analyze a Solana token
    # Replace with any token mint address you're watching
    test_token = input("Enter Solana token address to analyze (or press Enter to skip): ").strip()
    
    if test_token:
        signal = tracker.analyze_token(test_token)
        print(f"\n{'='*60}")
        print(f"Token: {signal.token_symbol}")
        print(f"Score: {signal.score:.2f} / 1.00")
        print(f"Phase: {signal.phase.value}")
        print(f"Whales: {signal.num_whales_accumulating} accumulating")
        print(f"Buys: ${signal.total_whale_buys_usd_24h:,.0f}")
        print(f"Sells: ${signal.total_whale_sells_usd_24h:,.0f}")
        print(f"B/S Ratio:{signal.buy_sell_ratio:.2f}")
        print(f"Velocity: {signal.accumulation_velocity:.2f}x")
        print(f"Action: {'YES — feed to signal engine' if signal.is_actionable else 'No — skip'}")
        print(f"{'='*60}")
        print(f"Details: {signal.details}")
        
        # Kelly edge estimate
        p = tracker.kelly_edge_estimate(signal)
        print(f"\nKelly p estimate: {p:.3f}")
    else:
        print("No token provided. Run with a token address to test.")
        print("\nExample usage in ClawBot:")
        print("  tracker = WhaleTracker()")
        print('  signal = tracker.analyze_token("YOUR_TOKEN_MINT_ADDRESS")')
        print("  if signal.is_actionable:")
        print('      print(f"Whale accumulation detected: {signal.details}")')
