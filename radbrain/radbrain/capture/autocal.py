"""Auto-calibration: find the report panels on screen without Ajit dragging rectangles.

The screen (largest Citrix window first, then each monitor) is grabbed in memory and run through Tesseract once
in TSV mode (word boxes only). Section headings (Befund, Beurteilung, Fragestellung, Technik …) that line up in a
column mark a report panel. Pair = two columns that both contain Befund/Beurteilung → left = draft, right =
final; final = the column with the most headings. The panel rectangle = the heading column's text block (from a
few lines above the first heading down to the last line before a large vertical gap). Only coordinates are kept —
no word, no image is stored or logged.

Used by hotkey_app.capture(): when no calibration exists, and again once when a capture's OCR shows no section
heading (the PACS window moved or the layout changed). `python -m radbrain.capture.autocal [pair|final]` runs it
by hand and prints the rectangles.
"""
from __future__ import annotations

import io
import re
import statistics
import subprocess
import sys

HEAD = re.compile(r"^(befund|befunde|beurteilung|fragestellung|technik|indikation|zusammenfassung|"
                  r"anamnese|untersuchungstechnik|impression)[:.]?$", re.I)
CORE = re.compile(r"^(befund|befunde|beurteilung)[:.]?$", re.I)


def words(img) -> list[dict]:
    """Word boxes from Tesseract TSV (image piped via stdin, nothing on disk)."""
    from radbrain.capture.ocr import _NO_WINDOW, OCRUnavailable, tesseract_cmd
    cmd = tesseract_cmd()
    if not cmd:
        raise OCRUnavailable("tesseract binary not found")
    g = img.convert("L")
    buf = io.BytesIO()
    g.save(buf, format="BMP")
    del g
    try:
        p = subprocess.run([cmd, "stdin", "stdout", "-l", "deu", "--psm", "3", "tsv"], input=buf.getvalue(),
                           capture_output=True, timeout=90, creationflags=_NO_WINDOW)
    finally:
        buf.close()
    out = []
    for ln in p.stdout.decode("utf-8", "replace").splitlines()[1:]:
        f = ln.split("\t")
        if len(f) < 12 or not f[11].strip():
            continue
        try:
            conf = float(f[10])
        except ValueError:
            continue
        if conf < 30:
            continue
        out.append({"l": int(f[6]), "t": int(f[7]), "w": int(f[8]), "h": int(f[9]), "s": f[11].strip()})
    return out


def _columns(heads: list[dict], width: int) -> list[list[dict]]:
    tol = max(40, int(0.06 * width))
    cols: list[list[dict]] = []
    for h in sorted(heads, key=lambda w: w["l"]):
        if cols and abs(h["l"] - cols[-1][0]["l"]) <= tol:
            cols[-1].append(h)
        else:
            cols.append([h])
    return cols


def _panel(col: list[dict], ws: list[dict], x_max: int, lh: float, size: tuple[int, int],
           fixed_width: int | None = None) -> dict:
    x0 = min(h["l"] for h in col) - int(1.5 * lh)
    top = max(0, min(h["t"] for h in col) - int(5 * lh))
    mine = sorted([w for w in ws if x0 <= w["l"] < x_max and w["t"] >= top], key=lambda w: w["t"])
    bottom = max(h["t"] + h["h"] for h in col)
    for w in mine:                                     # walk down while the text block continues
        if w["t"] <= bottom + 5 * lh:
            bottom = max(bottom, w["t"] + w["h"])
    block = [w for w in mine if w["t"] <= bottom]
    left = max(0, min([w["l"] for w in block] + [x0]) - int(0.6 * lh))
    if fixed_width:                                    # comparison view: both panels as wide as their spacing
        right = min(size[0], left + fixed_width)
    else:                                              # single panel: grow right while words stay connected
        right = left
        for w in sorted(block, key=lambda w: w["l"]):
            if w["l"] <= right + 4 * lh:
                right = max(right, w["l"] + w["w"])
        right = min(x_max, size[0], right + int(6 * lh))
    return {"left": left, "top": top, "width": max(10, right - left),
            "height": max(10, min(size[1], bottom + int(2 * lh)) - top)}


