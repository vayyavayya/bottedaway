"""
The workflow — morning and evening routines.

Each function reads state + market reality and returns a ``Brief``. Side
effects are deliberate and minimal:

  * evening() detects limit-order fills (market traded through your level) and
    flips those orders to ``filled`` so step 2 can prompt you to write a thesis.
  * both routines record entity-wallet moves into ``seen`` memory so the same
    buy/sell is never reported twice.
  * evening() appends the journal (step 4).

Nothing here places or cancels a real order or signs a transaction. It compares
*your intent* (positions, stops, orders, theses) against read-only market data
and tells you what deserves your attention. The rest is patience.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .brief import Brief, Section
from .sources import Catalysts, DexScreener, OnChain
from .state import LimitOrder, Position, Store, utcnow


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _fmt_price(p: Optional[float]) -> str:
    if p is None:
        return "—"
    if p >= 1:
        return f"${p:,.4f}".rstrip("0").rstrip(".")
    return f"${p:.8f}".rstrip("0").rstrip(".")


def _pct(v: Optional[float]) -> str:
    if v is None:
        return "—"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}%"


def _scan_entity_wallets(store: Store, onchain: OnChain,
                         want: str) -> Tuple[Section, List[dict]]:
    """
    want="buy"  -> morning: new buys on tokens you DON'T own.
    want="sell" -> evening: sells on tokens you DO own (exit signal).
    Returns the section plus the raw new moves recorded.
    """
    wallets = store.entity_wallets()
    owned_syms = store.owned_symbols()
    owned_addrs = store.owned_addresses()
    seen = store.seen()
    seen_keys = set(seen.get("buys", []) + seen.get("sells", []))

    if not wallets:
        return Section(
            heading="Entity wallets",
            summary="No entity wallets configured — add some with `daily-driver wallet add`.",
            tone="warn",
        ), []

    if not onchain.available:
        return Section(
            heading="Entity wallets",
            summary=f"On-chain scan not configured (set HELIUS_API_KEY). "
                    f"{len(wallets)} wallet(s) queued for scanning.",
            tone="warn",
            lines=[f"{w.label or w.address[:8]} — {w.address}" for w in wallets[:8]],
        ), []

    fresh: List[dict] = []
    for w in wallets:
        for mv in onchain.recent_moves(w.address, w.label or w.address[:6], w.chain):
            if mv.action != want:
                continue
            if mv.key in seen_keys:
                continue
            addr = (mv.token_address or "").lower()
            sym = mv.token_symbol.upper()
            if want == "buy":
                # New buys on tokens you DON'T already own.
                if addr in owned_addrs or sym in owned_syms:
                    continue
            else:  # sell
                # Sells only matter on tokens you DO own.
                if not (addr in owned_addrs or sym in owned_syms):
                    continue
            fresh.append(mv.to_dict())
            seen_keys.add(mv.key)

    # Persist dedupe memory.
    bucket = "buys" if want == "buy" else "sells"
    seen.setdefault(bucket, [])
    seen[bucket].extend(m["wallet"] + ":" + m["signature"] + ":" + m["token_address"] + ":" + m["action"]
                        for m in fresh)
    store.save_seen(seen)

    if not fresh:
        verb = "new buys on unowned tokens" if want == "buy" else "sells on your holdings"
        return Section(heading="Entity wallets",
                       summary=f"No {verb} across {len(wallets)} wallet(s).",
                       tone="good"), []

    lines = []
    for m in fresh[:15]:
        amt = f"{m['amount']:,.2f}" if m["amount"] else "?"
        lines.append(f"{m['wallet_label']} {m['action'].upper()} {m['token_symbol']} "
                     f"({amt}) — {m['token_address']}")
    tone = "alert" if want == "sell" else "warn"
    verb = "new buy(s) to research" if want == "buy" else "SELL(S) on your holdings"
    return Section(heading="Entity wallets", summary=f"{len(fresh)} {verb}.",
                   tone=tone, lines=lines), fresh


def _review_positions(store: Store, dex: DexScreener, evening: bool) -> Section:
    positions = store.positions()
    if not positions:
        return Section(heading="Open positions",
                       summary="Flat — no open positions. Patience.", tone="neutral")

    lines: List[str] = []
    breached = 0
    for p in positions:
        q = dex.quote(p.symbol, p.chain, p.token_address)
        price = q.get("price")
        chg = q.get("price_change_24h")
        status = "thesis intact"
        tone_flag = ""
        if price is not None and p.stop is not None:
            if price <= p.stop:
                status = f"⚠ STOP BREACHED (stop {_fmt_price(p.stop)})"
                breached += 1
                tone_flag = "!"
            else:
                dist = (price - p.stop) / price * 100 if price else 0
                status = f"stop {_fmt_price(p.stop)} ({dist:.1f}% away)"
        elif p.stop is None:
            status = "no stop set"
        pnl = ""
        if price is not None and p.entry_price:
            pnl = f", {_pct((price - p.entry_price) / p.entry_price * 100)} from entry"
        lines.append(f"{tone_flag}{p.symbol}: {_fmt_price(price)} ({_pct(chg)} 24h){pnl} — "
                     f"{status}. Thesis: {p.thesis or '—'}")

    tone = "alert" if breached else "good"
    summ = (f"{breached} position(s) with stop breached — decide now."
            if breached else f"{len(positions)} position(s), all above stop.")
    return Section(heading="Open positions", summary=summ, tone=tone, lines=lines)


# ---------------------------------------------------------------------------
# Morning
# ---------------------------------------------------------------------------


def morning(store: Optional[Store] = None,
            dex: Optional[DexScreener] = None,
            onchain: Optional[OnChain] = None,
            catalysts: Optional[Catalysts] = None) -> Brief:
    store = store or Store()
    dex = dex or DexScreener()
    onchain = onchain or OnChain()
    catalysts = catalysts or Catalysts()

    brief = Brief(title="☀️  Morning Brief", subtitle=f"{utcnow()} · scan · review · catalysts · orders")

    # 1. Entity wallets — new buys on tokens I don't own.
    sec1, _ = _scan_entity_wallets(store, onchain, want="buy")
    brief.add(sec1)

    # 2. Open positions — thesis intact? stop correct?
    brief.add(_review_positions(store, dex, evening=False))

    # 3. Overnight catalysts.
    watch_syms = sorted(store.owned_symbols() | {o.symbol.upper() for o in store.working_orders()})
    cat = catalysts.scan(watch_syms)
    cat_lines = [f"{i['symbol']}: {i['note']}" for i in cat.get("items", []) if i.get("note")]
    brief.add(Section(heading="Overnight catalysts", summary=cat["summary"],
                      tone="warn" if (cat.get("available") and cat_lines) else "neutral",
                      lines=cat_lines))

    # 4. Set limit orders for today's levels.
    working = store.working_orders()
    if working:
        olines = [f"{o.side.upper()} {o.symbol} @ {_fmt_price(o.price)} "
                  f"(${o.size_usd:,.0f}) — {o.thesis or 'plan pending'}" for o in working]
        summ = f"{len(working)} working order(s). Confirm levels still valid, then place on exchange."
        tone = "neutral"
    else:
        olines = []
        summ = "No working orders. Add today's levels with `daily-driver order add`."
        tone = "warn"
    brief.add(Section(heading="Limit orders for today", summary=summ, tone=tone, lines=olines))

    return brief


# ---------------------------------------------------------------------------
# Evening
# ---------------------------------------------------------------------------


def _detect_fills(store: Store, dex: DexScreener) -> List[LimitOrder]:
    """
    Detect that the market traded through a working order's level and flip it to
    ``filled``. A buy fills when price <= level; a sell fills when price >= level.
    Returns the orders newly marked filled.
    """
    orders = store.orders()
    newly: List[LimitOrder] = []
    changed = False
    for o in orders:
        if o.status != "working":
            continue
        q = dex.quote(o.symbol, o.chain, o.token_address)
        price = q.get("price")
        if price is None:
            continue
        hit = (o.side == "buy" and price <= o.price) or (o.side == "sell" and price >= o.price)
        if hit:
            o.status = "filled"
            o.filled_at = utcnow()
            newly.append(o)
            changed = True
    if changed:
        store.save_orders(orders)
    return newly


def evening(store: Optional[Store] = None,
            dex: Optional[DexScreener] = None,
            onchain: Optional[OnChain] = None,
            auto_journal: bool = True) -> Brief:
    store = store or Store()
    dex = dex or DexScreener()
    onchain = onchain or OnChain()

    brief = Brief(title="🌙  Evening Brief", subtitle=f"{utcnow()} · positions · fills · netflow · journal")

    # 1. Open positions + entity-wallet sells.
    brief.add(_review_positions(store, dex, evening=True))
    sell_sec, _ = _scan_entity_wallets(store, onchain, want="sell")
    sell_sec.heading = "Entity-wallet sells"
    brief.add(sell_sec)

    # 2. Did any limit orders fill? If yes, write the thesis.
    fills = _detect_fills(store, dex)
    if fills:
        flines = [f"FILLED {o.side.upper()} {o.symbol} @ {_fmt_price(o.price)} — "
                  f"write thesis: `daily-driver position add {o.symbol} ...` "
                  f"(order note: {o.thesis or '—'})" for o in fills]
        brief.add(Section(heading="Filled orders → write thesis",
                          summary=f"{len(fills)} order(s) filled today. Turn each into a position with a thesis.",
                          tone="warn", lines=flines))
    else:
        working = store.working_orders()
        brief.add(Section(heading="Filled orders → write thesis",
                          summary=(f"No fills today. {len(working)} order(s) still working."
                                   if working else "No fills, no working orders."),
                          tone="neutral"))

    # 3. Scan netflow — anything new building since this morning?
    watch_syms = sorted(store.owned_symbols() | {o.symbol.upper() for o in store.orders()})
    nlines: List[str] = []
    building = 0
    for sym in watch_syms:
        pos = next((p for p in store.positions() if p.symbol.upper() == sym), None)
        addr = pos.token_address if pos else None
        chain = pos.chain if pos else "solana"
        nf = dex.netflow(sym, chain, addr)
        if not nf.get("resolved"):
            continue
        heat, buy_ratio = nf["heat"], nf["buy_ratio"]
        flag = ""
        if heat >= 1.0 and buy_ratio >= 0.6:
            flag = "🔥 building"
            building += 1
        elif buy_ratio <= 0.4:
            flag = "distribution"
        nlines.append(f"{sym}: heat {heat}x liq, buy-ratio {buy_ratio:.0%}, "
                      f"{_pct(nf.get('price_change_24h'))} 24h {flag}".rstrip())
    brief.add(Section(heading="Netflow scan",
                      summary=(f"{building} name(s) heating up." if building
                               else "Nothing unusual building." if nlines
                               else "No tokens to scan netflow on."),
                      tone="warn" if building else "neutral", lines=nlines))

    # 4. Journal — one line on every position.
    positions = store.positions()
    jlines: List[str] = []
    entries = []
    for p in positions:
        q = dex.quote(p.symbol, p.chain, p.token_address)
        price = q.get("price")
        line = _default_journal_line(p, price)
        jlines.append(line)
        entries.append({"ts": utcnow(), "symbol": p.symbol, "price": price,
                        "note": line, "auto": True})
    if not positions:
        jlines = ["Flat. Nothing to journal. Patience."]
    if auto_journal and entries:
        store.journal_append(entries)
    brief.add(Section(heading="Journal (one line per position)",
                      summary="Appended to journal." if (auto_journal and entries)
                              else "Nothing journalled." if not entries else "Preview (not saved).",
                      tone="neutral", lines=jlines))

    return brief


def _default_journal_line(p: Position, price: Optional[float]) -> str:
    if price is None:
        return f"{p.symbol}: price unavailable — thesis {'intact' if p.thesis else 'undocumented'}."
    if p.stop is not None and price <= p.stop:
        return f"{p.symbol}: STOP HIT at {_fmt_price(price)} — reassess / exit."
    if p.entry_price:
        chg = (price - p.entry_price) / p.entry_price * 100
        mood = "in profit" if chg >= 0 else "underwater"
        return f"{p.symbol}: holding — {_fmt_price(price)} ({_pct(chg)}), {mood}, thesis intact."
    return f"{p.symbol}: holding — {_fmt_price(price)}, consolidation, thesis intact."
