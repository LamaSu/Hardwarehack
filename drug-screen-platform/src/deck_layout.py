"""
Deck layout of the Opentrons Flex for the drug screen.

One entry per deck slot, so the deck map image and the robot protocol use
the same assignment. Slots follow the Flex deck: rows A (back) to D (front),
columns 1-3 left to right, column 4 is the staging area.
"""

from dataclasses import dataclass
from typing import Optional

CATEGORY_TIPS = "tips"
CATEGORY_LIQUID = "liquid"
CATEGORY_PLATE = "plate"
CATEGORY_WASTE = "waste"
CATEGORY_FREE = "free"


@dataclass(frozen=True)
class DeckSlot:
    """
    What goes into one deck slot.

    Parameters
    ----------
    slot : str
        Flex deck slot, e.g. ``"B2"``.
    title : str
        Labware as written on the deck map.
    purpose : str
        What it's used for in the run.
    category : str
        One of the ``CATEGORY_*`` constants (used for colour on the map).
    load_name : str or None
        Opentrons load name, or None for fixtures and free slots.
    optional : bool, default=False
        True if the slot is only needed in some runs.
    """

    slot: str
    title: str
    purpose: str
    category: str
    load_name: Optional[str] = None
    optional: bool = False


DECK_LAYOUT: tuple[DeckSlot, ...] = (
    DeckSlot("A1", "Filter tip rack 1000 µL", "diluent and large volumes", CATEGORY_TIPS,
             "opentrons_flex_96_filtertiprack_1000ul"),
    DeckSlot("A2", "Filter tip rack 50 µL", "drug transfers (5–50 µL)", CATEGORY_TIPS,
             "opentrons_flex_96_filtertiprack_50ul"),
    DeckSlot("A3", "Trash bin", "used tips", CATEGORY_WASTE),
    DeckSlot("B1", "NEST 12-well reservoir", "15 mL troughs: drug stocks, one per compound", CATEGORY_LIQUID,
             "nest_12_reservoir_15ml"),
    DeckSlot("B2", "96 deep-well plate", "intermediate dilutions", CATEGORY_PLATE,
             "nest_96_wellplate_2ml_deep"),
    DeckSlot("B3", "NEST 1-well reservoir", "diluent (medium / buffer / water)", CATEGORY_LIQUID,
             "nest_1_reservoir_195ml"),
    DeckSlot("C1", "Tube rack, 1.5 mL tubes", "stocks if > 12 compounds or small volumes", CATEGORY_LIQUID,
             "opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap", optional=True),
    DeckSlot("C2", "Assay plate (96-well)", "cells + final doses", CATEGORY_PLATE,
             "corning_96_wellplate_360ul_flat"),
    DeckSlot("C3", "Free", "gripper parking (lids, plate swaps)", CATEGORY_FREE),
    DeckSlot("D1", "Spare tip rack", "refill for A1 / A2", CATEGORY_TIPS, optional=True),
    DeckSlot("D2", "Spare tip rack", "refill for A1 / A2", CATEGORY_TIPS, optional=True),
    DeckSlot("D3", "Waste chute", "if installed", CATEGORY_WASTE, optional=True),
)

PIPETTE_NOTE = "Pipette: Flex 8-Channel 1000 µL, partial tip pickup for per-well dosing"
GRIPPER_NOTE = "Gripper: moves plates, lids and empty tip racks"


def slot_map() -> dict[str, DeckSlot]:
    """Deck layout keyed by slot name."""
    return {item.slot: item for item in DECK_LAYOUT}
