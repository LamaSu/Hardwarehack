"""
Shared theme tokens and small window helpers.

Colors and helpers match the Drug Concentration Calculator (v3.2.0) so both
apps look like one family.
"""

import ctypes
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Optional

import customtkinter as ctk

BG = "#1E1E1E"
ROW = "#2F2F2F"
ROW_HOVER = "#3A3A3A"
CARD = "#262626"
INSET = "#333333"
BORDER = "#2A2A2A"
ACCENT = "#5CB8EC"
ACCENT_HOVER = "#4A9FD6"
TEXT = "#FFFFFF"
MUTED = "#9AA0A6"
FOOTER_COLOR = "#7D8287"
SUCCESS = "#6FCF6F"
WARNING = "#F2C94C"
ERROR = "#FF6B6B"

EMPTY_WELL = "#2B2B2B"
EMPTY_WELL_OUTLINE = "#3C3C3C"
VEHICLE_COLOR = "#8A9097"
UNTREATED_COLOR = "#4B5661"
UNTREATED_OUTLINE = "#6B7884"

# Distinct hues that read well on the dark background.
DRUG_PALETTE = [
    "#F2994A", "#6FCF6F", "#BB6BD9", "#F2C94C", "#EB5757", "#56CCF2",
    "#F78FB3", "#2DD4BF", "#9B8AFB", "#E0A96D", "#A3E635", "#FB7185",
]


def asset_path(*parts: str) -> Path:
    """
    Resolve a path under ``assets/``, from source or a frozen executable.

    Parameters
    ----------
    *parts : str
        Path segments under ``assets/``.

    Returns
    -------
    pathlib.Path
    """
    base = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent.parent
    return base / "assets" / Path(*parts)


def blend(color_a: str, color_b: str, weight: float) -> str:
    """
    Mix two hex colors.

    Parameters
    ----------
    color_a, color_b : str
        Hex colors like ``"#RRGGBB"``.
    weight : float
        0 returns ``color_a``, 1 returns ``color_b``.

    Returns
    -------
    str
        Mixed hex color.
    """
    weight = max(0.0, min(1.0, weight))
    a = [int(color_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(color_b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * weight):02X}" for x, y in zip(a, b))


class CTkToolTip:
    """
    Hover tooltip styled to match the dark palette.

    Parameters
    ----------
    widget : tkinter widget
        Widget to attach the tooltip to.
    text : str
        Text to display on hover.
    font : tuple
        Tk font tuple, e.g. ``("Segoe UI", 12)``.
    """

    def __init__(self, widget, text: str, font: tuple = ("Segoe UI", 12)) -> None:
        self.widget = widget
        self.text = text
        self.font = font
        self.tip: Optional[tk.Toplevel] = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")

    def show(self, _event=None) -> None:
        """Display the tooltip below the widget."""
        if self.tip:
            return
        x = self.widget.winfo_rootx()
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.tip = tk.Toplevel(self.widget)
        self.tip.wm_overrideredirect(True)
        self.tip.wm_geometry(f"+{x}+{y}")
        tk.Label(
            self.tip, text=self.text, bg=CARD, fg=TEXT, font=self.font, justify="left",
            relief="solid", borderwidth=1, padx=6, pady=3, wraplength=320,
        ).pack()

    def hide(self, _event=None) -> None:
        """Destroy the tooltip."""
        if self.tip:
            self.tip.destroy()
            self.tip = None


def apply_dark_titlebar(window) -> None:
    """
    Force a dark Windows title bar on a Tk/CTk window.

    Notes
    -----
    Windows only; no-ops on other platforms or unsupported builds.
    """
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 20, ctypes.byref(ctypes.c_int(1)), ctypes.sizeof(ctypes.c_int)
        )
    except Exception:
        pass


def center_window(window, parent=None) -> None:
    """
    Center a window on screen or over a parent window.

    Parameters
    ----------
    window : tkinter window
        Window to center.
    parent : tkinter window, optional
        Parent to center over. If None, centers on screen.
    """
    window.update_idletasks()
    if parent is None:
        x = (window.winfo_screenwidth() - window.winfo_width()) // 2
        y = (window.winfo_screenheight() - window.winfo_height()) // 2
    else:
        x = parent.winfo_rootx() + (parent.winfo_width() - window.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - window.winfo_height()) // 2
    window.geometry(f"+{max(x, 0)}+{max(y, 0)}")


def configure_dark_treeview(root, font_size: int = 11) -> None:
    """
    Configure the ``Dark.Treeview`` ttk style used for tables.

    Parameters
    ----------
    root : customtkinter.CTk
        Root window (used to read the display scaling).
    font_size : int, default=11
        Base font size before display scaling.
    """
    style = ttk.Style()
    style.theme_use("clam")
    try:
        scale = ctk.ScalingTracker.get_widget_scaling(root)
    except Exception:
        scale = 1.0
    size = round(font_size * scale)
    style.configure(
        "Dark.Treeview", background=ROW, fieldbackground=ROW, foreground=TEXT,
        borderwidth=0, rowheight=round(28 * scale), font=("Segoe UI", size),
    )
    style.map("Dark.Treeview", background=[("selected", ACCENT)], foreground=[("selected", BG)])
    style.configure(
        "Dark.Treeview.Heading", background=CARD, foreground=MUTED,
        borderwidth=0, font=("Segoe UI", size, "bold"),
    )
    style.map("Dark.Treeview.Heading", background=[("active", CARD)])
    style.configure(
        "Dark.Vertical.TScrollbar", background=ROW, troughcolor=CARD,
        bordercolor=BORDER, arrowcolor=MUTED,
    )
