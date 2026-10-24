"""Tests for the shared plan-and-check helper."""

from plate_layout import PlateLayout
from planning import plan_layout, well_volume
from verify_plan import example_layout


def test_well_volume_defaults_to_format_working_volume():
    assert well_volume(PlateLayout("96-well")) == 100


def test_well_volume_reads_saved_value():
    layout = PlateLayout("96-well")
    layout.pipetting["well_volume_ul"] = 150
    assert well_volume(layout) == 150


def test_plan_layout_example_passes():
    result = plan_layout(example_layout())
    assert result.report.passed
    assert len(result.plan.transfers) == 120
    assert result.volume_ul == 100


def test_saved_well_volume_survives_round_trip(tmp_path):
    layout = example_layout()
    layout.pipetting["well_volume_ul"] = 150
    layout.save_json(tmp_path / "plate.json")
    assert well_volume(PlateLayout.load_json(tmp_path / "plate.json")) == 150
