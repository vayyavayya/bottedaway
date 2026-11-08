"""Clipboard route: click into a calibrated panel, Ctrl+A, Ctrl+C, read CF_UNICODETEXT, restore the clipboard.

    copy_region_text(rect) -> str | None      one panel; None if the clipboard did not change or came back empty
    copy_regions({"draft": rect, "final": rect}) -> {"draft": str|None, "final": str|None}

The user's previous clipboard text is saved once and restored at the end (non-text clipboard content cannot
be restored and is cleared instead), so report text never lingers on the clipboard. The mouse cursor is put
back where it was. Nothing is logged or written. Win32 via ctypes; every OS call goes through a backend
object so the logic is testable on the Mac with a fake.
"""
from __future__ import annotations

import ctypes
import sys
import time

IS_WIN = sys.platform == "win32"
VK_CONTROL, VK_SHIFT, VK_MENU, VK_LWIN, VK_RWIN = 0x11, 0x10, 0x12, 0x5B, 0x5C
VK_A, VK_C = 0x41, 0x43
CF_UNICODETEXT = 13


class Win32Backend:
    """SendInput mouse/keyboard + Win32 clipboard."""

    def __init__(self):
        if not IS_WIN:
            raise OSError("Win32Backend needs Windows")
        from ctypes import wintypes
        self.w = wintypes
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        u, k = self.user32, self.kernel32
        ULONG_PTR = ctypes.c_size_t

        class MOUSEINPUT(ctypes.Structure):
            _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                        ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                        ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

        class HARDWAREINPUT(ctypes.Structure):
            _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]

        class _U(ctypes.Union):
            _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ("u",)
            _fields_ = [("type", wintypes.DWORD), ("u", _U)]

        self.INPUT, self.MOUSEINPUT, self.KEYBDINPUT = INPUT, MOUSEINPUT, KEYBDINPUT
        u.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        u.SendInput.restype = wintypes.UINT
        u.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
        u.MapVirtualKeyW.restype = wintypes.UINT
        u.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
        u.SetCursorPos.restype = wintypes.BOOL
        u.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
        u.GetCursorPos.restype = wintypes.BOOL
        u.GetAsyncKeyState.argtypes = [ctypes.c_int]
        u.GetAsyncKeyState.restype = ctypes.c_short
        u.OpenClipboard.argtypes = [wintypes.HWND]
        u.OpenClipboard.restype = wintypes.BOOL
        u.CloseClipboard.argtypes = []
        u.CloseClipboard.restype = wintypes.BOOL
        u.EmptyClipboard.argtypes = []
        u.EmptyClipboard.restype = wintypes.BOOL
        u.GetClipboardData.argtypes = [wintypes.UINT]
        u.GetClipboardData.restype = wintypes.HANDLE
        u.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
        u.SetClipboardData.restype = wintypes.HANDLE
        u.IsClipboardFormatAvailable.argtypes = [wintypes.UINT]
        u.IsClipboardFormatAvailable.restype = wintypes.BOOL
        u.CountClipboardFormats.argtypes = []
        u.CountClipboardFormats.restype = ctypes.c_int
        u.GetClipboardSequenceNumber.argtypes = []
        u.GetClipboardSequenceNumber.restype = wintypes.DWORD
        k.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
        k.GlobalAlloc.restype = wintypes.HGLOBAL
        k.GlobalLock.argtypes = [wintypes.HGLOBAL]
        k.GlobalLock.restype = ctypes.c_void_p
        k.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
        k.GlobalUnlock.restype = wintypes.BOOL
        k.GlobalFree.argtypes = [wintypes.HGLOBAL]
        k.GlobalFree.restype = wintypes.HGLOBAL

    # ---- input
    def _send(self, *inputs):
        arr = (self.INPUT * len(inputs))(*inputs)
        return self.user32.SendInput(len(inputs), arr, ctypes.sizeof(self.INPUT))

    def _key(self, vk, up=False):
        # VK *and* hardware scan code: the Citrix client forwards scan codes, a bare VK may arrive as nothing
        i = self.INPUT(type=1)
        scan = self.user32.MapVirtualKeyW(vk, 0)                  # MAPVK_VK_TO_VSC
        i.ki = self.KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=0x0002 if up else 0, time=0, dwExtraInfo=0)
        return i

    def _mouse(self, flags):
        i = self.INPUT(type=0)
        i.mi = self.MOUSEINPUT(dx=0, dy=0, mouseData=0, dwFlags=flags, time=0, dwExtraInfo=0)
        return i

    def cursor_pos(self):
        p = self.w.POINT()
        self.user32.GetCursorPos(ctypes.byref(p))
        return p.x, p.y

    def set_cursor(self, x, y):
        self.user32.SetCursorPos(int(x), int(y))

    def click(self, x, y):
        self.set_cursor(x, y)
        time.sleep(0.03)
        self._send(self._mouse(0x0002), self._mouse(0x0004))      # LEFTDOWN, LEFTUP

    def ctrl(self, vk):
        self._send(self._key(VK_CONTROL), self._key(vk), self._key(vk, up=True), self._key(VK_CONTROL, up=True))

    def modifiers_down(self) -> bool:
        return any(self.user32.GetAsyncKeyState(v) & 0x8000 for v in (VK_CONTROL, VK_SHIFT, VK_MENU, VK_LWIN, VK_RWIN))

    # ---- clipboard
    def _open(self, tries=20):
        for _ in range(tries):
            if self.user32.OpenClipboard(None):
                return True
            time.sleep(0.025)
        return False

    def seq(self) -> int:
        return int(self.user32.GetClipboardSequenceNumber())

    def get_text(self) -> str | None:
        if not self._open():
            return None
        try:
            if not self.user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                return None
            h = self.user32.GetClipboardData(CF_UNICODETEXT)
            if not h:
                return None
            p = self.kernel32.GlobalLock(h)
            if not p:
                return None
            try:
                return ctypes.wstring_at(p)
            finally:
                self.kernel32.GlobalUnlock(h)
        finally:
            self.user32.CloseClipboard()

    def has_content(self) -> bool:
        if not self._open():
            return False
        try:
            return self.user32.CountClipboardFormats() > 0
        finally:
            self.user32.CloseClipboard()

    def set_text(self, text: str) -> bool:
        data = ctypes.create_unicode_buffer(text)
        size = ctypes.sizeof(data)
        if not self._open():
            return False
        try:
            self.user32.EmptyClipboard()
            h = self.kernel32.GlobalAlloc(0x0002, size)          # GMEM_MOVEABLE
            if not h:
                return False
            p = self.kernel32.GlobalLock(h)
            ctypes.memmove(p, data, size)
            self.kernel32.GlobalUnlock(h)
            if not self.user32.SetClipboardData(CF_UNICODETEXT, h):
                self.kernel32.GlobalFree(h)
                return False
            return True                                          # the system owns h now
        finally:
            self.user32.CloseClipboard()
            del data

    def clear(self) -> bool:
        if not self._open():
            return False
        try:
            return bool(self.user32.EmptyClipboard())
        finally:
            self.user32.CloseClipboard()


