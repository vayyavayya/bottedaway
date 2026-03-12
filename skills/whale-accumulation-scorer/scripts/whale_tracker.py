"""ClawBot - Whale Accumulation Tracker (Updated March 2026)
============================================================
Monitors on-chain whale wallets for accumulation patterns on Solana and EVM chains.
Produces a normalized confidence score (0-1) per token that feeds into ClawBot's 
signal validation layer alongside Engine A (EMA reclaim) and other signals.

NEW SIGNAL PATTERNS (March 2026):
7. Dead coin revival / CTO accumulation (+0.25 bonus) - TROLL pattern
8. Market maker / institutional entry (+0.20 bonus) - NEIRO Wintermute/GSR pattern  
9. Fresh wallet accumulation spike (+0.15 bonus, 2x if 3+ wallets) - NEIRO/WIF pattern
10. Supply concentration acceleration (+/-0.15-0.20 context-dependent) - NEIRO 24% pattern
"""

import os
import time
import json
import logging
import hashlib
from typing import Optional, Dict, List, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import requests
try:
    from dotenv import load_dotenv
    load_dotenv("keys.env")
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("clawbot.whale_tracker")

# --- Config ---
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(SKILL_DIR, "config")

def _load_helius_key() -> str:
    key = os.getenv("HELIUS_API_KEY", "")
    if key:
        return key
    for creds_file in [os.path.expanduser("~/.config/helius/credentials.json"), "/Users/pterion2910/.config/helius/credentials.json"]:
        if os.path.exists(creds_file):
            try:
                with open(creds_file, 'r') as f:
                    return json.load(f).get("api_key", "")
            except:
                continue
    return ""

def _load_birdeye_key() -> str:
    key = os.getenv("BIRDEYE_API_KEY", "")
    if key:
        return key
    for creds_file in [os.path.expanduser("~/.config/birdeye/credentials.json"), "/Users/pterion2910/.config/birdeye/credentials.json"]:
        if os.path.exists(creds_file):
            try:
                with open(creds_file, 'r') as f:
                    return json.load(f).get("api_key", "")
            except:
                continue
    return ""

HELIUS_API_KEY = _load_helius_key()
BIRDEYE_API_KEY = _load_birdeye_key()
HELIUS_API = f"https://api.helius.xyz/v0"
BIRDEYE_API = "https://public-api.birdeye.so"

# --- Market Maker Config ---
class MarketMakerConfig:
    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(CONFIG_DIR, "market_makers.json")
        self.market_makers = {}
        self.mm_addresses = set()
        self.exchange_wallets = set()
        self.detection_rules = {}
        self._load()
    
    def _load(self):
        if not os.path.exists(self.config_path):
            logger.warning(f"MM config not found: {self.config_path}")
            return
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            for name, data in config.get("market_makers", {}).items():
                self.market_makers[name] = data
                for addr in data.get("addresses", []):
                    self.mm_addresses.add(addr.lower())
            for exch, addrs in config.get("exchange_hot_wallets", {}).items():
                for addr in addrs:
                    self.exchange_wallets.add(addr)
            self.detection_rules = config.get("detection_rules", {})
            logger.info(f"Loaded {len(self.mm_addresses)} MM, {len(self.exchange_wallets)} exchange wallets")
        except Exception as e:
            logger.error(f"Failed to load MM config: {e}")
    
    def is_market_maker(self, address: str) -> Tuple[bool, str]:
        addr = address.lower()
        if addr in self.mm_addresses:
            for name, data in self.market_makers.items():
                if addr in [a.lower() for a in data.get("addresses", [])]:
                    return True, name
        return False, ""
    
    def is_exchange(self, address: str) -> bool:
        return address in self.exchange_wallets
    
    def get_fresh_wallet_rules(self) -> Dict:
        return {
            "max_age_days": self.detection_rules.get("fresh_wallet_max_age_days", 7),
            "threshold_usd": self.detection_rules.get("fresh_wallet_threshold_usd", 50000),
            "coordination_hours": self.detection_rules.get("fresh_wallet_coordination_hours", 48),
            "multiplier_threshold": self.detection_rules.get("fresh_wallet_multiplier_threshold", 3)
        }

# --- Data Models ---
class AccumulationPhase(Enum):
    NONE = "none"
    EARLY_ACCUMULATION = "early"
    ACTIVE_ACCUMULATION = "active"
    HEAVY_ACCUMULATION = "heavy"
    DISTRIBUTION = "distribution"
    DEAD_COIN_REVIVAL = "dead_revival"
    INSTITUTIONAL_ENTRY = "institutional"

