"""
PROMAN Equipment Selector
Picks the right equipment model for a given TPH, stage count, and material.

Knowledge base derived from 9 PROMAN AggFlow PFDs (2026):
  150 TPH 2/3-stage Granite, 250 TPH 2/3-stage Granite/Basalt,
  300 TPH 3-stage Limestone, 600 TPH 3-stage Gabro,
  Tertiary-only VSI-200/300/5080 configs.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# MATERIAL HARDNESS GROUPS
# Hard = granite, basalt, quartzite, gabro, dolerite
# Medium = limestone, dolomite, sandstone, marble
# Soft = gypsum, chalk, recycled concrete
# ---------------------------------------------------------------------------

HARD_MATERIALS  = {"granite", "basalt", "quartzite", "quartz", "silica", "gabro",
                   "gabbro", "dolerite", "andesite", "rhyolite", "iron ore", "feldspar"}
SOFT_MATERIALS  = {"gypsum", "chalk", "recycled concrete", "coal"}
# Everything else → medium (limestone, dolomite, sandstone, marble, …)

def material_group(material: str) -> str:
    m = material.lower()
    if any(h in m for h in HARD_MATERIALS):
        return "hard"
    if any(s in m for s in SOFT_MATERIALS):
        return "soft"
    return "medium"


# ---------------------------------------------------------------------------
# VGF SELECTION
# ---------------------------------------------------------------------------

def select_vgf(tph: float) -> dict:
    """Return VGF model, feed capacity and max feed size."""
    if tph <= 165:
        return {
            "model": "VGF 1.0m x 4.0m",
            "footprint_key": "1000x4000",
            "feed_capacity_mtph": 150,
            "max_feed_mm": 500,
        }
    elif tph <= 280:
        return {
            "model": "VGF 1.2m x 5.0m",
            "footprint_key": "1200x5000",
            "feed_capacity_mtph": 250,
            "max_feed_mm": 650,
        }
    else:
        return {
            "model": "VGF 1.3m x 5.6m",
            "footprint_key": "1300x5600",
            "feed_capacity_mtph": 650,
            "max_feed_mm": 750,
        }


# ---------------------------------------------------------------------------
# JAW CRUSHER SELECTION
# ---------------------------------------------------------------------------

def select_jaw(tph: float, material: str = "granite") -> dict:
    """Return jaw model and recommended CSS."""
    grp = material_group(material)

    if tph <= 175:
        css = 110
        return {
            "model": "PROJaw 3624",
            "footprint_key": "PROJaw_3624",
            "css_mm": css,
            "tph_capacity": 150,
            "note": "Standard 36x24 jaw for up to 175 TPH.",
        }
    elif tph <= 370:
        # CSS varies by material softness
        if grp == "hard":
            css = 110
        elif grp == "soft":
            css = 152
        else:
            css = 127
        return {
            "model": "PROJaw 4230 (42x30)",
            "footprint_key": "PROJaw_4230",
            "css_mm": css,
            "tph_capacity": 350,
            "note": f"42x30 jaw. CSS {css}mm for {material}.",
        }
    else:
        return {
            "model": "PROJaw 49x38 (Hcy-1250x950)",
            "footprint_key": "PROJaw_49x38",
            "css_mm": 125,
            "tph_capacity": 650,
            "note": "Hydraulic 49x38 jaw. Used for 600 TPH gabro. Feed 0-750mm.",
        }


# ---------------------------------------------------------------------------
# CONE CRUSHER SELECTION
# ---------------------------------------------------------------------------

def select_cone(tph: float, material: str = "granite", stages: int = 2) -> dict:
    """Return cone model, CSS and any twin-cone flag."""
    grp = material_group(material)

    # 3-stage cones run tighter CSS than 2-stage (finer pre-VSI product)
    css_offset = -2 if stages >= 3 else 0

    if tph <= 185:
        css = (32 + css_offset) if grp == "hard" else 34
        return {
            "model": "PROCone-3510",
            "footprint_key": "PROCone_3510",
            "css_mm": max(22, css),
            "twin": False,
            "tph_capacity": 200,
        }
    elif tph <= 275:
        # PFD evidence: 250 TPH (granite+basalt) uses 4510. 300 TPH limestone uses 5010.
        css = (32 + css_offset) if grp != "soft" else 36
        return {
            "model": "PROCone-4510",
            "footprint_key": "PROCone_4510",
            "css_mm": max(22, css),
            "twin": False,
            "tph_capacity": 275,
        }
    elif tph <= 420:
        css = (34 + css_offset) if grp != "soft" else 40
        return {
            "model": "PROCone-5010",
            "footprint_key": "PROCone_5010",
            "css_mm": max(22, css),
            "twin": False,
            "tph_capacity": 400,
        }
    else:
        # Twin cones for >420 TPH
        css = (28 + css_offset)
        return {
            "model": "2x PROCone-5010 (twin, 50-50 split)",
            "footprint_key": "PROCone_5010",
            "css_mm": max(22, css),
            "twin": True,
            "motor_hp": "2x400 HP",
            "tph_capacity": 650,
            "note": "Twin cone arrangement as per 600 TPH gabro PFD.",
        }


# ---------------------------------------------------------------------------
# VSI SELECTION (Tertiary Stage)
# ---------------------------------------------------------------------------

def select_vsi(tph_into_vsi: float) -> dict:
    """Return VSI model for given throughput entering the tertiary stage."""
    # Thresholds derived from PFD VSI throughputs:
    # VSI-200 → 142 mt/h (150 TPH plant) | VSI-300 → 242 mt/h (250 TPH)
    # VSI-4060 → 312 mt/h (300 TPH)      | VSI-5080 → 650 mt/h (600 TPH)
    if tph_into_vsi <= 165:
        return {
            "model": "PROMAN REMco VSI-200",
            "footprint_key": "REMco_VSI200",
            "max_feed_mm": 30,
            "tph_capacity": 157,
        }
    elif tph_into_vsi <= 262:
        return {
            "model": "PROMAN REMco VSI-300",
            "footprint_key": "REMco_VSI300",
            "max_feed_mm": 40,
            "tph_capacity": 262,
        }
    elif tph_into_vsi <= 380:
        # Layout (300 TPH plant) confirms 2×250HP for VSI-4060
        return {
            "model": "PROMAN REMco VSI-4060",
            "footprint_key": "REMco_VSI4060",
            "max_feed_mm": 45,
            "motor_hp": "2x250 HP",
            "tph_capacity": 380,
        }
    else:
        return {
            "model": "PROMAN REMco VSI-5080",
            "footprint_key": "REMco_VSI5080",
            "max_feed_mm": 50,
            "motor_hp": "2x400 HP",
            "tph_capacity": 700,
        }


# ---------------------------------------------------------------------------
# SCREEN SELECTION
# ---------------------------------------------------------------------------

def select_screens(tph: float, stages: int, material: str = "granite") -> dict:
    """
    Return screen recommendations.
    2-stage → single final 4-deck screen
    3-stage → intermediate screen + final screen
    """
    if stages <= 2:
        if tph <= 175:
            final = {"model": "Screen 2.0m x 6.0m 4-Deck", "footprint_key": "2000x6000_4d", "decks": 4}
        elif tph <= 320:
            final = {"model": "Screen TBC for 250-300 TPH 2-stage", "footprint_key": "2000x6000_4d", "decks": 4}
        else:
            final = {"model": "Screen 2.4m x 8.1m 3-Deck", "footprint_key": "2400x8100_3d", "decks": 3}
        return {"intermediate": None, "final": final}

    else:  # 3-stage
        if tph <= 175:
            return {
                "intermediate": {"model": "Screen 1.2m x 4.0m 3-Deck", "footprint_key": "1200x4000_3d", "decks": 3},
                "final":        {"model": "Screen 2.0m x 5.0m 4-Deck", "footprint_key": "2000x5000_4d", "decks": 4},
            }
        elif tph <= 280:
            # PFD evidence (250 TPH Basalt 3-Stage): intermediate=1.2m×4m-3D (pre-VSI), final=2m×6m-4D
            return {
                "intermediate": {"model": "Screen 1.2m x 4.0m 3-Deck", "footprint_key": "1200x4000_3d", "decks": 3},
                "final":        {"model": "Screen 2.0m x 6.0m 4-Deck",  "footprint_key": "2000x6000_4d", "decks": 4},
            }
        elif tph <= 380:
            return {
                "intermediate": {"model": "Screen 2.0m x 5.0m 3-Deck", "footprint_key": "2000x5000_3d", "decks": 3},
                "final":        {"model": "Screen 2.0m x 7.0m 4-Deck", "footprint_key": "2000x7000_4d", "decks": 4},
            }
        else:  # 600 TPH → twin screens
            return {
                "intermediate": {"model": "2x Screen 2.4m x 8.1m 3-Deck", "footprint_key": "2400x8100_3d", "decks": 3, "twin": True},
                "final":        {"model": "2x Screen 2.4m x 8.1m 3-Deck", "footprint_key": "2400x8100_3d", "decks": 3, "twin": True},
            }


# ---------------------------------------------------------------------------
# PRODUCT GRADATION (screen cuts) RECOMMENDATION
# ---------------------------------------------------------------------------

def recommend_screen_cuts(stages: int, product_type: str = "standard") -> dict:
    """
    Return recommended screen deck cuts (mm) for the final screen.
    product_type: 'standard' | 'road' (MORTH/GSB) | 'concrete'
    """
    if stages <= 2:
        return {
            "cuts_mm": [40, 20, 10, 4.75],
            "products": ["40mm aggregate", "20mm aggregate", "10mm aggregate", "Crusher Dust"],
            "standard": "IS 383 / General"
        }
    else:
        if product_type == "road":
            return {
                "cuts_mm": [25, 19, 10, 5],
                "products": ["25mm GSB", "19mm WMM", "10mm Chips", "5mm Stone Dust"],
                "standard": "MORTH / IRC"
            }
        else:
            return {
                "cuts_mm": [20, 12, 8, 4.75],
                "products": ["20mm aggregate", "12mm aggregate", "8mm aggregate", "M-Sand / Crusher Dust"],
                "standard": "IS 383"
            }


# ---------------------------------------------------------------------------
# FULL PLANT EQUIPMENT SCHEDULE
# ---------------------------------------------------------------------------

def build_equipment_schedule(
    tph: float,
    stages: int,
    material: str = "granite",
    product_type: str = "standard",
) -> dict:
    """
    Master function: returns a complete equipment schedule for a PROMAN plant.

    Args:
        tph: Plant nominal capacity in metric tonnes per hour
        stages: Number of crushing stages (1-4)
        material: Feed material name (granite, basalt, limestone, etc.)
        product_type: 'standard' | 'road' | 'concrete'

    Returns:
        dict with keys: vgf, jaw, cone, vsi, screens, gradation, notes
    """
    # VSI throughput ≈ nominal TPH (PFD evidence):
    # 150 TPH plant → 142 mt/h VSI-200 | 250 TPH → 242 mt/h VSI-300
    # 300 TPH → 312 mt/h VSI-4060      | 600 TPH → 650 mt/h VSI-5080
    vsi_tph = tph

    schedule = {
        "tph_nominal": tph,
        "stages": stages,
        "material": material,
        "material_group": material_group(material),
        "product_type": product_type,
        "vgf":    select_vgf(tph),
        "jaw":    select_jaw(tph, material),
        "cone":   select_cone(tph, material, stages) if stages >= 2 else None,
        "vsi":    select_vsi(vsi_tph) if stages >= 3 else None,
        "screens": select_screens(tph, stages, material),
        "gradation": recommend_screen_cuts(stages, product_type),
    }

    # Add capacity notes
    notes = []
    if material_group(material) == "hard" and tph > 400:
        notes.append("Hard material >400 TPH: twin secondary cones recommended.")
    if stages == 3:
        notes.append("3-stage: intermediate surge bin + mechanical feeder required between cone and VSI.")
    if tph > 500:
        notes.append("600 TPH range: twin secondary cones and twin final screens.")
    notes.append("All capacities ±10% per AggFlow methodology. Moisture assumed ≤2%.")
    schedule["notes"] = notes

    return schedule


# ---------------------------------------------------------------------------
# QUICK TEST
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json

    configs = [
        (150, 2, "granite"), (150, 3, "granite"),
        (250, 2, "granite"), (250, 3, "basalt"),
        (300, 3, "limestone"), (600, 3, "gabro"),
    ]
    for tph, stg, mat in configs:
        r = build_equipment_schedule(tph, stg, mat)
        print(f"\n--- {tph} TPH {stg}-Stage [{mat}] ---")
        print(f"  VGF:  {r['vgf']['model']}")
        print(f"  JAW:  {r['jaw']['model']} CSS {r['jaw']['css_mm']}mm")
        if r['cone']:
            print(f"  CONE: {r['cone']['model']} CSS {r['cone']['css_mm']}mm")
        if r['vsi']:
            print(f"  VSI:  {r['vsi']['model']}")
        print(f"  CUTS: {r['gradation']['cuts_mm']}mm → {r['gradation']['products']}")
