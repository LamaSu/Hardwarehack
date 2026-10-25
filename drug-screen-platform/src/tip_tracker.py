"""
Assign a pipette and a tip to every transfer of a plan.

The result records exactly which tip (rack and well) each transfer uses, so
the robot protocol can pick tips explicitly and a camera can later compare
the tip racks with what they should look like after any step.

Pipette and tip-rack names are Opentrons Flex load names. Ranges come from
the Opentrons pipette definitions: the 1-channel 50 µL pipette covers
0.5-30 µL in low-volume mode and 5-50 µL otherwise; the 1000 µL pipette
covers 5-1000 µL.
"""

import math
from dataclasses import dataclass, field
from typing import Optional

from dilution_planner import RESERVOIR, DilutionPlan, Transfer
from plate_formats import parse_well, well_name

TIP_RACK_ROWS = 8
TIP_RACK_COLUMNS = 12
TIPS_PER_RACK = TIP_RACK_ROWS * TIP_RACK_COLUMNS


@dataclass(frozen=True)
class PipetteSetup:
    """
    One pipette and the tips it uses.

    Parameters
    ----------
    name : str
        Short name used in the app, e.g. ``"P50"``.
    load_name : str
        Opentrons instrument name, e.g. ``"flex_1channel_50"``.
    tip_rack : str
        Opentrons labware load name of its tip rack.
    min_volume_ul : float
        Smallest volume it pipettes within spec.
    max_volume_ul : float
        Largest volume per aspiration (limited by pipette and tip).
    """

    name: str
    load_name: str
    tip_rack: str
    min_volume_ul: float
    max_volume_ul: float


DEFAULT_PIPETTES: tuple[PipetteSetup, ...] = (
    PipetteSetup("P50", "flex_1channel_50", "opentrons_flex_96_tiprack_50ul", 0.5, 50.0),
    PipetteSetup("P1000", "flex_1channel_1000", "opentrons_flex_96_tiprack_1000ul", 5.0, 1000.0),
)


def tip_order() -> list[str]:
    """Tip wells in the order Opentrons picks them: down each column, then across."""
    return [well_name(row, column) for column in range(TIP_RACK_COLUMNS) for row in range(TIP_RACK_ROWS)]


_TIP_INDEX = {tip: index for index, tip in enumerate(tip_order())}


def validate_starting_tip(tip: str) -> Optional[str]:
    """Return a problem with a starting-tip well name, or None if it's valid."""
    try:
        row, column = parse_well(tip)
    except ValueError:
        return f"{tip!r} is not a well name"
    if row >= TIP_RACK_ROWS or column >= TIP_RACK_COLUMNS:
        return f"{tip} is outside a 96-tip rack"
    return None


@dataclass
class TipUse:
    """
    The tip used for one transfer.

    Parameters
    ----------
    step : int
        Transfer step number.
    pipette : str
        Pipette name.
    rack : int
        1-based tip rack number for that pipette.
    tip : str
        Tip well, e.g. ``"C4"``.
    new_tip : bool
        True if the tip is picked up for this transfer; False if the
        pipette keeps the tip from its previous transfer.
    trips : int
        Aspirate/dispense cycles needed (volume above the tip's maximum).
    """

    step: int
    pipette: str
    rack: int
    tip: str
    new_tip: bool
    trips: int = 1

    def label(self) -> str:
        """Short description, e.g. ``"P50 1·C4"``."""
        return f"{self.pipette} {self.rack}·{self.tip}" + ("" if self.new_tip else " (same)")


@dataclass
class TipPlan:
    """Result of ``plan_tips``."""

    uses: list[TipUse]
    pipettes: tuple[PipetteSetup, ...]
    starting_tips: dict[str, str]
    warnings: list[str] = field(default_factory=list)

    def tips_used(self, pipette: str) -> int:
        """Number of tips picked up by ``pipette``."""
        return sum(1 for use in self.uses if use.pipette == pipette and use.new_tip)

    def racks_needed(self, pipette: str) -> int:
        """Number of tip racks ``pipette`` needs, counting the partly used first rack."""
        used = self.tips_used(pipette)
        if not used:
            return 0
        start = _TIP_INDEX[self.starting_tips.get(pipette, "A1")]
        return math.ceil((start + used) / TIPS_PER_RACK)

    def empty_tip_positions(self, after_step: Optional[int] = None) -> dict[tuple[str, int], list[str]]:
        """
        Tip wells that should be empty, per (pipette, rack).

        Parameters
        ----------
        after_step : int, optional
            Transfer step to look after; None means after the whole plan.
            Step 0 gives the state before the run: only the tips that were
            already gone before ``starting_tips``.

        Returns
        -------
        dict
            ``(pipette, rack) -> tip wells`` in pick order. This is the
            expected state a camera check compares against.
        """
        empty: dict[tuple[str, int], list[str]] = {}
        for setup in self.pipettes:
            start = _TIP_INDEX[self.starting_tips.get(setup.name, "A1")]
            if start:
                empty[(setup.name, 1)] = tip_order()[:start]
        for use in self.uses:
            if after_step is not None and use.step > after_step:
                break
            if use.new_tip:
                empty.setdefault((use.pipette, use.rack), []).append(use.tip)
        return empty


