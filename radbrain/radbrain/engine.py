"""Phase 7 — the brain engine: Correct, Predict, Ask. Local only (llm.py refuses non-local hosts).

Correct (draft + signer):
  1. retrieve that signer's nearest pairs/finals (bge-m3 embeddings via local Ollama; trigram fallback);
  2. apply that signer's rulebook deterministically (rules with consistency >= 50 %);
  3. the local LLM rewrites in that signer's style, given the rules and the nearest examples;
  4. guards: the LLM version of a section is thrown away if it adds or drops a number, a side, an asserted entity or
     a content word that is not in the draft / the signer's rules — "never invent findings". The rules-only version
     is kept and the attempt is reported;
  5. consistency check of the draft itself: a Beurteilung entity without a basis in the Befund, side mismatch, a
     Befund finding missing in the Beurteilung → flagged, never fixed silently.
Output: German text, HTML with yellow = corrected, green = added, red strikethrough = deleted, plus short English
explanations, each pointing to a rule id or an example capture.
"""
from __future__ import annotations

import json
import re
import struct
from collections import Counter

from . import anonymise, config, diff, library, llm, miner, taxonomy

AUTO_APPLY = 0.5
SIDE = re.compile(r"\b(rechts|links|re\.|li\.|beidseits|bds\.?|rechtsseitig\w*|linksseitig\w*)", re.I)
NUM = re.compile(r"\d+(?:[.,]\d+)?\s?(?:mm|cm|ml|%|°|HU)?")
STYLE_OK = set("""kein keine keinen keiner nachweis anhalt hinweis vereinbar ehesten fraglich fragliche möglich
mögliche unauffällig unauffällige unauffälliger unauffälligen regelrecht regelrechte regelrechter empfohlen empfehlung
korrelation klinische klinisch kontrolle verlauf befund beurteilung zeigt zeigen sich darstellung dargestellt
abgrenzbar erkennbar nachweisbar sowie jedoch ohne mit bei zur zum der die das eines einer einem einen ein eine
weiterhin unverändert stationär konstant bekannt bekannten bekannte""".split())


# --------------------------------------------------------------------------------------------- input
def parse_draft(text: str) -> tuple[dict, str]:
    p = anonymise.parse(text)
    if p.had_heading:
        sec = {k: "\n".join(v).strip() for k, v in p.sections.items()}
    else:
        sec = {"befund": "\n".join(x for x in (text or "").splitlines() if x.strip()), "beurteilung": ""}
    return sec, p.exam


# --------------------------------------------------------------------------------------------- retrieval
def _vec_blob(v) -> bytes:
    return struct.pack(f"{len(v)}f", *v)


def _blob_vec(b: bytes):
    return struct.unpack(f"{len(b) // 4}f", b)


def _cap_text(c: dict) -> str:
    return "\n".join(x for x in (c.get("draft_befund") or c.get("final_befund") or "",
                                  c.get("draft_beurteilung") or c.get("final_beurteilung") or "") if x)


def retrieve(con, signer: str, query: str, k: int = 4, kind: str | None = None, exclude: set | None = None) -> list:
    where, args = "signer=?", [signer]
    if kind:
        where += " AND kind=?"
        args.append(kind)
    caps = [c for c in library.rows(con, where, args) if not exclude or c["id"] not in exclude]
    if not caps:
        return []
    model = config.models().embed
    qv = llm.embed([query]) if query.strip() else None
    scored = []
    if qv:
        have = {r["capture_id"]: _blob_vec(r["vec"]) for r in con.execute(
            "SELECT capture_id, vec FROM embeddings WHERE model=? AND part='draft'", (model,))}
        missing = [c for c in caps if c["id"] not in have]
        for i in range(0, len(missing), 32):
            chunk = missing[i:i + 32]
            vs = llm.embed([_cap_text(c) for c in chunk])
            if not vs:
                break
            for c, v in zip(chunk, vs):
                have[c["id"]] = v
                con.execute("INSERT OR REPLACE INTO embeddings VALUES (?,?,?,?)", (c["id"], model, "draft",
                                                                                     _vec_blob(v)))
        con.commit()
        for c in caps:
            if c["id"] in have:
                scored.append((llm.cosine(qv[0], have[c["id"]]), c))
        method = "embedding:" + model
    if not scored:
        scored = [(llm.lexical_sim(query, _cap_text(c)), c) for c in caps]
        method = "trigram"
    scored.sort(key=lambda x: -x[0])
    return [{"score": round(s, 3), "capture": c, "method": method} for s, c in scored[:k]]


