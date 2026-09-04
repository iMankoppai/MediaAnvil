"""Small Windows-specific guard that avoids repeated Tk redraws while moving a window."""

from __future__ import annotations

import ctypes
import sys
import tkinter as tk
from typing import Any


WM_SETREDRAW = 0x000B
VK_LBUTTON = 0x01
RDW_INVALIDATE = 0x0001
RDW_UPDATENOW = 0x0100
RDW_ALLCHILDREN = 0x0080
RDW_FRAME = 0x0400


class WindowsDragRedrawGuard:
    """Freeze client repaint during native move/resize and repaint once afterwards."""

    def __init__(self, root: tk.Misc, *, restore_delay_ms: int = 120, user32: Any = None) -> None:
        self.root = root
        self.restore_delay_ms = restore_delay_ms
        self.user32 = user32 if user32 is not None else ctypes.windll.user32
        self._suspended = False
        self._restore_job: str | None = None
        self._hwnd: int | None = None
        root.bind("<Configure>", self._on_configure, add="+")

    def _on_configure(self, event: tk.Event) -> None:
        # A toplevel bind tag also receives Configure events from descendants.
        if event.widget is not self.root:
            return
        if not (self.user32.GetAsyncKeyState(VK_LBUTTON) & 0x8000):
            return
        if not self._suspended:
            self._hwnd = int(self.root.winfo_id())
            self.user32.SendMessageW(self._hwnd, WM_SETREDRAW, 0, 0)
            self._suspended = True
        self._schedule_restore()

    def _schedule_restore(self) -> None:
        if self._restore_job is not None:
            try:
                self.root.after_cancel(self._restore_job)
            except tk.TclError:
                pass
        self._restore_job = self.root.after(self.restore_delay_ms, self.restore)

    def restore(self) -> None:
        self._restore_job = None
        if not self._suspended or self._hwnd is None:
            return
        self.user32.SendMessageW(self._hwnd, WM_SETREDRAW, 1, 0)
        self.user32.RedrawWindow(
            self._hwnd,
            None,
            None,
            RDW_INVALIDATE | RDW_UPDATENOW | RDW_ALLCHILDREN | RDW_FRAME,
        )
        self._suspended = False

    def close(self) -> None:
        if self._restore_job is not None:
            try:
                self.root.after_cancel(self._restore_job)
            except tk.TclError:
                pass
            self._restore_job = None
        self.restore()


def install_windows_drag_redraw_guard(root: tk.Misc) -> WindowsDragRedrawGuard | None:
    if sys.platform != "win32":
        return None
    return WindowsDragRedrawGuard(root)
