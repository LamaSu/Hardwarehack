"""
Drug Screen Designer - plate layout GUI.

Design a drug screening plate (6- to 1536-well), assign drugs and
concentrations to wells, and compute the pipetting worklist that will later
drive the Opentrons Flex.
"""

import math
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import customtkinter as ctk

sys.path.insert(0, str(Path(__file__).parent / "src"))

from dilution_planner import (  # noqa: E402
    INTERMEDIATE_LABWARE, STOCK, DilutionPlan, PipettingSettings, export_transfers_csv, plan_dilutions,
)
from font_manager import FontManager  # noqa: E402
from plan_checker import check_plan  # noqa: E402
from formatters import format_number, validate_decimal_input  # noqa: E402
from plate_canvas import PlateCanvas, WellStyle  # noqa: E402
from plate_formats import (  # noqa: E402
    DEFAULT_FORMAT, PLATE_FORMATS, flex_compatibility_note, parse_well, well_sort_key,
)
from plate_layout import (  # noqa: E402
    CONCENTRATION_UNITS, DEFAULT_EDGE_LIQUID, EDGE_LIQUIDS, MEDIUM_ONLY_ROLES, ROLE_EDGE, ROLE_POSITIVE,
    ROLE_TREATMENT, ROLE_UNTREATED, ROLE_VEHICLE, ROLES,
    PlateLayout, StockSolution, WellAssignment, from_nanomolar, to_nanomolar,
)
from reservoirs import DEFAULT_RESERVOIR, RESERVOIR_FORMATS, reservoir_from_display_name  # noqa: E402
from ui_helpers import (  # noqa: E402
    ACCENT, ACCENT_HOVER, BG, BORDER, CARD, DRUG_PALETTE, EDGE_COLOR, EDGE_OUTLINE, EMPTY_WELL, EMPTY_WELL_OUTLINE,
    ERROR, FOOTER_COLOR, MUTED, ROW, ROW_HOVER, SUCCESS, TEXT, UNTREATED_COLOR, UNTREATED_OUTLINE, VEHICLE_COLOR, WARNING,
    CTkToolTip, apply_dark_titlebar, asset_path, blend, center_window, configure_dark_treeview,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

APP_NAME = "Drug Screen Designer"
APP_VERSION = "v0.2.0"
SOLVENTS = ["DMSO", "Water", "PBS", "Ethanol", "Medium"]
FORMAT_BUTTON_VALUES = [name.split("-")[0] for name in PLATE_FORMATS]
PANEL_WIDTH = 340
DATA_DIR = Path(__file__).parent / "data" / "layouts"


def parse_number(text: str) -> tuple[Optional[float], str]:
    """
    Parse a positive number typed by the user.

    Parameters
    ----------
    text : str
        Raw input.

    Returns
    -------
    tuple of (float or None, str)
        Parsed value (None if invalid) and an error message.
    """
    is_valid, cleaned, error = validate_decimal_input(text)
    if not is_valid:
        return None, error
    value = float(cleaned)
    if value <= 0:
        return None, "Value must be greater than 0"
    return value, ""


def format_concentration_nm(value_nm: float) -> str:
    """
    Format a concentration in the most readable molar unit.

    Parameters
    ----------
    value_nm : float
        Concentration in nM.

    Returns
    -------
    str
        e.g. ``"2.5 µM"`` or ``"300 nM"``.
    """
    for unit in ("M", "mM", "µM"):
        if value_nm >= to_nanomolar(1, unit):
            return f"{format_number(from_nanomolar(value_nm, unit))} {unit}"
    return f"{format_number(value_nm)} nM"


class ScreenDesignerApp:
    """
    Main window: plate map on the left, assignment tools on the right,
    stocks and worklist in a second tab.

    Parameters
    ----------
    root : customtkinter.CTk
        Root window.
    """

    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        self.root.geometry("1360x860")
        self.root.minsize(1100, 720)
        self.root.configure(fg_color=BG)
        try:
            icon_path = asset_path("icon.ico")
            if icon_path.exists() and sys.platform.startswith("win"):
                self.root.iconbitmap(str(icon_path))
        except Exception:
            pass
        apply_dark_titlebar(self.root)

        self.layout = PlateLayout(DEFAULT_FORMAT)
        self.current_file: Optional[Path] = None
        self.dirty = False
        self.drug_colors: dict[str, str] = {}
        self.stock_vars: dict[str, tuple[tk.StringVar, tk.StringVar, tk.StringVar]] = {}
        self._flash_job: Optional[str] = None

        self.font_manager = FontManager()
        fm = self.font_manager
        self.title_font = fm.get_font("form_title", weight="bold")
        self.section_font = fm.get_font("body", weight="bold")
        self.body_font = fm.get_font("body")
        self.small_font = fm.get_font("small")
        self.mono_font = fm.get_font("small", family="Consolas")
        self.button_font = fm.get_font("body", weight="bold")

        self.plate_name_var = tk.StringVar(value=self.layout.name)
        self.role_var = tk.StringVar(value=ROLE_TREATMENT)
        self.drug_var = tk.StringVar()
        self.concentration_var = tk.StringVar()
        self.unit_var = tk.StringVar(value="µM")
        self.series_top_var = tk.StringVar(value="10")
        self.series_unit_var = tk.StringVar(value="µM")
        self.series_factor_var = tk.StringVar(value="3")
        self.series_direction_var = tk.StringVar(value="Along rows →")
        self.warn_edge_var = tk.BooleanVar(value=True)
        self.edge_liquid_var = tk.StringVar(value=DEFAULT_EDGE_LIQUID)
        self.well_volume_var = tk.StringVar(
            value=format_number(self.layout.plate_format.default_working_volume_ul)
        )
        self.min_transfer_var = tk.StringVar()
        self.intermediate_transfer_var = tk.StringVar()
        self.dead_volume_var = tk.StringVar()
        self.reservoir_dead_volume_var = tk.StringVar()
        self.reservoir_var = tk.StringVar(value=RESERVOIR_FORMATS[self.layout.reservoir].display_name)
        self._set_pipetting_vars(PipettingSettings.from_dict(self.layout.pipetting))
        self.current_plan: Optional[DilutionPlan] = None
        self.plate_name_var.trace_add("write", self._on_plate_name_changed)

        configure_dark_treeview(self.root)
        self._build_header()
        self._build_tabs()
        self._build_status_bar()
        self._bind_shortcuts()

        self._update_title()
        self._update_summary()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        center_window(self.root)

    # ------------------------------------------------------------------
    # Widget factories
    # ------------------------------------------------------------------
    def _button(self, parent, text: str, command, primary: bool = False, width: int = 120) -> ctk.CTkButton:
        return ctk.CTkButton(
            parent, text=text, command=command, width=width, height=34, corner_radius=8,
            font=self.button_font,
            fg_color=ACCENT if primary else ROW,
            hover_color=ACCENT_HOVER if primary else ROW_HOVER,
            text_color=BG if primary else TEXT,
        )

    def _entry(self, parent, variable: tk.StringVar, width: int = 120, placeholder: str = "") -> ctk.CTkEntry:
        return ctk.CTkEntry(
            parent, textvariable=variable, width=width, height=32, fg_color=ROW,
            border_color=BORDER, text_color=TEXT, font=self.body_font,
            placeholder_text=placeholder or None,
        )

    def _option_menu(self, parent, variable: tk.StringVar, values: list[str], width: int = 90, command=None):
        return ctk.CTkOptionMenu(
            parent, variable=variable, values=values, width=width, height=32,
            fg_color=ROW, button_color=ROW, button_hover_color=ROW_HOVER, text_color=TEXT,
            dropdown_fg_color=ROW, dropdown_hover_color=ROW_HOVER, dropdown_text_color=TEXT,
            font=self.body_font, dropdown_font=self.body_font, command=command,
        )

    def _section(self, parent, title: str, subtitle: str = "") -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12)
        card.pack(fill="x", pady=(0, 12))
        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 6))
        ctk.CTkLabel(header, text=title, font=self.section_font, text_color=TEXT).pack(side="left")
        if subtitle:
            ctk.CTkLabel(header, text=subtitle, font=self.mono_font, text_color=MUTED).pack(side="right")
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(0, 14))
        return body

    def _field_label(self, parent, text: str, row: int, tooltip: str = "") -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="w", pady=5, padx=(0, 10))
        ctk.CTkLabel(frame, text=text, font=self.body_font, text_color=MUTED).pack(side="left")
        if tooltip:
            icon = ctk.CTkLabel(frame, text=" ⓘ", font=self.body_font, text_color=ACCENT, cursor="hand2")
            icon.pack(side="left")
            CTkToolTip(icon, tooltip, ("Segoe UI", self.font_manager.get_size("small")))

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self.root, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(14, 4))

        title_block = ctk.CTkFrame(header, fg_color="transparent")
        title_block.pack(side="left")
        ctk.CTkLabel(title_block, text=APP_NAME, font=self.title_font, text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(
            title_block, text="plate layout -> worklist -> Opentrons Flex",
            font=self.mono_font, text_color=MUTED,
        ).pack(anchor="w")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")
        self._button(actions, "New", self.new_layout, width=70).pack(side="left", padx=4)
        self._button(actions, "Open…", self.open_layout, width=80).pack(side="left", padx=4)
        self._button(actions, "Save", self.save_layout, width=70).pack(side="left", padx=4)
        self._button(actions, "Export layout CSV", self.export_layout_csv, width=150).pack(side="left", padx=4)

        toolbar = ctk.CTkFrame(self.root, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=(8, 0))
        ctk.CTkLabel(toolbar, text="Plate name", font=self.body_font, text_color=MUTED).pack(side="left", padx=(0, 8))
        self._entry(toolbar, self.plate_name_var, width=220).pack(side="left", padx=(0, 24))
        ctk.CTkLabel(toolbar, text="Format", font=self.body_font, text_color=MUTED).pack(side="left", padx=(0, 8))
        self.format_selector = ctk.CTkSegmentedButton(
            toolbar, values=FORMAT_BUTTON_VALUES, command=self._on_format_selected,
            font=self.body_font, height=32, fg_color=ROW, unselected_color=ROW,
            unselected_hover_color=ROW_HOVER, selected_color=ACCENT,
            selected_hover_color=ACCENT_HOVER, text_color=TEXT,
        )
        self.format_selector.set(DEFAULT_FORMAT.split("-")[0])
        self.format_selector.pack(side="left")
        ctk.CTkLabel(toolbar, text="wells", font=self.body_font, text_color=MUTED).pack(side="left", padx=(8, 0))

    def _build_tabs(self) -> None:
        self.tabs = ctk.CTkTabview(
            self.root, fg_color="transparent", segmented_button_fg_color=ROW,
            segmented_button_selected_color=ACCENT, segmented_button_selected_hover_color=ACCENT_HOVER,
            segmented_button_unselected_color=ROW, segmented_button_unselected_hover_color=ROW_HOVER,
            text_color=TEXT, command=self._on_tab_changed, anchor="w",
        )
        self.tabs.pack(fill="both", expand=True, padx=14, pady=(4, 0))
        self.tab_layout = self.tabs.add("Plate layout")
        self.tab_worklist = self.tabs.add("Stocks & worklist")
        self._build_layout_tab(self.tab_layout)
        self._build_worklist_tab(self.tab_worklist)

    def _build_layout_tab(self, tab) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        plate_card = ctk.CTkFrame(tab, fg_color=CARD, corner_radius=12)
        plate_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        plate_card.grid_columnconfigure(0, weight=1)
        plate_card.grid_rowconfigure(0, weight=1)

        self.canvas = PlateCanvas(
            plate_card, self.layout.plate_format, self._well_style,
            on_selection_changed=self._on_selection_changed, on_hover=self._on_hover,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=8, pady=(8, 0))

        self.inspector_label = ctk.CTkLabel(
            plate_card, text="Hover a well to see its contents · drag to select · Ctrl/Shift to add",
            font=self.small_font, text_color=MUTED, anchor="w",
        )
        self.inspector_label.grid(row=1, column=0, sticky="ew", padx=18, pady=(2, 4))

        self.legend_frame = ctk.CTkFrame(plate_card, fg_color="transparent")
        self.legend_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 12))

        panel = ctk.CTkScrollableFrame(tab, fg_color="transparent", width=PANEL_WIDTH)
        panel.grid(row=0, column=1, sticky="ns")
        self._build_selection_section(panel)
        self._build_assign_section(panel)
        self._build_series_section(panel)
        self._build_edge_section(panel)
        self._rebuild_legend()

    def _build_selection_section(self, parent) -> None:
        body = self._section(parent, "Selection")
        self.selection_label = ctk.CTkLabel(
            body, text="No wells selected", font=self.body_font, text_color=TEXT, anchor="w",
            justify="left", wraplength=PANEL_WIDTH - 40,
        )
        self.selection_label.pack(fill="x", pady=(0, 8))
        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.pack(fill="x")
        self._button(buttons, "Select all", self.canvas.select_all, width=140).pack(side="left")
        self._button(buttons, "Clear", self.canvas.clear_selection, width=140).pack(side="right")

    def _build_assign_section(self, parent) -> None:
        body = self._section(parent, "Assign wells", "drug -> wells")
        body.grid_columnconfigure(1, weight=1)

        self._field_label(body, "Role", 0)
        self._option_menu(body, self.role_var, ROLES, width=190, command=self._on_role_changed).grid(
            row=0, column=1, columnspan=2, sticky="ew", pady=5)

        self._field_label(body, "Drug", 1, "For vehicle controls, enter the solvent (e.g. DMSO). "
                                            "Edge fill uses the liquid set under 'Plate edge'.")
        self.drug_combo = ctk.CTkComboBox(
            body, variable=self.drug_var, values=[], height=32, fg_color=ROW, border_color=BORDER,
            button_color=ROW, button_hover_color=ROW_HOVER, text_color=TEXT,
            dropdown_fg_color=ROW, dropdown_hover_color=ROW_HOVER, font=self.body_font,
        )
        self.drug_combo.grid(row=1, column=1, columnspan=2, sticky="ew", pady=5)

        self._field_label(body, "Final conc.", 2, "Final concentration in the well. Use a period for decimals.")
        self._entry(body, self.concentration_var, width=100).grid(row=2, column=1, sticky="ew", pady=5)
        self._option_menu(body, self.unit_var, CONCENTRATION_UNITS, width=80).grid(
            row=2, column=2, sticky="e", padx=(8, 0), pady=5)

        buttons = ctk.CTkFrame(body, fg_color="transparent")
        buttons.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self._button(buttons, "Assign to selection", self.assign_selection, primary=True, width=170).pack(side="left")
        self._button(buttons, "Empty wells", self.empty_selection, width=110).pack(side="right")

    def _build_series_section(self, parent) -> None:
        body = self._section(parent, "Dose series", "top -> serial")
        body.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            body, text="Uses the drug and role above. Each row (or column) of the selection becomes one series.",
            font=self.small_font, text_color=MUTED, wraplength=PANEL_WIDTH - 40, justify="left", anchor="w",
        ).grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 6))

        self._field_label(body, "Top conc.", 1)
        self._entry(body, self.series_top_var, width=100).grid(row=1, column=1, sticky="ew", pady=5)
        self._option_menu(body, self.series_unit_var, CONCENTRATION_UNITS, width=80).grid(
            row=1, column=2, sticky="e", padx=(8, 0), pady=5)

        self._field_label(body, "Dilution factor", 2, "Fold dilution between neighbouring wells, e.g. 3 for a 1:3 series.")
        self._entry(body, self.series_factor_var, width=100).grid(row=2, column=1, sticky="ew", pady=5)

        ctk.CTkSegmentedButton(
            body, values=["Along rows →", "Down columns ↓"], variable=self.series_direction_var,
            font=self.small_font, fg_color=ROW, unselected_color=ROW, unselected_hover_color=ROW_HOVER,
            selected_color=ACCENT, selected_hover_color=ACCENT_HOVER, text_color=TEXT,
        ).grid(row=3, column=0, columnspan=3, sticky="ew", pady=(8, 4))

        self._button(body, "Apply series to selection", self.apply_dose_series, primary=True, width=200).grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))

    def _build_edge_section(self, parent) -> None:
        body = self._section(parent, "Plate edge", "96-well and up")
        ctk.CTkLabel(
            body, text="Outer wells evaporate faster and skew readouts (edge effect). "
                       "Fill them with medium or buffer and keep drugs and controls on the inner wells.",
            font=self.small_font, text_color=MUTED, wraplength=PANEL_WIDTH - 40, justify="left", anchor="w",
        ).pack(fill="x", pady=(0, 6))
        liquid_row = ctk.CTkFrame(body, fg_color="transparent")
        liquid_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(liquid_row, text="Liquid", font=self.body_font, text_color=MUTED).pack(side="left", padx=(0, 10))
        ctk.CTkComboBox(
            liquid_row, variable=self.edge_liquid_var, values=EDGE_LIQUIDS, width=150, height=32, fg_color=ROW,
            border_color=BORDER, button_color=ROW, button_hover_color=ROW_HOVER, text_color=TEXT,
            dropdown_fg_color=ROW, dropdown_hover_color=ROW_HOVER, font=self.body_font,
        ).pack(side="left")
        ctk.CTkCheckBox(
            body, text="Warn before dosing edge wells", variable=self.warn_edge_var, font=self.body_font,
            text_color=TEXT, fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=BORDER,
            checkbox_width=20, checkbox_height=20,
        ).pack(anchor="w", pady=(0, 8))
        self._button(body, "Fill edge", self.fill_edge, width=200).pack(anchor="w")

    def _build_worklist_tab(self, tab) -> None:
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        left = ctk.CTkScrollableFrame(tab, fg_color="transparent", width=PANEL_WIDTH + 60)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 12))

        pipetting = self._section(left, "Pipetting", "limits -> plan")
        fields = (
            ("Final volume / well", self.well_volume_var,
             "Total liquid per assay well after dosing (medium + drug)."),
            ("Min. transfer", self.min_transfer_var,
             "Smallest volume your pipette and tips handle within spec. Flex 50 µL pipette in "
             "low-volume mode: 1 µL. Use a higher value (e.g. 5 µL) for better accuracy."),
            ("Intermediate transfer", self.intermediate_transfer_var,
             "Volume added from the intermediate plate into each assay well."),
            ("Dead volume", self.dead_volume_var,
             "Extra volume left in each intermediate well so the last aspiration isn't short."),
            ("Reservoir dead vol.", self.reservoir_dead_volume_var,
             "Extra volume left in each reservoir well. 2000 µL is a placeholder — check the real "
             "minimum on the reservoir we use."),
        )
        for row, (label, variable, tooltip) in enumerate(fields):
            self._field_label(pipetting, label, row, tooltip)
            self._entry(pipetting, variable, width=80).grid(row=row, column=1, sticky="w", pady=5)
            ctk.CTkLabel(pipetting, text="µL", font=self.body_font, text_color=MUTED).grid(
                row=row, column=2, sticky="w", padx=(6, 0))
        self._field_label(pipetting, "Reservoir", len(fields),
                          "Holds medium for the intermediate dilutions and the edge-fill liquids, "
                          "one liquid per well.")
        self._option_menu(
            pipetting, self.reservoir_var, [r.display_name for r in RESERVOIR_FORMATS.values()],
            width=210, command=self._on_reservoir_selected,
        ).grid(row=len(fields), column=1, columnspan=2, sticky="w", pady=5)

        self.stocks_body = self._section(left, "Stock solutions", "stock -> well")

        buttons = ctk.CTkFrame(left, fg_color="transparent")
        buttons.pack(fill="x", pady=(0, 12))
        self._button(buttons, "Update plan", self.update_worklist, primary=True, width=150).pack(side="left")
        self._button(buttons, "Export transfers CSV", self.export_worklist_csv, width=180).pack(side="right")

        self.prep_body = self._section(left, "Materials")

        table_card = ctk.CTkFrame(tab, fg_color=CARD, corner_radius=12)
        table_card.grid(row=0, column=1, sticky="nsew")
        table_card.grid_columnconfigure(0, weight=1)
        table_card.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(table_card, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        ctk.CTkLabel(header, text="Pipetting plan", font=self.section_font, text_color=TEXT).pack(side="left")
        self.plan_view_var = tk.StringVar(value="Assay plate")
        ctk.CTkSegmentedButton(
            header, values=["Assay plate", "Intermediate plate", "All transfers"],
            variable=self.plan_view_var, command=self._show_plan_view, font=self.small_font,
            fg_color=ROW, unselected_color=ROW, unselected_hover_color=ROW_HOVER,
            selected_color=ACCENT, selected_hover_color=ACCENT_HOVER, text_color=TEXT,
        ).pack(side="right")

        holder = tk.Frame(table_card, bg=CARD)
        holder.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)
        self.plan_frames: dict[str, tk.Frame] = {}
        self.assay_tree = self._make_table(holder, "Assay plate", (
            ("well", "Well", 50), ("role", "Role", 110), ("liquid", "Drug", 110), ("target", "Final", 80),
            ("source", "Source", 120), ("transfer", "Add µL", 70), ("medium", "Medium µL", 80),
            ("solvent", "Solvent %", 70), ("warnings", "Warnings", 220),
        ))
        self.intermediate_tree = self._make_table(holder, "Intermediate plate", (
            ("well", "Well", 50), ("contents", "Contents", 180), ("source", "From", 120),
            ("source_ul", "Source µL", 80), ("medium", "Medium µL", 80), ("total", "Total µL", 80),
            ("warnings", "Warnings", 220),
        ))
        self.transfer_tree = self._make_table(holder, "All transfers", (
            ("step", "#", 45), ("phase", "Phase", 75), ("source", "From", 170),
            ("dest", "To", 150), ("volume", "µL", 70), ("liquid", "Liquid", 140),
        ))
        self._show_plan_view("Assay plate")

    def _make_table(self, holder, name: str, columns: tuple) -> ttk.Treeview:
        frame = tk.Frame(holder, bg=CARD)
        frame.grid(row=0, column=0, sticky="nsew")
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(0, weight=1)
        keys = [key for key, _, _ in columns]
        tree = ttk.Treeview(frame, columns=keys, show="headings", style="Dark.Treeview")
        for key, heading, width in columns:
            tree.heading(key, text=heading, anchor="w")
            tree.column(key, width=width, minwidth=40, anchor="w", stretch=key == keys[-1])
        tree.tag_configure("warning", foreground=WARNING)
        tree.tag_configure("muted", foreground=MUTED)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview, style="Dark.Vertical.TScrollbar")
        tree.configure(yscrollcommand=scrollbar.set)
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.plan_frames[name] = frame
        return tree

    def _show_plan_view(self, name: str) -> None:
        self.plan_frames[name].tkraise()

    def _build_status_bar(self) -> None:
        bar = ctk.CTkFrame(self.root, fg_color="transparent", height=30)
        bar.pack(fill="x", padx=20, pady=(4, 10))
        self.summary_label = ctk.CTkLabel(bar, text="", font=self.mono_font, text_color=MUTED)
        self.summary_label.pack(side="left")
        ctk.CTkLabel(bar, text=f"{APP_VERSION} · S. Strasser", font=self.mono_font,
                     text_color=FOOTER_COLOR).pack(side="right")
        self.flash_label = ctk.CTkLabel(bar, text="", font=self.small_font, text_color=MUTED)
        self.flash_label.pack(side="right", padx=20)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Escape>", lambda _e: self.canvas.clear_selection())
        self.root.bind("<Delete>", self._on_delete_key)
        self.root.bind("<BackSpace>", self._on_delete_key)
        self.root.bind("<Control-s>", lambda _e: self.save_layout())
        self.root.bind("<Control-a>", self._on_select_all_key)

    # ------------------------------------------------------------------
    # Well styling and legend
    # ------------------------------------------------------------------
    def _drug_color(self, drug: str) -> str:
        if drug not in self.drug_colors:
            self.drug_colors[drug] = DRUG_PALETTE[len(self.drug_colors) % len(DRUG_PALETTE)]
        return self.drug_colors[drug]

    def _well_style(self, well: str) -> WellStyle:
        """Fill color encodes the drug; brightness encodes log concentration."""
        assignment = self.layout.get(well)
        if assignment is None:
            return EMPTY_WELL, EMPTY_WELL_OUTLINE, False
        if assignment.role == ROLE_UNTREATED:
            return UNTREATED_COLOR, UNTREATED_OUTLINE, False
        if assignment.role == ROLE_EDGE:
            return EDGE_COLOR, EDGE_OUTLINE, False
        if assignment.role == ROLE_VEHICLE:
            return VEHICLE_COLOR, VEHICLE_COLOR, False

        base = self._drug_color(assignment.drug)
        fill = base
        concentration_range = self.layout.concentration_range_nm(assignment.drug)
        if assignment.concentration and concentration_range and concentration_range[1] > concentration_range[0]:
            low, high = (math.log10(v) for v in concentration_range)
            position = (math.log10(to_nanomolar(assignment.concentration, assignment.unit)) - low) / (high - low)
            fill = blend(ROW, base, 0.3 + 0.7 * position)
        return fill, base, assignment.role == ROLE_POSITIVE

    def _rebuild_legend(self) -> None:
        for child in self.legend_frame.winfo_children():
            child.destroy()

        def add_item(column: int, row: int, color: str, text: str, ring: bool = False) -> None:
            item = ctk.CTkFrame(self.legend_frame, fg_color="transparent")
            item.grid(row=row, column=column, sticky="w", padx=(4, 18), pady=2)
            swatch = tk.Canvas(item, width=14, height=14, bg=CARD, highlightthickness=0)
            swatch.create_oval(1, 1, 13, 13, fill=color, outline=color)
            if ring:
                swatch.create_oval(5, 5, 9, 9, fill=BG, outline="")
            swatch.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(item, text=text, font=self.small_font, text_color=TEXT).pack(side="left")

        position = 0
        per_row = 4
        for drug in self.layout.drugs():
            wells = [a for a in self.layout.assignments.values() if a.drug == drug and a.role
                     in (ROLE_TREATMENT, ROLE_POSITIVE)]
            if not wells:
                continue
            text = f"{drug}  ({len(wells)})"
            concentration_range = self.layout.concentration_range_nm(drug)
            if concentration_range:
                low, high = concentration_range
                text += f"  {format_concentration_nm(low)}" + (
                    f" – {format_concentration_nm(high)}" if high > low else "")
            add_item(position % per_row, position // per_row, self._drug_color(drug), text,
                     ring=any(a.role == ROLE_POSITIVE for a in wells))
            position += 1

        fixed_row = (position + per_row - 1) // per_row
        add_item(0, fixed_row, VEHICLE_COLOR, "Vehicle control")
        add_item(1, fixed_row, UNTREATED_COLOR, "Untreated")
        add_item(2, fixed_row, MUTED, "Positive control", ring=True)
        add_item(3, fixed_row, EMPTY_WELL, "Empty")
        edge_liquids = sorted({a.drug for a in self.layout.assignments.values() if a.role == ROLE_EDGE and a.drug})
        add_item(0, fixed_row + 1, EDGE_COLOR,
                 "Edge fill" + (f" ({', '.join(edge_liquids)})" if edge_liquids else ""))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_selection_changed(self, selection: set[str]) -> None:
        count = len(selection)
        if count == 0:
            text = "No wells selected"
        else:
            wells = sorted(selection, key=well_sort_key)
            preview = ", ".join(wells[:6]) + (" …" if count > 6 else "")
            text = f"{count} well{'s' if count != 1 else ''} selected\n{preview}"
        self.selection_label.configure(text=text)

    def _on_hover(self, well: Optional[str]) -> None:
        if well is None:
            self.inspector_label.configure(
                text="Hover a well to see its contents · drag to select · Ctrl/Shift to add", text_color=MUTED)
            return
        assignment = self.layout.get(well)
        self.inspector_label.configure(
            text=f"{well}  ·  {assignment.label() if assignment else 'empty'}",
            text_color=TEXT if assignment else MUTED,
        )

    def _on_role_changed(self, role: str) -> None:
        if role == ROLE_VEHICLE and not self.drug_var.get().strip():
            self.drug_var.set("DMSO")

    def _on_reservoir_selected(self, display_name: str) -> None:
        self.layout.reservoir = reservoir_from_display_name(display_name).load_name
        self._mark_dirty()

    def _on_plate_name_changed(self, *_args) -> None:
        self.layout.name = self.plate_name_var.get().strip() or "Untitled plate"
        self._mark_dirty()

    def _on_format_selected(self, value: str) -> None:
        format_name = f"{value}-well"
        if format_name == self.layout.format_name:
            return
        new_format = PLATE_FORMATS[format_name]
        lost = [w for w in self.layout.assignments
                if not self._well_fits(w, new_format.rows, new_format.columns)]
        if lost and not messagebox.askyesno(
            "Change plate format",
            f"{len(lost)} assigned well(s) don't exist on a {format_name} plate and will be removed.\n\nContinue?",
            parent=self.root,
        ):
            self.format_selector.set(self.layout.format_name.split("-")[0])
            return

        self.layout.change_format(format_name)
        self.well_volume_var.set(format_number(new_format.default_working_volume_ul))
        self.canvas.set_plate_format(new_format)
        self._after_layout_change()
        note = flex_compatibility_note(new_format)
        if note:
            self.flash(note, WARNING, duration_ms=8000)

    @staticmethod
    def _well_fits(well: str, rows: int, columns: int) -> bool:
        row, col = parse_well(well)
        return row < rows and col < columns

    def _on_tab_changed(self) -> None:
        if self.tabs.get() == "Stocks & worklist":
            self._rebuild_stock_rows()
            self.update_worklist(quiet=True)

    def _focus_in_entry(self) -> bool:
        focused = self.root.focus_get()
        return isinstance(focused, (tk.Entry, ttk.Entry))

    def _on_delete_key(self, _event) -> None:
        if not self._focus_in_entry() and self.canvas.selection:
            self.empty_selection()

    def _on_select_all_key(self, _event) -> Optional[str]:
        if self._focus_in_entry():
            return None
        self.canvas.select_all()
        return "break"

    # ------------------------------------------------------------------
    # Actions: layout editing
    # ------------------------------------------------------------------
    def _selected_wells(self) -> Optional[list[str]]:
        wells = sorted(self.canvas.selection, key=well_sort_key)
        if not wells:
            self.flash("Select one or more wells first", WARNING)
            return None
        return wells

    def _confirm_edge_wells(self, wells: list[str], role: str) -> Optional[list[str]]:
        """
        Ask before putting drug or solvent into edge wells.

        Returns
        -------
        list of str or None
            Wells to fill (possibly without the edge wells), or None to cancel.
        """
        if role in MEDIUM_ONLY_ROLES or not self.warn_edge_var.get():
            return wells
        edge = set(self.layout.edge_wells())
        on_edge = [well for well in wells if well in edge]
        if not on_edge:
            return wells
        preview = ", ".join(on_edge[:8]) + (" …" if len(on_edge) > 8 else "")
        answer = messagebox.askyesnocancel(
            "Edge wells selected",
            f"{len(on_edge)} of the {len(wells)} selected wells are on the plate edge:\n{preview}\n\n"
            "Edge wells evaporate faster and often give skewed readings, so they're usually "
            "filled with medium instead.\n\n"
            "Yes — skip the edge wells\nNo — use all selected wells anyway\nCancel — do nothing",
            icon="warning", parent=self.root,
        )
        if answer is None:
            return None
        if not answer:
            return wells
        inner = [well for well in wells if well not in edge]
        if not inner:
            self.flash("All selected wells are on the edge — nothing assigned", WARNING)
            return None
        return inner

    def _edge_liquid(self) -> str:
        return self.edge_liquid_var.get().strip() or DEFAULT_EDGE_LIQUID

    def fill_edge(self) -> None:
        """Fill the outer ring of the plate with the chosen edge liquid."""
        edge = self.layout.edge_wells()
        if not edge:
            self.flash("Edge fill is meant for 96-well and larger plates", WARNING)
            return
        occupied = [well for well in edge
                    if well in self.layout.assignments and self.layout.get(well).role != ROLE_EDGE]
        overwrite = False
        if occupied:
            preview = ", ".join(occupied[:8]) + (" …" if len(occupied) > 8 else "")
            answer = messagebox.askyesnocancel(
                "Edge wells in use",
                f"{len(occupied)} edge well(s) already have contents:\n{preview}\n\n"
                f"Yes — replace them with {self._edge_liquid()}\n"
                "No — fill only the empty edge wells\nCancel — do nothing",
                icon="warning", parent=self.root,
            )
            if answer is None:
                return
            overwrite = answer
        filled = self.layout.fill_edge(self._edge_liquid(), overwrite)
        if not filled:
            self.flash("No empty edge wells to fill", MUTED)
            return
        self._after_layout_change(refresh_all=True)
        self.flash(f"Filled {len(filled)} edge well(s) with {self._edge_liquid()}", SUCCESS)
    def assign_selection(self) -> None:
        """Assign the drug/role/concentration from the form to all selected wells."""
        wells = self._selected_wells()
        if wells is None:
            return
        role = self.role_var.get()
        drug = self.drug_var.get().strip()
        concentration: Optional[float] = None
        concentration_text = self.concentration_var.get().strip()

        if role in (ROLE_TREATMENT, ROLE_POSITIVE):
            if not drug:
                self.flash("Enter a drug name", ERROR)
                return
            concentration, error = parse_number(concentration_text)
            if concentration is None:
                self.flash(f"Concentration: {error}", ERROR)
                return
        elif role == ROLE_VEHICLE:
            drug = drug or "DMSO"
        elif role == ROLE_EDGE:
            drug = self._edge_liquid()
        else:
            drug = ""

        wells = self._confirm_edge_wells(wells, role)
        if wells is None:
            return
        self.layout.assign(wells, WellAssignment(role, drug, concentration, self.unit_var.get()))
        self._after_layout_change(refresh_all=True)
        self.flash(f"Assigned {len(wells)} well(s)", SUCCESS)

    def empty_selection(self) -> None:
        """Remove contents from the selected wells."""
        wells = self._selected_wells()
        if wells is None:
            return
        self.layout.clear(wells)
        self._after_layout_change(refresh_all=True)
        self.flash(f"Emptied {len(wells)} well(s)", MUTED)

    def apply_dose_series(self) -> None:
        """Fill the selection with a serial dilution of the current drug."""
        wells = self._selected_wells()
        if wells is None:
            return
        drug = self.drug_var.get().strip()
        if not drug:
            self.flash("Enter a drug name in 'Assign wells'", ERROR)
            return
        top, error = parse_number(self.series_top_var.get())
        if top is None:
            self.flash(f"Top concentration: {error}", ERROR)
            return
        factor, error = parse_number(self.series_factor_var.get())
        if factor is None or factor <= 1:
            self.flash("Dilution factor must be a number > 1", ERROR)
            return
        role = self.role_var.get() if self.role_var.get() == ROLE_POSITIVE else ROLE_TREATMENT
        direction = "row" if self.series_direction_var.get().startswith("Along") else "column"
        wells = self._confirm_edge_wells(wells, role)
        if wells is None:
            return
        groups: dict[int, int] = {}
        for well in wells:
            row, col = parse_well(well)
            key = row if direction == "row" else col
            groups[key] = groups.get(key, 0) + 1
        steps = max(groups.values())
        if steps < 2:
            along = "in a row" if direction == "row" else "in a column"
            self.flash(f"Select at least 2 wells {along} — each {direction} becomes one series", WARNING,
                       duration_ms=6000)
            return
        self.layout.apply_dose_series(wells, drug, top, self.series_unit_var.get(), factor, direction, role)
        self._after_layout_change(refresh_all=True)
        unit = self.series_unit_var.get()
        top_nm = to_nanomolar(top, unit)
        self.flash(
            f"Applied {len(groups)} series × {steps} steps: {format_concentration_nm(top_nm)} → "
            f"{format_concentration_nm(top_nm / factor ** (steps - 1))}", SUCCESS, duration_ms=6000)

    def _after_layout_change(self, refresh_all: bool = False) -> None:
        # Concentration shading is relative per drug, so one edit can recolor other wells.
        if refresh_all:
            self.canvas.refresh()
        self.drug_combo.configure(values=self.layout.drugs())
        self._rebuild_legend()
        self._update_summary()
        self._mark_dirty()

    def _update_summary(self) -> None:
        fmt = self.layout.plate_format
        assigned = len(self.layout.assignments)
        drugs = len([d for d in self.layout.drugs()
                     if any(a.drug == d and a.role in (ROLE_TREATMENT, ROLE_POSITIVE)
                            for a in self.layout.assignments.values())])
        flex = fmt.opentrons_load_name or "no Flex labware"
        self.summary_label.configure(
            text=f"{assigned} / {fmt.well_count} wells assigned  ·  {drugs} drug(s)  ·  {flex}")

    # ------------------------------------------------------------------
    # Actions: stocks and worklist
    # ------------------------------------------------------------------
    def _rebuild_stock_rows(self) -> None:
        for child in self.stocks_body.winfo_children():
            child.destroy()
        drugs = [d for d in self.layout.drugs()
                 if any(a.drug == d and a.role in (ROLE_TREATMENT, ROLE_POSITIVE)
                        for a in self.layout.assignments.values())]
        if not drugs:
            ctk.CTkLabel(self.stocks_body, text="Assign drugs on the plate first.",
                         font=self.small_font, text_color=MUTED).grid(row=0, column=0, sticky="w")
            return

        for column, heading in enumerate(("Drug", "Stock conc.", "", "Solvent")):
            ctk.CTkLabel(self.stocks_body, text=heading, font=self.small_font, text_color=MUTED).grid(
                row=0, column=column, sticky="w", padx=(0, 6))

        for row, drug in enumerate(drugs, start=1):
            if drug not in self.stock_vars:
                stock = self.layout.stocks.get(drug, StockSolution(10, "mM", "DMSO"))
                self.stock_vars[drug] = (
                    tk.StringVar(value=format_number(stock.concentration)),
                    tk.StringVar(value=stock.unit),
                    tk.StringVar(value=stock.solvent),
                )
            conc_var, unit_var, solvent_var = self.stock_vars[drug]
            name = ctk.CTkFrame(self.stocks_body, fg_color="transparent")
            name.grid(row=row, column=0, sticky="w", pady=4, padx=(0, 6))
            swatch = tk.Canvas(name, width=12, height=12, bg=CARD, highlightthickness=0)
            color = self._drug_color(drug)
            swatch.create_oval(1, 1, 11, 11, fill=color, outline=color)
            swatch.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(name, text=drug, font=self.body_font, text_color=TEXT, width=90, anchor="w").pack(side="left")
            self._entry(self.stocks_body, conc_var, width=70).grid(row=row, column=1, pady=4, padx=(0, 6))
            self._option_menu(self.stocks_body, unit_var, CONCENTRATION_UNITS, width=70).grid(
                row=row, column=2, pady=4, padx=(0, 6))
            ctk.CTkComboBox(
                self.stocks_body, variable=solvent_var, values=SOLVENTS, width=100, height=32,
                fg_color=ROW, border_color=BORDER, button_color=ROW, button_hover_color=ROW_HOVER,
                text_color=TEXT, dropdown_fg_color=ROW, font=self.body_font,
            ).grid(row=row, column=3, pady=4)

    def _read_stocks(self) -> bool:
        for drug, (conc_var, unit_var, solvent_var) in self.stock_vars.items():
            if drug not in self.layout.drugs():
                continue
            value, error = parse_number(conc_var.get())
            if value is None:
                self.flash(f"Stock of {drug}: {error}", ERROR)
                return False
            self.layout.stocks[drug] = StockSolution(value, unit_var.get(), solvent_var.get().strip() or "DMSO")
        return True

    def _read_well_volume(self) -> Optional[float]:
        volume, error = parse_number(self.well_volume_var.get())
        if volume is None:
            self.flash(f"Well volume: {error}", ERROR)
            return None
        if volume > self.layout.plate_format.max_volume_ul:
            self.flash(f"Well volume exceeds the {format_number(self.layout.plate_format.max_volume_ul)} µL "
                       f"capacity of a {self.layout.format_name} plate", ERROR)
            return None
        return volume

    def _set_pipetting_vars(self, settings: PipettingSettings) -> None:
        self.min_transfer_var.set(format_number(settings.min_transfer_ul))
        self.intermediate_transfer_var.set(format_number(settings.intermediate_transfer_ul))
        self.dead_volume_var.set(format_number(settings.dead_volume_ul))
        self.reservoir_dead_volume_var.set(format_number(settings.reservoir_dead_volume_ul))

    def _read_pipetting(self, well_volume_ul: float) -> Optional[PipettingSettings]:
        values = {}
        for label, variable, key in (
            ("Min. transfer", self.min_transfer_var, "min_transfer_ul"),
            ("Intermediate transfer", self.intermediate_transfer_var, "intermediate_transfer_ul"),
        ):
            value, error = parse_number(variable.get())
            if value is None:
                self.flash(f"{label}: {error}", ERROR)
                return None
            values[key] = value
        for label, variable, key in (
            ("Dead volume", self.dead_volume_var, "dead_volume_ul"),
            ("Reservoir dead volume", self.reservoir_dead_volume_var, "reservoir_dead_volume_ul"),
        ):
            is_valid, cleaned, error = validate_decimal_input(variable.get().strip() or "0")
            if not is_valid or float(cleaned) < 0:
                self.flash(f"{label}: {error or 'must be ≥ 0'}", ERROR)
                return None
            values[key] = float(cleaned)
        settings = PipettingSettings(**values)
        problems = settings.validate(well_volume_ul)
        if problems:
            self.flash(problems[0], ERROR)
            return None
        self.layout.pipetting = settings.to_dict()
        return settings

    def _build_plan(self) -> Optional[DilutionPlan]:
        volume = self._read_well_volume()
        if volume is None or not self._read_stocks():
            return None
        settings = self._read_pipetting(volume)
        if settings is None:
            return None
        return plan_dilutions(self.layout, volume, settings)

    def update_worklist(self, quiet: bool = False) -> None:
        """Recompute the pipetting plan and fill the tables."""
        plan = self._build_plan()
        if plan is None:
            return
        self.current_plan = plan
        self._mark_dirty()

        for tree in (self.assay_tree, self.intermediate_tree, self.transfer_tree):
            tree.delete(*tree.get_children())

        def volume_text(value: Optional[float]) -> str:
            return "" if value is None else format_number(value, "µl")

        warning_count = 0
        for step in plan.assay_steps:
            tag = "warning" if step.warnings else ("muted" if step.role != ROLE_TREATMENT else "")
            warning_count += bool(step.warnings)
            self.assay_tree.insert("", "end", tags=(tag,), values=(
                step.well, step.role, step.liquid, step.target, step.source_label(),
                volume_text(step.transfer_ul), volume_text(step.medium_ul),
                "" if step.solvent_percent is None else f"{step.solvent_percent:.2g}",
                "; ".join(step.warnings),
            ))
        for item in plan.intermediates:
            source = f"{item.source_well} stock" if item.source_labware == STOCK else f"Int. {item.source_well}"
            self.intermediate_tree.insert("", "end", tags=("warning" if item.warnings else "",), values=(
                item.well, item.label(), source, volume_text(item.source_volume_ul),
                volume_text(item.medium_volume_ul), volume_text(item.total_volume_ul), "; ".join(item.warnings),
            ))
        for transfer in plan.transfers:
            self.transfer_tree.insert("", "end", tags=("muted" if transfer.phase == "prepare" else "",), values=(
                transfer.step, transfer.phase, f"{transfer.source_labware} {transfer.source_well}",
                f"{transfer.dest_labware} {transfer.dest_well}", volume_text(transfer.volume_ul), transfer.liquid,
            ))

        for child in self.prep_body.winfo_children():
            child.destroy()

        def line(text: str, muted: bool = False) -> None:
            ctk.CTkLabel(self.prep_body, text=text, font=self.small_font if muted else self.body_font,
                         text_color=MUTED if muted else TEXT, anchor="w", justify="left",
                         wraplength=PANEL_WIDTH).pack(anchor="w", pady=1)

        if not plan.stock_usage_ul:
            line("Nothing to dose yet.", muted=True)
        for liquid, total in plan.stock_usage_ul.items():
            stock = self.layout.stocks.get(liquid)
            source = (f"{format_number(stock.concentration)} {stock.unit} in {stock.solvent}"
                      if stock else liquid.replace(" (vehicle)", ""))
            line(f"{liquid}: {format_number(total, 'µl')} µL of {source}")
        if plan.needs_intermediate_plate:
            medium = sum(i.medium_volume_ul for i in plan.intermediates)
            line(f"Intermediate plate: {len(plan.intermediates)} wells ({INTERMEDIATE_LABWARE}), "
                 f"{format_number(medium, 'µl')} µL medium")
        if plan.reservoir_wells:
            line(f"Reservoir ({RESERVOIR_FORMATS[plan.reservoir_labware].display_name}), "
                 f"incl. {format_number(self.layout.pipetting['reservoir_dead_volume_ul'], 'µl')} µL "
                 "dead volume:")
            for item in plan.reservoir_wells:
                line(f"   {item.well}: {format_number(item.fill_ul / 1000)} mL {item.liquid}")
        line(f"{len(plan.transfers)} transfers in total. Add dead volume to source tubes.", muted=True)

        # Independent check: replay every transfer and compare each well with the layout.
        volume = self._read_well_volume()
        settings = PipettingSettings.from_dict(self.layout.pipetting)
        report = check_plan(self.layout, plan, volume, settings)
        failed = [w for w in report.wells if not w.ok]
        if report.passed:
            text, color = f"✓ Simulation: all {len(report.wells)} wells reach their target", SUCCESS
        else:
            text, color = f"✗ Simulation: {len(failed)} well(s), {len(report.problems)} transfer problem(s)", ERROR
        first_line = self.prep_body.winfo_children()[0]
        ctk.CTkLabel(self.prep_body, text=text, font=self.body_font, text_color=color, anchor="w").pack(
            anchor="w", pady=(0, 6), before=first_line)

        if not quiet and not report.passed:
            self.flash("Simulation check failed — see Materials", ERROR)
        elif not quiet:
            if warning_count or plan.warnings:
                self.flash(f"Plan updated — {warning_count + len(plan.warnings)} warning(s)", WARNING)
            elif plan.needs_intermediate_plate:
                self.flash(f"Plan updated — {len(plan.intermediates)} intermediate dilution(s) added", SUCCESS)
            else:
                self.flash(f"Plan updated — {len(plan.transfers)} transfers", SUCCESS)

    # ------------------------------------------------------------------
    # Actions: files
    # ------------------------------------------------------------------
    def _confirm_discard(self) -> bool:
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel("Unsaved changes", "Save changes to the current plate?", parent=self.root)
        if answer is None:
            return False
        if answer:
            return self.save_layout()
        return True

    def new_layout(self) -> None:
        """Start an empty plate."""
        if not self._confirm_discard():
            return
        self._load_into_ui(PlateLayout(self.layout.format_name))
        self.current_file = None
        self._set_dirty(False)

    def open_layout(self) -> None:
        """Load a plate layout from JSON."""
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            parent=self.root, title="Open plate layout", initialdir=self._initial_dir(),
            filetypes=[("Plate layout", "*.json"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            layout = PlateLayout.load_json(Path(path))
        except (OSError, ValueError) as error:
            messagebox.showerror("Open failed", str(error), parent=self.root)
            return
        self._load_into_ui(layout)
        self.current_file = Path(path)
        self._set_dirty(False)
        self.flash(f"Opened {Path(path).name}", SUCCESS)

    def save_layout(self) -> bool:
        """
        Save the plate layout as JSON.

        Returns
        -------
        bool
            True if the file was saved.
        """
        self._read_stocks()
        path = self.current_file
        if path is None:
            chosen = filedialog.asksaveasfilename(
                parent=self.root, title="Save plate layout", initialdir=self._initial_dir(),
                initialfile=f"{self._safe_name()}.json", defaultextension=".json",
                filetypes=[("Plate layout", "*.json")],
            )
            if not chosen:
                return False
            path = Path(chosen)
        try:
            self.layout.save_json(path)
        except OSError as error:
            messagebox.showerror("Save failed", str(error), parent=self.root)
            return False
        self.current_file = path
        self._set_dirty(False)
        self.flash(f"Saved {path.name}", SUCCESS)
        return True

    def export_layout_csv(self) -> None:
        """Export one row per well as CSV."""
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Export layout CSV", initialdir=self._initial_dir(),
            initialfile=f"{self._safe_name()}_layout.csv", defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            self.layout.export_layout_csv(Path(path))
        except OSError as error:
            messagebox.showerror("Export failed", str(error), parent=self.root)
            return
        self.flash(f"Exported {Path(path).name}", SUCCESS)

    def export_worklist_csv(self) -> None:
        """Export the ordered transfer list as CSV."""
        plan = self._build_plan()
        if plan is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Export transfers CSV", initialdir=self._initial_dir(),
            initialfile=f"{self._safe_name()}_transfers.csv", defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        try:
            export_transfers_csv(plan, Path(path))
        except OSError as error:
            messagebox.showerror("Export failed", str(error), parent=self.root)
            return
        self.flash(f"Exported {Path(path).name}", SUCCESS)

    def _load_into_ui(self, layout: PlateLayout) -> None:
        self.layout = layout
        self.drug_colors.clear()
        self.stock_vars.clear()
        self.plate_name_var.set(layout.name)
        self.format_selector.set(layout.format_name.split("-")[0])
        self.well_volume_var.set(format_number(layout.plate_format.default_working_volume_ul))
        self._set_pipetting_vars(PipettingSettings.from_dict(layout.pipetting))
        reservoir = RESERVOIR_FORMATS.get(layout.reservoir)
        if reservoir is None:
            self.flash(f"Unknown reservoir {layout.reservoir} in file — using the default", WARNING)
            layout.reservoir = DEFAULT_RESERVOIR
            reservoir = RESERVOIR_FORMATS[layout.reservoir]
        self.reservoir_var.set(reservoir.display_name)
        self.canvas.set_plate_format(layout.plate_format)
        self._after_layout_change()
        if self.tabs.get() == "Stocks & worklist":
            self._on_tab_changed()

    def _initial_dir(self) -> str:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            return str(DATA_DIR)
        except OSError:
            return str(Path.home())

    def _safe_name(self) -> str:
        return "".join(c if c.isalnum() or c in "-_" else "_" for c in self.layout.name).strip("_") or "plate"

    # ------------------------------------------------------------------
    # Window state
    # ------------------------------------------------------------------
    def flash(self, message: str, color: str = MUTED, duration_ms: int = 4000) -> None:
        """Show a short status message in the footer."""
        if self._flash_job:
            self.root.after_cancel(self._flash_job)
        self.flash_label.configure(text=message, text_color=color)
        self._flash_job = self.root.after(duration_ms, lambda: self.flash_label.configure(text=""))

    def _mark_dirty(self) -> None:
        self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        self.dirty = dirty
        self._update_title()

    def _update_title(self) -> None:
        file_part = self.current_file.name if self.current_file else self.layout.name
        self.root.title(f"{'* ' if self.dirty else ''}{file_part} — {APP_NAME}")

    def _on_close(self) -> None:
        if self._confirm_discard():
            self.root.destroy()


def main() -> None:
    """Launch the app."""
    root = ctk.CTk()
    ScreenDesignerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
