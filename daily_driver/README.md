# Daily Driver — a ten-minute-a-day crypto operating system

> "That's the entire day. Ten minutes total. The rest is patience."

Daily Driver turns a discretionary trading routine into two disciplined,
repeatable briefs. It never touches an exchange or signs a transaction — it
compares **your intent** (positions, stops, theses, limit-order levels) against
**read-only market reality** and tells you exactly what deserves attention.

```
Morning (5 min)                       Evening (5 min)
 1. Scan entity wallets — new buys      1. Positions intact? entity sells?
    on tokens you don't own             2. Any limit orders fill?
 2. Positions: thesis? stop level?         → write the thesis for each
 3. Overnight catalysts                 3. Netflow: anything new building?
 4. Set limit orders for today          4. Journal: one line per position
```

## Quick start

```bash
# From the repo root — no install needed
python3 -m daily_driver status

# Seed your book
python3 -m daily_driver position add SOL --size 250 --entry 150 --stop 138 \
    --address So11111111111111111111111111111111111111112 \
    --thesis "reclaim of range low, whales accumulating"

python3 -m daily_driver wallet add <address> --label whale_6 --tags trader
python3 -m daily_driver order add BONK --side buy --price 0.000009 --size 100 \
    --thesis "entry on the liquidity sweep"

# Run the routines
python3 -m daily_driver morning          # coloured terminal brief
python3 -m daily_driver evening --save    # also drops a markdown copy in reports/
python3 -m daily_driver evening --html brief.html   # standalone web page
```

Entity wallets are auto-seeded on first run from
`config/smart_money_config.json`, so your existing whale list carries over.

## What each source needs (all optional — degrades gracefully)

| Capability | Source | Env var | Without it |
|---|---|---|---|
| Prices / stops / fill detection / netflow | DexScreener | *(none — free)* | prices show `—` |
| Entity-wallet buys & sells | Helius (Solana) | `HELIUS_API_KEY` | wallets "queued", honest not-checked line |
| Overnight catalysts (news / X) | Perplexity | `PERPLEXITY_API_KEY` | prints a manual-check reminder with tickers |

No key ever fabricates data. A missing source produces an honest
"not configured" line, never an invented headline or a phantom fill.

## How fills work

Daily Driver **detects** that the market traded through your level — it does not
place or fill real orders. In the evening routine a buy order flips to `filled`
when price ≤ your level (a sell when price ≥ your level), and step 2 then prompts
you to write the thesis and promote it to a position. Placing the actual order
on your exchange stays a manual, deliberate act.

## State

Everything is human-readable JSON under `data/daily_driver/`:

- `positions.json` — open positions (symbol, size, entry, **stop**, **thesis**)
- `entity_wallets.json` — curated smart-money wallets to shadow
- `limit_orders.json` — working / filled / cancelled levels
- `journal.jsonl` — append-only, one line per position per evening
- `seen.json` — dedupe memory so a wallet move is reported once

Edit by hand, diff in git, back up trivially.

## Automating the two briefs

Match the repo's cron culture — e.g. Europe/Berlin morning & evening:

```cron
# Morning brief 08:00, evening brief 20:00 (server time)
0 8  * * *  cd /path/to/bottedaway && python3 -m daily_driver morning --save
0 20 * * *  cd /path/to/bottedaway && python3 -m daily_driver evening --save
```

## Tests

```bash
python3 -m pytest tests/test_daily_driver.py -q
```

All workflow logic is tested offline with fake sources — deterministic, no
network, no keys.
