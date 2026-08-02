"""
DexScreener client — free, keyless price / liquidity / flow data.

Used for:
  * pricing open positions and limit-order levels (fill detection)
  * a lightweight *netflow* proxy: 24h buy vs sell volume + volume-vs-liquidity
    surge, which surfaces "something building" without a paid on-chain feed.

Docs: https://docs.dexscreener.com/  (rate limit ~300 req/min, no key required)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    import requests
except ImportError:  # pragma: no cover - requests is a hard dep in practice
    requests = None  # type: ignore

BASE = "https://api.dexscreener.com"
TIMEOUT = 15


class DexScreener:
    def __init__(self, session: Any = None):
        self.available = requests is not None
        self._session = session or (requests.Session() if requests else None)

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        if not self._session:
            return None
        try:
            resp = self._session.get(f"{BASE}{path}", params=params, timeout=TIMEOUT)
            if resp.status_code != 200:
                return None
            return resp.json()
        except Exception:
            return None

    # -- primitives ----------------------------------------------------------

    def pairs_for_token(self, chain: str, token_address: str) -> List[Dict[str, Any]]:
        data = self._get(f"/token-pairs/v1/{chain}/{token_address}")
        return data if isinstance(data, list) else []

    def search(self, query: str) -> List[Dict[str, Any]]:
        data = self._get("/latest/dex/search", {"q": query})
        if isinstance(data, dict):
            return data.get("pairs", []) or []
        return []

    # -- derived -------------------------------------------------------------

    @staticmethod
    def _best_pair(pairs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Pick the deepest-liquidity pair — the most reliable price source."""
        if not pairs:
            return None
        return max(pairs, key=lambda p: (p.get("liquidity", {}) or {}).get("usd", 0) or 0)

    def quote(self, symbol: str, chain: str = "solana",
              token_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Return a normalized quote for a token. Falls back to a symbol search
        when no address is known. Always returns a dict; ``price`` is None when
        the token could not be resolved.
        """
        pairs: List[Dict[str, Any]] = []
        if token_address:
            pairs = self.pairs_for_token(chain, token_address)
        if not pairs and symbol:
            candidates = self.search(symbol)
            # Prefer exact base-symbol matches on the requested chain.
            sym = symbol.upper()
            pairs = [
                p for p in candidates
                if (p.get("baseToken", {}) or {}).get("symbol", "").upper() == sym
                and (chain is None or p.get("chainId") == chain)
            ] or candidates

        best = self._best_pair(pairs)
        if not best:
            return {"symbol": symbol, "price": None, "resolved": False}

        liq = (best.get("liquidity", {}) or {}).get("usd")
        vol = best.get("volume", {}) or {}
        txns = best.get("txns", {}) or {}
        price_change = best.get("priceChange", {}) or {}
        return {
            "symbol": (best.get("baseToken", {}) or {}).get("symbol", symbol),
            "resolved": True,
            "price": _to_float(best.get("priceUsd")),
            "chain": best.get("chainId", chain),
            "token_address": (best.get("baseToken", {}) or {}).get("address", token_address),
            "pair_address": best.get("pairAddress"),
            "liquidity_usd": _to_float(liq),
            "volume_24h": _to_float(vol.get("h24")),
            "volume_6h": _to_float(vol.get("h6")),
            "price_change_24h": _to_float(price_change.get("h24")),
            "price_change_6h": _to_float(price_change.get("h6")),
            "txns_24h": txns.get("h24", {}),
            "url": best.get("url"),
        }

    def netflow(self, symbol: str, chain: str = "solana",
                token_address: Optional[str] = None) -> Dict[str, Any]:
        """
        Netflow proxy for a token: buy vs sell pressure over 24h plus a
        volume/liquidity "heat" ratio. High heat + buy skew = something building.
        """
        q = self.quote(symbol, chain, token_address)
        if not q.get("resolved"):
            return {"symbol": symbol, "resolved": False}

        txns = q.get("txns_24h", {}) or {}
        buys = txns.get("buys", 0) or 0
        sells = txns.get("sells", 0) or 0
        total = buys + sells
        buy_ratio = (buys / total) if total else 0.0
        liq = q.get("liquidity_usd") or 0.0
        vol = q.get("volume_24h") or 0.0
        heat = (vol / liq) if liq else 0.0
        return {
            "symbol": q["symbol"],
            "resolved": True,
            "buys": buys,
            "sells": sells,
            "buy_ratio": round(buy_ratio, 3),
            "volume_24h": vol,
            "liquidity_usd": liq,
            "heat": round(heat, 2),          # 24h volume as a multiple of liquidity
            "price_change_24h": q.get("price_change_24h"),
            "url": q.get("url"),
        }


def _to_float(v: Any) -> Optional[float]:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None
