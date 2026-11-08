"""In-memory screen capture. Nothing in here ever writes an image to disk.

  grab_region(l, t, w, h)   mss, Windows + macOS (on macOS coords are points, the image comes back in pixels)
  grab_rect(rect)           same with a {"left","top","width","height"} dict (calibration.json format)
  find_citrix_windows()     Windows: EnumWindows, matches titles/classes/processes of Citrix Workspace
  grab_window(hwnd, method) Windows: PrintWindow(PW_RENDERFULLCONTENT) -> fallback mss of the window rect;
                            "wgc" uses Windows Graphics Capture via the optional `windows-capture` package
  is_black(img)             blank-capture test: >98 % near-black pixels or almost no variance

Windows-only pieces are guarded so the module imports on the Mac.
"""
from __future__ import annotations

import ctypes
import os
import sys
import threading

from PIL import Image, ImageStat

IS_WIN = sys.platform == "win32"
PW_RENDERFULLCONTENT = 0x00000002
CITRIX_TITLE_KEYS = ("citrix", "workspace", "desktop viewer")
CITRIX_CLASS_KEYS = ("transparent windows client", "wfica", "ctxica", "citrix")
CITRIX_EXES = ("wfica32.exe", "wfica.exe", "cdviewer.exe", "selfservice.exe", "receiver.exe")


# ------------------------------------------------------------------------------------------------ DPI
_DPI_DONE = False


def set_dpi_awareness() -> str:
    """Per-monitor DPI awareness so window rects, Tk coordinates and mss pixels agree. Idempotent."""
    global _DPI_DONE
    if not IS_WIN:
        return "n/a"
    if _DPI_DONE:
        return "already"
    _DPI_DONE = True
    try:   # Windows 10 1703+: PER_MONITOR_AWARE_V2
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return "per_monitor_v2"
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)     # PROCESS_PER_MONITOR_DPI_AWARE
        return "per_monitor"
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        return "system"
    except Exception:
        return "unaware"


# ------------------------------------------------------------------------------------------------ mss
def _mss():
    import mss
    factory = getattr(mss, "MSS", None) or mss.mss        # mss >= 10 renamed the factory
    return factory()


def _shot_to_image(shot) -> Image.Image:
    return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def grab_region(left: int, top: int, width: int, height: int) -> Image.Image:
    """Screen region -> PIL image, in memory. A fresh mss instance per call (mss handles are per-thread)."""
    set_dpi_awareness()
    if width <= 0 or height <= 0:
        raise ValueError("empty region")
    with _mss() as sct:
        shot = sct.grab({"left": int(left), "top": int(top), "width": int(width), "height": int(height)})
        img = _shot_to_image(shot)
        del shot
    return img


def grab_rect(rect: dict) -> Image.Image:
    return grab_region(rect["left"], rect["top"], rect["width"], rect["height"])


def monitors() -> list[dict]:
    """mss monitors: [0] is the virtual screen (union), [1..] the physical monitors."""
    set_dpi_awareness()
    with _mss() as sct:
        return [dict(m) for m in sct.monitors]


def virtual_screen() -> dict:
    m = monitors()[0]
    return {k: int(m[k]) for k in ("left", "top", "width", "height")}


def mac_screen_capture_allowed() -> bool | None:
    """macOS: has this process Screen Recording permission? None if it cannot be determined."""
    if sys.platform != "darwin":
        return None
    try:
        cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
        return bool(cg.CGPreflightScreenCaptureAccess())
    except Exception:
        return None


# ------------------------------------------------------------------------------------------------ blank test
def is_black(img: Image.Image, *, dark_frac: float = 0.98, min_std: float = 1.5) -> bool:
    """True for a failed capture: >98 % near-black pixels (DRM/overlay black) or ~zero variance (flat fill)."""
    g = img.convert("L")
    if max(g.size) > 800:
        g.thumbnail((800, 800))
    hist = g.histogram()
    n = max(1, sum(hist))
    if sum(hist[:20]) / n > dark_frac:
        return True
    return ImageStat.Stat(g).stddev[0] < min_std


