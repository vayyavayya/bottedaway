# Iran–US War · Live Dashboard

Five numbers, no narrative. A situational-awareness board that shows the war
**ending in the data before it ends in the headlines** — the moment
tanker-interference falls while Hormuz transits climb.

![five numbers: launches, interference, transits, VLCC completions, Brent backwardation]

## The five numbers

| # | Metric | Reads the war as | Good direction |
|---|--------|------------------|----------------|
| 1 | **Iranian launches / week** | ability-to-hurt (near-zero = gone) | ↓ |
| 2 | **Tanker-interference incidents / week** | the true endgame gauge | ↓ |
| 3 | **Hormuz transits / day** | strait reopening (sustained >30–40 under escort) | ↑ |
| 4 | **VLCC completions / week** | the corridor being proven, hull by hull | ↑ |
| 5 | **Brent backwardation (M1–M3), Monday** | physical tightness relaxing early | ↓ |

Plus: **Brent** and **US 10Y** price series with war events overlaid, and
**Pearson correlations** between each conflict metric and Brent (and Brent↔US10Y).

**The end-signal** lights up automatically when interference falls *and* transits
rise in the same week — "capacity failure arriving."

## Quick start

```bash
pip install -r requirements.txt
python build.py            # fetch live Brent + US10Y, assemble, render
open dashboard.html        # standalone, data embedded — no server needed
```

`build.py` writes two things:

- `data/dashboard.json` — the assembled data model (machine-readable)
- `dashboard.html` — a **self-contained** dashboard (open it directly, or publish
  it as a Claude artifact)

Offline / no network? `python build.py --offline` reuses the last market series.
To use the fetch-based page instead of the embedded one: `python serve.py` then
open `http://localhost:8000/template.html`.

## Where the data comes from

**Market data is live and automatic.** Brent (`cb.f`) and US 10Y yield (`10usy.b`)
are pulled from Stooq's free daily CSV — no API key.

**The conflict data is OSINT-fed — there is no free real-time API for it.** The four
conflict metrics and the Brent forward curve live in `data/*.json`. Each block lists
its sources. Refresh them each period (weekly, plus Monday for the curve):

| File | What to update | Sources |
|------|----------------|---------|
| `data/conflict.json` | launches, interference, transits, VLCC — append `{period,value}` | UKMTO · Lloyd's List · Ambrey/Dryad · Kpler/Vortexa · TankerTrackers · ACLED · ISW |
| `data/curve.json` | Monday Brent M1–M6 + M1–M3 spread history | ICE Brent settlements · Barchart · Investing.com |
| `data/events.json` | war-arc phase index + dated timeline events | ISW · news wires |

> ⚠️ The numbers shipped in `data/*.json` are **illustrative seed data** so the
> dashboard renders end-to-end. Replace them with sourced values before relying on
> anything. The header shows a `SEED DATA` badge until you set `"provenance"` to
> something other than `seed-placeholder`.

## Feeding it to Claude Cowork

This repo is built for an agent to keep alive. A typical Cowork loop:

1. **Refresh conflict data** — read each metric's `sources`, gather the latest
   period's values, append a `{period, value}` object to each series in
   `data/conflict.json`. Update `data/curve.json` every Monday and advance the arc
   phase / add events in `data/events.json`.
2. **Rebuild** — `python build.py` (pulls fresh Brent + US10Y, recomputes deltas,
   correlations, backwardation, and the end-signal).
3. **Publish** — open/publish `dashboard.html` as an artifact, or commit it.

Everything downstream of the JSON is automatic, so Cowork only ever edits the small
data files and reruns one command.

## Files

```
build.py          fetch market data + assemble + render   (stdlib + requests)
template.html     the dashboard UI (vanilla JS, inline-SVG charts, no deps)
serve.py          optional static server for the fetch-based page
data/
  conflict.json   the 4 OSINT conflict metrics  (edit me)
  curve.json      Brent forward curve snapshot   (edit me, Mondays)
  events.json     war-arc phases + timeline      (edit me)
  dashboard.json  generated model                (output)
dashboard.html    generated standalone dashboard (output)
```

Not trading advice. Correlation is not causation; conflict metrics are
noisy and source-dependent. Built for situational awareness.
