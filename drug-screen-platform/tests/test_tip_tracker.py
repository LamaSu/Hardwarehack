"""Tests for pipette and tip assignment."""

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dilution_planner import RESERVOIR, export_transfers_csv, plan_dilutions  # noqa: E402
from tip_tracker import TIPS_PER_RACK, plan_tips, tip_order  # noqa: E402
from verify_plan import example_layout  # noqa: E402

from test_plan_checker import _random_layout  # noqa: E402


def _edge_plan():
    layout = example_layout()
    layout.fill_edge("PBS", overwrite=True)
    return plan_dilutions(layout, 100)


def test_tip_order_runs_down_columns():
    order = tip_order()
    assert order[:3] == ["A1", "B1", "C1"]
    assert order[8] == "A2"
    assert order[-1] == "H12" and len(order) == TIPS_PER_RACK


@pytest.mark.parametrize("seed", range(50))
def test_no_tip_is_picked_twice_and_volumes_fit(seed):
    layout, volume, settings = _random_layout(seed)
    plan = plan_dilutions(layout, volume, settings)
    tips = plan_tips(plan)
    assert len(tips.uses) == len(plan.transfers)
    picked = [(use.pipette, use.rack, use.tip) for use in tips.uses if use.new_tip]
    assert len(picked) == len(set(picked))
    pipettes = {setup.name: setup for setup in tips.pipettes}
    for transfer, use in zip(plan.transfers, tips.uses):
        assert transfer.volume_ul / use.trips <= pipettes[use.pipette].max_volume_ul + 1e-9


def test_tip_is_only_kept_for_the_same_reservoir_liquid():
    plan = _edge_plan()
    tips = plan_tips(plan)
    previous = {}
    for transfer, use in zip(plan.transfers, tips.uses):
        if not use.new_tip:
            before = previous[use.pipette]
            assert transfer.source_labware == RESERVOIR == before.source_labware
            assert transfer.liquid == before.liquid
        previous[use.pipette] = transfer
    edge = [use for transfer, use in zip(plan.transfers, tips.uses) if transfer.phase == "edge"]
    assert sum(use.new_tip for use in edge) == 1
    doses = [use for transfer, use in zip(plan.transfers, tips.uses) if transfer.phase == "dose"]
    assert all(use.new_tip for use in doses)


def test_large_volumes_use_the_big_pipette_in_trips():
    plan = _edge_plan()
    tips = plan_tips(plan)
    for transfer, use in zip(plan.transfers, tips.uses):
        if transfer.volume_ul > 50:
            assert use.pipette == "P1000"
            assert use.trips == -(-transfer.volume_ul // 1000)
        else:
            assert use.pipette == "P50"


def test_starting_tip_and_new_racks():
    plan = _edge_plan()
    tips = plan_tips(plan, starting_tips={"P50": "H12"})
    first = next(use for use in tips.uses if use.pipette == "P50")
    assert (first.rack, first.tip) == (1, "H12")
    second = [use for use in tips.uses if use.pipette == "P50" and use.new_tip][1]
    assert (second.rack, second.tip) == (2, "A1")
    assert tips.racks_needed("P50") == 1 + -(-(tips.tips_used("P50") - 1) // TIPS_PER_RACK)


def test_invalid_starting_tip_raises():
    with pytest.raises(ValueError):
        plan_tips(_edge_plan(), starting_tips={"P50": "J1"})


def test_empty_tip_positions_follow_the_run():
    plan = _edge_plan()
    tips = plan_tips(plan, starting_tips={"P50": "C1"})
    assert tips.empty_tip_positions(after_step=0) == {("P50", 1): ["A1", "B1"]}
    after_all = tips.empty_tip_positions()
    assert sum(len(wells) for wells in after_all.values()) == (
        2 + tips.tips_used("P50") + tips.tips_used("P1000"))
    first_dose = next(t.step for t in plan.transfers if t.phase == "dose")
    before_dose = tips.empty_tip_positions(after_step=first_dose - 1)
    at_dose = tips.empty_tip_positions(after_step=first_dose)
    assert sum(map(len, at_dose.values())) == sum(map(len, before_dose.values())) + 1


def test_export_includes_tips(tmp_path):
    plan = _edge_plan()
    tips = plan_tips(plan)
    path = tmp_path / "transfers.csv"
    export_transfers_csv(plan, path, tips)
    with open(path, encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["pipette"] == tips.uses[0].pipette
    assert rows[0]["tip_well"] == "A1" and rows[0]["new_tip"] == "True"
