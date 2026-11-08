"""RadBrain capture tray app (Windows): python -m radbrain.capture.hotkey_app [--once pair|final]

  Ctrl+Shift+B  capture a PAIR  (left panel = draft, right panel = signed final)
  Ctrl+Shift+F  capture a FINAL (signed report only)

Route per data_dir()/settings.json "route": "clipboard" (click panel, Ctrl+A, Ctrl+C, restore clipboard) or
"ocr" (grab calibrated regions in memory -> OCR -> drop the image). Default: probe_citrix.json
recommended_route, else "ocr". A failed clipboard copy falls back to OCR for that capture.
Result goes to pipeline.ingest(kind, draft_text, final_text, source="hotkey"); a toast shows
"Saved — B1 · CT Thorax · Lungenembolie" / "Quarantined — <reason>" / "Duplicate — skipped".

Tray: counter tooltip "RadBrain · B1 12/500 · B2 … · B3 …", Recalibrate (pair/final), Route toggle,
Open dashboard (http://127.0.0.1:8650), Open quarantine folder, Quit.
Logs (data_dir()/logs/capture.log): statuses, signer codes, lengths, timings. Never report text, never titles.
The module imports on macOS/Linux (Windows APIs are only touched inside functions) so capture() is testable.
"""
from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path
from typing import Callable

IS_WIN = sys.platform == "win32"
DASHBOARD_URL = "http://127.0.0.1:8650"
HOTKEYS = {1: ("pair", 0x42), 2: ("final", 0x46)}       # id -> (kind, VK_B / VK_F)
MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT = 0x0002, 0x0004, 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012
MIN_TEXT_CHARS = 20
PROJECT_DIR = Path(__file__).resolve().parents[2]       # folder that contains the radbrain package

log = logging.getLogger("radbrain.capture")