is_blank = is_black


# ------------------------------------------------------------------------------------------------ Win32
if IS_WIN:
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    try:
        dwmapi = ctypes.WinDLL("dwmapi")
    except OSError:  # pragma: no cover
        dwmapi = None

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.IsIconic.argtypes = [wintypes.HWND]
    user32.IsIconic.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user32.GetWindowRect.restype = wintypes.BOOL
    user32.GetDC.argtypes = [wintypes.HWND]
    user32.GetDC.restype = wintypes.HDC
    user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user32.ReleaseDC.restype = ctypes.c_int
    user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user32.PrintWindow.restype = wintypes.BOOL
    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi32.CreateCompatibleDC.restype = wintypes.HDC
    gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
    gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
    gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi32.SelectObject.restype = wintypes.HGDIOBJ
    gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi32.DeleteObject.restype = wintypes.BOOL
    gdi32.DeleteDC.argtypes = [wintypes.HDC]
    gdi32.DeleteDC.restype = wintypes.BOOL
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                    ctypes.POINTER(wintypes.DWORD)]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG), ("biHeight", wintypes.LONG),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD),
                    ("biCompression", wintypes.DWORD), ("biSizeImage", wintypes.DWORD),
                    ("biXPelsPerMeter", wintypes.LONG), ("biYPelsPerMeter", wintypes.LONG),
                    ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]

    gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT,
                                ctypes.c_void_p, ctypes.POINTER(BITMAPINFO), wintypes.UINT]
    gdi32.GetDIBits.restype = ctypes.c_int


def _require_win():
    if not IS_WIN:
        raise OSError("Windows only")


def _process_exe(pid: int) -> str:
    h = kernel32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value)
        return ""
    finally:
        kernel32.CloseHandle(h)


