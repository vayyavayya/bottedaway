"""Dummy PACS comparison view: python -m radbrain.capture.dummy_window [--pair 0] [--geometry-out f.json]

Two read-only text panels side by side (left = draft, right = signed final) with a FICTIONAL report pair;
words that differ are highlighted in yellow. → / ← cycle through the 3 pairs, Esc closes.
It is the target for the end-to-end test of calibrate / grab / OCR / clipboard. All names are fake.
--geometry-out writes the panel rectangles (screen coordinates, mss space) as JSON whenever the view
changes, so a test can grab exactly the text areas.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

PAIRS = [
    {
        "title": "CT Thorax mit KM",
        "draft": "CT Thorax mit KM i.v. vom 02.11.2026\n\n"
                 "Befund:\nFüllungsdefekte in den Segmentarterien des Unterlappens re.\n"
                 "Kein Pleuraerguss. Kein Pneumothorax.\nHerz nicht vergrößert.\n\n"
                 "Beurteilung:\nV.a. Lungenembolie re.\n\n"
                 "Entwurf: Dr. med. Muster",
        "final": "CT Thorax mit KM i.v. vom 02.11.2026\n\n"
                 "Befund:\nFüllungsdefekte in den Segment- und Subsegmentarterien des Unterlappens re.\n"
                 "Kleiner Pleuraerguss re. dorsobasal, ca. 8 mm. Kein Pneumothorax.\n"
                 "RV/LV-Quotient 0,9, keine Rechtsherzbelastung.\n\n"
                 "Beurteilung:\nSegmentale Lungenembolie re. ohne Rechtsherzbelastung.\n\n"
                 "Elektronisch signiert: Dr. med. Probe",
    },
    {
        "title": "MRT LWS nativ",
        "draft": "MRT LWS nativ vom 03.11.2026\n\n"
                 "Befund:\nBandscheibenvorfall LWK 3/4 mit Kontakt zur Nervenwurzel L4 li.\n"
                 "Osteochondrose LWK 4/5. Spinalkanal weit.\n\n"
                 "Beurteilung:\nBandscheibenvorfall LWK 3/4 li.\n\n"
                 "Entwurf: Dr. med. Muster",
        "final": "MRT LWS nativ vom 03.11.2026\n\n"
                 "Befund:\nMediolateraler Bandscheibenprolaps LWK 3/4 li. mit Kompression der Nervenwurzel L4 li.\n"
                 "Osteochondrose Modic Typ II LWK 4/5. Keine Spinalkanalstenose.\n\n"
                 "Beurteilung:\nBandscheibenprolaps LWK 3/4 li. mit Wurzelkompression L4 li.\n\n"
                 "Elektronisch signiert: Dr. med. Beispiel",
    },
    {
        "title": "Röntgen Thorax",
        "draft": "Röntgen Thorax p.a. vom 04.11.2026\n\n"
                 "Befund:\nZ.n. Anlage einer Thoraxdrainage re.\nKein Pneumothorax.\n"
                 "Pleuraerguss li. basal.\n\n"
                 "Beurteilung:\nKein Pneumothorax.\n\n"
                 "Entwurf: Dr. med. Muster",
        "final": "Röntgen Thorax p.a. vom 04.11.2026\n\n"
                 "Befund:\nZ.n. Anlage einer Thoraxdrainage re., Spitze projiziert auf den 3. ICR.\n"
                 "Kein Pneumothorax. Größenregredienter Pleuraerguss li. basal.\n\n"
                 "Beurteilung:\nRegelrechte Drainagenlage, kein Pneumothorax.\n"
                 "Rückläufiger Pleuraerguss li.\n\n"
                 "Elektronisch signiert: Dr. med. Test-B3",
    },
]

_TOKEN = re.compile(r"\S+")


def changed_spans(a: str, b: str) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Character spans of words that differ (word-level diff): (spans in a, spans in b)."""
    ta = [(m.start(), m.end(), m.group()) for m in _TOKEN.finditer(a)]
    tb = [(m.start(), m.end(), m.group()) for m in _TOKEN.finditer(b)]
    sm = difflib.SequenceMatcher(None, [t[2] for t in ta], [t[2] for t in tb], autojunk=False)
    sa, sb = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        sa += [(ta[k][0], ta[k][1]) for k in range(i1, i2)]
        sb += [(tb[k][0], tb[k][1]) for k in range(j1, j2)]
    return sa, sb