# --------------------------------------------------------------------------------------------- rules
def _phrase_rx(phrase: str) -> re.Pattern:
    toks = phrase.split()
    parts = []
    for i, t in enumerate(toks):
        if i:
            parts.append(r"\s*" if re.fullmatch(r"[^\w\s]", t) else r"\s+")
        parts.append(re.escape(t))
    return re.compile(r"(?<![\wÄÖÜäöüß])" + "".join(parts) + r"(?![\wÄÖÜäöüß])", re.I)


def _cap_first(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _sentence_start(text: str, pos: int) -> bool:
    before = text[:pos].rstrip(" \t")
    return not before or before[-1] in ".!?\n:" or re.search(r"(^|\n)\s*\d+[.)]$", before) is not None


def _orig(r: dict, phrase: str) -> str:
    """The phrase as the signer actually writes it (rules are stored case-folded)."""
    rx = _phrase_rx(phrase)
    for ex in r.get("examples") or []:
        m = rx.search(ex.get("final") or "")
        if m:
            return m.group(0)
    return diff.detok(phrase)


def apply_rule(text: str, r: dict, region: str | None) -> tuple[str, bool]:
    op = r["op"]
    if op in ("sub", "del"):
        rx = _phrase_rx(r["before"])
        repl = _orig(r, r["after"]) if op == "sub" else ""
        changed = False

        def f(m):
            nonlocal changed
            changed = True
            out = repl
            start = _sentence_start(m.string, m.start())
            if start and out:
                out = _cap_first(out)
            return out
        new = rx.sub(f, text)
        if changed and op == "del":
            new = re.sub(r"(^|[.!?:]\s+|\n\s*(?:\d+[.)]\s+)?)\s*([a-zäöü])", lambda m: m.group(1) + m.group(2).upper(),
                         new)
            new = re.sub(r"[ \t]{2,}", " ", new).replace(" ,", ",").replace(" .", ".")
            new = re.sub(r",\s*,", ",", new)
        return new, changed
    if op == "ins":
        cond = r.get("condition") or {}
        if cond.get("region") and cond["region"] != region:
            return text, False
        phrase = _cap_first(_orig(r, r["after"]))
        if _phrase_rx(r["after"]).search(text):
            return text, False
        sep = "\n" if text.strip() else ""
        numbered = re.findall(r"(?m)^\s*(\d+)[.)]\s", text)
        if numbered:
            phrase = f"{int(numbered[-1]) + 1}. {phrase}"
        return text.rstrip() + sep + phrase, True
    if op == "number":
        sents = diff.sentences(text)
        if not sents or any(diff.NUM_PREFIX.match(s) for s in sents):
            return text, False
        return "\n".join(f"{i + 1}. {s}" for i, s in enumerate(sents)), True
    if op == "reorder":
        sents = [diff.NUM_PREFIX.sub("", s) for s in diff.sentences(text)]
        if len(sents) < 2:
            return text, False
        normals = set(taxonomy.NORMAL_KEY.values())
        scores = [bool(set(taxonomy.pathologies(s)) - normals) for s in sents]
        main = next((i for i, x in enumerate(scores) if x), 0)
        if main == 0:
            return text, False
        order = [sents[main]] + sents[:main] + sents[main + 1:]
        numbered = bool(re.search(r"(?m)^\s*\d+[.)]\s", text))
        return "\n".join((f"{i + 1}. " if numbered else "") + s for i, s in enumerate(order)), True
    return text, False


def apply_rulebook(sections: dict, rules: list[dict], region: str | None) -> tuple[dict, list[dict]]:
    out = dict(sections)
    applied = []
    order = {"reorder": 0, "sub": 1, "del": 2, "ins": 3, "number": 4}
    for r in sorted(rules, key=lambda r: (order.get(r["op"], 9), -r["count"])):
        if r["consistency"] < AUTO_APPLY or r["op"] == "unnumber":
            continue
        sec = r["section"]
        if sec not in out and r["op"] != "ins":
            continue
        new, ch = apply_rule(out.get(sec, ""), r, region)
        if ch:
            out[sec] = new
            ex = (r.get("examples") or [{}])[0]
            applied.append({"rule": r["rid"], "scope": r["scope"], "label": r["label"], "en": miner.explain_en(r),
                            "consistency": r["consistency"], "example": ex.get("capture"), "section": sec})
    return out, applied


# --------------------------------------------------------------------------------------------- guards
def _content(s: str) -> Counter:
    return Counter(t.casefold() for t in diff.tokens(s) if re.match(r"[^\W\d_]", t) and len(t) >= 4
                   and t.casefold() not in STYLE_OK)


def _sides(s: str) -> Counter:
    norm = {"re.": "rechts", "li.": "links", "bds": "beidseits", "bds.": "beidseits"}
    return Counter(norm.get(m.group(1).casefold(), m.group(1).casefold()[:6]) for m in SIDE.finditer(s or ""))


def _nums(s: str) -> Counter:
    return Counter(m.group(0).replace(" ", "").replace(",", ".") for m in NUM.finditer(s or "")
                   if not re.fullmatch(r"\d+\.?", m.group(0).strip()) or len(m.group(0).strip()) > 2)


def guard(section: str, src: str, out: str, allowed: set[str]) -> list[str]:
    """Reasons why an LLM rewrite of one section must be rejected (empty = accepted)."""
    why = []
    strip = lambda s: "\n".join(diff.NUM_PREFIX.sub("", x) for x in (s or "").split("\n"))  # noqa: E731
    if _nums(strip(out)) != _nums(strip(src)):
        why.append("Zahlen/Maße verändert")
    if set(_sides(out)) - set(_sides(src)):
        why.append("neue Seitenangabe")
    new_words = [w for w in (_content(out) - _content(src)) if w not in allowed]
    if new_words:
        why.append("neue Inhalte: " + ", ".join(sorted(new_words)[:6]))
    pin, pout = set(taxonomy.pathologies(src)), set(taxonomy.pathologies(out))
    if pout - pin:
        why.append("neuer Befund: " + ", ".join(taxonomy.label(k) for k in sorted(pout - pin)))
    if pin - pout and section == "beurteilung":
        why.append("Befund entfernt: " + ", ".join(taxonomy.label(k) for k in sorted(pin - pout)))
    return why


def consistency_flags(sections: dict) -> list[dict]:
    """Does the Beurteilung follow from the Befund? Flags only — the engine never fixes this silently."""
    flags = []
    bef, beu = sections.get("befund", ""), sections.get("beurteilung", "")
    if not beu.strip():
        flags.append({"level": "warn", "text": "Keine Beurteilung im Entwurf."})
        return flags
    pb, pu = set(taxonomy.pathologies(bef)), set(taxonomy.pathologies(beu))
    normals = set(taxonomy.NORMAL_KEY.values())
    for k in sorted(pu - pb - normals):
        e = taxonomy.BY_KEY[k]
        if not e.pattern.search(bef):
            flags.append({"level": "error", "text": f"Beurteilung nennt „{e.label}“, der Befund beschreibt es nicht.",
                          "en": f"The Beurteilung states {e.label} but the Befund gives no basis for it."})
    for k in sorted(pb - pu - normals):
        flags.append({"level": "warn", "text": f"Befund beschreibt „{taxonomy.label(k)}“, die Beurteilung erwähnt es "
                                               "nicht.", "en": f"{taxonomy.label(k)} is in the Befund but not in the "
                                                               "Beurteilung."})
    for k in sorted(pb & pu):
        e = taxonomy.BY_KEY[k]
        sb = " ".join(s for s in diff.sentences(bef) if e.pattern.search(s))
        su = " ".join(s for s in diff.sentences(beu) if e.pattern.search(s))
        a, b = set(_sides(sb)) & {"rechts", "links"}, set(_sides(su)) & {"rechts", "links"}
        if a and b and not (a & b):
            flags.append({"level": "error", "text": f"Seitenwiderspruch bei „{e.label}“: Befund {'/'.join(sorted(a))}, "
                                                    f"Beurteilung {'/'.join(sorted(b))}.",
                          "en": f"Side mismatch for {e.label}."})
    return flags


# --------------------------------------------------------------------------------------------- correct
SYSTEM = ("Du bist der Stil-Assistent von {code} ({role}) einer radiologischen Abteilung. Du korrigierst den Entwurf "
          "eines Assistenzarztes so, wie {code} ihn beim Vidieren umschreibt. Du änderst NUR Wortwahl, Satzbau, "
          "Reihenfolge und die Logik der Beurteilung. Du erfindest NIEMALS Befunde, Zahlen, Maße, Seitenangaben oder "
          "Diagnosen und lässt keine weg. Antworte nur mit JSON: {{\"befund\": str, \"beurteilung\": str, "
          "\"changes\": [{{\"what\": str (English, short), \"source\": \"rule id oder example id oder style\"}}]}}")


def _prompt(code: str, sections: dict, rules: list[dict], examples: list[dict]) -> str:
    lines = [f"Regeln von {code} (aus echten Korrekturen gelernt):"]
    for r in rules[:20]:
        lines.append(f"- {r['rid']} [{r['scope']}, {r['consistency']:.0%}] {r['label']}")
    lines.append("\nBeispiele (Entwurf → Endfassung von " + code + "):")
    for ex in examples:
        c = ex["capture"]
        if c["kind"] == "pair":
            lines.append(f"[E{c['id']}] ENTWURF Befund: {c.get('draft_befund') or ''}\nENTWURF Beurteilung: "
                         f"{c.get('draft_beurteilung') or ''}\nENDFASSUNG Befund: {c.get('final_befund') or ''}\n"
                         f"ENDFASSUNG Beurteilung: {c.get('final_beurteilung') or ''}\n")
        else:
            lines.append(f"[E{c['id']}] ENDFASSUNG Befund: {c.get('final_befund') or ''}\nENDFASSUNG Beurteilung: "
                         f"{c.get('final_beurteilung') or ''}\n")
    lines.append("Zu korrigierender Entwurf (Regeln sind schon angewandt):")
    lines.append("Befund:\n" + sections.get("befund", ""))
    lines.append("Beurteilung:\n" + sections.get("beurteilung", ""))
    return "\n".join(lines)


def correct(draft_text: str, signer: str, *, use_llm: bool = True, con=None, exclude: set | None = None,
            sections: dict | None = None, region: str | None = None) -> dict:
    if signer not in config.CODES:
        raise ValueError("signer must be B1, B2 or B3")
    own = con is None
    con = con or library.connect()
    try:
        if sections is None:
            sections, exam = parse_draft(draft_text)
        else:
            exam = ""
        region = region or taxonomy.region(exam + "\n" + "\n".join(sections.values()))
        rules = miner.rules_for(con, signer)
        query = "\n".join(sections.get(k, "") for k in ("befund", "beurteilung"))
        examples = retrieve(con, signer, query, k=3, exclude=exclude)
        ruled, applied = apply_rulebook(sections, rules, region)
        final, llm_used, rejected, llm_changes = dict(ruled), False, [], []
        if use_llm and (config.models().llm and llm.available().get("llm")):
            res = llm.chat_json(SYSTEM.format(code=signer, role=config.ROLES[signer]),
                                _prompt(signer, ruled, rules, examples))
            if isinstance(res, dict):
                allowed = set()
                for r in rules:
                    allowed |= set(_content(diff.detok(r["after"])))
                for sec in ("befund", "beurteilung"):
                    cand = res.get(sec)
                    if not isinstance(cand, str) or not cand.strip() or sec not in ruled:
                        continue
                    why = guard(sec, sections.get(sec, ""), cand, allowed)
                    if why:
                        rejected.append({"section": sec, "why": why})
                    else:
                        final[sec] = cand.strip()
                        llm_used = True
                for ch in res.get("changes") or []:
                    if isinstance(ch, dict) and ch.get("what"):
                        llm_changes.append({"en": str(ch["what"])[:200], "source": str(ch.get("source", ""))[:40]})
        flags = consistency_flags(sections)
        for rj in rejected:
            flags.append({"level": "info", "text": f"LLM-Vorschlag für {rj['section']} verworfen ({'; '.join(rj['why'])})"
                                                   " — regelbasierte Fassung behalten.",
                          "en": "The local model's rewrite was rejected by the no-new-findings guard."})
        html = {k: diff.highlight_html(sections.get(k, ""), final.get(k, "")) for k in ("befund", "beurteilung")
                if sections.get(k) or final.get(k)}
        explanations = [{"en": a["en"], "source": a["rule"], "scope": a["scope"], "example": a["example"]}
                        for a in applied]
        if llm_used:
            explanations += [{"en": c["en"], "source": c["source"] or "style", "scope": "LLM", "example": None}
                             for c in llm_changes[:8]]
        return {"signer": signer, "sections_in": sections, "sections_out": final, "html": html,
                "explanations": explanations, "flags": flags, "rules_applied": applied,
                "examples": [{"id": e["capture"]["id"], "score": e["score"], "method": e["method"],
                              "kind": e["capture"]["kind"]} for e in examples],
                "llm_used": llm_used, "model": config.models().llm if llm_used else None,
                "rules_available": len(rules)}
    finally:
        if own:
            con.close()


# --------------------------------------------------------------------------------------------- predict
def predict(draft_text: str, signer: str, *, con=None, sections: dict | None = None, region=None) -> dict:
    """Which phrases will this signer probably change? (before signing)"""
    own = con is None
    con = con or library.connect()
    try:
        if sections is None:
            sections, exam = parse_draft(draft_text)
            region = region or taxonomy.region(exam + "\n" + "\n".join(sections.values()))
        hits = []
        for r in miner.rules_for(con, signer):
            sec = r["section"]
            text = sections.get(sec, "")
            if r["op"] in ("sub", "del"):
                for m in _phrase_rx(r["before"]).finditer(text):
                    hits.append({"section": sec, "start": m.start(), "end": m.end(), "phrase": m.group(0),
                                 "rule": r["rid"], "label": r["label"], "p": r["consistency"], "scope": r["scope"]})
            elif r["op"] == "ins" and miner.applicable(r, sec, {f"draft_{sec}": text, "region": region},
                                                       r.get("condition")):
                hits.append({"section": sec, "start": None, "end": None, "phrase": None, "rule": r["rid"],
                             "label": r["label"], "p": r["consistency"], "scope": r["scope"]})
            elif r["op"] in ("number", "reorder") and miner.applicable(r, sec, {f"draft_{sec}": text}, None):
                hits.append({"section": sec, "start": None, "end": None, "phrase": None, "rule": r["rid"],
                             "label": r["label"], "p": r["consistency"], "scope": r["scope"]})
        hits.sort(key=lambda h: -h["p"])
        html = {}
        import html as H
        for sec in ("befund", "beurteilung"):
            t = sections.get(sec, "")
            spans = sorted([h for h in hits if h["section"] == sec and h["start"] is not None], key=lambda h: h["start"])
            out, pos = [], 0
            for h in spans:
                if h["start"] < pos:
                    continue
                out.append(H.escape(t[pos:h["start"]]))
                out.append(f'<span class="p" title="{H.escape(h["label"])} · {h["p"]:.0%}">{H.escape(t[h["start"]:h["end"]])}'
                           f'<sup>{h["rule"]}</sup></span>')
                pos = h["end"]
            out.append(H.escape(t[pos:]))
            html[sec] = "".join(out).replace("\n", "<br>")
        return {"signer": signer, "hits": hits, "html": html, "flags": consistency_flags(sections)}
    finally:
        if own:
            con.close()


# --------------------------------------------------------------------------------------------- ask
def _entity_from(q: str) -> str | None:
    ql = q.casefold()
    for e in taxonomy.ENTITIES:
        if e.label.casefold().split("/")[0] in ql or e.key in ql or (e.pattern.pattern != "$^" and e.pattern.search(q)):
            return e.key
    return None


def ask(question: str, *, con=None, use_llm: bool = False) -> dict:
    """"How does B1 word a Lungenembolie?" → that signer's real Beurteilung sentences + a B1/B2/B3 comparison."""
    own = con is None
    con = con or library.connect()
    try:
        codes = [c for c in config.CODES if re.search(rf"\b{c}\b", question, re.I)] or list(config.CODES)
        ent = _entity_from(question)
        if not ent:
            return {"question": question, "entity": None, "answer": "Keine Entität aus dem Katalog erkannt — z. B. "
                    "„Wie formuliert B1 eine Lungenembolie?“", "by_signer": {}}
        e = taxonomy.BY_KEY[ent]
        by = {}
        for code in config.CODES:
            caps = [c for c in library.rows(con, "signer=?", (code,)) if ent in c["pathologies"]]
            sents = Counter()
            ids = {}
            for c in caps:
                for s in diff.sentences(c.get("final_beurteilung") or ""):
                    if e.pattern.search(s) or ent.startswith("normal"):
                        k = diff.NUM_PREFIX.sub("", s).strip()
                        sents[k] += 1
                        ids.setdefault(k, c["id"])
            openings = Counter(" ".join(diff.tokens(s)[:2]) for s in sents.elements())
            rules = [r for r in miner.rules_for(con, code) if r["section"] == "beurteilung"]
            by[code] = {"n": len(caps), "examples": [{"text": s, "count": n, "capture": ids[s]}
                                                     for s, n in sents.most_common(5)],
                        "openings": openings.most_common(3),
                        "beurteilung_rules": [{"rid": r["rid"], "label": r["label"], "scope": r["scope"]}
                                              for r in rules[:6]]}
        answer = None
        if use_llm and llm.available().get("llm"):
            ctx = json.dumps({c: by[c]["examples"] for c in codes}, ensure_ascii=False)
            res = llm.chat_json("Du fasst zusammen, wie Radiologen formulieren. Nur aus den Beispielen, nichts "
                                "erfinden. JSON: {\"answer\": str (English, 3-5 Sätze, mit Zitaten auf Deutsch)}",
                                f"Frage: {question}\nBeispiele je Unterzeichner: {ctx}")
            answer = (res or {}).get("answer")
        return {"question": question, "entity": ent, "label": e.label, "codes": codes, "by_signer": by,
                "answer": answer}
    finally:
        if own:
            con.close()
