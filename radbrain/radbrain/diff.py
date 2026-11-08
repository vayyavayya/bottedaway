"""Word-level diffs per section (draft → final), plus sentence-level reorder and numbering detection."""
from __future__ import annotations

import difflib
import re

TOK = re.compile(r"\[[A-Z0-9]+\]|\d+(?:[.,]\d+)?|[^\W\d_][\w'’./-]*[\w]|[^\W\d_]|[^\w\s]")
NUM_PREFIX = re.compile(r"^\s*\d+[.)]\s+")
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ0-9\[])|\n+")


def tokens(s: str) -> list[str]:
    return TOK.findall(s or "")


SENT_INLINE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ\[])")


def sentences(s: str) -> list[str]:
    """Sentences per line; a leading "1." numbering stays attached to its point."""
    out = []
    for line in (s or "").split("\n"):
        line = line.strip()
        if not line:
            continue
        m = NUM_PREFIX.match(line)
        prefix, rest = (m.group(0), line[m.end():]) if m else ("", line)
        parts = [x.strip() for x in SENT_INLINE.split(rest) if x.strip()]
        if parts:
            parts[0] = prefix + parts[0]
            out += parts
    return out


def detok(toks) -> str:
    """Tokens back to readable text: no space before punctuation."""
    s = " ".join(toks if isinstance(toks, list) else str(toks).split())
    return re.sub(r"\s+([.,;:!?)])", r"\1", s).replace("( ", "(")


def _norm_sent(s: str) -> str:
    return re.sub(r"\s+", " ", NUM_PREFIX.sub("", s)).strip().casefold()


def structure_ops(draft: str, final: str) -> tuple[list[dict], str]:
    """Numbering and reordering of sentences. Returns (ops, draft rearranged to the final's order) so that the word
    diff afterwards only sees wording changes."""
    ops: list[dict] = []
    dl, fl = sentences(draft), sentences(final)
    d_num = sum(bool(NUM_PREFIX.match(x)) for x in dl)
    f_num = sum(bool(NUM_PREFIX.match(x)) for x in fl)
    if fl and f_num >= max(1, len(fl) - 1) and d_num == 0:
        ops.append({"op": "number", "before": "", "after": "1. 2. …"})
    elif dl and d_num >= max(1, len(dl) - 1) and f_num == 0:
        ops.append({"op": "unnumber", "before": "1. 2. …", "after": ""})
    dn = [_norm_sent(x) for x in dl]
    fn = [_norm_sent(x) for x in fl]
    common = [x for x in fn if x in dn]
    order_d = [x for x in dn if x in common]
    if len(common) >= 2 and order_d != [x for x in fn if x in order_d]:
        ops.append({"op": "reorder", "before": " | ".join(order_d[:3]), "after": " | ".join(fn[:3])})
        # rearrange draft sentences into the final's relative order
        rank = {x: i for i, x in enumerate(fn)}
        pairs = list(zip(dn, [NUM_PREFIX.sub("", x) for x in dl]))
        moved = sorted([p for p in pairs if p[0] in rank], key=lambda p: rank[p[0]])
        it = iter(moved)
        new = [next(it)[1] if p[0] in rank else p[1] for p in pairs]
        draft = "\n".join(new)
    if any(o["op"] == "number" for o in ops):
        draft = "\n".join(sentences(draft))
    return ops, draft


def word_ops(draft: str, final: str) -> list[dict]:
    """difflib on tokens; numbering prefixes are removed first (handled by structure_ops)."""
    a = tokens("\n".join(NUM_PREFIX.sub("", x) for x in (draft or "").split("\n")))
    b = tokens("\n".join(NUM_PREFIX.sub("", x) for x in (final or "").split("\n")))
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    ops = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        ops.append({"op": {"replace": "sub", "delete": "del", "insert": "ins"}[tag],
                    "before": " ".join(a[i1:i2]), "after": " ".join(b[j1:j2]),
                    "ctx_before": " ".join(a[max(0, i1 - 4):i1]), "ctx_after": " ".join(a[i2:i2 + 4]),
                    "pos": i1, "len_a": len(a)})
    return ops


def section_diff(draft: str, final: str) -> dict:
    sops, rearranged = structure_ops(draft, final)
    return {"structure": sops, "words": word_ops(rearranged, final),
            "len_draft": len(tokens(draft)), "len_final": len(tokens(final))}


def diff_sections(draft: dict, final: dict) -> dict:
    out = {}
    for k in ("fragestellung", "technik", "befund", "beurteilung"):
        d, f = draft.get(k) or "", final.get(k) or ""
        if d or f:
            out[k] = section_diff(d, f)
    return out


def change_rate(draft: str, final: str) -> float:
    """1 - token similarity: 0 = untouched, 1 = rewritten completely."""
    a, b = tokens(draft), tokens(final)
    if not a and not b:
        return 0.0
    return 1.0 - difflib.SequenceMatcher(a=a, b=b, autojunk=False).ratio()


def highlight_html(draft: str, final: str) -> str:
    """yellow = corrected, green = added, red strikethrough = deleted (Phase 7 output colours)."""
    import html
    a, b = _spaced_tokens(draft), _spaced_tokens(final)
    sm = difflib.SequenceMatcher(a=[t.strip() for t in a], b=[t.strip() for t in b], autojunk=False)
    out = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            out.append(html.escape("".join(b[j1:j2])))
        elif tag == "replace":
            out.append(f'<del class="d">{html.escape("".join(a[i1:i2]))}</del>'
                       f'<mark class="c">{html.escape("".join(b[j1:j2]))}</mark>')
        elif tag == "delete":
            out.append(f'<del class="d">{html.escape("".join(a[i1:i2]))}</del>')
        else:
            out.append(f'<mark class="a">{html.escape("".join(b[j1:j2]))}</mark>')
    return "".join(out).replace("\n", "<br>")


def _spaced_tokens(s: str) -> list[str]:
    """Tokens with their trailing whitespace so the HTML keeps the original spacing and line breaks."""
    return re.findall(r"\S+\s*|\s+", s or "")
