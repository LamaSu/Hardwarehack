"""
Turn a dilution plan into an Opentrons Flex Python protocol.

The generated file is self-contained: deck constants at the top (edit them
to match the robot), the tube map as a comment block for whoever loads the
rack, and the planner's transfer list replayed in order. The camera takes a
"before" picture first and an "after" picture last.
"""

import math
from datetime import datetime

from dilution_planner import ASSAY, INTERMEDIATE, INTERMEDIATE_LABWARE, MEDIUM, STOCK, DilutionPlan
from plate_layout import PlateLayout

API_LEVEL = "2.30"

SMALL_PIPETTE = ("flex_1channel_50", "left", 50.0)
LARGE_PIPETTE = ("flex_1channel_1000", "right", 1000.0)
TIPS_50 = "opentrons_flex_96_tiprack_50ul"
TIPS_1000 = "opentrons_flex_96_tiprack_1000ul"
STOCK_RACK = "opentrons_24_tuberack_nest_1.5ml_snapcap"
STOCK_TUBE_CAPACITY_UL = 1500.0
MEDIUM_RESERVOIR = "nest_1_reservoir_195ml"
MEDIUM_CAPACITY_UL = 195000.0

DECK = {
    "trash": "A3",
    ASSAY: "C2",
    INTERMEDIATE: "B2",
    STOCK: "C1",
    MEDIUM: "D2",
}
TIP_SLOTS = ["A2", "A1", "B1", "B3", "C3", "D1", "D3"]
TUBE_POSITIONS = [f"{row}{col}" for col in range(1, 7) for row in "ABCD"]
DEAD_VOLUME_UL = {STOCK: 20.0, MEDIUM: 1000.0}


class ProtocolError(ValueError):
    """The layout or plan can't be turned into a Flex protocol."""


def tube_map(plan: DilutionPlan) -> dict[str, str]:
    """
    Stock tube position for every stock or solvent the plan draws from.

    Tubes are filled A1, B1, C1, D1, A2, ... in order of first use.

    Raises
    ------
    ProtocolError
        If more liquids are needed than the 24-tube rack holds.
    """
    mapping: dict[str, str] = {}
    for transfer in plan.transfers:
        if transfer.source_labware == STOCK and transfer.source_well not in mapping:
            if len(mapping) == len(TUBE_POSITIONS):
                needed = len({t.source_well for t in plan.transfers if t.source_labware == STOCK})
                raise ProtocolError(
                    f"The plan needs {needed} stock tubes but the rack holds {len(TUBE_POSITIONS)}."
                )
            mapping[transfer.source_well] = TUBE_POSITIONS[len(mapping)]
    return mapping


def _pipette_parts(volume_ul: float) -> tuple[str, int]:
    """Which pipette moves ``volume_ul`` and in how many equal parts."""
    if volume_ul <= SMALL_PIPETTE[2]:
        return "small", 1
    return "large", math.ceil(volume_ul / LARGE_PIPETTE[2])


def _tip_racks(plan: DilutionPlan) -> tuple[list[str], list[str]]:
    """Deck slots for the 50 µL and 1000 µL tip racks the plan needs."""
    tips = {"small": 0, "large": 0}
    for transfer in plan.transfers:
        pipette, parts = _pipette_parts(transfer.volume_ul)
        tips[pipette] += parts
    small_racks = math.ceil(tips["small"] / 96)
    large_racks = math.ceil(tips["large"] / 96)
    if small_racks + large_racks > len(TIP_SLOTS):
        raise ProtocolError(
            f"The plan needs {tips['small'] + tips['large']} tips "
            f"({small_racks + large_racks} racks); the deck has room for {len(TIP_SLOTS)} racks."
        )
    return TIP_SLOTS[:small_racks], TIP_SLOTS[small_racks:small_racks + large_racks]


def _liquid_volumes(plan: DilutionPlan, tubes: dict[str, str]) -> dict[str, float]:
    """Volume to load per stock liquid and for the medium, including dead volume."""
    used: dict[str, float] = {}
    for transfer in plan.transfers:
        if transfer.source_labware in (STOCK, MEDIUM):
            key = transfer.source_well if transfer.source_labware == STOCK else MEDIUM
            used[key] = used.get(key, 0.0) + transfer.volume_ul
    volumes: dict[str, float] = {}
    for liquid in tubes:
        volumes[liquid] = round(used[liquid] + DEAD_VOLUME_UL[STOCK], 1)
        if volumes[liquid] > STOCK_TUBE_CAPACITY_UL:
            raise ProtocolError(
                f"{liquid} needs {volumes[liquid]:g} µL but a stock tube holds {STOCK_TUBE_CAPACITY_UL:g} µL."
            )
    if MEDIUM in used:
        volumes[MEDIUM] = round(used[MEDIUM] + DEAD_VOLUME_UL[MEDIUM], 1)
        if volumes[MEDIUM] > MEDIUM_CAPACITY_UL:
            raise ProtocolError(f"The plan needs {volumes[MEDIUM]:g} µL of medium; the reservoir holds 195 mL.")
    return volumes


