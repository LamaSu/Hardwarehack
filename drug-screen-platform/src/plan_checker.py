"""
Check a pipetting plan by simulating it, independently of the planner's maths.

Every well starts empty. The transfers are executed in order, tracking the
volume, the amount of each drug, the volume of each solvent and the volume
of each reservoir liquid in every well.
At the end, each assay well is compared with what the layout asked for.
"""

from dataclasses import dataclass, field
from typing import Optional

from dilution_planner import (
    ASSAY, INTERMEDIATE, MEDIUM, RESERVOIR, STOCK, DilutionPlan, PipettingSettings,
)
from plate_layout import MEDIUM_ONLY_ROLES, ROLE_EDGE, ROLE_VEHICLE, PlateLayout, to_nanomolar
from reservoirs import RESERVOIR_FORMATS

RELATIVE_TOLERANCE = 1e-3


@dataclass
class _WellContents:
    volume_ul: float = 0.0
    drug_fmol: dict[str, float] = field(default_factory=dict)  # nM × µL = fmol
    solvent_ul: dict[str, float] = field(default_factory=dict)
    # Bulk liquids from the reservoir, keyed by casefolded name.
    reservoir_ul: dict[str, float] = field(default_factory=dict)

    def remove(self, volume_ul: float) -> "_WellContents":
        """Take ``volume_ul`` out of the well (well-mixed) and return it."""
        fraction = volume_ul / self.volume_ul
        taken = _WellContents(
            volume_ul,
            {k: v * fraction for k, v in self.drug_fmol.items()},
            {k: v * fraction for k, v in self.solvent_ul.items()},
            {k: v * fraction for k, v in self.reservoir_ul.items()},
        )
        self.volume_ul -= volume_ul
        for parts, taken_parts in ((self.drug_fmol, taken.drug_fmol), (self.solvent_ul, taken.solvent_ul),
                                   (self.reservoir_ul, taken.reservoir_ul)):
            for key in parts:
                parts[key] -= taken_parts[key]
        return taken

    def add(self, other: "_WellContents") -> None:
        """Add liquid to the well."""
        self.volume_ul += other.volume_ul
        for parts, other_parts in ((self.drug_fmol, other.drug_fmol), (self.solvent_ul, other.solvent_ul),
                                   (self.reservoir_ul, other.reservoir_ul)):
            for key, value in other_parts.items():
                parts[key] = parts.get(key, 0.0) + value


@dataclass
class WellCheck:
    """Simulated result for one assay well."""

    well: str
    expected: str
    simulated: str
    solvent_percent: float
    ok: bool
    problem: str = ""


@dataclass
class CheckReport:
    """Result of ``check_plan``."""

    wells: list[WellCheck]
    problems: list[str]

    @property
    def passed(self) -> bool:
        """True if every well matches and no transfer broke a rule."""
        return not self.problems and all(w.ok for w in self.wells)


def _close(value: float, expected: float) -> bool:
    if expected == 0:
        return abs(value) < 1e-9
    return abs(value - expected) <= RELATIVE_TOLERANCE * abs(expected)


