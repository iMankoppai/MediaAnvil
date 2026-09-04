"""Shared visual tokens and ttk styles for the desktop interface."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


COLORS = {
    "window": "#f4f7fb",
    "sidebar": "#eef4fb",
    "card": "#ffffff",
    "border": "#dce4ee",
    "text": "#172033",
    "muted": "#64748b",
    "blue": "#1677ff",
    "blue_hover": "#0f68e6",
    "blue_soft": "#eaf3ff",
    "danger": "#c83b48",
    "danger_soft": "#fff1f2",
    "success": "#278454",
    "warning": "#a76508",
    "error": "#c83b48",
}

SIZES = {
    "page_pad_x": 20,
    "page_pad_y": 16,
    "card_pad": 12,
    "section_gap": 10,
    "control_pad_y": 7,
    "primary_pad_y": 9,
}

STATUS_STYLES = {
    "info": "Info.Status.TLabel",
    "success": "Success.Status.TLabel",
    "warning": "Warning.Status.TLabel",
    "error": "Error.Status.TLabel",
}


def configure_theme(root: tk.Misc) -> ttk.Style:
    """Apply the app-wide light theme without changing the GUI toolkit."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root.option_add("*Font", ("Microsoft YaHei UI", 10))
    root.option_add("*Text.Font", ("Microsoft YaHei UI", 10))
    root.option_add("*Listbox.Font", ("Microsoft YaHei UI", 10))
    root.option_add("*selectBackground", COLORS["blue_soft"])
    root.option_add("*selectForeground", COLORS["text"])

    style.configure("TFrame", background=COLORS["window"])
    style.configure("Page.TFrame", background=COLORS["window"])
    style.configure("Sidebar.TFrame", background=COLORS["sidebar"])
    style.configure("Card.TFrame", background=COLORS["card"])
    style.configure("TLabel", background=COLORS["window"], foreground=COLORS["text"])
    style.configure("Card.TLabel", background=COLORS["card"], foreground=COLORS["text"])
    style.configure("Muted.TLabel", foreground=COLORS["muted"], background=COLORS["window"])
    style.configure("CardMuted.TLabel", foreground=COLORS["muted"], background=COLORS["card"])
    style.configure("Info.Status.TLabel", foreground=COLORS["blue"], background=COLORS["card"])
    style.configure("Success.Status.TLabel", foreground=COLORS["success"], background=COLORS["card"])
    style.configure("Warning.Status.TLabel", foreground=COLORS["warning"], background=COLORS["card"])
    style.configure("Error.Status.TLabel", foreground=COLORS["error"], background=COLORS["card"])
    style.configure("Title.TLabel", font=("Microsoft YaHei UI", 20, "bold"))
    style.configure("Subtitle.TLabel", foreground=COLORS["muted"])
    style.configure("Section.TLabel", font=("Microsoft YaHei UI", 11, "bold"))
    style.configure("Brand.TLabel", background=COLORS["sidebar"], font=("Microsoft YaHei UI", 16, "bold"))
    style.configure("BrandSub.TLabel", background=COLORS["sidebar"], foreground=COLORS["muted"])

    style.configure(
        "TButton",
        padding=(12, 7),
        background="#f8fafc",
        foreground=COLORS["text"],
        bordercolor=COLORS["border"],
        focusthickness=1,
        focuscolor=COLORS["blue"],
    )
    style.map("TButton", background=[("active", "#edf2f7"), ("disabled", "#eef1f5")])
    style.configure("Compact.TButton", padding=(7, 6))
    style.configure("Secondary.TButton", padding=(12, 7), background="#ffffff", bordercolor=COLORS["border"])
    style.configure(
        "Accent.TButton",
        padding=(16, 9),
        background=COLORS["blue"],
        foreground="#ffffff",
        bordercolor=COLORS["blue"],
        font=("Microsoft YaHei UI", 10, "bold"),
    )
    style.map("Accent.TButton", background=[("active", COLORS["blue_hover"]), ("disabled", "#9bbdec")])
    style.configure(
        "Danger.TButton",
        background=COLORS["danger_soft"],
        foreground=COLORS["danger"],
        bordercolor="#f5c2c7",
    )
    style.map("Danger.TButton", background=[("active", "#ffe4e6")])
    style.configure(
        "CompactDanger.TButton",
        padding=(7, 6),
        background=COLORS["danger_soft"],
        foreground=COLORS["danger"],
        bordercolor="#f5c2c7",
    )

    style.configure("TEntry", padding=7, fieldbackground="#ffffff", bordercolor=COLORS["border"])
    style.configure("TCombobox", padding=6, fieldbackground="#ffffff", bordercolor=COLORS["border"])
    style.configure("TSpinbox", padding=6, fieldbackground="#ffffff", bordercolor=COLORS["border"])
    style.configure("TProgressbar", background=COLORS["blue"], troughcolor="#e7edf5", thickness=8)
    style.configure("TRadiobutton", background=COLORS["card"])
    style.configure("TCheckbutton", background=COLORS["card"])
    style.configure("TLabelframe", background=COLORS["card"], bordercolor=COLORS["border"], relief="solid")
    style.configure("TLabelframe.Label", background=COLORS["card"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 10, "bold"))
    style.configure("Card.TLabelframe", background=COLORS["card"], bordercolor=COLORS["border"], relief="solid")
    style.configure("Card.TLabelframe.Label", background=COLORS["card"], foreground=COLORS["text"], font=("Microsoft YaHei UI", 10, "bold"))
    return style
