"""One-time calibration: python -m radbrain.capture.calibrate [--mode pair|final] [--show]

A fullscreen, semi-transparent, topmost tkinter overlay spanning the whole virtual screen (all monitors).
It is a local window, so it sits above the Citrix session. Ajit drags:
  pair mode   rectangle 1 = LEFT panel (draft / Entwurf), rectangle 2 = RIGHT panel (final / signiert)
  final mode  one rectangle = the signed report panel
Keys: Enter = save, Backspace = redo last rectangle, Esc = cancel.

calibration.json (data dir):
{"version": 1, "platform": "win32", "dpi_awareness": "per_monitor_v2", "virtual_screen": {...},
 "monitors": [...], "pair": {"draft": rect, "final": rect, "updated": iso}, "final": {"final": rect, ...}}
rect = {"left", "top", "width", "height"} in the same coordinate space mss uses (physical pixels on Windows
with DPI awareness; points on macOS).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from radbrain.capture.settings import load_json, save_json

MODES = {"pair": ("draft", "final"), "final": ("final",)}
LABELS = {"draft": "LEFT panel = DRAFT (Entwurf)", "final": "RIGHT panel = FINAL (signierter Befund)"}
MIN_SIDE = 40


def calibration_path() -> Path:
    from radbrain import config
    return config.data_dir() / "calibration.json"


def load_calibration() -> dict:
    cal = load_json(calibration_path())
    return cal if isinstance(cal, dict) else {}


def normalise_rect(x0: float, y0: float, x1: float, y1: float) -> dict:
    l, r = sorted((int(round(x0)), int(round(x1))))
    t, b = sorted((int(round(y0)), int(round(y1))))
    return {"left": l, "top": t, "width": r - l, "height": b - t}


def valid_rect(rect: dict | None) -> bool:
    try:
        return rect["width"] >= MIN_SIDE and rect["height"] >= MIN_SIDE
    except (TypeError, KeyError):
        return False


def save_regions(mode: str, rects: dict, *, virtual_screen: dict | None = None,
                 monitors: list | None = None, dpi_awareness: str | None = None) -> dict:
    if mode not in MODES:
        raise ValueError(mode)
    names = MODES[mode]
    if set(rects) != set(names) or not all(valid_rect(rects[n]) for n in names):
        raise ValueError(f"{mode} needs valid rectangles for {names}")
    cal = load_calibration()
    cal["version"] = 1
    cal["platform"] = sys.platform
    if dpi_awareness is not None:
        cal["dpi_awareness"] = dpi_awareness
    if virtual_screen is not None:
        cal["virtual_screen"] = virtual_screen
    if monitors is not None:
        cal["monitors"] = monitors
    cal[mode] = {**{n: dict(rects[n]) for n in names}, "updated": time.strftime("%Y-%m-%dT%H:%M:%S")}
    save_json(calibration_path(), cal)
    return cal


def get_regions(kind: str, cal: dict | None = None) -> dict | None:
    """{"draft": rect, "final": rect} for kind "pair", {"final": rect} for "final"; None if not calibrated.
    A pair calibration also serves "final" (its right panel) when no single-final calibration exists."""
    cal = load_calibration() if cal is None else cal
    block = cal.get(kind) or {}
    names = MODES[kind]
    if all(valid_rect(block.get(n)) for n in names):
        return {n: block[n] for n in names}
    if kind == "final" and valid_rect((cal.get("pair") or {}).get("final")):
        return {"final": cal["pair"]["final"]}
    return None


def layout_changed(cal: dict | None = None) -> bool:
    """True if the monitor layout differs from the one calibrated against (coordinates may be off)."""
    cal = load_calibration() if cal is None else cal
    saved = cal.get("virtual_screen")
    if not saved:
        return False
    try:
        from radbrain.capture.grab import virtual_screen
        return virtual_screen() != saved
    except Exception:
        return False


# ------------------------------------------------------------------------------------------------ overlay
def run_overlay(mode: str = "pair") -> dict | None:
    """Shows the overlay and returns {name: rect} (screen coordinates) or None if cancelled."""
    import tkinter as tk

    from radbrain.capture.grab import set_dpi_awareness, virtual_screen
    set_dpi_awareness()                       # before Tk creates any window
    names = MODES[mode]
    vs = virtual_screen()
    root = tk.Tk()
    root.title("RadBrain calibration")
    root.overrideredirect(True)
    root.geometry(f"{vs['width']}x{vs['height']}+{vs['left']}+{vs['top']}")
    root.attributes("-topmost", True)
    try:
        root.attributes("-alpha", 0.35)
    except tk.TclError:
        pass
    root.configure(bg="black", cursor="crosshair")
    cv = tk.Canvas(root, bg="#101018", highlightthickness=0, cursor="crosshair")
    cv.pack(fill="both", expand=True)
    state = {"rects": {}, "start": None, "item": None, "result": None}
    colors = {"draft": "#ffd400", "final": "#00e676"}
    hint = cv.create_text(40, 40, anchor="nw", fill="white", font=("Segoe UI", 20, "bold"), text="")
    sub = cv.create_text(40, 80, anchor="nw", fill="#dddddd", font=("Segoe UI", 13),
                         text="Drag a rectangle tightly around the report text. Enter = save · "
                              "Backspace = redo · Esc = cancel")

    def current():
        for n in names:
            if n not in state["rects"]:
                return n
        return None

    def refresh():
        n = current()
        step = len(state["rects"]) + 1
        if n:
            cv.itemconfigure(hint, text=f"Rectangle {step}/{len(names)}: {LABELS[n]}")
        else:
            cv.itemconfigure(hint, text="Done - press Enter to save, Backspace to redo")
        cv.tag_raise(hint)
        cv.tag_raise(sub)

    def on_press(e):
        n = current()
        if not n:
            return
        state["start"] = (e.x_root, e.y_root, e.x, e.y)
        state["item"] = cv.create_rectangle(e.x, e.y, e.x, e.y, outline=colors[n], width=3)

    def on_drag(e):
        if state["start"] and state["item"]:
            _, _, cx, cy = state["start"]
            cv.coords(state["item"], cx, cy, e.x, e.y)

    def on_release(e):
        n = current()
        if not (n and state["start"]):
            return
        sx, sy, cx, cy = state["start"]
        rect = normalise_rect(sx, sy, e.x_root, e.y_root)
        state["start"] = None
        if not valid_rect(rect):
            cv.delete(state["item"])
            state["item"] = None
            return
        state["rects"][n] = rect
        cv.itemconfigure(state["item"], tags=(f"r_{n}",))
        cv.create_text(min(cx, e.x) + 8, min(cy, e.y) + 6, anchor="nw", fill=colors[n],
                       font=("Segoe UI", 14, "bold"), text=n.upper(), tags=(f"r_{n}",))
        state["item"] = None
        refresh()

    def on_back(_e=None):
        if state["rects"]:
            last = list(state["rects"])[-1]
            state["rects"].pop(last)
            cv.delete(f"r_{last}")
            refresh()

    def on_enter(_e=None):
        if current() is None:
            state["result"] = dict(state["rects"])
            root.destroy()

    def on_esc(_e=None):
        state["result"] = None
        root.destroy()

    cv.bind("<ButtonPress-1>", on_press)
    cv.bind("<B1-Motion>", on_drag)
    cv.bind("<ButtonRelease-1>", on_release)
    root.bind("<Return>", on_enter)
    root.bind("<KP_Enter>", on_enter)
    root.bind("<BackSpace>", on_back)
    root.bind("<Escape>", on_esc)
    refresh()
    root.after(50, lambda: (root.focus_force(), root.lift()))
    root.mainloop()
    return state["result"]


def calibrate(mode: str = "pair") -> dict | None:
    from radbrain.capture.grab import monitors, set_dpi_awareness, virtual_screen
    dpi = set_dpi_awareness()
    rects = run_overlay(mode)
    if not rects:
        return None
    mons = [{k: int(m[k]) for k in ("left", "top", "width", "height")} for m in monitors()]
    return save_regions(mode, rects, virtual_screen=virtual_screen(), monitors=mons, dpi_awareness=dpi)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="RadBrain panel calibration")
    ap.add_argument("--mode", choices=sorted(MODES), default="pair")
    ap.add_argument("--show", action="store_true", help="print the stored calibration and exit")
    args = ap.parse_args(argv)
    if args.show:
        import json
        print(json.dumps(load_calibration(), indent=2))
        return 0
    cal = calibrate(args.mode)
    if cal is None:
        print("calibration cancelled")
        return 1
    print(f"saved {args.mode} calibration -> {calibration_path()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