def check_plan(
    layout: PlateLayout,
    plan: DilutionPlan,
    well_volume_ul: float,
    settings: Optional[PipettingSettings] = None,
) -> CheckReport:
    """
    Simulate a plan and compare the result with the layout.

    Parameters
    ----------
    layout : PlateLayout
        Layout the plan was made for (targets and stocks).
    plan : DilutionPlan
        Plan from ``plan_dilutions``.
    well_volume_ul : float
        Final volume per assay well in µL.
    settings : PipettingSettings, optional
        Limits to check transfers against.

    Returns
    -------
    CheckReport

    Notes
    -----
    Checks performed:

    - every transfer is ≥ the minimum transfer volume
    - no well is aspirated below 0 µL, and intermediate wells keep at least
      the dead volume and stay within their capacity
    - every assay well ends at the right volume and drug concentration
    - vehicle wells contain the same solvent percentage as the highest dose
    - untreated and edge wells contain no drug or solvent, and edge wells
      contain only their fill liquid
    - every reservoir transfer takes the right liquid, no reservoir well
      drops below the reservoir dead volume or holds more than it can
    """
    settings = settings or PipettingSettings()
    problems: list[str] = []
    intermediate: dict[str, _WellContents] = {}
    assay: dict[str, _WellContents] = {}

    reservoir_format = RESERVOIR_FORMATS.get(plan.reservoir_labware)
    reservoir: dict[str, tuple[str, float]] = {}  # well -> (liquid, volume left)
    for item in plan.reservoir_wells:
        if reservoir_format is None or item.well not in reservoir_format.wells:
            problems.append(f"Reservoir {item.well}: not a well of {plan.reservoir_labware}")
        elif item.fill_ul > reservoir_format.well_volume_ul + 1e-6:
            problems.append(f"Reservoir {item.well}: {item.fill_ul:.0f} µL exceeds well capacity")
        if item.well in reservoir:
            problems.append(f"Reservoir {item.well}: holds more than one liquid")
        reservoir[item.well] = (item.liquid, item.fill_ul)

    # Assay wells are pre-filled with medium (e.g. seeded cells).
    for step in plan.assay_steps:
        if step.medium_ul:
            assay[step.well] = _WellContents(step.medium_ul)

    for transfer in plan.transfers:
        label = f"Step {transfer.step} ({transfer.source_labware} {transfer.source_well} → " \
                f"{transfer.dest_labware} {transfer.dest_well}, {transfer.volume_ul:.3g} µL)"
        if transfer.volume_ul < settings.min_transfer_ul - 1e-9:
            problems.append(f"{label}: below the {settings.min_transfer_ul:g} µL minimum")

        if transfer.source_labware == RESERVOIR:
            if transfer.source_well not in reservoir:
                problems.append(f"{label}: no such reservoir well in the plan")
                continue
            reservoir_liquid, left = reservoir[transfer.source_well]
            if reservoir_liquid.casefold() != transfer.liquid.casefold():
                problems.append(f"{label}: reservoir well holds {reservoir_liquid}, not {transfer.liquid}")
            if left < transfer.volume_ul - 1e-9:
                problems.append(f"{label}: reservoir well runs dry")
            reservoir[transfer.source_well] = (reservoir_liquid, left - transfer.volume_ul)
            liquid = _WellContents(transfer.volume_ul, {}, {}, {reservoir_liquid.casefold(): transfer.volume_ul})
        elif transfer.source_labware == STOCK:
            stock = layout.stocks.get(transfer.source_well)
            if stock is not None:
                liquid = _WellContents(
                    transfer.volume_ul,
                    {transfer.source_well: to_nanomolar(stock.concentration, stock.unit) * transfer.volume_ul},
                    {stock.solvent.upper(): transfer.volume_ul},
                )
            else:  # pure solvent for vehicle controls
                liquid = _WellContents(transfer.volume_ul, {}, {transfer.source_well.upper(): transfer.volume_ul})
        elif transfer.source_labware == INTERMEDIATE:
            source = intermediate.get(transfer.source_well)
            if source is None or source.volume_ul < transfer.volume_ul - 1e-9:
                problems.append(f"{label}: source well is empty or doesn't hold enough")
                continue
            liquid = source.remove(transfer.volume_ul)
        else:
            problems.append(f"{label}: unknown source")
            continue

        target = intermediate if transfer.dest_labware == INTERMEDIATE else assay
        target.setdefault(transfer.dest_well, _WellContents()).add(liquid)

    for well, contents in intermediate.items():
        if contents.volume_ul < settings.dead_volume_ul - 1e-6:
            problems.append(f"Intermediate {well}: only {contents.volume_ul:.3g} µL left, "
                            f"less than the {settings.dead_volume_ul:g} µL dead volume")
    for well, (reservoir_liquid, left) in reservoir.items():
        if left < settings.reservoir_dead_volume_ul - 1e-6:
            problems.append(f"Reservoir {well} ({reservoir_liquid}): only {left:.0f} µL left, less than the "
                            f"{settings.reservoir_dead_volume_ul:g} µL dead volume")
    for item in plan.intermediates:
        if item.total_volume_ul > settings.max_intermediate_volume_ul + 1e-6:
            problems.append(f"Intermediate {item.well}: {item.total_volume_ul:.0f} µL exceeds well capacity")

    # Highest solvent fraction per solvent among treated wells, for vehicle checks.
    max_solvent: dict[str, float] = {}
    for well, contents in assay.items():
        assignment = layout.get(well)
        treated = assignment and assignment.role != ROLE_VEHICLE and assignment.role not in MEDIUM_ONLY_ROLES
        if treated and contents.volume_ul:
            for solvent, volume in contents.solvent_ul.items():
                max_solvent[solvent] = max(max_solvent.get(solvent, 0.0), volume / contents.volume_ul)

    checks: list[WellCheck] = []
    for step in plan.assay_steps:
        assignment = layout.get(step.well)
        contents = assay.get(step.well, _WellContents())
        solvent_percent = 100 * sum(contents.solvent_ul.values()) / contents.volume_ul if contents.volume_ul else 0.0

        if step.warnings and step.transfer_ul is None and assignment.role not in MEDIUM_ONLY_ROLES:
            checks.append(WellCheck(step.well, assignment.label(), "not dosed", solvent_percent, False,
                                    "; ".join(step.warnings)))
            continue
        if not _close(contents.volume_ul, well_volume_ul):
            checks.append(WellCheck(step.well, f"{well_volume_ul:g} µL", f"{contents.volume_ul:.4g} µL",
                                    solvent_percent, False, "wrong final volume"))
            continue

        if assignment.role in MEDIUM_ONLY_ROLES:
            expected = f"{assignment.drug or MEDIUM} only"
            fill_liquid = (assignment.drug.strip() or MEDIUM).casefold()
            if contents.drug_fmol or contents.solvent_ul:
                simulated, problem = "contains compound", "medium-only well received compound"
            elif assignment.role == ROLE_EDGE and not _close(contents.reservoir_ul.get(fill_liquid, 0.0),
                                                             contents.volume_ul):
                simulated, problem = "wrong liquid", "edge well got the wrong liquid"
            else:
                simulated, problem = expected, ""
            checks.append(WellCheck(step.well, expected, simulated, solvent_percent, not problem, problem))
        elif assignment.role == ROLE_VEHICLE:
            solvent = (assignment.drug or "DMSO").upper()
            expected = 100 * max_solvent.get(solvent, max(max_solvent.values(), default=0.0))
            ok = _close(solvent_percent, expected) and not contents.drug_fmol
            checks.append(WellCheck(step.well, f"{expected:.3g}% {solvent}", f"{solvent_percent:.3g}% {solvent}",
                                    solvent_percent, ok, "" if ok else "solvent doesn't match highest dose"))
        else:
            expected_nm = to_nanomolar(assignment.concentration, assignment.unit)
            simulated_nm = contents.drug_fmol.get(assignment.drug, 0.0) / contents.volume_ul
            other_drugs = [d for d, amount in contents.drug_fmol.items() if d != assignment.drug and amount > 0]
            ok = _close(simulated_nm, expected_nm) and not other_drugs
            problem = "" if ok else ("contaminated with " + ", ".join(other_drugs) if other_drugs
                                     else "wrong concentration")
            checks.append(WellCheck(step.well, f"{expected_nm:.4g} nM", f"{simulated_nm:.4g} nM",
                                    solvent_percent, ok, problem))

    return CheckReport(checks, problems)
