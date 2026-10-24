"""
Plan and check a layout in one call, shared by the CLI and the web API.
"""

from dataclasses import dataclass
from typing import Optional

from dilution_planner import DilutionPlan, PipettingSettings, plan_dilutions
from plan_checker import CheckReport, check_plan
from plate_formats import well_name
from plate_layout import (
    ROLE_POSITIVE, ROLE_UNTREATED, ROLE_VEHICLE, PlateLayout, StockSolution, WellAssignment,
)

WELL_VOLUME_KEY = "well_volume_ul"


@dataclass
class PlanResult:
    """A layout's pipetting plan together with its simulation check."""

    plan: DilutionPlan
    report: CheckReport
    volume_ul: float
    settings: PipettingSettings


def well_volume(layout: PlateLayout) -> float:
    """
    Final volume per assay well in µL.

    Uses ``layout.pipetting["well_volume_ul"]`` when saved, otherwise the
    plate format's working volume.
    """
    saved = layout.pipetting.get(WELL_VOLUME_KEY)
    return float(saved) if saved else float(layout.plate_format.default_working_volume_ul)


def plan_layout(layout: PlateLayout, volume_ul: Optional[float] = None) -> PlanResult:
    """
    Plan the dilutions for ``layout`` and replay them with the checker.

    Parameters
    ----------
    layout : PlateLayout
        Layout with assignments, stocks and pipetting settings.
    volume_ul : float, optional
        Final volume per assay well; defaults to ``well_volume(layout)``.

    Raises
    ------
    ValueError
        If the pipetting settings are invalid.
    """
    volume = volume_ul if volume_ul is not None else well_volume(layout)
    settings = PipettingSettings.from_dict(layout.pipetting)
    problems = settings.validate(volume)
    if problems:
        raise ValueError("; ".join(problems))
    plan = plan_dilutions(layout, volume, settings)
    return PlanResult(plan, check_plan(layout, plan, volume, settings), volume, settings)


def example_layout() -> PlateLayout:
    """96-well ferroptosis screen: two dose series in triplicate plus controls."""
    layout = PlateLayout("96-well", "Example screen")
    layout.apply_dose_series([well_name(r, c) for r in range(3) for c in range(1, 11)], "Erastin", 20, "µM", 2)
    layout.apply_dose_series([well_name(r, c) for r in range(3, 6) for c in range(1, 11)], "RSL3", 1, "µM", 3)
    layout.assign([well_name(r, 0) for r in range(6)], WellAssignment(ROLE_VEHICLE, "DMSO"))
    layout.assign([well_name(r, 11) for r in range(6)],
                  WellAssignment(ROLE_POSITIVE, "Staurosporine", 1, "µM"))
    layout.assign([well_name(r, c) for r in (6, 7) for c in range(12)], WellAssignment(ROLE_UNTREATED))
    for drug in ("Erastin", "RSL3", "Staurosporine"):
        layout.stocks[drug] = StockSolution(10, "mM", "DMSO")
    return layout