def default_backend():
    return Win32Backend()


def _wait_modifiers_released(be, timeout: float = 2.0) -> bool:
    """The hotkey is Ctrl+Shift+...: if Shift is still held, our Ctrl+A would become Ctrl+Shift+A."""
    t_end = time.monotonic() + timeout
    while time.monotonic() < t_end:
        if not be.modifiers_down():
            return True
        time.sleep(0.02)
    return False


def _center(rect: dict) -> tuple[int, int]:
    return rect["left"] + rect["width"] // 2, rect["top"] + rect["height"] // 2


def _copy_one(be, rect: dict, *, settle: float, timeout: float, deselect: bool) -> str | None:
    x, y = _center(rect)
    before = be.seq()
    be.click(x, y)
    time.sleep(settle)
    be.ctrl(VK_A)
    time.sleep(settle)
    be.ctrl(VK_C)
    # Citrix syncs the clipboard asynchronously: poll for the sequence number to move
    t_end = time.monotonic() + timeout
    changed = False
    while time.monotonic() < t_end:
        if be.seq() != before:
            changed = True
            time.sleep(0.05)              # let delayed rendering finish
            break
        time.sleep(0.03)
    text = be.get_text() if changed else None
    if deselect:
        be.click(x, y)                    # collapse the Ctrl+A selection
    if not text or not text.strip():
        return None
    return text


def copy_regions(regions: dict[str, dict], *, backend=None, settle: float = 0.12, timeout: float = 2.5,
                 deselect: bool = True) -> dict[str, str | None]:
    """Panel by panel (dict order, e.g. draft then final). Restores clipboard and cursor afterwards."""
    be = backend or default_backend()
    if not _wait_modifiers_released(be):
        raise RuntimeError("modifier keys still held")
    saved_text = be.get_text()
    cursor = be.cursor_pos()
    out: dict[str, str | None] = {}
    try:
        for name, rect in regions.items():
            out[name] = _copy_one(be, rect, settle=settle, timeout=timeout, deselect=deselect)
    finally:
        if saved_text is not None:
            be.set_text(saved_text)
        else:
            be.clear()                    # report text must not stay on the clipboard
        del saved_text
        be.set_cursor(*cursor)
    return out


def copy_region_text(rect: dict, **kw) -> str | None:
    return copy_regions({"panel": rect}, **kw)["panel"]
