"""
Reservoir labware for bulk liquids (medium, PBS, water).

Load names, well names and volumes are taken from the Opentrons standard
labware definitions (shared-data/labware/definitions/2 in the Opentrons
repository), so they can be passed straight to ``protocol.load_labware``.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ReservoirFormat:
    """
    One reservoir labware type.

    Parameters
    ----------
    load_name : str
        Opentrons labware load name.
    display_name : str
        Name shown in the app.
    wells : tuple of str
        Well names in fill order.
    well_volume_ul : float
        Capacity of each well in µL.
    """

    load_name: str
    display_name: str
    wells: tuple[str, ...]
    well_volume_ul: float


def _columns(count: int) -> tuple[str, ...]:
    return tuple(f"A{column}" for column in range(1, count + 1))


_EIGHT_ROWS = tuple(f"{row}1" for row in "ABCDEFGH")

RESERVOIR_FORMATS: dict[str, ReservoirFormat] = {
    reservoir.load_name: reservoir for reservoir in (
        ReservoirFormat("opentrons_tough_12_reservoir_22ml", "Opentrons Tough 12 × 22 mL", _columns(12), 22000),
        ReservoirFormat("opentrons_tough_4_reservoir_72ml", "Opentrons Tough 4 × 72 mL", _columns(4), 72000),
        ReservoirFormat("opentrons_tough_1_reservoir_300ml", "Opentrons Tough 1 × 300 mL", _columns(1), 300000),
        ReservoirFormat("nest_12_reservoir_15ml", "NEST 12 × 15 mL", _columns(12), 15000),
        ReservoirFormat("nest_12_reservoir_22ml", "NEST 12 × 22 mL", _columns(12), 22000),
        ReservoirFormat("nest_8_reservoir_22ml", "NEST 8 × 22 mL", _EIGHT_ROWS, 22000),
        ReservoirFormat("nest_1_reservoir_195ml", "NEST 1 × 195 mL", _columns(1), 195000),
        ReservoirFormat("nest_1_reservoir_290ml", "NEST 1 × 290 mL", _columns(1), 290000),
        ReservoirFormat("usascientific_12_reservoir_22ml", "USA Scientific 12 × 22 mL", _columns(12), 22000),
        ReservoirFormat("agilent_1_reservoir_290ml", "Agilent 1 × 290 mL", _columns(1), 290000),
        ReservoirFormat("axygen_1_reservoir_90ml", "Axygen 1 × 90 mL", _columns(1), 90000),
    )
}

# Opentrons-branded and listed for the Flex; change once we know what the lab has.
DEFAULT_RESERVOIR = "opentrons_tough_12_reservoir_22ml"


def reservoir_from_display_name(display_name: str) -> ReservoirFormat:
    """
    Look up a reservoir by the name shown in the app.

    Raises
    ------
    KeyError
        If no reservoir has that display name.
    """
    for reservoir in RESERVOIR_FORMATS.values():
        if reservoir.display_name == display_name:
            return reservoir
    raise KeyError(display_name)