# ------------------------------------------------------------------------------------------------ logging
def setup_logging() -> Path:
    from radbrain import config
    p = config.data_dir() / "logs" / "capture.log"
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) for h in log.handlers):
        h = logging.handlers.RotatingFileHandler(p, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        log.addHandler(h)
        log.setLevel(logging.INFO)
        log.propagate = False
    return p


def log_exception(where: str, e: BaseException) -> None:
    """Exception type + stack frames only: messages can carry data, so they are not logged."""
    frames = "".join(traceback.format_tb(e.__traceback__)[-4:]).replace("\n", " | ")
    log.error("%s failed: %s at %s", where, type(e).__name__, frames[-600:])


# ------------------------------------------------------------------------------------------------ text bits
def toast_text(result: dict) -> str:
    st = (result or {}).get("status")
    if st == "saved":
        mod = " ".join(x for x in (result.get("modality"), result.get("region")) if x)
        parts = [result.get("signer") or "?"]
        if mod:
            parts.append(mod)
        if result.get("pathologies"):
            parts.append(str(result["pathologies"][0]))
        return "Saved — " + " · ".join(parts)
    if st == "quarantined":
        return f"Quarantined — {result.get('reason') or 'unknown'}"
    if st == "duplicate":
        return "Duplicate — skipped"
    return f"Capture failed — {(result or {}).get('reason') or 'unknown'}"


def counts_tooltip(counts: dict | None) -> str:
    from radbrain import config
    parts = ["RadBrain"]
    for code in config.CODES:
        c = (counts or {}).get(code) or {}
        parts.append(f"{code} {int(c.get('pairs', 0))}/{config.TARGET_PAIRS}")
    return " · ".join(parts)[:127]          # Windows tray tooltip limit (szTip[128])


# ------------------------------------------------------------------------------------------------ capture
def _default_ingest(kind, draft_text, final_text, source="hotkey"):
    from radbrain import pipeline
    return pipeline.ingest(kind, draft_text, final_text, source=source)


def _default_grab(rect):
    from radbrain.capture.grab import grab_rect
    return grab_rect(rect)


def _default_ocr(img):
    from radbrain.capture.ocr import ocr
    return ocr(img)


def _default_copy(regions):
    from radbrain.capture.clip import copy_regions
    return copy_regions(regions)


def _default_detect(kind):
    """Find the panels on the current screen (autocal); None → use the saved calibration."""
    from radbrain.capture import autocal
    from radbrain.capture.settings import load_json, settings_path
    if load_json(settings_path()).get("autodetect", True) is False:
        return None
    try:
        return autocal.auto(kind, save=True)
    except Exception as e:  # noqa: BLE001
        log_exception("autodetect", e)
        return None


def _default_blank(img):
    from radbrain.capture.grab import is_black
    return is_black(img)


def _fail(reason: str, **extra) -> dict:
    return {"status": "error", "id": None, "signer": None, "modality": None, "region": None,
            "pathologies": [], "reason": reason, **extra}


def _ocr_regions(regions, grab, ocr, blank) -> tuple[dict, str | None]:
    texts: dict[str, str] = {}
    for name, rect in regions.items():
        img = grab(rect)
        try:
            if blank(img):
                return texts, f"blank_capture:{name}"
            texts[name] = ocr(img)
        finally:
            del img                       # the screenshot never outlives this loop iteration
    return texts, None


def capture(kind: str, *, route: str | None = None, regions: dict | None = None,
            grab: Callable | None = None, ocr: Callable | None = None, ingest: Callable | None = None,
            copy: Callable | None = None, blank: Callable | None = None, fallback: bool = True,
            detect: Callable | None = None) -> dict:
    """One capture. Every side-effecting dependency is injectable (tests run this on the Mac).
    Returns pipeline.ingest's dict, or {"status": "error", "reason": ...} when nothing usable was captured."""
    from radbrain.capture import calibrate
    from radbrain.capture.settings import current_route
    if kind not in ("pair", "final"):
        raise ValueError(kind)
    grab, ocr, ingest = grab or _default_grab, ocr or _default_ocr, ingest or _default_ingest
    copy, blank = copy or _default_copy, blank or _default_blank
    route = route or current_route()
    t0 = time.perf_counter()
    if regions is None and route != "clipboard":
        regions = (detect or _default_detect)(kind)      # panels found on screen right now (autocal)
    regions = regions or calibrate.get_regions(kind)
    if not regions:
        log.info("capture kind=%s route=%s status=error reason=not_calibrated", kind, route)
        return _fail("not_calibrated")
    need = ("draft", "final") if kind == "pair" else ("final",)
    regions = {n: regions[n] for n in need}

    texts: dict = {}
    used = route
    err = None
    if route == "clipboard":
        try:
            texts = copy(regions) or {}
        except Exception as e:
            log_exception("clipboard", e)
            texts = {}
        missing = [n for n in need if not texts.get(n) or len(texts[n].strip()) < MIN_TEXT_CHARS]
        if missing:
            if fallback:
                log.info("capture kind=%s clipboard_empty=%s -> ocr fallback", kind, ",".join(missing))
                used = "ocr+fallback"
                more, err = _ocr_regions({n: regions[n] for n in missing}, grab, ocr, blank)
                texts.update(more)
            else:
                err = f"clipboard_empty:{missing[0]}"
    else:
        used = "ocr"
        texts, err = _ocr_regions(regions, grab, ocr, blank)

    if err is None:
        for n in need:
            if not texts.get(n) or len(texts[n].strip()) < MIN_TEXT_CHARS:
                err = f"no_text:{n}"
                break
    lens = "/".join(str(len(texts.get(n) or "")) for n in need)
    if err:
        texts.clear()
        log.info("capture kind=%s route=%s status=error reason=%s chars=%s sec=%.2f",
                 kind, used, err, lens, time.perf_counter() - t0)
        return _fail(err)

    draft = texts.get("draft") if kind == "pair" else None
    final = texts["final"]
    texts.clear()
    try:
        res = ingest(kind, draft, final, source="hotkey")
    except Exception as e:
        log_exception("ingest", e)
        return _fail(f"ingest_error:{type(e).__name__}")
    finally:
        del draft, final
    log.info("capture kind=%s route=%s status=%s id=%s signer=%s chars=%s sec=%.2f", kind, used,
             res.get("status"), res.get("id"), res.get("signer"), lens, time.perf_counter() - t0)
    return res


# ------------------------------------------------------------------------------------------------ UI bits
def make_icon(busy: bool = False):
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([2, 2, 61, 61], radius=14, fill=(196, 120, 10) if busy else (24, 60, 120))
    try:
        font = ImageFont.load_default(42)
    except TypeError:  # very old Pillow
        font = ImageFont.load_default()
    d.text((32, 33), "R", font=font, fill="white", anchor="mm")
    d.ellipse([44, 6, 58, 20], fill=(26, 138, 92))
    return img


_TOAST_LOCK = threading.Lock()


def _tk_toast(text: str, seconds: float = 3.0) -> None:
    import tkinter as tk
    with _TOAST_LOCK:
        root = tk.Tk()
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg="#1d2733")
        tk.Label(root, text=text, bg="#1d2733", fg="white", font=("Segoe UI", 11), padx=18, pady=12).pack()
        root.update_idletasks()
        w, h = root.winfo_width(), root.winfo_height()
        root.geometry(f"+{root.winfo_screenwidth() - w - 24}+{root.winfo_screenheight() - h - 72}")
        state = {"a": 0.95}

        def fade():
            state["a"] -= 0.08
            if state["a"] <= 0:
                root.destroy()
                return
            try:
                root.attributes("-alpha", state["a"])
            except tk.TclError:
                pass
            root.after(40, fade)

        root.after(int(seconds * 1000), fade)
        root.mainloop()


