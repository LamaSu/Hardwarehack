# Drug Screen Designer

Design drug screening plates and generate the pipetting worklist for an
end-to-end screen on the Opentrons Flex. Built for the Physical AI for
Science Hack (San Francisco, Oct 2026), open track.

Shares its look and core calculation code with the
[Drug Concentration Calculator](https://github.com/steffiAI/drug-dosage-calculator).

![Plate layout](docs/screenshot_96well.png)

## Features (v0.2.0)

- **Plate formats**: 6, 12, 24, 48, 96, 384 and 1536 wells
- **Well selection**: click, drag a rectangle, click/drag row or column labels,
  corner = select all, Ctrl/Shift to add or remove wells
- **Assign wells**: drug, final concentration (M/mM/µM/nM) and role
  (treatment, vehicle control, positive control, untreated, edge fill)
- **Plate edge**: on 96-well and larger plates, a warning before drugs or controls go into
  the outer ring (edge effect), and one click to fill the edge with medium, PBS, water
  or any other liquid
- **Dose series**: fill a selection with a serial dilution, along rows or down columns
- **Plate map**: color = drug, brightness = log concentration, ring = positive control
- **Pipetting plan**: per-drug stock concentration and solvent; the planner works out
  stock volumes (C1·V1 = C2·V2) and adds **intermediate dilutions** automatically when a
  direct transfer would be below the minimum pipetting volume (configurable, default
  1 µL for the Flex 50 µL pipette in low-volume mode). Dose series become serial
  dilutions on a 96 deep-well intermediate plate; very concentrated stocks get
  pre-dilution steps. Vehicle controls are matched to the highest solvent percentage
  of the treated wells, and DMSO above 0.5% is flagged
- **Reservoir**: medium for the intermediate plate and the edge-fill liquids come from a
  reservoir (default `opentrons_tough_12_reservoir_22ml`, any standard Opentrons reservoir
  selectable), one liquid per well; Materials lists how much to pour into each well
- **Tip tracking**: every transfer gets a pipette (Flex P50 or P1000) and an exact tip
  (rack and well, picked A1, B1 … H1, A2 like the Opentrons API). A tip is only reused for
  the same reservoir liquid going into empty wells; everything that touches drug, solvent
  or cells gets a fresh tip. Partly used racks: set the first free tip. The expected
  empty tip positions after any step are available for a later camera check
- **Transfer list**: every robot step in order (edge fill from the reservoir, medium into
  the intermediate plate, intermediate preparation, dosing of the assay plate),
  exportable as CSV for the Opentrons protocol
- **Simulation check**: every plan is replayed transfer by transfer, independently of the
  planner, and each well is compared with the layout (concentration, volume, solvent %,
  no well aspirated dry, every transfer ≥ the minimum). Shown in the app after
  "Update plan" and available as `scripts/verify_plan.py`
- **Files**: save/open layouts as JSON (including stocks and pipetting settings),
  export the layout and the transfer list as CSV

![Pipetting plan](docs/screenshot_worklist.png)

![Intermediate plate](docs/screenshot_intermediate.png)

## Deck layout

![Flex deck layout](docs/deck_layout.png)

Slot assignments live in `src/deck_layout.py`; redraw the map after changing them:

```bash
uv run --with pillow --with matplotlib python scripts/draw_deck_layout.py
```

## Requirements

- Python 3.11+
- Package manager: uv

## Installation

```bash
git clone <repo-url>
cd drug-screen-platform
uv sync
uv run python main.py
```

## Checking the plan

```bash
uv run pytest                                      # unit tests + 300 random plate layouts
uv run python scripts/verify_plan.py               # simulate the built-in example plate
uv run python scripts/verify_plan.py plate.json    # simulate a layout saved from the app
uv run python scripts/verify_plan.py plate.json --min-transfer 5 --all
```

## Project structure

```
drug-screen-platform/
├── main.py                # GUI (CustomTkinter)
├── src/
│   ├── plate_formats.py   # plate geometry, well naming, Opentrons labware names
│   ├── plate_layout.py    # layout model, dose series, JSON/CSV
│   ├── dilution_planner.py # intermediate dilutions and ordered transfer list
│   ├── reservoirs.py      # Opentrons reservoir labware (load names, wells, volumes)
│   ├── tip_tracker.py     # pipette and tip per transfer, expected tip-rack state
│   ├── deck_layout.py     # Flex deck slot assignments
│   ├── plan_checker.py    # replays the transfers and checks every well
│   ├── plate_canvas.py    # interactive plate widget
│   ├── ui_helpers.py      # theme tokens and window helpers
│   ├── calculators.py     # from Drug Concentration Calculator
│   ├── formatters.py      # from Drug Concentration Calculator
│   └── font_manager.py    # from Drug Concentration Calculator
├── scripts/
│   ├── verify_plan.py     # command-line plan check
│   └── draw_deck_layout.py # renders docs/deck_layout.png
├── tests/
└── assets/
```

## Roadmap

- Opentrons Flex protocol generation from the transfer list (Python API, `opentrons.protocol_api`), tested in the Opentrons simulator
- Randomized layouts
- PubChem molecular weight lookup for stock preparation

## License

MIT License