def _choose_pipette(volume_ul: float, pipettes: tuple[PipetteSetup, ...]) -> tuple[PipetteSetup, int]:
    """Smallest pipette that takes the volume in one go, else the largest in several trips."""
    for setup in sorted(pipettes, key=lambda p: p.max_volume_ul):
        if setup.min_volume_ul - 1e-9 <= volume_ul <= setup.max_volume_ul + 1e-9:
            return setup, 1
    largest = max(pipettes, key=lambda p: p.max_volume_ul)
    if volume_ul > largest.max_volume_ul:
        return largest, math.ceil(volume_ul / largest.max_volume_ul - 1e-9)
    return min(pipettes, key=lambda p: p.min_volume_ul), 1


def _can_keep_tip(previous: Optional[Transfer], transfer: Transfer) -> bool:
    # Reservoir liquids go into empty wells (edge wells, intermediates before any drug),
    # so the tip never touches anything that could carry over.
    return (
        previous is not None
        and transfer.source_labware == RESERVOIR
        and previous.source_labware == RESERVOIR
        and previous.liquid.casefold() == transfer.liquid.casefold()
    )


def plan_tips(
    plan: DilutionPlan,
    pipettes: tuple[PipetteSetup, ...] = DEFAULT_PIPETTES,
    starting_tips: Optional[dict[str, str]] = None,
) -> TipPlan:
    """
    Assign a pipette and tip to every transfer.

    Parameters
    ----------
    plan : DilutionPlan
        Plan from ``plan_dilutions``.
    pipettes : tuple of PipetteSetup, default=DEFAULT_PIPETTES
        Pipettes on the robot.
    starting_tips : dict, optional
        ``pipette name -> first unused tip`` in the first rack, for racks
        that are already partly used. Defaults to ``"A1"``.

    Returns
    -------
    TipPlan

    Raises
    ------
    ValueError
        If a starting tip isn't a valid tip-rack well.

    Notes
    -----
    A pipette keeps its tip only for consecutive reservoir transfers of the
    same liquid; everything that touches drug, solvent or cells gets a fresh
    tip. Tips are picked down each column (A1, B1, ... H1, A2, ...).
    """
    starting_tips = {setup.name: "A1" for setup in pipettes} | dict(starting_tips or {})
    for pipette, tip in starting_tips.items():
        problem = validate_starting_tip(tip)
        if problem:
            raise ValueError(f"Starting tip for {pipette}: {problem}")

    next_index = {setup.name: _TIP_INDEX[starting_tips[setup.name]] for setup in pipettes}
    last_transfer: dict[str, Transfer] = {}
    current_tip: dict[str, tuple[int, str]] = {}
    uses: list[TipUse] = []
    warnings: list[str] = []

    for transfer in plan.transfers:
        setup, trips = _choose_pipette(transfer.volume_ul, pipettes)
        if transfer.volume_ul < setup.min_volume_ul - 1e-9:
            warnings.append(f"Step {transfer.step}: {transfer.volume_ul:.3g} µL is below the "
                            f"{setup.min_volume_ul:g} µL minimum of the {setup.name}")
        keep = _can_keep_tip(last_transfer.get(setup.name), transfer) and setup.name in current_tip
        if not keep:
            index = next_index[setup.name]
            current_tip[setup.name] = (index // TIPS_PER_RACK + 1, tip_order()[index % TIPS_PER_RACK])
            next_index[setup.name] = index + 1
        rack, tip = current_tip[setup.name]
        uses.append(TipUse(transfer.step, setup.name, rack, tip, not keep, trips))
        last_transfer[setup.name] = transfer
    return TipPlan(uses, tuple(pipettes), starting_tips, warnings)