def show_toast(text: str) -> None:
    try:
        from winotify import Notification
        Notification(app_id="RadBrain", title="RadBrain", msg=text, duration="short").show()
        return
    except Exception:
        pass
    threading.Thread(target=_tk_toast, args=(text,), daemon=True).start()


# ------------------------------------------------------------------------------------------------ Win32
def _single_instance() -> bool:
    if not IS_WIN:
        return True
    import ctypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.CreateMutexW.restype = ctypes.c_void_p
    _single_instance.handle = k.CreateMutexW(None, False, "Local\\RadBrainCapture")
    return ctypes.get_last_error() != 183           # ERROR_ALREADY_EXISTS


class HotkeyThread(threading.Thread):
    """RegisterHotKey + GetMessage loop in one thread (hotkeys belong to the registering thread)."""

    def __init__(self, on_hotkey: Callable[[str], None]):
        super().__init__(name="radbrain-hotkeys", daemon=True)
        self.on_hotkey = on_hotkey
        self.thread_id = None
        self.registered: list[str] = []
        self.failed: list[str] = []
        self.ready = threading.Event()

    def run(self):
        import ctypes
        from ctypes import wintypes
        u = ctypes.WinDLL("user32", use_last_error=True)
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        u.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        u.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
        u.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        self.thread_id = k.GetCurrentThreadId()
        for hid, (kind, vk) in HOTKEYS.items():
            if u.RegisterHotKey(None, hid, MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT, vk):
                self.registered.append(kind)
            else:
                self.failed.append(kind)
                log.error("RegisterHotKey failed kind=%s err=%s", kind, ctypes.get_last_error())
        self.ready.set()
        msg = wintypes.MSG()
        try:
            while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY and msg.wParam in HOTKEYS:
                    self.on_hotkey(HOTKEYS[msg.wParam][0])
        finally:
            for hid in HOTKEYS:
                u.UnregisterHotKey(None, hid)

    def stop(self):
        if self.thread_id:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)