def generate_protocol(layout: PlateLayout, plan: DilutionPlan) -> str:
    """
    Build the Flex protocol source for ``plan``.

    Parameters
    ----------
    layout : PlateLayout
        Layout the plan was made for (plate name and labware).
    plan : DilutionPlan
        Plan from ``plan_dilutions``.

    Returns
    -------
    str
        Python source of an Opentrons protocol (apiLevel 2.30).

    Raises
    ------
    ProtocolError
        If the plate has no Opentrons labware or the plan doesn't fit the deck.
    """
    fmt = layout.plate_format
    if fmt.opentrons_load_name is None:
        raise ProtocolError(f"{fmt.name}: no Opentrons labware definition, can't run on the Flex.")
    tubes = tube_map(plan)
    small_slots, large_slots = _tip_racks(plan)
    volumes = _liquid_volumes(plan, tubes)

    tube_lines = "\n".join(
        f"#   {tube}: {liquid} ({volumes[liquid]:g} µL)" for liquid, tube in tubes.items()
    ) or "#   (no stock tubes needed)"
    medium_line = (
        f"#   Medium reservoir {DECK[MEDIUM]}: {volumes[MEDIUM]:g} µL"
        if MEDIUM in volumes else "#   Medium reservoir: not needed"
    )
    transfer_lines = "".join(
        f"    ({t.phase!r}, {t.source_labware!r}, {t.source_well!r}, {t.dest_labware!r}, "
        f"{t.dest_well!r}, {round(t.volume_ul, 3)!r}),\n"
        for t in plan.transfers
    )
    transfers_literal = f"[\n{transfer_lines}]" if transfer_lines else "[]"

    return f'''"""
{layout.name}: drug screen protocol for the Opentrons Flex.

Generated by drug-screen-platform on {datetime.now().isoformat(timespec="seconds")}.
The assay plate is expected to be pre-filled (cells in medium); this protocol
only adds the planned transfers.
"""

# Load the robot before starting:
#   Assay plate {fmt.opentrons_load_name} in {DECK[ASSAY]}
#   Intermediate plate {INTERMEDIATE_LABWARE} in {DECK[INTERMEDIATE]} (empty)
#   Stock tubes ({STOCK_RACK} in {DECK[STOCK]}):
{tube_lines}
{medium_line}
#   Tip racks: 50 µL in {small_slots or "-"}, 1000 µL in {large_slots or "-"}

requirements = {{"robotType": "Flex", "apiLevel": "{API_LEVEL}"}}
metadata = {{
    "protocolName": {layout.name!r},
    "author": "drug-screen-platform",
    "description": "Generated from a plate layout; before/after camera images.",
}}

# Deck: edit these to match the robot.
ASSAY_PLATE = ({fmt.opentrons_load_name!r}, {DECK[ASSAY]!r})
INTERMEDIATE_PLATE = ({INTERMEDIATE_LABWARE!r}, {DECK[INTERMEDIATE]!r})
STOCK_RACK = ({STOCK_RACK!r}, {DECK[STOCK]!r})
MEDIUM_RESERVOIR = ({MEDIUM_RESERVOIR!r}, {DECK[MEDIUM]!r})
TRASH_SLOT = {DECK["trash"]!r}
SMALL_PIPETTE = ({SMALL_PIPETTE[0]!r}, {SMALL_PIPETTE[1]!r})
LARGE_PIPETTE = ({LARGE_PIPETTE[0]!r}, {LARGE_PIPETTE[1]!r})
TIPS_50_SLOTS = {small_slots!r}
TIPS_1000_SLOTS = {large_slots!r}

STOCK_TUBES = {tubes!r}
LIQUID_VOLUMES = {volumes!r}

# (phase, source labware, source well, destination labware, destination well, volume µL)
TRANSFERS = {transfers_literal}


def run(protocol):
    protocol.capture_image(home_before=True, filename="before")

    protocol.load_trash_bin(TRASH_SLOT)
    labware = {{
        "assay": protocol.load_labware(*ASSAY_PLATE),
        "intermediate": protocol.load_labware(*INTERMEDIATE_PLATE),
        "stock": protocol.load_labware(*STOCK_RACK),
        "medium": protocol.load_labware(*MEDIUM_RESERVOIR),
    }}
    tips_50 = [protocol.load_labware({TIPS_50!r}, slot) for slot in TIPS_50_SLOTS]
    tips_1000 = [protocol.load_labware({TIPS_1000!r}, slot) for slot in TIPS_1000_SLOTS]
    small = protocol.load_instrument(*SMALL_PIPETTE, tip_racks=tips_50)
    large = protocol.load_instrument(*LARGE_PIPETTE, tip_racks=tips_1000)

    for liquid, tube in STOCK_TUBES.items():
        defined = protocol.define_liquid(name=liquid)
        labware["stock"].load_liquid(wells=[tube], volume=LIQUID_VOLUMES[liquid], liquid=defined)
    if "medium" in LIQUID_VOLUMES:
        defined = protocol.define_liquid(name="Medium")
        labware["medium"].load_liquid(wells=["A1"], volume=LIQUID_VOLUMES["medium"], liquid=defined)

    for phase, source_labware, source_well, dest_labware, dest_well, volume in TRANSFERS:
        if source_labware == "stock":
            source_well = STOCK_TUBES[source_well]
        elif source_labware == "medium":
            source_well = "A1"
        source = labware[source_labware][source_well]
        destination = labware[dest_labware][dest_well]
        if volume <= {SMALL_PIPETTE[2]:g}:
            pipette, parts = small, 1
        else:
            pipette, parts = large, -(-volume // {LARGE_PIPETTE[2]:g})
        part = volume / parts
        for _ in range(int(parts)):
            if pipette is small:
                small.configure_for_volume(part)
            pipette.pick_up_tip()
            pipette.aspirate(part, source)
            pipette.dispense(part, destination)
            pipette.drop_tip()

    protocol.capture_image(home_before=True, filename="after")
'''
