"""
PROMAN Masters Manager
Load, save, and query all master data files.
All JSON files live in engine/masters/.
"""

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

MASTERS_DIR = Path(__file__).parent / "masters"
MASTERS_DIR.mkdir(exist_ok=True)

MASTER_NAMES = [
    "stages", "footprints", "materials",
    "gradations", "engine_config", "layout_templates",
]


# ---------------------------------------------------------------------------
# CORE IO
# ---------------------------------------------------------------------------

def load(name: str) -> dict:
    """Load a master JSON file. Returns {} if missing."""
    path = MASTERS_DIR / f"{name}.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(name: str, data: dict, updated_by: str = "system") -> dict:
    """Save a master JSON file, stamping metadata."""
    if "_meta" in data:
        data["_meta"]["last_updated"] = date.today().isoformat()
        data["_meta"]["updated_by"]   = updated_by
    path = MASTERS_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data


# ---------------------------------------------------------------------------
# CONVENIENCE GETTERS
# ---------------------------------------------------------------------------

def get_stage(stages: int) -> dict:
    """Return stage spec for a given number of stages (1-4)."""
    master = load("stages")
    return master.get(str(stages), {})


def get_material(name: str) -> dict:
    """Return material properties. Case-insensitive partial match."""
    master = load("materials")
    # Exact match first
    if name in master:
        return master[name]
    # Case-insensitive
    nl = name.lower()
    for key, val in master.items():
        if key.lower() == nl:
            return val
    # Partial match
    for key, val in master.items():
        if nl in key.lower() or key.lower() in nl:
            return val
    return {}


def get_footprint(category: str, model: str) -> dict:
    """Return equipment footprint dimensions."""
    master = load("footprints")
    cat = category.upper()
    cat_data = master.get(cat, {})
    if model in cat_data:
        return cat_data[model]
    # Try normalised model key
    norm = model.replace('"', '').replace("'", "").replace(" ", "")
    for key, val in cat_data.items():
        if key.replace(" ", "") == norm:
            return val
    return {}


def get_gradation(product_name: str) -> dict:
    """Return gradation spec for a product."""
    master = load("gradations")
    if product_name in master:
        return master[product_name]
    nl = product_name.lower()
    for key, val in master.items():
        if nl in key.lower() or key.lower() in nl:
            return val
    return {}


def get_engine_config() -> dict:
    """Return engine configuration parameters."""
    return load("engine_config")


def get_layout_template(style: str = "cascade") -> dict:
    """Return a layout template by style name."""
    master = load("layout_templates")
    return master.get(style, master.get("cascade", {}))


def material_capacity_factor(material: str) -> float:
    """Return capacity correction factor for a material (default 1.0 = granite)."""
    mat = get_material(material)
    return mat.get("capacity_factor", 1.0)


def get_all_footprints_flat() -> list:
    """Return all footprint entries as a flat list for the UI."""
    master = load("footprints")
    rows = []
    for cat, models in master.items():
        if cat.startswith("_"):
            continue
        for model, dims in models.items():
            rows.append({"category": cat, "model": model, **dims})
    return rows


def get_all_materials_list() -> list:
    """Return all materials as a flat list for the UI."""
    master = load("materials")
    rows = []
    for name, props in master.items():
        if name.startswith("_"):
            continue
        rows.append({"name": name, **props})
    return rows


def get_all_gradations_list() -> list:
    master = load("gradations")
    rows = []
    for name, props in master.items():
        if name.startswith("_"):
            continue
        rows.append({"product": name, **props})
    return rows
