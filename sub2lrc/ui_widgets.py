"""Reusable presentation-only widgets for the desktop GUI."""

from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont, ttk
from typing import Callable


class ToolTip:
    """Small native-looking hover tip whose text is resolved when shown."""

    def __init__(self, widget: tk.Misc, text: str | Callable[[], str], delay_ms: int = 450) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._job: str | None = None
        self._window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    def _schedule(self, _event: object | None = None) -> None:
        self.hide()
        self._job = self.widget.after(self.delay_ms, self.show)

    def show(self) -> None:
        self._job = None
        value = self.text() if callable(self.text) else self.text
        if not value or not self.widget.winfo_exists():
            return
        window = tk.Toplevel(self.widget)
        window.wm_overrideredirect(True)
        window.attributes("-topmost", True)
        label = tk.Label(
            window,
            text=value,
            justify="left",
            background="#fffdf3",
            foreground="#27364d",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=5,
            wraplength=620,
            font=("Microsoft YaHei UI", 9),
        )
        label.pack()
        x = self.widget.winfo_pointerx() + 12
        y = self.widget.winfo_pointery() + 18
        window.wm_geometry(f"+{x}+{y}")
        self._window = window

    def hide(self, _event: object | None = None) -> None:
        if self._job is not None:
            try:
                self.widget.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        if self._window is not None:
            self._window.destroy()
            self._window = None


class ElidedLabel(ttk.Label):
    """Display an ellipsis when needed while keeping the source value intact."""

    def __init__(self, master: tk.Misc, *, textvariable: tk.StringVar, **kwargs: object) -> None:
        self.source_variable = textvariable
        self.display_variable = tk.StringVar(master=master)
        super().__init__(master, textvariable=self.display_variable, **kwargs)
        self._trace_id = textvariable.trace_add("write", self._queue_refresh)
        self._refresh_job: str | None = None
        self.bind("<Configure>", self._queue_refresh, add="+")
        self.bind("<Destroy>", self._cleanup, add="+")
        self.tooltip = ToolTip(self, self.source_variable.get)
        self._queue_refresh()

    def _queue_refresh(self, *_args: object) -> None:
        try:
            if self._refresh_job is not None:
                self.after_cancel(self._refresh_job)
            self._refresh_job = self.after_idle(self._refresh)
        except tk.TclError:
            self._refresh_job = None

    def _refresh(self) -> None:
        self._refresh_job = None
        if not self.winfo_exists():
            return
        value = self.source_variable.get()
        available = self.winfo_width() - 6
        if available <= 12:
            self.display_variable.set(value)
            return
        font_value = ttk.Style(self).lookup(self.cget("style") or "TLabel", "font")
        try:
            font = tkfont.Font(self, font=font_value or self.cget("font"))
        except tk.TclError:
            font = tkfont.nametofont("TkDefaultFont")
        if font.measure(value) <= available:
            self.display_variable.set(value)
            return
        suffix = "…"
        low, high = 0, len(value)
        while low < high:
            middle = (low + high + 1) // 2
            if font.measure(value[:middle] + suffix) <= available:
                low = middle
            else:
                high = middle - 1
        self.display_variable.set(value[:low] + suffix)

    def _cleanup(self, _event: object | None = None) -> None:
        if self._refresh_job is not None:
            try:
                self.after_cancel(self._refresh_job)
            except tk.TclError:
                pass
            self._refresh_job = None
        try:
            self.source_variable.trace_remove("write", self._trace_id)
        except tk.TclError:
            pass


def attach_variable_tooltip(widget: tk.Misc, variable: tk.Variable) -> ToolTip:
    return ToolTip(widget, lambda: str(variable.get()))


def set_text_empty_state(widget: tk.Text, icon: str, title: str, detail: str) -> None:
    """Apply the same icon/title/detail empty state to a read-only text area."""
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", f"{icon}\n\n{title}\n{detail}")
    widget.tag_configure("empty", justify="center", foreground="#7a879b", spacing1=5, spacing3=5)
    widget.tag_add("empty", "1.0", "end")
    widget.configure(state="disabled")
