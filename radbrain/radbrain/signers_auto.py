"""Local signer discovery — so Ajit does not have to type names into signers.json.

From the signature lines of every capture (drafts: "Entwurf/Erstellt von …", finals: "Elektronisch signiert/
freigegeben …") the surname and the role word (Chefarzt, Leitender Oberarzt, Oberarzt …) are collected into
<data dir>/signer_candidates.json — ON THE PC ONLY, file mode 600, never logged, never in the repo, never sent anywhere.
Captures store only a salted hash key of the name (signer_key / author_key) so they can be assigned retroactively.

Auto-assignment (high confidence only): exactly one surname ever signs as "Chefarzt/Chefärztin" (>= 2 finals)
→ B1; exactly one as "Leitende(r) Oberarzt/-ärztin" → B2. B3 (one particular Oberarzt), "me" and "staff" are one
click in the dashboard (tab Unterzeichner). Every assignment also updates the captures that were saved before it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time

from . import config, library

ROLE_RX = [("leitend", re.compile(r"leitende[rn]?\s+ober(arzt|ärztin)|\bLOA\b|\bLOÄ\b", re.I)),
           ("chefarzt", re.compile(r"chef(arzt|ärztin)|\bCA\b|\bCÄ\b|klinikdirektor", re.I)),
           ("oberarzt", re.compile(r"ober(arzt|ärztin)|\bOA\b|\bOÄ\b", re.I)),
           ("facharzt", re.compile(r"fach(arzt|ärztin)|\bFA\b", re.I)),
           ("assistenz", re.compile(r"assistenz(arzt|ärztin)|weiterbildung", re.I))]
FINAL_RX = re.compile(r"signiert|freigegeben|vidiert|validiert|unterschrieben|gez\.", re.I)
DRAFT_RX = re.compile(r"entwurf|erstellt|diktiert|geschrieben|befundet|vorläufig", re.I)
TITLE_TOK = re.compile(r"^(prof\.?|dr\.?|med\.?|habil\.?|pd|priv\.-?doz\.?|dipl\.-?med\.?|univ\.?|m\.?d\.?|"
                       r"herr|frau|von|van|de)$", re.I)
CAP_TOK = re.compile(r"^[A-ZÄÖÜÀ-ÞĀ-Ž][\wäöüßà-ÿā-ž'’-]+$")
ROLE_WORDS = re.compile(r"(arzt|ärztin|LOA|LOÄ|OA|OÄ|CA|CÄ|FA|Klinik|Radiologie|Abteilung|Institut|Elektronisch|"
                        r"Signiert|Freigegeben|Entwurf|Erstellt)$", re.I)


def _path():
    return config.data_dir() / "signer_candidates.json"


def key(surname: str) -> str:
    return hashlib.sha256(("radbrain-signer:" + surname.strip().casefold()).encode()).hexdigest()[:16]


def parse_line(line: str) -> dict | None:
    """'Elektronisch signiert: Prof. Dr. med. Xyz, Chefarzt, 12.03.2024' → {surname, role, kind}."""
    kind = "final" if FINAL_RX.search(line) else "draft" if DRAFT_RX.search(line) else None
    body = line.split(":", 1)[1] if ":" in line and (kind or re.match(r"^\s*\w+\s*:", line)) else line
    body = re.sub(r"\d{1,2}[.:/-]\d{1,2}([.:/-]\d{2,4})?", " ", body)
    chunk = body.split(",")[0]
    toks = [t.strip(" .;()") for t in chunk.split()]
    names = [t for t in toks if t and not TITLE_TOK.match(t + ("." if not t.endswith(".") else ""))
             and not TITLE_TOK.match(t) and CAP_TOK.match(t) and not ROLE_WORDS.search(t)]
    if not names:
        return None
    role = next((r for r, rx in ROLE_RX if rx.search(line)), None)
    return {"surname": names[-1], "role": role, "kind": kind}


def from_lines(lines: list[str]) -> list[dict]:
    out = []
    for ln in lines:
        p = parse_line(ln)
        if p:
            out.append(p)
    return out


def load() -> dict:
    p = _path()
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(d: dict) -> None:
    p = _path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass


def observe(parsed: list[dict], as_kind: str) -> str | None:
    """Record names seen in one capture's signature block. Returns the key of the main one (or None)."""
    if not parsed:
        return None
    want = [p for p in parsed if p["kind"] == as_kind] or parsed
    main = want[0]
    d = load()
    now = time.time()
    for p in want[:2]:
        k = key(p["surname"])
        e = d.setdefault(k, {"name": p["surname"], "roles": {}, "final": 0, "draft": 0, "first": now})
        e[as_kind] = e.get(as_kind, 0) + 1
        if p["role"]:
            e["roles"][p["role"]] = e["roles"].get(p["role"], 0) + 1
        e["last"] = now
    _save(d)
    return key(main["surname"])


def assigned() -> dict:
    """key → code (B1/B2/B3/me/staff) from signers.json."""
    sig = config.signers()
    out = {}
    for code in config.CODES:
        for n in sig.by_code.get(code, []):
            out[key(n)] = code
    for n in sig.me:
        out[key(n)] = "me"
    for n in sig.staff:
        out[key(n)] = "staff"
    return out


def assign(k: str, code: str, con=None) -> dict:
    if code not in config.CODES + ("me", "staff", "none"):
        raise ValueError("code")
    d = load()
    if k not in d:
        raise ValueError("unknown signer")
    name = d[k]["name"]
    p = config.data_dir() / "signers.json"
    raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"signers": {}, "me": [], "staff": []}
    raw.setdefault("signers", {})
    for c in config.CODES:                                    # remove from any previous place
        raw["signers"][c] = [n for n in raw["signers"].get(c, []) if key(n) != k]
    raw["me"] = [n for n in raw.get("me", []) if key(n) != k]
    raw["staff"] = [n for n in raw.get("staff", []) if key(n) != k]
    if code in config.CODES:
        raw["signers"][code].append(name)
    elif code in ("me", "staff"):
        raw[code].append(name)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, p)
    own = con is None
    con = con or library.connect()
    try:
        n = 0
        if code in config.CODES:
            n = con.execute("UPDATE captures SET signer=? WHERE signer_key=? AND (signer IS NULL OR signer<>?)",
                            (code, k, code)).rowcount
        elif code == "me":
            n = con.execute("UPDATE captures SET author_is_me=1 WHERE author_key=?", (k,)).rowcount
        con.commit()
        return {"ok": True, "code": code, "captures_updated": n}
    finally:
        if own:
            con.close()


def auto_assign(con=None) -> list[str]:
    """B1 = the only Chefarzt signer, B2 = the only Leitende(r) OA signer — only when unambiguous. Codes assigned."""
    d = load()
    have = assigned()
    sig = config.signers()
    done = []
    for role, code in (("chefarzt", "B1"), ("leitend", "B2")):
        if sig.by_code.get(code):
            continue
        cands = [k for k, e in d.items() if e["roles"].get(role, 0) >= 2 and e.get("final", 0) >= 2 and k not in have]
        if len(cands) == 1:
            assign(cands[0], code, con)
            done.append(code)
    return done


def listing() -> list[dict]:
    """For the local dashboard only (names are shown to Ajit on his own screen)."""
    d = load()
    have = assigned()
    rows = [{"key": k, "name": e["name"], "roles": e["roles"], "final": e.get("final", 0), "draft": e.get("draft", 0),
             "assigned": have.get(k)} for k, e in d.items()]
    rows.sort(key=lambda r: (-r["final"], -r["draft"]))
    return rows
