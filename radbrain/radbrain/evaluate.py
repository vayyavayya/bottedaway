"""Phase 8 — evaluation harness.

Hold out 10 % of each brain's pairs (deterministic by capture id), mine the rules on the other 90 %, run Correct on
the held-out drafts and compare with the real finals:
  chrF (character n-gram F-score, n = 1..6, beta = 2) and normalised edit distance (word level)
  engine output vs final   against the baseline   untouched draft vs final
Predict mode: of the edits the signer really made (word-level), the share the predictor flagged (recall), and of the
flags the share that were really changed (precision).
Scores on synthetic data are marked synthetic in the stored result and on the dashboard.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import time
from collections import Counter

from . import config, diff, engine, library, miner

HOLDOUT = 0.10


def chrf(hyp: str, ref: str, n: int = 6, beta: float = 2.0) -> float:
    hyp, ref = " ".join(hyp.split()), " ".join(ref.split())
    precs, recs = [], []
    for k in range(1, n + 1):
        h = Counter(hyp[i:i + k] for i in range(max(0, len(hyp) - k + 1)))
        r = Counter(ref[i:i + k] for i in range(max(0, len(ref) - k + 1)))
        if not h or not r:
            continue
        m = sum((h & r).values())
        precs.append(m / sum(h.values()))
        recs.append(m / sum(r.values()))
    if not precs:
        return 0.0
    p, r = sum(precs) / len(precs), sum(recs) / len(recs)
    if p + r == 0:
        return 0.0
    return 100 * (1 + beta ** 2) * p * r / (beta ** 2 * p + r)


def ned(hyp: str, ref: str) -> float:
    """Normalised word-level edit distance (0 = identical)."""
    a, b = diff.tokens(hyp), diff.tokens(ref)
    if not a and not b:
        return 0.0
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    dist = sum(max(i2 - i1, j2 - j1) for t, i1, i2, j1, j2 in sm.get_opcodes() if t != "equal")
    return dist / max(len(a), len(b))


def is_holdout(cid: int) -> bool:
    return int(hashlib.sha1(f"holdout-{cid}".encode()).hexdigest(), 16) % 100 < HOLDOUT * 100


def _joined(c: dict, prefix: str) -> str:
    return "\n".join(x for x in (c.get(f"{prefix}_befund") or "", c.get(f"{prefix}_beurteilung") or "") if x)


def run(con=None, *, llm: bool = False, llm_sample: int = 10) -> dict:
    own = con is None
    con = con or library.connect()
    try:
        caps = library.rows(con, "kind='pair' AND signer IS NOT NULL")
        held = {c["id"] for c in caps if is_holdout(c["id"])}
        synthetic = bool(caps) and all(c["synthetic"] for c in caps)
        # rules from the training part only; restored to the full mine afterwards
        miner.mine(con, exclude_ids=held, write_files=False)
        out = {"at": time.time(), "synthetic": synthetic, "holdout_share": HOLDOUT, "by_signer": {}}
        for code in config.CODES:
            test = [c for c in caps if c["id"] in held and c["signer"] == code]
            if not test:
                continue
            base_c, eng_c, base_e, eng_e = [], [], [], []
            tp = fp = fn = 0
            llm_c, llm_n = [], 0
            for i, c in enumerate(test):
                sections = {"befund": c.get("draft_befund") or "", "beurteilung": c.get("draft_beurteilung") or ""}
                ref, src = _joined(c, "final"), _joined(c, "draft")
                use_llm = llm and llm_n < llm_sample
                r = engine.correct("", code, use_llm=use_llm, con=con, exclude=held, sections=sections,
                                   region=c.get("region"))
                hyp = "\n".join(r["sections_out"].get(k, "") for k in ("befund", "beurteilung"))
                base_c.append(chrf(src, ref))
                eng_c.append(chrf(hyp, ref))
                base_e.append(ned(src, ref))
                eng_e.append(ned(hyp, ref))
                if use_llm:
                    llm_n += 1
                    llm_c.append(chrf(hyp, ref) - chrf(src, ref))
                # predict: token positions in the draft that the signer changed vs flagged
                p = engine.predict("", code, con=con, sections=sections, region=c.get("region"))
                for sec in ("befund", "beurteilung"):
                    d, f = sections.get(sec, ""), c.get(f"final_{sec}") or ""
                    changed = _changed_chars(d, f)
                    flagged = set()
                    for h in p["hits"]:
                        if h["section"] == sec and h["start"] is not None:
                            flagged |= set(range(h["start"], h["end"]))
                    if not changed and not flagged:
                        continue
                    tp += len(changed & flagged)
                    fp += len(flagged - changed)
                    fn += len(changed - flagged)
            avg = lambda x: round(sum(x) / len(x), 2) if x else None  # noqa: E731
            out["by_signer"][code] = {
                "n_test": len(test), "n_train": len([c for c in caps if c["signer"] == code]) - len(test),
                "chrf_draft": avg(base_c), "chrf_engine": avg(eng_c),
                "ned_draft": avg(base_e), "ned_engine": avg(eng_e),
                "predict_recall": round(tp / (tp + fn), 3) if tp + fn else None,
                "predict_precision": round(tp / (tp + fp), 3) if tp + fp else None,
                "llm_n": llm_n, "llm_chrf_gain": avg(llm_c)}
        miner.mine(con)          # back to rules from all pairs
        con.execute("INSERT INTO eval_runs (at, synthetic, result) VALUES (?,?,?)",
                    (out["at"], int(synthetic), json.dumps(out)))
        con.commit()
        return out
    finally:
        if own:
            con.close()


def _changed_chars(d: str, f: str) -> set[int]:
    """Character positions in the draft that were replaced or deleted in the final (insertions: the char before)."""
    sm = difflib.SequenceMatcher(a=d, b=f, autojunk=False)
    out = set()
    for t, i1, i2, j1, j2 in sm.get_opcodes():
        if t in ("replace", "delete"):
            out |= set(range(i1, i2))
    return out


def latest(con) -> dict | None:
    r = con.execute("SELECT result FROM eval_runs ORDER BY id DESC LIMIT 1").fetchone()
    return json.loads(r["result"]) if r else None


def history(con) -> list[dict]:
    return [json.loads(r["result"]) for r in con.execute("SELECT result FROM eval_runs ORDER BY id")]
