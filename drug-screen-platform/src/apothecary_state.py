"""
What the concoction console remembers on this laptop (``runs/apothecary.json``):
trough names, colours and volumes, the next unused tip column of each rack, and
which plate columns already hold a concoction.
"""

import json
from datetime import datetime
from typing import Optional

import run_store
from concoction import COLUMNS, TIP_COLUMNS_PER_RACK, TROUGHS, Recipe

FILE_NAME = "apothecary.json"
# Liquid tints for the troughs, picked to stay distinguishable side by side.
TINTS = ["#4F9DDE", "#E0A43A", "#5DB37E", "#C8566B", "#8A6FD1", "#3FB6B0",
         "#D9774A", "#A3B83D", "#D45FA6", "#6C8CA6", "#B88B5A", "#7C5CA3"]


def _default() -> dict:
    return {
        "troughs": [{"trough": t, "name": f"Trough {t}", "color": TINTS[t - 1], "volume_ul": None}
                    for t in range(1, TROUGHS + 1)],
        "tips": {"small_next": 1, "large_next": 1},
        "plates": {},
    }


def _path():
    return run_store.RUNS_DIR / FILE_NAME


def load() -> dict:
    try:
        return {**_default(), **json.loads(_path().read_text(encoding="utf-8"))}
    except FileNotFoundError:
        return _default()
    except (OSError, json.JSONDecodeError) as error:
        raise OSError(f"Could not read {_path()}: {error}") from error


def save(state: dict) -> None:
    path = _path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except OSError as error:
        raise OSError(f"Could not write {path}: {error}") from error


def tips_view(state: dict) -> dict:
    tips = state["tips"]
    return {**tips, "small_left": TIP_COLUMNS_PER_RACK - tips["small_next"] + 1,
            "large_left": TIP_COLUMNS_PER_RACK - tips["large_next"] + 1}


def plate_columns(state: dict, plate: str) -> dict:
    return state["plates"].get(run_store.slugify(plate), {})


def trough_volumes(state: dict) -> dict[int, float]:
    return {t["trough"]: t["volume_ul"] for t in state["troughs"] if t["volume_ul"] is not None}


def record_brew(state: dict, plate: str, recipes: list[Recipe], summary: dict, run_id: str) -> None:
    """Advance the tip columns, take the draws out of the troughs and mark the columns as brewed."""
    state["tips"]["small_next"] += summary["small_tips"]
    state["tips"]["large_next"] += summary["large_tips"]
    for trough in state["troughs"]:
        drawn = summary["trough_draw_ul"].get(trough["trough"], 0)
        if trough["volume_ul"] is not None:
            trough["volume_ul"] = round(max(trough["volume_ul"] - drawn, 0), 3)
    columns = state["plates"].setdefault(run_store.slugify(plate), {})
    for recipe in recipes:
        columns[str(recipe.column)] = {
            "name": recipe.name,
            "ingredients": [{"trough": i.trough, "volume_ul": i.volume_ul} for i in recipe.ingredients],
            "brewed": datetime.now().isoformat(timespec="seconds"),
            "run_id": run_id,
        }
    save(state)