@dataclass
class WalletProfile:
    address: str
    label: str = ""
    cluster_id: Optional[str] = None
    first_seen: float = 0.0
    last_activity_timestamp: float = 0.0
    dormancy_days: float = 0.0
    historical_win_rate: float = 0.5
    total_tokens_tracked: int = 0
    avg_hold_duration_hours: float = 0.0
    score_modifier: float = 1.0
    is_exchange_withdrawal: bool = False
    early_holder: bool = False
    wallet_creation_time: float = 0.0
    funds_source: str = ""
    is_fresh: bool = False
    market_maker_name: str = ""
    is_market_maker: bool = False
    
    @property
    def quality_score(self) -> float:
        dormancy_bonus = min(self.dormancy_days / 180, 1.0) * 0.3
        win_bonus = self.historical_win_rate * 0.4
        hold_bonus = min(self.avg_hold_duration_hours / 168, 1.0) * 0.3
        mm_bonus = 0.5 if self.is_market_maker else 0.0
        return min(dormancy_bonus + win_bonus + hold_bonus + mm_bonus, 1.0)
    
    def is_dormant_reactivation(self, current_time: float, threshold_days: int = 60) -> bool:
        if self.last_activity_timestamp == 0:
            return False
        return (current_time - self.last_activity_timestamp) / 86400 >= threshold_days
    
    def get_wallet_age_days(self, current_time: float = None) -> float:
        if self.wallet_creation_time == 0:
            return float('inf')
        return ((current_time or time.time()) - self.wallet_creation_time) / 86400

@dataclass
class WhaleTransaction:
    wallet: str
    token_address: str
    token_symbol: str
    side: str
    amount_tokens: float
    amount_usd: float
    timestamp: float
    tx_hash: str
    funds_source: str = ""
    is_fresh_wallet: bool = False

@dataclass
class TokenHolderSnapshot:
    timestamp: float
    top_10_holders_pct: float
    top_50_holders_pct: float
    top_100_holders_pct: float
    holder_count: int
    price: float
    market_cap: float

@dataclass
class WhaleSignal:
    token_address: str
    token_symbol: str
    score: float
    phase: AccumulationPhase
    num_whales_accumulating: int
    total_whale_buys_usd_24h: float
    total_whale_sells_usd_24h: float
    buy_sell_ratio: float
    accumulation_velocity: float
    top_wallet_quality: float
    details: str
    timestamp: float = field(default_factory=time.time)
    signal_tags: List[str] = field(default_factory=list)
    bonus_breakdown: Dict[str, float] = field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        return self.score >= 0.4 and self.phase in (
            AccumulationPhase.ACTIVE_ACCUMULATION,
            AccumulationPhase.HEAVY_ACCUMULATION,
            AccumulationPhase.DEAD_COIN_REVIVAL,
            AccumulationPhase.INSTITUTIONAL_ENTRY,
        )

# --- Blacklists ---
EXCHANGE_WALLETS = {"5tzFkiKscXHK5ZXCGbXZxdw7gTjjD1mBwuoFbhUvuAi9", "FWznbcNXWQuHTawe9RxvQ2LdCENLsh12dsznf4RiouN5", "H8sMJSCVzfius7NBqzkY4FhKJR9z22qY3yJ85DxQjwF", "GzPHuS2ynTCz68J9Q2hFk8bJyU87gWCBq5p1n3k9N3X"}
DEX_POOL_AUTHORITIES = {"5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1", "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8", "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc", "2LecshUwdyHxiL25o4cPNY9FNqRk63PzxKQ4mZ69hX5d", "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo", "M2mx93ekt1fmXSVkTrUL9xVFHkmME8HTUi5Cyc5aF7K", "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"}
CONTRACT_PATTERNS = {"11111111111111111111111111111111", "So11111111111111111111111111111111111111112"}
BLACKLISTED_ADDRESSES = EXCHANGE_WALLETS | DEX_POOL_AUTHORITIES | CONTRACT_PATTERNS

# --- Thresholds ---
MIN_WHALE_TX_USD = 5000
MIN_HOLDER_BALANCE_USD = 10000
MIN_LIQUIDITY_USD = 50000
MAX_SUPPLY_PCT_FOR_WHALE = 10.0
MAX_WHALES_TO_ANALYZE = 20

# --- Bonus Constants ---
BONUS_DORMANT_REACTIVATION = 0.15
BONUS_EXCHANGE_WITHDRAWAL = 0.20
BONUS_DOMINANT_ACCUMULATOR = 0.10
PENALTY_EARLY_WHALE_SELLING = -0.30

# NEW: Patterns 7-10
BONUS_DEAD_COIN_REVIVAL = 0.25
DEAD_COIN_MIN_AGE_DAYS = 90
DEAD_COIN_MAX_MC = 500000
DEAD_COIN_ATL_PROXIMITY = 0.10

BONUS_MARKET_MAKER_ENTRY = 0.20
MM_MIN_PURCHASE_USD = 50000

BONUS_FRESH_WALLET = 0.15
FRESH_WALLET_MULTIPLIER = 2.0

