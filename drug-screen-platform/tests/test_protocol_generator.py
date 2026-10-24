"""Tests for the Flex protocol generator; every protocol must pass the Opentrons simulator."""

import io

import pytest
from opentrons.simulate import simulate

from dilution_planner import PipettingSettings, plan_dilutions
from plate_layout import ROLE_UNTREATED, PlateLayout, StockSolution, WellAssignment
from planning import plan_layout
from protocol_generator import ProtocolError, generate_protocol, tube_map
from verify_plan import example_layout


def _simulate(text: str) -> list:
    log, _ = simulate(io.StringIO(text), "protocol.py")
    return log


def test_example_protocol_simulates():
    layout = example_layout()
    result = plan_layout(layout)
    _simulate(generate_protocol(layout, result.plan))


def test_capture_image_first_and_last():
    layout = example_layout()
    text = generate_protocol(layout, plan_layout(layout).plan)
    body = text[text.index("def run("):]
    assert body.count("capture_image(") == 2
    assert body.index('filename="before"') < body.index(".aspirate(")
    assert body.rindex('filename="after"') > body.rindex(".dispense(")


def test_requirements_api_level():
    layout = example_layout()
    text = generate_protocol(layout, plan_layout(layout).plan)
    assert '"apiLevel": "2.30"' in text
    assert '"robotType": "Flex"' in text


def test_tube_map_is_column_major_in_order_of_first_use():
    layout = example_layout()
    plan = plan_layout(layout).plan
    mapping = tube_map(plan)
    assert list(mapping.values())[:4] == ["A1", "B1", "C1", "D1"]
    assert set(mapping) == {"Erastin", "RSL3", "Staurosporine", "DMSO"}
    text = generate_protocol(layout, plan)
    for liquid, tube in mapping.items():
        assert f"#   {tube}: {liquid}" in text


def test_empty_layout_simulates():
    layout = PlateLayout("96-well", "Blank")
    layout.assign(["A1", "A2"], WellAssignment(ROLE_UNTREATED))
    text = generate_protocol(layout, plan_layout(layout).plan)
    _simulate(text)
    assert "TRANSFERS = []" in text


def test_384_well_simulates():
    layout = PlateLayout("384-well", "Big")
    layout.apply_dose_series([f"A{c}" for c in range(1, 11)], "Erastin", 20, "µM", 2)
    layout.stocks["Erastin"] = StockSolution(10, "mM", "DMSO")
    _simulate(generate_protocol(layout, plan_layout(layout).plan))


def test_large_volume_is_split_for_the_1000_ul_pipette():
    layout = PlateLayout("6-well", "Big wells")
    layout.assign(["A1"], WellAssignment(drug="Erastin", concentration=1, unit="µM"))
    layout.stocks["Erastin"] = StockSolution(10, "mM", "DMSO")
    settings = PipettingSettings(intermediate_transfer_ul=1500, max_intermediate_volume_ul=2000)
    plan = plan_dilutions(layout, 2000, settings)
    _simulate(generate_protocol(layout, plan))


def test_1536_refused():
    layout = PlateLayout("1536-well", "Tiny")
    plan = plan_dilutions(layout, 8, PipettingSettings(intermediate_transfer_ul=2))
    with pytest.raises(ProtocolError, match="no Opentrons labware"):
        generate_protocol(layout, plan)


def test_too_many_stocks_refused():
    layout = PlateLayout("96-well", "Many drugs")
    for index in range(25):
        drug = f"Drug{index}"
        layout.assign([f"{'ABCDEFGH'[index // 12]}{index % 12 + 1}"],
                      WellAssignment(drug=drug, concentration=1, unit="µM"))
        layout.stocks[drug] = StockSolution(10, "mM", "Water")
    with pytest.raises(ProtocolError, match="24"):
        generate_protocol(layout, plan_layout(layout).plan)


def test_names_cannot_inject_code():
    import ast

    hostile = 'Evil"""\nimport os\nos.system("echo pwned")\n"""'
    layout = PlateLayout("96-well", hostile)
    drug = "X\nimport subprocess  # \r y"
    layout.apply_dose_series([f"A{c}" for c in range(1, 4)], drug, 20, "µM", 2)
    layout.stocks[drug] = StockSolution(10, "mM", "DMSO")
    text = generate_protocol(layout, plan_layout(layout).plan)
    tree = ast.parse(text)
    assert not [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert not [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                and getattr(n.func, "attr", "") == "system"]
    _simulate(text)
