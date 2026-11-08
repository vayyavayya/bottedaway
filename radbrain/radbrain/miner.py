"""Phase 5 — correction rule miner.

From every pair's word-level diff (per section) the edits are canonicalised:
  substitution  „eher“ → „am ehesten“
  deletion      „es zeigt sich“ gestrichen  (incl. "Es zeigt sich eine" → "Eine": the case change is not an edit)
  addition      „kein pneumothorax .“ ergänzt (with a learnt condition, e.g. region Thorax)
  numbering     Beurteilung nummeriert
  reordering    Beurteilung umgestellt
An edit becomes a rule for a signer when it recurs (count >= max(3, 3 % of that signer's pairs)) and is consistent
(changed in >= 30 % of the pairs where it could apply). HOUSE STANDARD = a rule for >= 2 of the 3 signers;
PERSONAL = only this signer. Rulebooks are written as rulebook_B1.md … in the data dir (never in the repo).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import Counter, defaultdict

from . import config, diff, library, taxonomy

SECTIONS = ("befund", "beurteilung")
MIN_COUNT = 3
MIN_SHARE = 0.03
MIN_CONSISTENCY = 0.30


def _cf(toks: list[str]) -> list[str]:
    return [t.casefold() for t in toks]


def canonical(op: dict) -> dict | None:
    a, b = diff.tokens(op["before"]), diff.tokens(op["after"])
    ca, cb = _cf(a), _cf(b)
    if op["op"] == "sub":
        # strip a shared case-insensitive prefix/suffix ("Es zeigt sich eine" -> "Eine" == deletion of "es zeigt sich")
        i = 0
        while i < min(len(ca), len(cb)) and ca[i] == cb[i]:
            i += 1
        j = 0
        while j < min(len(ca), len(cb)) - i and ca[len(ca) - 1 - j] == cb[len(cb) - 1 - j]:
            j += 1
        ca, cb = ca[i:len(ca) - j], cb[i:len(cb) - j]
        if not ca and not cb:
            return None                                    # only capitalisation changed
        if not cb:
            return {"op": "del", "before": " ".join(_rotate(ca)), "after": ""}
        if not ca:
            return {"op": "ins", "before": "", "after": " ".join(_rotate(cb))}
        return {"op": "sub", "before": " ".join(ca), "after": " ".join(cb)}
    if op["op"] == "del":
        ca = _rotate(ca)
        return {"op": "del", "before": " ".join(ca), "after": ""} if ca else None
    if op["op"] == "ins":
        cb = _rotate(cb)
        return {"op": "ins", "before": "", "after": " ".join(cb)} if cb else None
    return None


def _rotate(t: list[str]) -> list[str]:
    """". klinische korrelation empfohlen" and "klinische korrelation empfohlen ." are the same insertion."""
    if len(t) > 1 and t[0] in (".", ";", ","):
        return t[1:] + [t[0]]
    return t


def _key(section: str, c: dict) -> str:
    return f"{c['op']}|{section}|{c['before']}|{c['after']}"


def rid(key: str) -> str:
    return "R" + hashlib.sha1(key.encode()).hexdigest()[:6].upper()


def edits_of(capture: dict) -> list[tuple[str, dict]]:
    """[(key, canonical edit)] for one pair, each key once."""
    out, seen = [], set()
    for sec in SECTIONS:
        d = (capture.get("diff") or {}).get(sec)
        if not d:
            continue
        for s in d.get("structure", []):
            c = {"op": s["op"], "before": "", "after": ""}
            k = _key(sec, c)
            if k not in seen:
                seen.add(k)
                out.append((k, c))
        for w in d.get("words", []):
            c = canonical(w)
            if not c:
                continue
            k = _key(sec, c)
            if k not in seen:
                seen.add(k)
                out.append((k, c))
    return out


def _norm_text(s: str) -> str:
    return " ".join(_cf(diff.tokens(s or "")))


def applicable(c: dict, section: str, cap: dict, condition: dict | None = None) -> bool:
    """Could this edit have been made in this pair? (denominator for the consistency check / predict mode)"""
    if condition and condition.get("region") and cap.get("region") != condition["region"]:
        return False
    draft = _norm_text(cap.get(f"draft_{section}") or "")
    if c["op"] in ("sub", "del"):
        return f" {c['before']} " in f" {draft} "
    if c["op"] == "ins":
        return f" {c['after']} " not in f" {draft} "
    if c["op"] == "number":
        return not re.search(r"(^|\n)\s*\d+[.)]\s", cap.get(f"draft_{section}") or "")
    if c["op"] == "reorder":
        return len(diff.sentences(cap.get(f"draft_{section}") or "")) >= 2
    return True


def label_de(c: dict, section: str) -> str:
    sec = "Befund" if section == "befund" else "Beurteilung"
    b, a = diff.detok(c["before"]), diff.detok(c["after"])
    return {"sub": f"„{b}“ → „{a}“ ({sec})",
            "del": f"„{b}“ gestrichen ({sec})",
            "ins": f"„{a}“ ergänzt ({sec})",
            "number": f"{sec} nummeriert",
            "unnumber": f"{sec}: Nummerierung entfernt",
            "reorder": f"{sec}: Reihenfolge umgestellt (Hauptbefund nach vorn)"}.get(c["op"], c["op"])


def explain_en(rule: dict) -> str:
    op, b, a = rule["op"], diff.detok(rule["before"]), diff.detok(rule["after"])
    return {"sub": f'replaces "{b}" with "{a}"', "del": f'cuts "{b}"', "ins": f'adds "{a}"',
            "number": "numbers the Beurteilung points", "unnumber": "removes the numbering",
            "reorder": "puts the main finding first in the Beurteilung"}.get(op, op)


def _example(cap: dict, section: str, c: dict) -> dict:
    d, f = cap.get(f"draft_{section}") or "", cap.get(f"final_{section}") or ""
    ds, fs = diff.sentences(d), diff.sentences(f)
    if c["op"] in ("sub", "del"):
        s_d = next((s for s in ds if f" {c['before']} " in f" {_norm_text(s)} "), ds[0] if ds else "")
    else:
        s_d = ""
    if c["op"] in ("sub", "ins"):
        s_f = next((s for s in fs if f" {c['after']} " in f" {_norm_text(s)} "), fs[-1] if fs else "")
    elif c["op"] in ("number", "reorder"):
        s_d, s_f = " / ".join(ds[:3]), " / ".join(fs[:3])
    else:
        s_f = ""
    return {"capture": cap["id"], "draft": s_d[:300], "final": s_f[:300]}


def mine(con=None, *, exclude_ids: set[int] | None = None, write_files: bool = True) -> dict:
    own = con is None
    con = con or library.connect()
    try:
        caps = [c for c in library.rows(con, "kind='pair' AND signer IS NOT NULL")
                if not exclude_ids or c["id"] not in exclude_ids]
        by_signer: dict[str, list[dict]] = defaultdict(list)
        for c in caps:
            by_signer[c["signer"]].append(c)
        found: dict[str, dict[str, dict]] = {}
        for signer, lst in by_signer.items():
            occ: dict[str, list[dict]] = defaultdict(list)
            edit: dict[str, dict] = {}
            for cap in lst:
                for k, c in edits_of(cap):
                    occ[k].append(cap)
                    edit[k] = c
            need = max(MIN_COUNT, math.ceil(MIN_SHARE * len(lst)))
            rules = {}
            for k, hits in occ.items():
                if len(hits) < need:
                    continue
                section = k.split("|")[1]
                c = edit[k]
                cond = None
                if c["op"] == "ins":
                    regs = Counter(h.get("region") for h in hits)
                    r, n = regs.most_common(1)[0]
                    if r and n / len(hits) >= 0.8:
                        allr = Counter(x.get("region") for x in lst)
                        if allr[r] < 0.8 * len(lst):     # only a condition if the region is not everything
                            cond = {"region": r}
                present = sum(1 for cap in lst if applicable(c, section, cap, cond)) or len(hits)
                present = max(present, len(hits))
                if len(hits) / present < MIN_CONSISTENCY:
                    continue
                hit_ids = sorted(h["id"] for h in hits)
                rules[k] = {"key": k, "signer": signer, "rid": rid(k), "op": c["op"], "section": section,
                            "before": c["before"], "after": c["after"], "count": len(hits), "present": present,
                            "pairs": len(lst), "condition": cond, "label": label_de(c, section),
                            "examples": [_example(h, section, c) for h in sorted(hits, key=lambda h: -h["id"])[:2]],
                            "birth_capture": hit_ids[need - 1]}
            found[signer] = rules
        signers_of: dict[str, set] = defaultdict(set)
        for s, rules in found.items():
            for k in rules:
                signers_of[k].add(s)
        old = {(r["key"], r["signer"]) for r in con.execute("SELECT key, signer FROM rules")}
        con.execute("DELETE FROM rules")
        now = time.time()
        total = new = 0
        for s, rules in found.items():
            for k, r in rules.items():
                r["scope"] = "HOUSE STANDARD" if len(signers_of[k]) >= 2 else "PERSONAL"
                r["shared_with"] = sorted(signers_of[k] - {s})
                con.execute("INSERT INTO rules (key, signer, rid, op, section, before, after, label, scope, count, "
                            "present, pairs, condition, examples, birth_capture, mined_at) VALUES "
                            "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                            (k, s, r["rid"], r["op"], r["section"], r["before"], r["after"], r["label"], r["scope"],
                             r["count"], r["present"], r["pairs"], json.dumps(r["condition"]),
                             json.dumps(r["examples"], ensure_ascii=False), r["birth_capture"], now))
                total += 1
                new += (k, s) not in old
        synthetic = all(c["synthetic"] for c in caps) if caps else False
        con.execute("INSERT INTO mine_runs (at, pairs, rules, new_rules, synthetic) VALUES (?,?,?,?,?)",
                    (now, len(caps), total, new, int(synthetic)))
        con.commit()
        if write_files and not exclude_ids:
            write_rulebooks(con, synthetic=synthetic)
        return {"pairs": len(caps), "rules": total, "new_rules": new,
                "by_signer": {s: len(r) for s, r in found.items()}}
    finally:
        if own:
            con.close()


def rules_for(con, signer: str) -> list[dict]:
    out = []
    for r in con.execute("SELECT * FROM rules WHERE signer=? ORDER BY scope, count DESC", (signer,)):
        d = dict(r)
        d["condition"] = json.loads(d["condition"]) if d["condition"] else None
        d["examples"] = json.loads(d["examples"] or "[]")
        d["consistency"] = round(d["count"] / max(1, d["present"]), 2)
        out.append(d)
    return out


def write_rulebooks(con, synthetic: bool = False) -> list:
    paths = []
    for code in config.CODES:
        rules = rules_for(con, code)
        n = con.execute("SELECT COUNT(*) FROM captures WHERE kind='pair' AND signer=?", (code,)).fetchone()[0]
        lines = [f"# Rulebook {code} ({config.ROLES[code]})", "",
                 f"Mined {time.strftime('%d.%m.%Y %H:%M')} from {n} correction pairs."
                 + (" **SYNTHETIC DATA — not a real signer.**" if synthetic else ""), "",
                 "Rule = recurring edit (≥ 3 pairs and ≥ 3 % of this signer's pairs, changed in ≥ 30 % of the pairs "
                 "where it applies). HOUSE STANDARD = at least 2 of 3 signers do it; PERSONAL = only this signer.", ""]
        for scope in ("HOUSE STANDARD", "PERSONAL"):
            sel = [r for r in rules if r["scope"] == scope]
            lines += [f"## {scope} ({len(sel)})", ""]
            for r in sel:
                cond = f" — nur bei {r['condition']['region']}" if r["condition"] else ""
                lines.append(f"### {r['rid']} · {r['label']}{cond}")
                lines.append(f"- count {r['count']} / {r['present']} applicable pairs "
                             f"(consistency {r['consistency']:.0%})")
                for ex in r["examples"]:
                    lines.append(f"- Beispiel #{ex['capture']}: _{ex['draft'] or '—'}_ → **{ex['final'] or '—'}**")
                lines.append("")
        p = config.data_dir() / "rulebooks" / f"rulebook_{code}.md"
        p.write_text("\n".join(lines), encoding="utf-8")
        paths.append(p)
    return paths


def saturation(con) -> dict:
    """{signer: {entity: {"n": captures, "saturated": bool, "since_new": k}}} over pairs, chronological."""
    births = defaultdict(set)
    for r in con.execute("SELECT signer, birth_capture FROM rules"):
        births[r["signer"]].add(r["birth_capture"])
    out: dict[str, dict] = {c: {} for c in config.CODES}
    caps = library.rows(con, "kind='pair' AND signer IS NOT NULL")
    by = defaultdict(list)
    for c in caps:
        for p in c["pathologies"] or ["(ohne)"]:
            by[(c["signer"], p)].append(c["id"])
    for (s, p), ids in by.items():
        last_birth = max((i for i in ids if i in births[s]), default=None)
        since = len([i for i in ids if last_birth is None or i > last_birth])
        out.setdefault(s, {})[p] = {"n": len(ids), "since_new": since,
                                    "saturated": len(ids) >= config.SATURATION_WINDOW
                                    and since >= config.SATURATION_WINDOW}
    return out


def open_next(con, limit: int = 12) -> dict:
    """Per signer: which entities to open next in PACS (not saturated, fewest captures first)."""
    sat = saturation(con)
    finals = defaultdict(Counter)
    for c in library.rows(con, "signer IS NOT NULL"):
        for p in c["pathologies"]:
            finals[c["signer"]][p] += 1
    out = {}
    for s in config.CODES:
        items = []
        for e in taxonomy.ENTITIES:
            st = sat.get(s, {}).get(e.key, {"n": 0, "since_new": 0, "saturated": False})
            if st["saturated"]:
                continue
            items.append({"entity": e.key, "label": e.label, "pairs": st["n"], "all": finals[s][e.key],
                          "need": max(0, config.SATURATION_WINDOW - st["since_new"])})
        items.sort(key=lambda x: (x["pairs"], x["all"]))
        out[s] = items[:limit]
    return out
