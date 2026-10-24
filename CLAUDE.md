# Hardwarehack

Physical AI for Science Hack (San Francisco, Oct 2026), Track 3 (open track):
an end-to-end drug screening platform driving an Opentrons Flex.

## Layout

- `drug-screen-platform/` — Python 3.11 desktop app (CustomTkinter), managed with uv
  - `main.py` — GUI: plate layout tab, stocks & pipetting plan tab
  - `src/plate_formats.py` — plate geometry, well names, Opentrons labware load names
  - `src/plate_layout.py` — layout model (wells → drug, concentration, role), JSON/CSV
  - `src/dilution_planner.py` — intermediate dilutions and the ordered transfer list
  - `src/plan_checker.py` — replays the transfer list and checks every well (independent of the planner)
  - `scripts/verify_plan.py` — command-line check of a saved layout
  - `src/plate_canvas.py` — interactive plate widget
  - `tests/` — pytest
- `docker/`, `docker-compose.yml`, `scripts/start_claude.sh` — Claude Code container

## Commands (inside the container)

```bash
cd drug-screen-platform
uv sync
uv run pytest
uv run python scripts/verify_plan.py              # example plate
uv run python scripts/verify_plan.py plate.json   # layout saved from the app
```

Any change to the planner must keep `tests/test_plan_checker.py` green (300 random layouts).

The GUI can't open inside the container (no display); run it on the Windows host
with `uv run python main.py`.

## Conventions

- Numpy-style docstrings and type hints; comments only where they explain *why*
- Descriptive names, no single-letter variables except loop indices
- try/except around file I/O and external calls
- Keep GUI and logic separate: anything a robot protocol needs lives in `src/`, not `main.py`
- Commit messages: conventional commits, short (e.g. `feat: add intermediate plate view`)
- Work on a branch; the user pushes from the Windows host
