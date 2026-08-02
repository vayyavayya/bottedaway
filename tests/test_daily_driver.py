"""
Tests for the Daily Driver.

The workflow is exercised with *fake* data sources so tests are deterministic,
offline, and never touch the network. This mirrors how the real sources degrade
gracefully — the workflow only ever consumes their public method surface.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from daily_driver.state import EntityWallet, LimitOrder, Position, Store  # noqa: E402
from daily_driver.workflow import evening, morning  # noqa: E402
from daily_driver.sources.onchain import WalletMove  # noqa: E402


# --- Fakes -----------------------------------------------------------------


class FakeDex:
    def __init__(self, quotes=None, flows=None):
        self._quotes = quotes or {}
        self._flows = flows or {}

    def quote(self, symbol, chain="solana", token_address=None):
        return self._quotes.get(symbol.upper(),
                                {"symbol": symbol, "price": None, "resolved": False})

    def netflow(self, symbol, chain="solana", token_address=None):
        return self._flows.get(symbol.upper(), {"symbol": symbol, "resolved": False})


class FakeOnChain:
    def __init__(self, moves_by_wallet=None, available=True):
        self.available = available
        self._moves = moves_by_wallet or {}

    def recent_moves(self, address, label, chain="solana", limit=25):
        return self._moves.get(address, [])


class FakeCatalysts:
    def __init__(self, available=True, items=None):
        self.available = available
        self._items = items or []

    def scan(self, symbols):
        return {"available": self.available,
                "summary": "test summary",
                "items": self._items, "raw": ""}


@pytest.fixture
def store(tmp_path):
    return Store(data_dir=tmp_path)


# --- State round-trip -------------------------------------------------------


def test_position_roundtrip(store):
    store.add_position(Position(symbol="SOL", token_address="MintSOL", size_usd=250,
                               entry_price=150, stop=138, thesis="range reclaim"))
    positions = store.positions()
    assert len(positions) == 1
    assert positions[0].symbol == "SOL"
    assert positions[0].stop == 138
    assert store.owned_symbols() == {"SOL"}
    assert "mintsol" in store.owned_addresses()


def test_position_add_is_upsert(store):
    store.add_position(Position(symbol="SOL", stop=138))
    store.add_position(Position(symbol="SOL", stop=140))
    assert len(store.positions()) == 1
    assert store.positions()[0].stop == 140


def test_order_id_is_deterministic():
    o = LimitOrder(symbol="SOL", side="buy", price=140.5)
    assert o.id == "SOL-buy-140_5"


def test_seen_memory_is_capped(store):
    seen = {"buys": [f"k{i}" for i in range(3000)], "sells": []}
    store.save_seen(seen)
    assert len(store.seen()["buys"]) == 2000


# --- Morning routine --------------------------------------------------------


def test_morning_flags_new_entity_buy_on_unowned_token(store):
    store.add_wallet(EntityWallet(address="W1", label="whale_1"))
    dex = FakeDex()
    move = WalletMove("W1", "whale_1", "buy", "BONK", "BonkMint", 1000.0,
                      "solana", "sig1", 111)
    onchain = FakeOnChain({"W1": [move]})
    brief = morning(store, dex=dex, onchain=onchain, catalysts=FakeCatalysts())
    wallets_sec = brief.sections[0]
    assert "1 new buy" in wallets_sec.summary
    assert any("BONK" in l for l in wallets_sec.lines)


def test_morning_ignores_buys_on_owned_tokens(store):
    store.add_wallet(EntityWallet(address="W1", label="whale_1"))
    store.add_position(Position(symbol="BONK", token_address="BonkMint"))
    move = WalletMove("W1", "whale_1", "buy", "BONK", "BonkMint", 1000.0,
                      "solana", "sig1", 111)
    onchain = FakeOnChain({"W1": [move]})
    brief = morning(store, dex=FakeDex(), onchain=onchain, catalysts=FakeCatalysts())
    assert "No new buys" in brief.sections[0].summary


def test_morning_dedupes_across_runs(store):
    store.add_wallet(EntityWallet(address="W1", label="whale_1"))
    move = WalletMove("W1", "whale_1", "buy", "BONK", "BonkMint", 1000.0,
                      "solana", "sig1", 111)
    onchain = FakeOnChain({"W1": [move]})
    morning(store, dex=FakeDex(), onchain=onchain, catalysts=FakeCatalysts())
    brief2 = morning(store, dex=FakeDex(), onchain=onchain, catalysts=FakeCatalysts())
    assert "No new buys" in brief2.sections[0].summary


def test_morning_stop_breach_is_alert(store):
    store.add_position(Position(symbol="SOL", token_address="MintSOL",
                               entry_price=150, stop=138, thesis="t"))
    dex = FakeDex(quotes={"SOL": {"symbol": "SOL", "price": 130.0, "resolved": True,
                                  "price_change_24h": -12.0}})
    brief = morning(store, dex=dex, onchain=FakeOnChain(available=False),
                    catalysts=FakeCatalysts())
    pos_sec = brief.sections[1]
    assert pos_sec.tone == "alert"
    assert "STOP BREACHED" in " ".join(pos_sec.lines)


# --- Evening routine --------------------------------------------------------


def test_evening_detects_buy_fill_and_prompts_thesis(store):
    store.add_order(LimitOrder(symbol="SOL", side="buy", price=140, size_usd=250,
                               token_address="MintSOL", thesis="reclaim"))
    dex = FakeDex(quotes={"SOL": {"symbol": "SOL", "price": 138.0, "resolved": True,
                                  "price_change_24h": -2.0}})
    brief = evening(store, dex=dex, onchain=FakeOnChain(available=False))
    # order should now be filled
    assert store.orders()[0].status == "filled"
    fill_sec = next(s for s in brief.sections if "Filled orders" in s.heading)
    assert "1 order(s) filled" in fill_sec.summary


def test_evening_sell_order_not_filled_when_below_level(store):
    store.add_order(LimitOrder(symbol="SOL", side="sell", price=200,
                               token_address="MintSOL"))
    dex = FakeDex(quotes={"SOL": {"symbol": "SOL", "price": 150.0, "resolved": True}})
    evening(store, dex=dex, onchain=FakeOnChain(available=False))
    assert store.orders()[0].status == "working"


def test_evening_journals_one_line_per_position(store):
    store.add_position(Position(symbol="SOL", token_address="MintSOL",
                               entry_price=150, stop=138))
    store.add_position(Position(symbol="BONK", token_address="BonkMint",
                               entry_price=0.00001, stop=0.000008))
    dex = FakeDex(quotes={
        "SOL": {"symbol": "SOL", "price": 160.0, "resolved": True, "price_change_24h": 5.0},
        "BONK": {"symbol": "BONK", "price": 0.000012, "resolved": True, "price_change_24h": 3.0},
    })
    evening(store, dex=dex, onchain=FakeOnChain(available=False))
    journal = store.journal_read()
    assert len(journal) == 2
    symbols = {e["symbol"] for e in journal}
    assert symbols == {"SOL", "BONK"}


def test_evening_entity_sell_on_holding_is_alert(store):
    store.add_position(Position(symbol="BONK", token_address="BonkMint"))
    store.add_wallet(EntityWallet(address="W1", label="whale_1"))
    move = WalletMove("W1", "whale_1", "sell", "BONK", "BonkMint", 500.0,
                      "solana", "sigS", 222)
    onchain = FakeOnChain({"W1": [move]})
    dex = FakeDex(quotes={"BONK": {"symbol": "BONK", "price": 0.00001, "resolved": True}})
    brief = evening(store, dex=dex, onchain=onchain)
    sell_sec = next(s for s in brief.sections if "sells" in s.heading.lower())
    assert sell_sec.tone == "alert"


def test_evening_netflow_flags_building(store):
    store.add_position(Position(symbol="SOL", token_address="MintSOL"))
    dex = FakeDex(
        quotes={"SOL": {"symbol": "SOL", "price": 150.0, "resolved": True}},
        flows={"SOL": {"symbol": "SOL", "resolved": True, "heat": 2.5,
                       "buy_ratio": 0.7, "price_change_24h": 8.0}},
    )
    brief = evening(store, dex=dex, onchain=FakeOnChain(available=False))
    netflow_sec = next(s for s in brief.sections if "Netflow" in s.heading)
    assert "heating up" in netflow_sec.summary
    assert any("building" in l for l in netflow_sec.lines)


# --- Rendering --------------------------------------------------------------


def test_briefs_render_all_formats(store):
    brief = morning(store, dex=FakeDex(), onchain=FakeOnChain(available=False),
                    catalysts=FakeCatalysts())
    assert "Morning Brief" in brief.to_terminal(use_color=False)
    assert "# ☀️  Morning Brief" in brief.to_markdown()
    html = brief.to_html()
    assert html.startswith("<!doctype html>")
    assert "Morning Brief" in html


def test_dexscreener_parsing_offline():
    """The DexScreener client's derivation logic works without a network call."""
    from daily_driver.sources.dexscreener import DexScreener
    dex = DexScreener()
    pairs = [
        {"chainId": "solana", "baseToken": {"symbol": "SOL", "address": "MintSOL"},
         "priceUsd": "150.5", "liquidity": {"usd": 1_000_000},
         "volume": {"h24": 2_000_000}, "txns": {"h24": {"buys": 700, "sells": 300}},
         "priceChange": {"h24": 5.0}, "pairAddress": "P1", "url": "http://x"},
        {"chainId": "solana", "baseToken": {"symbol": "SOL", "address": "MintSOL"},
         "priceUsd": "150.0", "liquidity": {"usd": 10}, "volume": {"h24": 1},
         "txns": {"h24": {"buys": 1, "sells": 1}}, "priceChange": {"h24": 0.0}},
    ]
    best = dex._best_pair(pairs)
    assert best["pairAddress"] == "P1"  # deepest liquidity wins