# ------------------------------------------------------------------------------------------------ app
class TrayApp:
    def __init__(self):
        self.lock = threading.Lock()
        self.icon = None
        self.hotkeys = None
        self._stop = threading.Event()

    # capture worker -------------------------------------------------------------
    def on_hotkey(self, kind: str):
        threading.Thread(target=self.run_capture, args=(kind,), daemon=True).start()

    def run_capture(self, kind: str):
        if not self.lock.acquire(blocking=False):
            log.info("capture kind=%s ignored: busy", kind)
            return
        try:
            self._set_busy(True)
            res = capture(kind)
            show_toast(toast_text(res))
            self.refresh_tooltip()
        except Exception as e:
            log_exception("capture", e)
            show_toast(f"Capture failed — {type(e).__name__}")
        finally:
            self._set_busy(False)
            self.lock.release()

    def _set_busy(self, busy: bool):
        if self.icon is not None:
            try:
                self.icon.icon = make_icon(busy)
            except Exception:
                pass

    def refresh_tooltip(self):
        try:
            from radbrain import pipeline
            tip = counts_tooltip(pipeline.counts())
        except Exception as e:
            tip = "RadBrain · counter unavailable"
            log.info("counts unavailable: %s", type(e).__name__)
        if self.icon is not None:
            self.icon.title = tip

    def _tooltip_loop(self):
        while not self._stop.wait(60):
            self.refresh_tooltip()

    # menu actions -------------------------------------------------------------------
    def recalibrate(self, mode: str):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PROJECT_DIR) + os.pathsep + env.get("PYTHONPATH", "")
        subprocess.Popen([sys.executable, "-m", "radbrain.capture.calibrate", "--mode", mode],
                         cwd=str(PROJECT_DIR), env=env)
        log.info("recalibrate mode=%s started", mode)

    def set_route(self, route: str):
        from radbrain.capture.settings import update_settings
        update_settings(route=route)
        log.info("route set to %s", route)
        show_toast(f"Route: {route}")

    def open_quarantine(self):
        from radbrain import config
        p = str(config.quarantine_dir())
        if IS_WIN:
            os.startfile(p)  # noqa: S606 - local folder
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", p])

    def quit(self, icon=None, _item=None):
        self._stop.set()
        if self.hotkeys:
            self.hotkeys.stop()
        log.info("quit")
        if self.icon is not None:
            self.icon.stop()

    def build_menu(self):
        from pystray import Menu, MenuItem as Item

        from radbrain.capture.settings import current_route
        return Menu(
            Item("Capture pair  (Ctrl+Shift+B)", lambda: self.on_hotkey("pair")),
            Item("Capture final (Ctrl+Shift+F)", lambda: self.on_hotkey("final")),
            Menu.SEPARATOR,
            Item("Recalibrate (pair)", lambda: self.recalibrate("pair")),
            Item("Recalibrate (final)", lambda: self.recalibrate("final")),
            Item("Route: clipboard", lambda: self.set_route("clipboard"),
                 checked=lambda _i: current_route() == "clipboard", radio=True),
            Item("Route: OCR", lambda: self.set_route("ocr"),
                 checked=lambda _i: current_route() == "ocr", radio=True),
            Menu.SEPARATOR,
            Item("Open dashboard", lambda: webbrowser.open(DASHBOARD_URL)),
            Item("Open quarantine folder", lambda: self.open_quarantine()),
            Menu.SEPARATOR,
            Item("Quit", self.quit),
        )

    def run(self) -> int:
        import pystray
        self.hotkeys = HotkeyThread(self.on_hotkey)
        self.hotkeys.start()
        self.hotkeys.ready.wait(5)
        self.icon = pystray.Icon("RadBrain", make_icon(), "RadBrain", self.build_menu())
        self.refresh_tooltip()
        threading.Thread(target=self._tooltip_loop, daemon=True, name="radbrain-tooltip").start()
        log.info("started hotkeys=%s failed=%s", ",".join(self.hotkeys.registered) or "-",
                 ",".join(self.hotkeys.failed) or "-")
        if self.hotkeys.failed:
            show_toast("Hotkey busy: " + ", ".join(self.hotkeys.failed) + " (another app holds it)")
        self.icon.run()
        return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="RadBrain capture tray app (Windows)")
    ap.add_argument("--once", choices=["pair", "final"], help="run one capture now, print the toast, exit")
    ap.add_argument("--route", choices=["clipboard", "ocr"], help="override the route for --once")
    args = ap.parse_args(argv)
    setup_logging()
    threading.excepthook = lambda a: log_exception(f"thread {a.thread.name if a.thread else '?'}", a.exc_value)
    from radbrain.capture.grab import set_dpi_awareness
    set_dpi_awareness()                      # coordinates must match calibration.json and mss
    if args.once:
        res = capture(args.once, route=args.route)
        print(toast_text(res))
        return 0 if res.get("status") in ("saved", "duplicate", "quarantined") else 1
    if not IS_WIN:
        print("hotkey_app tray mode is Windows-only; use --once on other systems.")
        return 2
    if not _single_instance():
        log.info("another instance is running; exiting")
        return 0
    return TrayApp().run()


if __name__ == "__main__":
    sys.exit(main())