def window_rect(hwnd) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) in physical pixels; DWM extended frame bounds (no invisible borders)
    when available, else GetWindowRect."""
    _require_win()
    set_dpi_awareness()
    r = wintypes.RECT()
    if dwmapi is not None:
        try:
            if dwmapi.DwmGetWindowAttribute(wintypes.HWND(hwnd), 9, ctypes.byref(r), ctypes.sizeof(r)) == 0:
                return r.left, r.top, r.right, r.bottom
        except Exception:
            pass
    user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def describe_window(hwnd) -> dict:
    _require_win()
    n = user32.GetWindowTextLengthW(hwnd)
    tbuf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, tbuf, n + 1)
    cbuf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cbuf, 256)
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return {"hwnd": int(hwnd), "title": tbuf.value, "cls": cbuf.value, "pid": int(pid.value),
            "exe": _process_exe(pid.value), "rect": window_rect(hwnd),
            "minimised": bool(user32.IsIconic(hwnd))}


def citrix_match(info: dict) -> list[str]:
    why = []
    t, c, e = info.get("title", "").lower(), info.get("cls", "").lower(), info.get("exe", "").lower()
    why += [f"title:{k}" for k in CITRIX_TITLE_KEYS if k in t]
    why += [f"class:{k}" for k in CITRIX_CLASS_KEYS if k in c]
    why += [f"exe:{k}" for k in CITRIX_EXES if e == k]
    return why


def list_windows() -> list[dict]:
    """All visible, non-empty top-level windows (in memory; callers must not log titles)."""
    _require_win()
    hwnds: list[int] = []

    def cb(hwnd, _lp):
        if user32.IsWindowVisible(hwnd):
            hwnds.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(cb), 0)
    out = []
    for h in hwnds:
        try:
            info = describe_window(h)
        except Exception:
            continue
        l, t, r, b = info["rect"]
        if r - l >= 50 and b - t >= 50:
            out.append(info)
    return out


def find_citrix_windows() -> list[dict]:
    """Visible Citrix windows (seamless apps, Desktop Viewer, Workspace). Each dict carries a "match" list.
    Titles are returned for in-process use only; never log or persist them (a PACS title can carry a name)."""
    if not IS_WIN:
        return []
    out = []
    for info in list_windows():
        why = citrix_match(info)
        if why:
            info["match"] = why
            out.append(info)
    return out


def foreground_window() -> int | None:
    if not IS_WIN:
        return None
    return int(user32.GetForegroundWindow() or 0) or None


def _printwindow(hwnd) -> Image.Image | None:
    _require_win()
    set_dpi_awareness()
    r = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(r))         # PrintWindow paints relative to GetWindowRect
    w, h = r.right - r.left, r.bottom - r.top
    if w <= 0 or h <= 0:
        return None
    screen_dc = user32.GetDC(None)
    mem_dc = gdi32.CreateCompatibleDC(screen_dc)
    bmp = gdi32.CreateCompatibleBitmap(screen_dc, w, h)
    old = gdi32.SelectObject(mem_dc, bmp)
    buf = None
    try:
        ok = user32.PrintWindow(hwnd, mem_dc, PW_RENDERFULLCONTENT)
        gdi32.SelectObject(mem_dc, old)                  # GetDIBits wants the bitmap deselected
        old = None
        if not ok:
            return None
        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h                      # top-down rows
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0                  # BI_RGB
        buf = ctypes.create_string_buffer(w * h * 4)
        lines = gdi32.GetDIBits(mem_dc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
        if lines != h:
            return None
        return Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1).copy()
    finally:
        if old is not None:
            gdi32.SelectObject(mem_dc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mem_dc)
        user32.ReleaseDC(None, screen_dc)
        del buf


def _mss_window(hwnd) -> Image.Image | None:
    l, t, r, b = window_rect(hwnd)
    if r - l <= 0 or b - t <= 0:
        return None
    return grab_region(l, t, r - l, b - t)


def wgc_available() -> bool:
    if not IS_WIN:
        return False
    try:
        import importlib.util
        return importlib.util.find_spec("windows_capture") is not None
    except Exception:
        return False


def _wgc_window(hwnd, title: str | None = None, timeout: float = 4.0) -> Image.Image | None:
    """One frame via Windows Graphics Capture (package `windows-capture`), converted in memory.
    Frame.save_as_image is never used."""
    from windows_capture import WindowsCapture
    holder: dict = {}
    done = threading.Event()
    if title is None:
        title = describe_window(hwnd)["title"]
    cap = None
    for kwargs in ({"window_hwnd": int(hwnd)}, {"window_name": title}):
        try:
            cap = WindowsCapture(cursor_capture=False, draw_border=False, **kwargs)
            break
        except TypeError:
            continue
    if cap is None:
        return None

    @cap.event
    def on_frame_arrived(frame, capture_control):
        try:
            if "img" not in holder:
                fb = frame.frame_buffer                  # numpy (h, w, 4) BGRA
                h, w = fb.shape[0], fb.shape[1]
                holder["img"] = Image.frombytes("RGB", (w, h), fb.tobytes(), "raw", "BGRX")
                del fb
        finally:
            done.set()
            capture_control.stop()

    @cap.event
    def on_closed():
        done.set()

    control = cap.start_free_threaded()
    done.wait(timeout)
    try:
        control.stop()
    except Exception:
        pass
    return holder.pop("img", None)


def grab_window(hwnd, method: str = "auto") -> Image.Image | None:
    """method: "printwindow" | "mss" | "wgc" | "auto" (PrintWindow, fall back to mss if blank/failed)."""
    _require_win()
    if method == "printwindow":
        return _printwindow(hwnd)
    if method == "mss":
        return _mss_window(hwnd)
    if method == "wgc":
        return _wgc_window(hwnd) if wgc_available() else None
    if method != "auto":
        raise ValueError(method)
    img = None
    try:
        img = _printwindow(hwnd)
    except Exception:
        img = None
    if img is None or is_black(img):
        img = _mss_window(hwnd)
    return img