BONUS_SUPPLY_CONCENTRATION = 0.15
PENALTY_SUPPLY_CONCENTRATION = -0.20
SUPPLY_CONCENTRATION_THRESHOLD = 0.05
SUPPLY_CONCENTRATION_WINDOW_DAYS = 7

# --- WhaleTracker ---
class WhaleTracker:
    def __init__(self):
        self.wallet_profiles = {}
        self.tx_history = defaultdict(list)
        self.holder_snapshots = defaultdict(list)
        self._session = requests.Session()
        self.mm_config = MarketMakerConfig()
        
        if not HELIUS_API_KEY:
            logger.warning("HELIUS_API_KEY not set")
        if not BIRDEYE_API_KEY:
            logger.error("BIRDEYE_API_KEY required")

    def analyze_token(self, token_address: str, chain: str = "solana") -> WhaleSignal:
        logger.info(f"Analyzing {token_address[:16]}...")
        token_meta = {}
        holders = self._get_top_holders(token_address, chain)
        # Fallback to Helius/DexScreener if Birdeye returns no data OR no metadata
        if not holders or not token_meta.get("price"):
            fb = self._get_token_data_fallback(token_address, chain)
            holders = fb.get('holders', [])
            if fb.get('metadata', {}).get('price'):
                token_meta = fb['metadata']
                logger.info(f'Using fallback: {token_meta.get("symbol", "???")}')
        if not holders:
            return self._empty_signal(token_address)

        # Use cached token_meta if set from fallback
        token_meta = self._get_token_metadata(token_address, chain)

        symbol = token_meta.get("symbol", "???")
        liquidity = token_meta.get("liquidity", 0)

        if liquidity < MIN_LIQUIDITY_USD:
            return self._empty_signal(token_address, symbol=symbol)

        dead_coin_data = self._check_dead_coin_revival(token_address, token_meta)
        self._update_holder_snapshot(token_address, holders, token_meta)
        whales = self._filter_whales(holders, token_meta)

        whale_txs = []
        for whale_addr in whales:
            txs = self._get_wallet_token_txs(whale_addr, token_address, chain)
            whale_txs.extend(txs)
            time.sleep(0.15)

        token_price = float(token_meta.get("price", 0))
        signal = self._score_accumulation(token_address, symbol, whales, whale_txs, liquidity, token_price, token_meta, dead_coin_data)
        logger.info(f"{symbol}: score={signal.score:.2f} phase={signal.phase.value} tags={signal.signal_tags}")
        return signal

    def batch_scan(self, token_addresses: List[str], chain: str = "solana") -> List[WhaleSignal]:
        signals = []
        for addr in token_addresses:
            try:
                sig = self.analyze_token(addr, chain)
                signals.append(sig)
                time.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed {addr[:16]}: {e}")
                signals.append(self._empty_signal(addr))
        return signals

    def get_signal_for_engine(self, token_address: str, chain: str = "solana") -> Tuple[float, dict]:
        signal = self.analyze_token(token_address, chain)
        meta = {"phase": signal.phase.value, "num_whales": signal.num_whales_accumulating, "buy_sell_ratio": signal.buy_sell_ratio,
                "velocity": signal.accumulation_velocity, "details": signal.details, "signal_tags": signal.signal_tags, "bonus_breakdown": signal.bonus_breakdown}
        return signal.score, meta

    # --- Pattern 7: Dead Coin Revival ---
    def _check_dead_coin_revival(self, token_address: str, token_meta: Dict) -> Dict:
        result = {"is_dead_coin": False, "age_days": 0, "near_atl": False, "concentration_increasing": False, "score": 0.0}
        try:
            token_age_days = token_meta.get("token_age_days", 0)
            creation_time = token_meta.get("creation_timestamp", 0)
            if creation_time > 0:
                token_age_days = (time.time() - creation_time) / 86400
            result["age_days"] = token_age_days
            if token_age_days < DEAD_COIN_MIN_AGE_DAYS:
                return result
            market_cap = token_meta.get("market_cap", 0) or token_meta.get("mcap", 0)
            if market_cap > DEAD_COIN_MAX_MC:
                return result
            current_price = float(token_meta.get("price", 0))
            atl_price = float(token_meta.get("atl", 0) or token_meta.get("all_time_low", 0))
            if atl_price > 0 and current_price > 0:
                result["near_atl"] = (current_price / atl_price) <= (1 + DEAD_COIN_ATL_PROXIMITY)
            snapshots = self.holder_snapshots.get(token_address, [])
            if len(snapshots) >= 2:
                cutoff = time.time() - (30 * 86400)
                old = None
                for s in snapshots:
                    if s.timestamp >= cutoff:
                        old = s
                        break
                if old:
                    result["concentration_increasing"] = (snapshots[-1].top_100_holders_pct - old.top_100_holders_pct) >= 0.03
            result["is_dead_coin"] = result["age_days"] >= DEAD_COIN_MIN_AGE_DAYS and market_cap <= DEAD_COIN_MAX_MC and result["near_atl"] and result["concentration_increasing"]
            if result["is_dead_coin"]:
                result["score"] = BONUS_DEAD_COIN_REVIVAL
                logger.info(f"Dead coin revival: {token_address[:16]} age={result['age_days']:.0f}d MC=${market_cap:,.0f}")
        except Exception as e:
            logger.debug(f"Dead coin check failed: {e}")
        return result

    # --- Pattern 8: Market Maker Entry ---
    def _detect_market_maker_entry(self, whale_addrs: List[str], transactions: List[WhaleTransaction]) -> Tuple[bool, str, float]:
        mm_detected = False
        mm_name = ""
        total_mm_volume = 0.0
        for tx in transactions:
            if tx.side == "buy":
                is_mm, name = self.mm_config.is_market_maker(tx.wallet)
                if is_mm and tx.amount_usd >= MM_MIN_PURCHASE_USD:
                    mm_detected = True
                    mm_name = name
                    total_mm_volume += tx.amount_usd
                    if tx.wallet in self.wallet_profiles:
                        p = self.wallet_profiles[tx.wallet]
                        p.is_market_maker = True
                        p.market_maker_name = name
                        p.label = "market_maker"
        bonus = BONUS_MARKET_MAKER_ENTRY if mm_detected else 0.0
        if mm_detected:
            logger.info(f"MM entry: {mm_name} ${total_mm_volume:,.0f}")
        return mm_detected, mm_name, bonus

    # --- Pattern 9: Fresh Wallet Accumulation ---
    def _detect_fresh_wallet_accumulation(self, token_address: str, transactions: List[WhaleTransaction]) -> Tuple[float, int, List[str]]:
        now = time.time()
        rules = self.mm_config.get_fresh_wallet_rules()
        fresh_wallets = []
        fresh_buys = []
        for tx in transactions:
            if tx.side != "buy" or tx.amount_usd < rules["threshold_usd"]:
                continue
            profile = self.wallet_profiles.get(tx.wallet)
            if not profile:
                continue
            wallet_age = profile.get_wallet_age_days(now)
            if wallet_age <= rules["max_age_days"]:
                if profile.funds_source == "exchange" or profile.is_exchange_withdrawal:
                    fresh_wallets.append(tx.wallet)
                    fresh_buys.append(tx)
                    profile.is_fresh = True
                    profile.label = "fresh_wallet"
        num_fresh = len(set(fresh_wallets))
        if num_fresh == 0:
            return 0.0, 0, []
        base_bonus = BONUS_FRESH_WALLET * min(num_fresh, 5)
        if num_fresh >= rules["multiplier_threshold"] and len(fresh_buys) >= 2:
            times = sorted([tx.timestamp for tx in fresh_buys])
            span_hours = (times[-1] - times[0]) / 3600
            if span_hours <= rules["coordination_hours"]:
                base_bonus *= FRESH_WALLET_MULTIPLIER
                logger.info(f"Fresh wallet coordination: {num_fresh} wallets in {span_hours:.1f}h (2x)")
        return base_bonus, num_fresh, list(set(fresh_wallets))

    # --- Pattern 10: Supply Concentration ---
    def _detect_supply_concentration_change(self, token_address: str, token_price: float, price_change_24h: float = 0.0) -> Tuple[float, float]:
        snapshots = self.holder_snapshots.get(token_address, [])
        if len(snapshots) < 2:
            return 0.0, 0.0
        cutoff = time.time() - (SUPPLY_CONCENTRATION_WINDOW_DAYS * 86400)
        old = None
        for s in snapshots:
            if s.timestamp >= cutoff:
                old = s
                break
        if not old:
            return 0.0, 0.0
        change = snapshots[-1].top_10_holders_pct - old.top_10_holders_pct
        if abs(change) < SUPPLY_CONCENTRATION_THRESHOLD:
            return 0.0, change
        price_change = price_change_24h if price_change_24h != 0 else ((snapshots[-1].price - old.price) / old.price if old.price > 0 else 0)
        if change > 0:
            if price_change <= 0.05:
                logger.info(f"Supply concentration BULLISH: +{change*100:.1f}% price {price_change*100:+.1f}%")
                return BONUS_SUPPLY_CONCENTRATION, change
            else:
                logger.info(f"Supply concentration RISK: +{change*100:.1f}% price {price_change*100:+.1f}%")
                return PENALTY_SUPPLY_CONCENTRATION, change
        return 0.0, change

    def _update_holder_snapshot(self, token_address: str, holders: List[Dict], token_meta: Dict):
        try:
            top10 = sum(float(h.get("percentage", 0) or 0) for h in holders[:10])
            top50 = sum(float(h.get("percentage", 0) or 0) for h in holders[:50])
            top100 = sum(float(h.get("percentage", 0) or 0) for h in holders[:100])
            snapshot = TokenHolderSnapshot(timestamp=time.time(), top_10_holders_pct=top10, top_50_holders_pct=top50,
                                          top_100_holders_pct=top100, holder_count=len(holders),
                                          price=float(token_meta.get("price", 0)), market_cap=float(token_meta.get("market_cap", 0)))
            self.holder_snapshots[token_address].append(snapshot)
            cutoff = time.time() - (60 * 86400)
            self.holder_snapshots[token_address] = [s for s in self.holder_snapshots[token_address] if s.timestamp >= cutoff]
        except Exception as e:
            logger.debug(f"Snapshot update failed: {e}")

    # --- Data Fetchers ---
    def _get_top_holders(self, token_address: str, chain: str = "solana") -> List[Dict]:
        try:
            resp = self._session.get(f"{BIRDEYE_API}/defi/v3/token/holder", headers={"X-API-KEY": BIRDEYE_API_KEY, "x-chain": chain},
                                    params={"address": token_address, "offset": 0, "limit": 50}, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("data", {}).get("items", [])
        except Exception as e:
            logger.error(f"Holder fetch failed: {e}")
        return []

    def _get_token_metadata(self, token_address: str, chain: str = "solana") -> Dict:
        try:
            resp = self._session.get(f"{BIRDEYE_API}/defi/v3/token/overview", headers={"X-API-KEY": BIRDEYE_API_KEY, "x-chain": chain},
                                    params={"address": token_address}, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("data", {})
        except Exception as e:
            logger.error(f"Metadata fetch failed: {e}")
        return {}

    def _get_wallet_token_txs(self, wallet: str, token_address: str, chain: str = "solana", lookback_hours: int = 72) -> List[WhaleTransaction]:
        txs = []
        cutoff = time.time() - (lookback_hours * 3600)
        if HELIUS_API_KEY and chain == "solana":
            txs = self._helius_wallet_txs(wallet, token_address, cutoff)
        if not txs:
            txs = self._birdeye_wallet_txs(wallet, token_address, chain, cutoff)
        self.tx_history[token_address].extend(txs)
        return txs

    def _helius_wallet_txs(self, wallet, token_address, cutoff):
        """Helius Developer: getTransactionsForAddress RPC."""
        txs = []
        if not HELIUS_API_KEY:
            return txs
        try:
            rpc = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransactionsForAddress",
                "params": [wallet, {"limit": 100}]
            }
            r = requests.post(rpc, json=payload, timeout=30)
            if r.status_code == 200:
                result = r.json().get("result", [])
                if isinstance(result, dict):
                    result = result.get("data", [])
                for tx in result:
                    ts = tx.get("blockTime", 0)
                    if ts < cutoff:
                        continue
                    meta = tx.get("meta", {})
                    if meta.get("err"):
                        continue
                    pre = {b.get("mint"): float(b.get("uiTokenAmount", {}).get("uiAmount", 0))
                           for b in meta.get("preTokenBalances", []) if b.get("owner") == wallet}
                    post = {b.get("mint"): float(b.get("uiTokenAmount", {}).get("uiAmount", 0))
                            for b in meta.get("postTokenBalances", []) if b.get("owner") == wallet}
                    delta = post.get(token_address, 0) - pre.get(token_address, 0)
                    if abs(delta) > 0.000001:
                        side = "buy" if delta > 0 else "sell"
                        txs.append(WhaleTransaction(
                            wallet=wallet, token_address=token_address, token_symbol="",
                            side=side, amount_tokens=abs(delta), amount_usd=0,
                            timestamp=ts, tx_hash=tx.get("signature", "")
                        ))
        except Exception as e:
            logger.debug(f"Helius: {e}")
        return txs


    def _birdeye_wallet_txs(self, wallet: str, token_address: str, chain: str, cutoff: float) -> List[WhaleTransaction]:
        txs = []
        try:
            resp = self._session.get(f"{BIRDEYE_API}/v1/wallet/tx_list", headers={"X-API-KEY": BIRDEYE_API_KEY, "x-chain": chain},
                                    params={"wallet": wallet, "limit": 50}, timeout=10)
            if resp.status_code != 200:
                return []
            for tx in resp.json().get("data", {}).get("items", []):
                ts = tx.get("blockUnixTime", 0)
                if ts < cutoff:
                    continue
                if token_address in json.dumps(tx):
                    side = "buy" if tx.get("side", "") == "buy" else "sell"
                    txs.append(WhaleTransaction(wallet=wallet, token_address=token_address, token_symbol="", side=side,
                                                amount_tokens=float(tx.get("tokenAmount", 0)), amount_usd=float(tx.get("volumeUSD", 0)),
                                                timestamp=ts, tx_hash=tx.get("txHash", "")))
        except Exception as e:
            logger.error(f"Birdeye tx failed: {e}")
        return txs

    # --- Analysis ---

    # --- Fallback Data Sources (Helius + DexScreener) ---
    def _get_token_data_fallback(self, token_address, chain='solana'):
        logger.info(f'Birdeye 404, using fallback for {token_address[:16]}...')
        metadata = self._get_dexscreener_metadata(token_address)
        holders = self._get_helius_holders(token_address)
        return {'metadata': metadata, 'holders': holders, 'source': 'fallback'}
    
    def _get_dexscreener_metadata(self, token_address):
        try:
            resp = self._session.get(f'https://api.dexscreener.com/latest/dex/tokens/{token_address}', timeout=10)
            if resp.status_code == 200:
                pairs = resp.json().get('pairs', [])
                if pairs:
                    top = max(pairs, key=lambda x: float(x.get('liquidity', {}).get('usd', 0) or 0))
                    base = top.get('baseToken', {})
                    return {
                        'symbol': base.get('symbol', '???'),
                        'price': float(top.get('priceUsd', 0) or 0),
                        'liquidity': float(top.get('liquidity', {}).get('usd', 0) or 0),
                        'volume_24h': float(top.get('volume', {}).get('h24', 0) or 0),
                        'volume': float(top.get('volume', {}).get('h24', 0) or 0),
                    }
        except Exception as e:
            logger.error(f'DexScreener failed: {e}')
        return {}
    
    def _get_helius_holders(self, token_address, limit=50):
        """Get top token holders via Helius getTokenLargestAccounts."""
        if not HELIUS_API_KEY:
            return []
        holders = []
        try:
            rpc = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}"
            payload = {"jsonrpc": "2.0", "id": 1, "method": "getTokenLargestAccounts", "params": [token_address]}
            resp = self._session.post(rpc, json=payload, timeout=30)
            if resp.status_code == 200:
                accounts = resp.json().get("result", {}).get("value", [])
                for acc in accounts[:limit]:
                    holders.append({
                        "address": acc.get("address", ""),
                        "amount": float(acc.get("uiAmount", 0)),
                        "uiAmount": float(acc.get("uiAmount", 0)),
                        "percentage": 0
                    })
                total = sum(h["amount"] for h in holders)
                if total > 0:
                    for h in holders:
                        h["percentage"] = (h["amount"] / total) * 100
                logger.info(f"Helius returned {len(holders)} holders")
        except Exception as e:
            logger.error(f"Helius failed: {e}")
        return holders


    def _filter_whales(self, holders: List[Dict], token_meta: Dict) -> List[str]:
        price = float(token_meta.get("price", 0)) or 0.0001
        filtered = []
        for h in holders:
            addr = h.get("address", "") or h.get("owner", "")
            if not addr or addr in BLACKLISTED_ADDRESSES:
                continue
            is_mm, _ = self.mm_config.is_market_maker(addr)
            balance = float(h.get("amount", 0) or h.get("uiAmount", 0))
            usd = balance * price
            pct = h.get("percentage", 0) or 0.0
            if usd < MIN_HOLDER_BALANCE_USD and not is_mm:
                continue
            if pct > MAX_SUPPLY_PCT_FOR_WHALE and not is_mm:
                continue
            if addr not in self.wallet_profiles:
                self.wallet_profiles[addr] = WalletProfile(address=addr, first_seen=time.time())
            if is_mm:
                self.wallet_profiles[addr].is_market_maker = True
                self.wallet_profiles[addr].label = "market_maker"
            filtered.append((addr, usd, pct))
        filtered.sort(key=lambda x: x[1], reverse=True)
        return [w[0] for w in filtered[:MAX_WHALES_TO_ANALYZE]]

    def _score_accumulation(self, token_address: str, symbol: str, whale_addrs: List[str], transactions: List[WhaleTransaction],
                           liquidity: float, token_price: float = 0.0, token_meta: Dict = None, dead_coin_data: Dict = None) -> WhaleSignal:
        now = time.time()
        h24 = now - 86400
        h4 = now - 14400

        buys_24h = [(tx, tx.amount_usd or (tx.amount_tokens * token_price if token_price > 0 else 0)) 
                     for tx in transactions if tx.timestamp > h24 and tx.side == "buy"]
        sells_24h = [(tx, tx.amount_usd or (tx.amount_tokens * token_price if token_price > 0 else 0)) 
                      for tx in transactions if tx.timestamp > h24 and tx.side == "sell"]

        total_buy = sum(usd for _, usd in buys_24h)
        total_sell = sum(usd for _, usd in sells_24h)
        
        buys_4h = [(tx, usd) for tx, usd in buys_24h if tx.timestamp > h4]
        sells_4h = [(tx, usd) for tx, usd in sells_24h if tx.timestamp > h4]
        buy_4h = sum(usd for _, usd in buys_4h)
        sell_4h = sum(usd for _, usd in sells_4h)

        distinct_buyers = len(set(tx.wallet for tx, _ in buys_24h))
        distinct_sellers = len(set(tx.wallet for tx, _ in sells_24h))

        # Component scores
        bsr = total_buy / total_sell if total_sell > 0 else (10.0 if total_buy > 0 else 1.0)
        
        # STRICT RULE: bsr < 0.8 = distribution (net selling)
        is_distribution = bsr < 0.8
        
        ratio_score = min(bsr / (bsr + 2.0), 1.0) if not is_distribution else 0.0
        
        count_score = min(distinct_buyers * 0.18, 0.95) if not is_distribution else 0.0

        # Velocity: ONLY measures buying acceleration
        # If 4h sells >= 4h buys, velocity is 0 (no buying momentum)
        rate_24h = total_buy / 24.0 if total_buy > 0 else 0
        rate_4h = buy_4h / 4.0 if buy_4h > 0 else 0
        
        if is_distribution or buy_4h <= sell_4h:
            velocity = 0.0
            velocity_score = 0.0
        else:
            velocity = rate_4h / rate_24h if rate_24h > 0 else 0
            velocity_score = min(velocity / (velocity + 1.5), 1.0)

        buyer_wallets = [self.wallet_profiles.get(tx.wallet) for tx, _ in buys_24h if tx.wallet in self.wallet_profiles]
        quality_score = sum(w.quality_score for w in buyer_wallets) / len(buyer_wallets) if buyer_wallets else 0.3

        size_ratio = total_buy / liquidity if liquidity > 0 else 0
        size_score = min(size_ratio / 0.25, 1.0)

        # Base score
        base_score = ratio_score * 0.25 + count_score * 0.20 + velocity_score * 0.20 + quality_score * 0.15 + size_score * 0.20

        # Bonuses
        bonus_signals = {}
        signal_tags = []
        
        # Original bonuses
        dormant_count = sum(1 for tx, _ in buys_24h if self.wallet_profiles.get(tx.wallet) and self.wallet_profiles[tx.wallet].is_dormant_reactivation(now, 60))
        if dormant_count > 0:
            bonus_signals["dormant_reactivation"] = BONUS_DORMANT_REACTIVATION * min(dormant_count, 3) / 3
        
        ex_buyers = sum(1 for tx, _ in buys_24h if self.wallet_profiles.get(tx.wallet, WalletProfile(address="")).is_exchange_withdrawal)
        if ex_buyers > 0:
            bonus_signals["exchange_withdrawal"] = BONUS_EXCHANGE_WITHDRAWAL * min(ex_buyers, 2) / 2
        
        if total_buy > 0:
            wallet_vols = {}
            for tx, usd in buys_24h:
                wallet_vols[tx.wallet] = wallet_vols.get(tx.wallet, 0) + usd
            max_share = max(wallet_vols.values()) / total_buy if wallet_vols else 0
            if max_share > 0.30:
                bonus_signals["dominant_accumulator"] = BONUS_DOMINANT_ACCUMULATOR

        # NEW Pattern 7: Dead Coin Revival
        if dead_coin_data and dead_coin_data.get("is_dead_coin"):
            bonus_signals["dead_coin_revival"] = dead_coin_data["score"]
            signal_tags.append("dead_revival")
            logger.info(f"  BONUS: Dead coin revival (+{dead_coin_data['score']:.2f})")

        # NEW Pattern 8: Market Maker Entry
        mm_detected, mm_name, mm_bonus = self._detect_market_maker_entry(whale_addrs, transactions)
        if mm_detected:
            bonus_signals["market_maker_entry"] = mm_bonus
            signal_tags.append(f"mm_entry:{mm_name}")

        # NEW Pattern 9: Fresh Wallet
        fresh_bonus, num_fresh, _ = self._detect_fresh_wallet_accumulation(token_address, transactions)
        if fresh_bonus > 0:
            bonus_signals["fresh_wallet"] = fresh_bonus
            signal_tags.append(f"fresh:{num_fresh}")

        # NEW Pattern 10: Supply Concentration
        price_change_24h = (token_meta.get("priceChange24h", 0) / 100) if token_meta else 0
        conc_bonus, conc_change = self._detect_supply_concentration_change(token_address, token_price, price_change_24h)
        if conc_bonus != 0:
            bonus_signals["supply_concentration"] = conc_bonus
            signal_tags.append(f"supply:{'up' if conc_bonus > 0 else 'risk'}")

        total_bonus = sum(bonus_signals.values())
        adjusted = base_score + total_bonus

        if bonus_signals:
            logger.info(f"  Bonuses: {bonus_signals} | Base: {base_score:.3f} -> Adjusted: {adjusted:.3f}")

        # Phase determination - STRICT RULES
        if is_distribution:
            # Net selling pressure - this is distribution, not accumulation
            phase = AccumulationPhase.DISTRIBUTION
            adjusted = 0.0  # Zero out all scores during distribution
        elif dead_coin_data and dead_coin_data.get("is_dead_coin"):
            phase = AccumulationPhase.DEAD_COIN_REVIVAL
        elif mm_detected:
            phase = AccumulationPhase.INSTITUTIONAL_ENTRY
        elif adjusted < 0.2:
            phase = AccumulationPhase.NONE
        elif adjusted < 0.4:
            phase = AccumulationPhase.EARLY_ACCUMULATION
        elif adjusted < 0.7:
            phase = AccumulationPhase.ACTIVE_ACCUMULATION
        else:
            phase = AccumulationPhase.HEAVY_ACCUMULATION
        final_score = max(0.0, min(1.0, adjusted))

        vel_desc = "distributing" if velocity < 0 else ("accelerating" if velocity > 1 else "flat/decelerating")
        details = f"{symbol}: {distinct_buyers} whales (${total_buy:,.0f}) vs {distinct_sellers} sellers (${total_sell:,.0f}) 24h. Vel {vel_desc} ({abs(velocity):.1f}x). Size={size_ratio*100:.1f}% liq."
        if signal_tags:
            details += f" Signals: {', '.join(signal_tags)}."

        return WhaleSignal(token_address=token_address, token_symbol=symbol, score=final_score, phase=phase,
                          num_whales_accumulating=distinct_buyers, total_whale_buys_usd_24h=total_buy,
                          total_whale_sells_usd_24h=total_sell, buy_sell_ratio=bsr, accumulation_velocity=velocity,
                          top_wallet_quality=max((w.quality_score for w in buyer_wallets), default=0), details=details,
                          signal_tags=signal_tags, bonus_breakdown=bonus_signals)

    def _empty_signal(self, token_address: str, symbol: str = "???") -> WhaleSignal:
        return WhaleSignal(token_address=token_address, token_symbol=symbol, score=0.0, phase=AccumulationPhase.NONE,
                          num_whales_accumulating=0, total_whale_buys_usd_24h=0, total_whale_sells_usd_24h=0,
                          buy_sell_ratio=1.0, accumulation_velocity=0.0, top_wallet_quality=0.0,
                          details="No whale data available", signal_tags=[], bonus_breakdown={})

    def cluster_wallets(self, wallets: List[str]) -> Dict[str, List[str]]:
        clusters = {}
        if not HELIUS_API_KEY:
            return {w[:8]: [w] for w in wallets}
        for wallet in wallets:
            try:
                resp = self._session.get(f"{HELIUS_API}/addresses/{wallet}/transactions",
                                         params={"api-key": HELIUS_API_KEY, "type": "TRANSFER", "limit": 10}, timeout=10)
                if resp.status_code == 200:
                    txs = resp.json()
                    for tx in reversed(txs):
                        for nt in tx.get("nativeTransfers", []):
                            if nt.get("toUserAccount") == wallet and nt.get("amount", 0) > 0:
                                funder = nt.get("fromUserAccount", "")
                                if funder and funder not in EXCHANGE_WALLETS:
                                    clusters[funder] = clusters.get(funder, []) + [wallet]
                                    break
                time.sleep(0.15)
            except Exception as e:
                logger.error(f"Clustering failed for {wallet[:16]}: {e}")
        return clusters

    def enrich_engine_a_signal(self, token_address: str, engine_a_score: float, chain: str = "solana") -> Tuple[float, str]:
        whale_signal = self.analyze_token(token_address, chain)
        if not whale_signal.is_actionable:
            combined = engine_a_score * 0.7
            return combined, f"EMA only (no whale). Discounted to {combined:.2f}"
        combined = (engine_a_score * 0.6) + (whale_signal.score * 0.4)
        if engine_a_score > 0.6 and whale_signal.score > 0.6:
            combined = min(combined * 1.15, 1.0)
        reason = f"EMA({engine_a_score:.2f}) + Whale({whale_signal.score:.2f}) = {combined:.2f}. {whale_signal.details}"
        return combined, reason

    def kelly_edge_estimate(self, whale_signal: WhaleSignal) -> float:
        return 0.45 + (whale_signal.score * 0.20)


if __name__ == "__main__":
    tracker = WhaleTracker()
    test_token = input("Enter token address: ").strip()
    if test_token:
        signal = tracker.analyze_token(test_token)
        print(f"\nToken: {signal.token_symbol}")
        print(f"Score: {signal.score:.2f}")
        print(f"Phase: {signal.phase.value}")
        print(f"Tags: {signal.signal_tags}")
        print(f"Actionable: {signal.is_actionable}")
        print(f"Details: {signal.details}")
    else:
        print("No token provided")

