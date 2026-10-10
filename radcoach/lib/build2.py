"""Build a Docs batchUpdate that inserts structured blocks at one index.

blocks: list of [kind, text, (extra)]
  kind: h1, h2, h3, p, b (bullet), b2 (nested bullet), img (text=url, extra=width pt)
  inline markup in text: **bold**, [label](url), !!red!! (red text, for his highlights)
The inserted text must land at the start of an EMPTY paragraph (its newline is reused).
usage: python3 build.py spec.json out.json
spec: {"at": int, "tab": "t.x" or null, "rev": "...", "blocks": [...]}
"""
import json, re, sys

TOK = re.compile(r"\*\*(.+?)\*\*|\[(.+?)\]\((https?://[^)]+)\)|!!(.+?)!!|==(.+?)==|\+\+(.+?)\+\+|~~(.+?)~~|__(.+?)__")


def u16(s):
    return len(s.encode("utf-16-le")) // 2


def parse(text):
    out, spans, pos = "", [], 0
    for m in TOK.finditer(text):
        out += text[pos:m.start()]
        start = u16(out)
        if m.group(1) is not None:
            out += m.group(1); spans.append((start, u16(out), "bold", None))
        elif m.group(2) is not None:
            out += m.group(2); spans.append((start, u16(out), "link", m.group(3)))
        elif m.group(4) is not None:
            out += m.group(4); spans.append((start, u16(out), "red", None))
        elif m.group(5) is not None:
            out += m.group(5); spans.append((start, u16(out), "yellow", None))
        elif m.group(6) is not None:
            out += m.group(6); spans.append((start, u16(out), "green", None))
        elif m.group(7) is not None:
            out += m.group(7); spans.append((start, u16(out), "strike", None))
        else:
            out += m.group(8); spans.append((start, u16(out), "gray", None))
        pos = m.end()
    out += text[pos:]
    return out, spans


