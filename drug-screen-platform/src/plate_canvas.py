"""
Interactive microplate widget.

Click a well to select it, drag to select a rectangle, click or drag over
row/column labels to select whole rows/columns, click the corner to select
all. Hold Ctrl or Shift to add to the current selection.
"""

import math
import tkinter as tk
from typing import Callable, Iterable, Optional

from plate_formats import PlateFormat, row_label, well_name
from ui_helpers import ACCENT, BG, CARD, EMPTY_WELL, EMPTY_WELL_OUTLINE, MUTED, ROW_HOVER

# (fill, outline, show_ring) for one well
WellStyle = tuple[str, str, bool]

_CONTROL_MASK = 0x0004
_SHIFT_MASK = 0x0001
_PADDING = 12


class PlateCanvas(tk.Canvas):
    """
    Canvas that draws a plate and handles well selection.

    Parameters
    ----------
    master : tkinter widget
        Parent widget.
    plate_format : PlateFormat
        Initial plate format.
    style_provider : callable
        ``style_provider(well) -> (fill, outline, show_ring)``.
    on_selection_changed : callable, optional
        Called with the new selection (set of well names).
    on_hover : callable, optional
        Called with the hovered well name, or None.
    """

    def __init__(
        self,
        master,
        plate_format: PlateFormat,
        style_provider: Callable[[str], WellStyle],
        on_selection_changed: Optional[Callable[[set[str]], None]] = None,
        on_hover: Optional[Callable[[Optional[str]], None]] = None,
        **kwargs,
    ) -> None:
        kwargs.setdefault("bg", CARD)
        kwargs.setdefault("highlightthickness", 0)
        super().__init__(master, **kwargs)
        self.plate_format = plate_format
        self.style_provider = style_provider
        self.on_selection_changed = on_selection_changed
        self.on_hover = on_hover

        self.selection: set[str] = set()
        self._well_items: dict[str, tuple[int, int]] = {}
        self._cell = 0.0
        self._left = 0.0
        self._top = 0.0
        self._drag_origin: Optional[tuple[str, int, int]] = None
        self._drag_base: set[str] = set()
        self._drag_moved = False
        self._hovered: Optional[str] = None
        self._resize_job: Optional[str] = None

        self.bind("<Configure>", self._on_configure)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda _e: self._set_hover(None))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_plate_format(self, plate_format: PlateFormat) -> None:
        """Switch to a new plate format and clear the selection."""
        self.plate_format = plate_format
        self.selection.clear()
        self.redraw()
        self._notify_selection()

    def set_selection(self, wells: Iterable[str]) -> None:
        """Replace the selection."""
        new_selection = set(wells) & set(self._well_items)
        changed = self.selection ^ new_selection
        self.selection = new_selection
        self.refresh(changed)
        self._notify_selection()

    def select_all(self) -> None:
        """Select every well."""
        self.set_selection(self._well_items)

    def clear_selection(self) -> None:
        """Deselect all wells."""
        self.set_selection(())

    def refresh(self, wells: Optional[Iterable[str]] = None) -> None:
        """
        Restyle wells without redrawing the whole plate.

        Parameters
        ----------
        wells : iterable of str, optional
            Wells to restyle. All wells if None.
        """
        targets = self._well_items if wells is None else wells
        selected_width = max(2, round(self._cell * 0.09))
        for well in targets:
            items = self._well_items.get(well)
            if items is None:
                continue
            oval, ring = items
            fill, outline, show_ring = self.style_provider(well)
            if well in self.selection:
                self.itemconfigure(oval, fill=fill, outline=ACCENT, width=selected_width)
            else:
                self.itemconfigure(oval, fill=fill, outline=outline, width=1)
            self.itemconfigure(ring, state="normal" if show_ring else "hidden")

    def redraw(self) -> None:
        """Recompute geometry and redraw the full plate."""
        self.delete("all")
        self._well_items.clear()
        fmt = self.plate_format
        width, height = self.winfo_width(), self.winfo_height()
        if width < 50 or height < 50:
            return

        row_label_width = 34 if fmt.rows > 26 else 26
        column_label_height = 22
        cell = min(
            (width - 2 * _PADDING - row_label_width) / fmt.columns,
            (height - 2 * _PADDING - column_label_height) / fmt.rows,
        )
        grid_width = cell * fmt.columns
        self._cell = cell
        self._left = (width - grid_width - row_label_width) / 2 + row_label_width
        self._top = _PADDING + column_label_height

        font_size = int(max(7, min(13, cell * 0.36)))
        label_font = ("Segoe UI", font_size)
        label_step = 1 if cell >= 16 else 2

        for col in range(fmt.columns):
            if col % label_step == 0:
                self.create_text(
                    self._left + (col + 0.5) * cell, self._top - column_label_height / 2,
                    text=str(col + 1), fill=MUTED, font=label_font,
                )
        for row in range(fmt.rows):
            if row % label_step == 0:
                self.create_text(
                    self._left - row_label_width / 2, self._top + (row + 0.5) * cell,
                    text=row_label(row), fill=MUTED, font=label_font,
                )
        # Corner "select all" marker
        self.create_text(
            self._left - row_label_width / 2, self._top - column_label_height / 2,
            text="◢", fill=ROW_HOVER, font=label_font,
        )

        radius = cell * 0.42
        ring_radius = radius * 0.42
        for row in range(fmt.rows):
            center_y = self._top + (row + 0.5) * cell
            for col in range(fmt.columns):
                center_x = self._left + (col + 0.5) * cell
                oval = self.create_oval(
                    center_x - radius, center_y - radius, center_x + radius, center_y + radius,
                    fill=EMPTY_WELL, outline=EMPTY_WELL_OUTLINE,
                )
                ring = self.create_oval(
                    center_x - ring_radius, center_y - ring_radius,
                    center_x + ring_radius, center_y + ring_radius,
                    fill=BG, outline="", state="hidden",
                )
                self._well_items[well_name(row, col)] = (oval, ring)

        self.refresh()

    # ------------------------------------------------------------------
    # Hit testing
    # ------------------------------------------------------------------
    def _region_at(self, x: float, y: float) -> tuple[Optional[str], int, int]:
        """Return ``(region, row, col)``; region is grid/row/column/corner/None."""
        if self._cell <= 0:
            return None, 0, 0
        fmt = self.plate_format
        col = math.floor((x - self._left) / self._cell)
        row = math.floor((y - self._top) / self._cell)
        in_cols = 0 <= col < fmt.columns
        in_rows = 0 <= row < fmt.rows
        left_of_grid = self._left - 40 <= x < self._left
        above_grid = self._top - 26 <= y < self._top
        if in_rows and in_cols:
            return "grid", row, col
        if left_of_grid and above_grid:
            return "corner", 0, 0
        if left_of_grid and in_rows:
            return "row", row, 0
        if above_grid and in_cols:
            return "column", 0, col
        return None, 0, 0

    def _clamped_cell(self, x: float, y: float) -> tuple[int, int]:
        fmt = self.plate_format
        col = min(max(math.floor((x - self._left) / self._cell), 0), fmt.columns - 1)
        row = min(max(math.floor((y - self._top) / self._cell), 0), fmt.rows - 1)
        return row, col

    def _wells_in_drag(self, end_row: int, end_col: int) -> set[str]:
        region, start_row, start_col = self._drag_origin
        fmt = self.plate_format
        rows = range(min(start_row, end_row), max(start_row, end_row) + 1)
        cols = range(min(start_col, end_col), max(start_col, end_col) + 1)
        if region == "row":
            cols = range(fmt.columns)
        elif region == "column":
            rows = range(fmt.rows)
        elif region == "corner":
            rows, cols = range(fmt.rows), range(fmt.columns)
        return {well_name(r, c) for r in rows for c in cols}

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def _on_configure(self, _event) -> None:
        if self._resize_job:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(60, self.redraw)

    def _on_press(self, event) -> None:
        self.focus_set()
        additive = bool(event.state & (_CONTROL_MASK | _SHIFT_MASK))
        region, row, col = self._region_at(event.x, event.y)
        if region is None:
            self._drag_origin = None
            if not additive:
                self.clear_selection()
            return
        self._drag_origin = (region, row, col)
        self._drag_base = set(self.selection) if additive else set()
        self._drag_moved = False
        self._apply_drag(row, col)

    def _on_drag(self, event) -> None:
        if self._drag_origin is None:
            return
        row, col = self._clamped_cell(event.x, event.y)
        self._drag_moved = True
        self._apply_drag(row, col)

    def _on_release(self, event) -> None:
        if self._drag_origin is None:
            return
        region, row, col = self._drag_origin
        # Ctrl/Shift-click on an already selected well deselects it.
        if region == "grid" and not self._drag_moved:
            well = well_name(row, col)
            if well in self._drag_base:
                self.set_selection(self._drag_base - {well})
        self._drag_origin = None

    def _apply_drag(self, row: int, col: int) -> None:
        new_selection = self._drag_base | self._wells_in_drag(row, col)
        if new_selection != self.selection:
            changed = self.selection ^ new_selection
            self.selection = new_selection
            self.refresh(changed)
            self._notify_selection()

    def _on_motion(self, event) -> None:
        region, row, col = self._region_at(event.x, event.y)
        self._set_hover(well_name(row, col) if region == "grid" else None)
        self.configure(cursor="hand2" if region else "")

    def _set_hover(self, well: Optional[str]) -> None:
        if well != self._hovered:
            self._hovered = well
            if self.on_hover:
                self.on_hover(well)

    def _notify_selection(self) -> None:
        if self.on_selection_changed:
            self.on_selection_changed(set(self.selection))