def detect(img, origin: tuple[int, int] = (0, 0), kind: str = "pair") -> dict | None:
    ws = words(img)
    heads = [w for w in ws if HEAD.match(w["s"])]
    if not heads:
        return None
    lh = statistics.median([w["h"] for w in ws]) if ws else 14
    W, H = img.size
    cols = [c for c in _columns(heads, W) if any(CORE.match(h["s"]) for h in c)]
    if not cols:
        return None
    if kind == "pair":
        if len(cols) < 2:
            return None
        cols = sorted(sorted(cols, key=len, reverse=True)[:2], key=lambda c: min(h["l"] for h in c))
        names = ("draft", "final")
    else:
        cols = [max(cols, key=len)]
        names = ("final",)
    out = {}
    spacing = (min(h["l"] for h in cols[1]) - min(h["l"] for h in cols[0])) if len(cols) == 2 else None
    for i, (name, col) in enumerate(zip(names, cols)):
        x_max = min(h["l"] for h in cols[i + 1]) - int(lh) if i + 1 < len(cols) else W
        r = _panel(col, ws, x_max, lh, (W, H), fixed_width=(spacing - int(lh)) if spacing else None)
        out[name] = {"left": r["left"] + origin[0], "top": r["top"] + origin[1], "width": r["width"],
                     "height": r["height"]}
    return out


def _sources():
    """(image, origin) candidates: Citrix windows (largest first) on Windows, then every monitor."""
    from radbrain.capture import grab
    if sys.platform == "win32":
        try:
            wins = sorted(grab.find_citrix_windows(), key=lambda w: -(w["rect"][2] - w["rect"][0]) *
                          (w["rect"][3] - w["rect"][1]))
            for w in wins:
                if w.get("minimised"):
                    continue
                l, t, r, b = w["rect"]
                yield grab.grab_region(l, t, r - l, b - t), (l, t)
        except Exception:  # noqa: BLE001
            pass
    for m in grab.monitors():
        yield grab.grab_region(m["left"], m["top"], m["width"], m["height"]), (m["left"], m["top"])


def auto(kind: str = "pair", save: bool = True) -> dict | None:
    """Find the panels on the current screen; saves them as the calibration for `kind`. None if not found."""
    from radbrain.capture import grab
    dpi = grab.set_dpi_awareness()
    fallback = None
    for img, origin in _sources():
        W, H = img.size
        try:
            rects = detect(img, origin, kind)
        finally:
            del img
        if not rects:
            continue
        clipped = any(r["left"] + r["width"] >= origin[0] + W - 3 or r["top"] + r["height"] >= origin[1] + H - 3
                      for r in rects.values())
        if clipped:                       # a panel runs off this source (window overlapped / partly off-screen)
            fallback = fallback or rects
            continue
        return _save(kind, rects, dpi, save)
    return _save(kind, fallback, dpi, save) if fallback else None


def _save(kind, rects, dpi, save):
    if save:
        from radbrain.capture import calibrate, grab
        calibrate.save_regions(kind, rects, virtual_screen=grab.virtual_screen(), monitors=grab.monitors(),
                               dpi_awareness=dpi)
    return rects


def has_heading(text: str | None) -> bool:
    return bool(text) and any(HEAD.match(ln.strip().split(" ")[0]) for ln in text.splitlines() if ln.strip())


def main(argv=None) -> int:
    import json
    kind = (argv or sys.argv[1:] or ["pair"])[0]
    r = auto(kind)
    print(json.dumps({"kind": kind, "found": bool(r), "rects": r}, indent=2))
    return 0 if r else 1


if __name__ == "__main__":
    sys.exit(main())