def build(spec):
    at, tab, blocks = spec["at"], spec.get("tab"), spec["blocks"]
    def loc(i):
        d = {"index": i}
        if tab: d["tabId"] = tab
        return d
    def rng(a, b):
        d = {"startIndex": a, "endIndex": b}
        if tab: d["tabId"] = tab
        return d
    paras = []  # (start, end_incl_newline, kind, spans, extra)
    full = ""
    cur = at
    for blk in blocks:
        kind, text = blk[0], blk[1]
        extra = blk[2] if len(blk) > 2 else None
        if kind == "img":
            t, spans = "", []
        else:
            t, spans = parse(text)
        start = cur
        full += t + "\n"
        cur += u16(t) + 1
        paras.append((start, cur, kind, [(start + a, start + b, k, v) for a, b, k, v in spans], extra, text))
    # drop final newline: reuse the existing empty paragraph's newline
    if not spec.get("split"):
        full = full[:-1]
    reqs = [{"insertText": {"location": loc(at), "text": full}}]
    end = cur  # end index of last paragraph incl. reused newline
    reqs.append({"updateTextStyle": {"range": rng(at, end), "textStyle": {},
                                      "fields": "bold,italic,underline,strikethrough,fontSize,foregroundColor,backgroundColor,link"}})
    named = {"h1": "HEADING_1", "h2": "HEADING_2", "h3": "HEADING_3"}
    # paragraph styles
    for s, e, kind, spans, extra, _ in paras:
        reqs.append({"updateParagraphStyle": {"range": rng(s, e), "paragraphStyle": {"namedStyleType": named.get(kind, "NORMAL_TEXT")},
                                               "fields": "namedStyleType"}})
    for s, e, kind, spans, extra, _ in paras:
        if kind in ("bs", "img", "cap"):
            reqs.append({"updateParagraphStyle": {"range": rng(s, e), "paragraphStyle": {"spaceBelow": {"magnitude": 8, "unit": "PT"}},
                                                   "fields": "spaceBelow"}})
    # bullets: group consecutive b/b2 paragraphs; nested level by leading tab is not used,
    # so nested items get indentStart afterwards
    groups, g = [], []
    for p in paras:
        if p[2] in ("b", "b2"):
            g.append(p)
        else:
            if g: groups.append(g); g = []
    if g: groups.append(g)
    for g in groups:
        reqs.append({"createParagraphBullets": {"range": rng(g[0][0], g[-1][1]), "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE"}})
    for s, e, kind, spans, extra, _ in paras:
        if kind == "b2":
            reqs.append({"updateParagraphStyle": {"range": rng(s, e), "paragraphStyle": {
                "indentStart": {"magnitude": 72, "unit": "PT"}, "indentFirstLine": {"magnitude": 54, "unit": "PT"}},
                "fields": "indentStart,indentFirstLine"}})
    # inline spans
    for s, e, kind, spans, extra, _ in paras:
        for a, b, k, v in spans:
            if k == "bold":
                ts, f = {"bold": True}, "bold"
            elif k == "link":
                ts, f = {"link": {"url": v}}, "link"
            elif k == "yellow":
                ts, f = {"backgroundColor": {"color": {"rgbColor": {"red": 1.0, "green": 0.92, "blue": 0.35}}}}, "backgroundColor"
            elif k == "green":
                ts, f = {"backgroundColor": {"color": {"rgbColor": {"red": 0.72, "green": 0.9, "blue": 0.72}}}}, "backgroundColor"
            elif k == "strike":
                ts, f = {"strikethrough": True, "foregroundColor": {"color": {"rgbColor": {"red": 0.8, "green": 0.1, "blue": 0.1}}}}, "strikethrough,foregroundColor"
            elif k == "gray":
                ts, f = {"italic": True, "foregroundColor": {"color": {"rgbColor": {"red": 0.45, "green": 0.45, "blue": 0.45}}}}, "italic,foregroundColor"
            else:
                ts, f = {"foregroundColor": {"color": {"rgbColor": {"red": 1.0}}}}, "foregroundColor"
            reqs.append({"updateTextStyle": {"range": rng(a, b), "textStyle": ts, "fields": f}})
    # images last, descending
    imgs = [p for p in paras if p[2] == "img"]
    for s, e, kind, spans, extra, url in sorted(imgs, key=lambda p: -p[0]):
        r = {"location": loc(s), "uri": url}
        if extra:
            r["objectSize"] = {"width": {"magnitude": extra, "unit": "PT"}}
        if extra and isinstance(extra, list):
            r["objectSize"] = {"width": {"magnitude": extra[0], "unit": "PT"}, "height": {"magnitude": extra[1], "unit": "PT"}}
        reqs.append({"insertInlineImage": r})
    # coalesce adjacent updateParagraphStyle with identical style
    merged = []
    for r in reqs:
        if merged and "updateParagraphStyle" in r and "updateParagraphStyle" in merged[-1]:
            a, b = merged[-1]["updateParagraphStyle"], r["updateParagraphStyle"]
            if a["paragraphStyle"] == b["paragraphStyle"] and a["fields"] == b["fields"] and a["range"]["endIndex"] == b["range"]["startIndex"]:
                a["range"]["endIndex"] = b["range"]["endIndex"]
                continue
        merged.append(r)
    reqs = merged
    out = {"requests": reqs}
    if spec.get("rev"):
        out["writeControl"] = {"requiredRevisionId": spec["rev"]}
    return out, end


if __name__ == "__main__":
    specs = json.load(open(sys.argv[1]))
    if isinstance(specs, dict): specs = [specs]
    specs.sort(key=lambda s: -s["at"])
    out = {"requests": []}
    for sp in specs:
        o, end = build(sp)
        out["requests"] += o["requests"]
        if "writeControl" in o: out["writeControl"] = o["writeControl"]
        print("spec at", sp["at"], "end", end)
    json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False)
    print("requests", len(out["requests"]), "bytes", len(json.dumps(out, ensure_ascii=False)))
