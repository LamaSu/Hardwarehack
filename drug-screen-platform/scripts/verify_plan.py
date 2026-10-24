"""
Verify a plate layout's pipetting plan by simulating every transfer.

Usage
-----
    uv run python scripts/verify_plan.py                     # built-in example plate
    uv run python scripts/verify_plan.py my_plate.json       # layout saved from the app
    uv run python scripts/verify_plan.py my_plate.json --volume 100 --min-transfer 5

Exit code is 0 if every well checks out, 1 otherwise.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dilution_planner import PipettingSettings, plan_dilutions  # noqa: E402
from plan_checker import check_plan  # noqa: E402
from plate_formats import well_name  # noqa: E402
from plate_layout import (  # noqa: E402
    ROLE_POSITIVE, ROLE_UNTREATED, ROLE_VEHICLE, PlateLayout, StockSolution, WellAssignment,
)


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("layout", nargs="?", type=Path, help="Layout JSON saved from the app")
    parser.add_argument("--volume", type=float, help="Final volume per assay well in µL")
    parser.add_argument("--min-transfer", type=float, help="Override the minimum transfer volume in µL")
    parser.add_argument("--all", action="store_true", help="List every well, not only failures")
    args = parser.parse_args()

    try:
        layout = PlateLayout.load_json(args.layout) if args.layout else example_layout()
    except (OSError, ValueError) as error:
        print(f"Could not load layout: {error}")
        return 1

    settings = PipettingSettings.from_dict(layout.pipetting)
    if args.min_transfer is not None:
        settings.min_transfer_ul = args.min_transfer
    volume = args.volume or layout.plate_format.default_working_volume_ul

    try:
        plan = plan_dilutions(layout, volume, settings)
    except ValueError as error:
        print(f"Invalid settings: {error}")
        return 1
    report = check_plan(layout, plan, volume, settings)

    print(f"{layout.name} ({layout.format_name}), {volume:g} µL per well, "
          f"min. transfer {settings.min_transfer_ul:g} µL")
    print(f"{len(plan.transfers)} transfers, {len(plan.intermediates)} intermediate wells, "
          f"{len(report.wells)} assay wells checked\n")

    failures = [w for w in report.wells if not w.ok]
    rows = report.wells if args.all else failures
    if rows:
        print(f"{'Well':<6}{'Expected':<18}{'Simulated':<18}{'Solvent %':<11}Status")
        for check in rows:
            status = "ok" if check.ok else f"FAIL: {check.problem}"
            print(f"{check.well:<6}{check.expected:<18}{check.simulated:<18}{check.solvent_percent:<11.3g}{status}")
        print()
    for problem in report.problems:
        print(f"FAIL: {problem}")

    if report.passed:
        print(f"PASSED: all {len(report.wells)} wells reach their target; every transfer is "
              f"≥ {settings.min_transfer_ul:g} µL and no well runs dry.")
        return 0
    print(f"FAILED: {len(failures)} well(s), {len(report.problems)} transfer problem(s).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
