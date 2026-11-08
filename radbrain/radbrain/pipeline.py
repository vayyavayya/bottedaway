"""One capture: anonymise → (quarantine | library) → re-mine trigger. The only entry point the capture tool calls.

Raw text exists only inside this call. A capture that fails the anonymiser goes to the local quarantine folder
(data dir, never synced) as JSON with the reasons, for Ajit to review in the dashboard; it is released (scrubbed
text as he confirms it) or discarded there. Nothing else ever writes raw text.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path

from . import anonymise, config, diff, library, signers_auto, taxonomy

log = logging.getLogger("radbrain.pipeline")


def _log(msg: str) -> None:
    """Statuses and codes only — never report text."""
    try:
        with (config.data_dir() / "logs" / "pipeline.log").open("a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def _quarantine(kind: str, draft: str | None, final: str, reasons: list[str], source: str) -> str:
    qid = time.strftime("%Y%m%d-%H%M%S-") + hashlib.sha256((final or "").encode()).hexdigest()[:8]
    p = config.quarantine_dir() / f"{qid}.json"
    p.write_text(json.dumps({"id": qid, "kind": kind, "draft": draft, "final": final, "reasons": reasons,
                             "source": source, "at": time.time()}, ensure_ascii=False), encoding="utf-8")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return qid


def tag(final_sections: dict, exam: str) -> tuple[str | None, str | None, list[str]]:
    allt = "\n".join([exam] + [final_sections.get(k, "") for k in ("technik", "befund", "beurteilung")])
    mod = taxonomy.modality(exam) or taxonomy.modality(allt)
    reg = taxonomy.region(exam + "\n" + allt)
    paths = taxonomy.pathologies(final_sections.get("beurteilung", ""), final_sections.get("befund", ""), mod)
    return mod, reg, paths


def ingest(kind: str, draft_text: str | None, final_text: str, source: str = "hotkey", *, synthetic: bool = False,
           force_release: bool = False, con=None, remine: bool = True) -> dict:
    """kind 'pair' (draft + final) or 'final'. Returns status saved | quarantined | duplicate (+ codes/tags)."""
    if kind not in ("pair", "final"):
        raise ValueError("kind must be pair or final")
    sig = config.signers()
    rf = anonymise.anonymise(final_text, sig)
    rd = anonymise.anonymise(draft_text, sig) if kind == "pair" and draft_text else None
    reasons = list(rf.reasons) + ([f"Entwurf: {x}" for x in rd.reasons] if rd else [])
    if kind == "pair" and not (draft_text or "").strip():
        reasons.append("Entwurf leer")
    if reasons and not force_release:
        qid = _quarantine(kind, draft_text, final_text, reasons, source)
        _log(f"quarantined {qid} kind={kind} reasons={len(reasons)}")
        return {"status": "quarantined", "id": None, "quarantine_id": qid, "signer": rf.signer, "modality": None,
                "region": None, "pathologies": [], "reason": "; ".join(reasons)}
    mod, reg, paths = tag(rf.sections, rf.exam)
    dsec = rd.sections if rd else None
    pf = signers_auto.from_lines(rf.signature)
    pdr = signers_auto.from_lines(rd.signature) if rd else []
    fmain = next((x for x in pf if x["kind"] == "final"), pf[0] if pf else None)
    dmain = next((x for x in pdr if x["kind"] == "draft"), pdr[0] if pdr else None)
    signer_key = signers_auto.key(fmain["surname"]) if fmain else None
    author_key = signers_auto.key(dmain["surname"]) if dmain else None
    known_codes = signers_auto.assigned()
    signer = rf.signer or (known_codes.get(signer_key) if known_codes.get(signer_key) in config.CODES else None)
    rf.signer = signer
    row = dict(kind=kind, signer=signer, signer_key=signer_key, author_key=author_key,
               author_is_me=int(bool(rd and (rd.author_is_me or known_codes.get(author_key) == "me"))),
               modality=mod, region=reg,
               exam=rf.exam, pathologies=paths, fragestellung=rf.sections.get("fragestellung"),
               technik=rf.sections.get("technik"), final_befund=rf.sections.get("befund"),
               final_beurteilung=rf.sections.get("beurteilung"), source=source, synthetic=int(synthetic),
               content_hash=library.content_hash(kind, dsec, rf.sections))
    if dsec is not None:
        row.update(draft_befund=dsec.get("befund"), draft_beurteilung=dsec.get("beurteilung"),
                   diff=diff.diff_sections(dsec, rf.sections),
                   change_rate=diff.change_rate("\n".join(dsec.get(k, "") for k in ("befund", "beurteilung")),
                                                "\n".join(rf.sections.get(k, "") for k in ("befund", "beurteilung"))))
    own = con is None
    con = con or library.connect()
    try:
        cid = library.insert(con, **row)
        con.commit()
        if cid is None:
            _log(f"duplicate kind={kind} signer={rf.signer}")
            return {"status": "duplicate", "id": None, "signer": rf.signer, "modality": mod, "region": reg,
                    "pathologies": paths, "reason": "identische Erfassung"}
        signers_auto.observe(pf, "final")
        if pdr:
            signers_auto.observe(pdr, "draft")
        auto = signers_auto.auto_assign(con)
        if auto:
            _log(f"auto-assigned {','.join(auto)}")
            rf.signer = rf.signer or con.execute("SELECT signer FROM captures WHERE id=?", (cid,)).fetchone()[0]
        _log(f"saved {cid} kind={kind} signer={rf.signer} mod={mod} reg={reg} path={','.join(paths)}")
        if remine and kind == "pair":
            maybe_remine(con, synthetic=synthetic)
        return {"status": "saved", "id": cid, "signer": rf.signer, "modality": mod, "region": reg,
                "pathologies": paths, "reason": "" if rf.signer else "Unterzeichner nicht erkannt (signers.json)"}
    finally:
        if own:
            con.close()


def maybe_remine(con, synthetic: bool = False) -> bool:
    n = con.execute("SELECT COUNT(*) FROM captures WHERE kind='pair' AND signer IS NOT NULL").fetchone()[0]
    last = library.kv_get(con, "last_mine_pairs", 0)
    if n - last >= config.REMINE_EVERY:
        from . import miner
        miner.mine(con)
        library.kv_set(con, "last_mine_pairs", n)
        con.commit()
        try:
            from . import evaluate
            evaluate.run(con, llm=False)
        except Exception as e:  # noqa: BLE001
            _log(f"eval after re-mine failed: {type(e).__name__}")
        return True
    return False


def counts() -> dict:
    return library.counts()


# ------------------------------------------------------------------------------------------------- quarantine review
def quarantine_list() -> list[dict]:
    out = []
    for p in sorted(config.quarantine_dir().glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.append({"id": d["id"], "kind": d["kind"], "reasons": d["reasons"], "at": d["at"]})
    return out


def quarantine_preview(qid: str) -> dict:
    """What the anonymiser WOULD keep, with the words it could not explain marked — for Ajit's review (local only)."""
    d = _q_load(qid)
    sig = config.signers()
    rf = anonymise.anonymise(d["final"], sig)
    rd = anonymise.anonymise(d["draft"], sig) if d.get("draft") else None
    unk = anonymise.unknown_tokens(rf.text + "\n" + rf.exam + ("\n" + rd.text if rd else ""))
    return {"id": qid, "kind": d["kind"], "reasons": d["reasons"], "final_scrubbed": rf.text,
            "draft_scrubbed": rd.text if rd else None, "unknown_words": unk, "signer": rf.signer}


def quarantine_release(qid: str, cleared_words: list[str] | None = None) -> dict:
    """Ajit confirmed the scrubbed version is clean: the unknown words he cleared join the local allowlist and the
    capture is ingested (scrubbing still runs; only the residual check is overridden)."""
    d = _q_load(qid)
    if cleared_words:
        anonymise.add_to_allowlist(cleared_words)
    res = ingest(d["kind"], d.get("draft"), d["final"], source=d.get("source", "hotkey") + "+released",
                 force_release=True)
    _q_path(qid).unlink(missing_ok=True)
    return res


def quarantine_discard(qid: str) -> None:
    _q_path(qid).unlink(missing_ok=True)


def _q_path(qid: str) -> Path:
    if not all(ch.isalnum() or ch == "-" for ch in qid):
        raise ValueError("bad id")
    return config.quarantine_dir() / f"{qid}.json"


def _q_load(qid: str) -> dict:
    return json.loads(_q_path(qid).read_text(encoding="utf-8"))
