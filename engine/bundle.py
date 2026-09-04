"""
PROMAN Bundle Quotation
Quotes any combination of equipment + optional conveyors,
without requiring a full plant spec.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import rate_card as rc
from engine import (ConveyorSpec, LineItem, Quotation, PlantSpec,
                    _conveyor_hp, _chutes_and_supports_cost,
                    _calc_structural, _calc_electrical)
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# BUNDLE ITEM
# ---------------------------------------------------------------------------

@dataclass
class BundleEquipmentItem:
    category: str          # VGF / JAW / CONE / VSI / SCREEN / MVF / WSG / METAL_DETECTOR
    model: str             # e.g. "4510", "2000x6000_4d"
    qty: int = 1
    note: str = ""         # free-text for this line


@dataclass
class BundleConveyorItem:
    width_mm: int          # 500 / 650 / 800 / 1000 / 1200
    length_m: float
    qty: int = 1
    note: str = ""


@dataclass
class BundleSpec:
    client_name:   str
    ref_no:        str = ""
    date:          str = ""
    equipment:     List[BundleEquipmentItem] = field(default_factory=list)
    conveyors:     List[BundleConveyorItem]  = field(default_factory=list)
    include_chutes: bool = True              # add chutes & supports line if conveyors present
    include_erection: bool = False
    erection_lump: float = 0.0              # override erection value


# ---------------------------------------------------------------------------
# FETCHERS
# ---------------------------------------------------------------------------

def _fetch(category: str, model: str) -> dict:
    cat = category.upper()
    if cat == "VGF":    return rc.get_vgf(model) or {}
    if cat == "JAW":    return rc.get_jaw(model) or {}
    if cat == "CONE":   return rc.get_cone(model) or {}
    if cat == "VSI":    return rc.get_vsi(model) or {}
    if cat == "SCREEN": return rc.get_screen(model) or {}
    if cat == "MVF":    return rc.get_mvf(model) or {}
    if cat == "WSG":    return rc.get_wsg(model) or {}
    if cat in ("METAL_DETECTOR", "MD"):
        d = rc.METAL_DETECTOR
        return {"list": d["list"], "best": d["best"], "hp": 0}
    return {}


def _label(category: str, model: str) -> str:
    cat = category.upper()
    if cat == "VGF":    return f"Vibrating Grizzly Feeder VGF {model}mm"
    if cat == "JAW":    return f"Primary Jaw Crusher PROjaw-{model}\""
    if cat == "CONE":   return f"Secondary Cone Crusher PROcone-{model}"
    if cat == "VSI":    return f"Tertiary VSI REMCO {model}"
    if cat == "SCREEN": return f"Vibratory Screen {model.upper()}"
    if cat == "MVF":    return f"Mechanical Vibratory Feeder MVF {model}"
    if cat == "WSG":    return f"ORTNER WSG-{model} Sand Washing System"
    if cat in ("METAL_DETECTOR", "MD"): return "Metal Detector"
    return f"{category} {model}"


# ---------------------------------------------------------------------------
# MAIN BUILDER
# ---------------------------------------------------------------------------

def build_bundle_quotation(spec: BundleSpec) -> Quotation:
    """
    Build a quotation for a mix of equipment + optional conveyors.
    Returns a Quotation with sub_a_items and sub_b_conveyors populated.
    Sub C / D / E are zero unless overridden.
    """
    # Create a dummy PlantSpec for the Quotation container
    ps = PlantSpec(
        client_name = spec.client_name,
        tph         = 0,
        stages      = 0,
        ref_no      = spec.ref_no,
        date        = spec.date,
    )
    q = Quotation(spec=ps)

    # ── Sub A: equipment ──────────────────────────────────────────────────
    sl = 1
    for item in spec.equipment:
        data  = _fetch(item.category, item.model)
        label = _label(item.category, item.model)
        if item.note:
            label += f" — {item.note}"

        if not data:
            q.warnings.append(f"{item.category} {item.model}: not found in rate card")
            continue

        lp = data.get("list")
        bp = data.get("best")
        hp = data.get("hp", 0)
        flags = []
        if data.get("flag"):
            flags.append(data["flag"])
            q.warnings.append(data["flag"])

        li = LineItem(
            sl          = str(sl),
            description = label,
            qty         = item.qty,
            hp          = hp * item.qty,
            list_price  = round(lp * item.qty, 2) if lp is not None else None,
            best_price  = round(bp * item.qty, 2) if bp is not None else None,
            flags       = flags,
        )
        q.sub_a_items.append(li)
        sl += 1

    # ── Sub B: conveyors ──────────────────────────────────────────────────
    for i, cv in enumerate(spec.conveyors, 1):
        hp = _conveyor_hp(cv.width_mm, cv.length_m)
        purpose = cv.note or f"conveyor_{i}"
        for j in range(cv.qty):
            tag = f"BC-{len(q.sub_b_conveyors)+1:02d}"
            q.sub_b_conveyors.append(ConveyorSpec(
                tag=tag, width_mm=cv.width_mm, length_m=cv.length_m,
                hp=hp, purpose=purpose,
            ))

    if spec.include_chutes and q.sub_b_conveyors:
        q.sub_b_chutes_list, q.sub_b_chutes_best = _chutes_and_supports_cost(q.sub_b_conveyors)

    # ── Sub E: erection ───────────────────────────────────────────────────
    if spec.include_erection:
        q.erection = spec.erection_lump if spec.erection_lump else 3.0  # default 3L for small bundles

    return q


# ---------------------------------------------------------------------------
# TPH INFERENCE
# ---------------------------------------------------------------------------

def infer_tph(
    jaw_model: str = None,
    cone_model: str = None,
    vsi_model: str = None,
    feed_size_mm: int = None,
    material: str = None,
    stages: int = None,
) -> dict:
    """
    Estimate TPH from whatever equipment or context is available.
    Returns {"tph_min", "tph_max", "tph_mid", "basis", "confidence"}
    """
    tph_min, tph_max = None, None
    basis = []
    confidence = "low"

    def _overlap(a_min, a_max, b_min, b_max):
        return max(a_min, b_min), min(a_max, b_max)

    # From jaw model
    if jaw_model:
        jaw = rc.get_jaw(jaw_model)
        if jaw and jaw.get("tph_range"):
            lo, hi = jaw["tph_range"]
            tph_min, tph_max = (lo, hi) if tph_min is None else _overlap(tph_min, tph_max, lo, hi)
            basis.append(f"Jaw {jaw_model} range {lo}–{hi} TPH")
            confidence = "medium"

    # From cone model
    if cone_model:
        cone = rc.get_cone(cone_model)
        if cone and cone.get("tph_range"):
            lo, hi = cone["tph_range"]
            tph_min, tph_max = (lo, hi) if tph_min is None else _overlap(tph_min, tph_max, lo, hi)
            basis.append(f"Cone {cone_model} range {lo}–{hi} TPH")
            confidence = "medium"

    # From VSI model
    if vsi_model:
        vsi = rc.get_vsi(vsi_model)
        if vsi and vsi.get("tph_range"):
            lo, hi = vsi["tph_range"]
            tph_min, tph_max = (lo, hi) if tph_min is None else _overlap(tph_min, tph_max, lo, hi)
            basis.append(f"VSI {vsi_model} range {lo}–{hi} TPH")
            confidence = "high" if jaw_model or cone_model else "medium"

    # Material softness adjustment
    material_factor = 1.0
    if material:
        m = material.lower()
        if "limestone" in m or "dolomite" in m:
            material_factor = 1.15
            basis.append("Limestone/Dolomite: +15% capacity assumed")
        elif "quartzite" in m or "quartz" in m:
            material_factor = 0.85
            basis.append("Quartzite: −15% capacity assumed")
        elif "basalt" in m:
            material_factor = 0.95

    # Feed size adjustment: larger feed → lower effective TPH
    if feed_size_mm:
        if feed_size_mm > 700:
            material_factor *= 0.90
            basis.append(f"Large feed ({feed_size_mm}mm): −10% effective capacity")
        elif feed_size_mm < 400:
            material_factor *= 1.10
            basis.append(f"Small feed ({feed_size_mm}mm): +10% effective capacity")

    if tph_min is None:
        # Fallback by stages
        defaults = {2: (150, 300), 3: (200, 400), None: (100, 500)}
        tph_min, tph_max = defaults.get(stages, defaults[None])
        basis.append(f"Defaulted from {stages}-stage typical range")

    tph_min  = int(tph_min  * material_factor)
    tph_max  = int(tph_max  * material_factor)
    tph_mid  = (tph_min + tph_max) // 2

    return {
        "tph_min":    tph_min,
        "tph_max":    tph_max,
        "tph_mid":    tph_mid,
        "basis":      basis,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# CLI TEST
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Test 1: Screen station — 1x Screen + ground hopper + 2 conveyors
    spec = BundleSpec(
        client_name = "ABC Quarry",
        ref_no      = "PR/09-26/B-001",
        equipment   = [
            BundleEquipmentItem("SCREEN", "2000x6000_4d", qty=1, note="Final product screen"),
            BundleEquipmentItem("MVF",    "100-160",      qty=1, note="Screen feed feeder"),
            BundleEquipmentItem("METAL_DETECTOR", "std", qty=1),
        ],
        conveyors   = [
            BundleConveyorItem(800,  18, qty=1, note="Feed to screen"),
            BundleConveyorItem(650,  15, qty=4, note="Product belts"),
        ],
        include_erection=True, erection_lump=2.0,
    )
    q = build_bundle_quotation(spec)
    print("=== Screen Station Bundle ===")
    for i in q.sub_a_items:
        print(f"  {i.sl}. {i.description} | HP:{i.hp} | List:{i.list_price}L")
    for c in q.sub_b_conveyors:
        print(f"  {c.tag}: {c.width_mm}mm x {c.length_m}m = ₹{c.cost_lakhs}L")
    print(f"  Grand Total List: ₹{q.grand_total_list()}L")
    print()

    # Test 2: TPH inference from Cone model
    r = infer_tph(cone_model="4510", material="limestone", stages=2)
    print("=== TPH Inference (Cone 4510, limestone) ===")
    print(f"  Projected: {r['tph_min']}–{r['tph_max']} TPH (mid: {r['tph_mid']})")
    print(f"  Confidence: {r['confidence']}")
    for b in r['basis']: print(f"  • {b}")