class DummyPACS:
    def __init__(self, pair: int = 0, font_size: int = 13, geometry_out: str | None = None):
        import tkinter as tk
        from tkinter import font as tkfont

        from radbrain.capture.grab import set_dpi_awareness
        set_dpi_awareness()
        self.tk = tk
        self.idx = pair % len(PAIRS)
        self.geometry_out = Path(geometry_out) if geometry_out else None
        self.root = tk.Tk()
        self.root.title("Dummy PACS - Befundvergleich (fiktive Testdaten)")
        self.root.configure(bg="#2b2f36")
        fam = next((f for f in ("Segoe UI", "Arial", "Helvetica") if f in tkfont.families()), "TkDefaultFont")
        self.font = (fam, font_size)
        self.header = tk.Label(self.root, text="", bg="#2b2f36", fg="#e0e0e0", font=(fam, font_size + 1, "bold"),
                               anchor="w", padx=10, pady=6)
        self.header.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.panels = {}
        for col, (name, label) in enumerate((("draft", "Entwurf"), ("final", "Final (signiert)"))):
            fr = tk.LabelFrame(self.root, text=label, bg="#2b2f36", fg="#c8c8c8", font=(fam, font_size - 1),
                               padx=4, pady=4)
            fr.grid(row=1, column=col, sticky="nsew", padx=8, pady=(0, 8))
            txt = tk.Text(fr, width=62, height=17, wrap="word", font=self.font, bg="white", fg="#111111",
                          relief="flat", padx=10, pady=8, highlightthickness=0, cursor="xterm")
            txt.pack(fill="both", expand=True)
            txt.tag_configure("chg", background="#fff36b")
            self.panels[name] = txt
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.bind("<Right>", lambda e: self.show(self.idx + 1))
        self.root.bind("<Left>", lambda e: self.show(self.idx - 1))
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.bind("<Configure>", lambda e: self.root.after(150, self.write_geometry))
        self.show(self.idx)

    def show(self, idx: int):
        self.idx = idx % len(PAIRS)
        p = PAIRS[self.idx]
        self.header.configure(text=f"Vergleich {self.idx + 1}/{len(PAIRS)} - {p['title']}   (→ nächster)")
        sa, sb = changed_spans(p["draft"], p["final"])
        for name, spans in (("draft", sa), ("final", sb)):
            t = self.panels[name]
            t.configure(state="normal")
            t.delete("1.0", "end")
            t.insert("1.0", p[name])
            for s, e in spans:
                t.tag_add("chg", f"1.0+{s}c", f"1.0+{e}c")
            t.configure(state="disabled")      # read-only, but still selectable / Ctrl+A-able
        self.root.after(200, self.write_geometry)

    def rects(self) -> dict:
        out = {}
        for name, t in self.panels.items():
            out[name] = {"left": t.winfo_rootx(), "top": t.winfo_rooty(),
                         "width": t.winfo_width(), "height": t.winfo_height()}
        return out

    def write_geometry(self):
        if not self.geometry_out:
            return
        data = {"pair_index": self.idx, "rects": self.rects(), "draft": PAIRS[self.idx]["draft"],
                "final": PAIRS[self.idx]["final"]}
        tmp = self.geometry_out.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.geometry_out)

    def run(self, exit_after: float | None = None, auto_advance: float | None = None, topmost: bool = False):
        if exit_after:
            self.root.after(int(exit_after * 1000), self.root.destroy)
        if auto_advance:
            def tick():
                self.show(self.idx + 1)
                self.root.after(int(auto_advance * 1000), tick)
            self.root.after(int(auto_advance * 1000), tick)
        self.root.lift()
        self.root.attributes("-topmost", True)
        if not topmost:
            self.root.after(800, lambda: self.root.attributes("-topmost", False))
        self.root.focus_force()
        self.root.mainloop()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Dummy PACS comparison window (fictional data)")
    ap.add_argument("--pair", type=int, default=0)
    ap.add_argument("--font-size", type=int, default=13)
    ap.add_argument("--geometry-out", default=None)
    ap.add_argument("--exit-after", type=float, default=None, help="close after N seconds")
    ap.add_argument("--auto-advance", type=float, default=None, help="show the next pair every N seconds (tests)")
    ap.add_argument("--topmost", action="store_true", help="keep the window above others (tests)")
    args = ap.parse_args(argv)
    DummyPACS(args.pair, args.font_size, args.geometry_out).run(args.exit_after, args.auto_advance, args.topmost)
    return 0


if __name__ == "__main__":
    sys.exit(main())
