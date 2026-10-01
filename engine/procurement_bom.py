"""
PROMAN Deep Procurement BOM
Generates a multi-category, multi-level BOM from an equipment schedule.

Categories:
  MANUFACTURED   - Main equipment bodies (PROMAN-made)
  BOUGHT_OUT     - Motors, drives, bearings, electrical, lubrication
  WEAR_PARTS     - Jaw/cone/VSI wear liners, screen media (initial supply)
  CONSUMABLES    - Lubricants, filters, gaskets
  STRUCTURAL     - Fabricated steel structure, platforms, walkways
  CONVEYOR       - Per-conveyor component breakdown
"""

from __future__ import annotations
import math

# ---------------------------------------------------------------------------
# MOTOR / DRIVE SPECS per equipment model
# ---------------------------------------------------------------------------
MOTOR_SPECS: dict[str, dict] = {
    "VGF 1.0m x 4.0m":                      {"qty":2,"kw":7.5, "hp":10,  "type":"Vibrator Motor TEFC",          "start":"DOL"},
    "VGF 1.2m x 5.0m":                      {"qty":2,"kw":11,  "hp":15,  "type":"Vibrator Motor TEFC",          "start":"DOL"},
    "VGF 1.3m x 5.6m":                      {"qty":2,"kw":15,  "hp":20,  "type":"Vibrator Motor TEFC",          "start":"DOL"},
    "PROJaw 3624":                           {"qty":1,"kw":75,  "hp":100, "type":"SCIM, IP55, B3 foot-mtd",      "start":"Soft Starter"},
    "PROJaw 4230 (42x30)":                  {"qty":1,"kw":132, "hp":177, "type":"SCIM, IP55, B3 foot-mtd",      "start":"Soft Starter"},
    "PROJaw 49x38 (Hcy-1250x950)":          {"qty":1,"kw":200, "hp":268, "type":"SCIM, IP55, B3 foot-mtd",      "start":"Soft Starter"},
    "PROCone-3510":                          {"qty":1,"kw":110, "hp":148, "type":"SCIM, IP55, B3 foot-mtd",      "start":"Soft Starter"},
    "PROCone-4510":                          {"qty":1,"kw":160, "hp":215, "type":"SCIM, IP55, B3 foot-mtd",      "start":"Soft Starter"},
    "PROCone-5010":                          {"qty":1,"kw":220, "hp":295, "type":"SCIM, IP55, B3 foot-mtd",      "start":"Soft Starter"},
    "2x PROCone-5010 (twin, 50-50 split)":  {"qty":2,"kw":220, "hp":295, "type":"SCIM, IP55, B3 foot-mtd",      "start":"Soft Starter"},
    "PROMAN REMco VSI-200":                  {"qty":2,"kw":75,  "hp":100, "type":"SCIM, IP55, Flange-mtd",       "start":"Star-Delta"},
    "PROMAN REMco VSI-300":                  {"qty":2,"kw":110, "hp":148, "type":"SCIM, IP55, Flange-mtd",       "start":"Star-Delta"},
    "PROMAN REMco VSI-4060":                 {"qty":2,"kw":185, "hp":250, "type":"SCIM, IP55, Flange-mtd",       "start":"Star-Delta"},  # Layout confirms 2×250HP
    "PROMAN REMco VSI-5080":                 {"qty":2,"kw":315, "hp":423, "type":"SCIM, IP55, Flange-mtd",       "start":"Star-Delta"},
    "Screen 1.2m x 4.0m 3-Deck":            {"qty":2,"kw":7.5, "hp":10,  "type":"Vibrator Motor TEFC",          "start":"DOL"},
    "Screen 2.0m x 5.0m 3-Deck":            {"qty":2,"kw":11,  "hp":15,  "type":"Vibrator Motor TEFC",          "start":"DOL"},
    "Screen 2.0m x 5.0m 4-Deck":            {"qty":2,"kw":11,  "hp":15,  "type":"Vibrator Motor TEFC",          "start":"DOL"},
    "Screen 2.0m x 6.0m 4-Deck":            {"qty":2,"kw":15,  "hp":20,  "type":"Vibrator Motor TEFC",          "start":"DOL"},
    "Screen 2.0m x 7.0m 4-Deck":            {"qty":2,"kw":18.5,"hp":25,  "type":"Vibrator Motor TEFC",          "start":"DOL"},
    "Screen 2.4m x 8.1m 3-Deck":            {"qty":4,"kw":22,  "hp":30,  "type":"Vibrator Motor TEFC",          "start":"DOL"},
    "2x Screen 2.4m x 8.1m 3-Deck":         {"qty":8,"kw":22,  "hp":30,  "type":"Vibrator Motor TEFC",          "start":"DOL"},
}

# ---------------------------------------------------------------------------
# WEAR PARTS — Jaw Crusher (initial supply: 2 sets)
# ---------------------------------------------------------------------------
_JAW_WEAR: dict[str, list] = {
    "PROJaw 3624": [
        {"item":"Fixed Jaw Plate",           "material":"Mn13Cr2 Cast Manganese Steel","unit":"Nos","qty":2,"wt_kg":580,"life_hrs":"800-1000","note":"Primary wear face"},
        {"item":"Swing Jaw Plate",           "material":"Mn13Cr2 Cast Manganese Steel","unit":"Nos","qty":2,"wt_kg":520,"life_hrs":"600-800", "note":"Higher wear than fixed"},
        {"item":"Cheek Plates (Side Liners)","material":"Mn13 Cast Steel",             "unit":"Set","qty":2,"wt_kg":40, "life_hrs":"1500",    "note":"Pair per side"},
        {"item":"Toggle Plate (Safety Fuse)","material":"Grey Cast Iron",              "unit":"Nos","qty":2,"wt_kg":35, "life_hrs":"—",       "note":"Replace if overload occurs"},
        {"item":"Toggle Seat",               "material":"Bronze / UHMWPE",             "unit":"Nos","qty":2,"wt_kg":8,  "life_hrs":"—",       "note":"Replace with toggle plate"},
    ],
    "PROJaw 4230 (42x30)": [
        {"item":"Fixed Jaw Plate",           "material":"Mn13Cr2 Cast Manganese Steel","unit":"Nos","qty":2,"wt_kg":950, "life_hrs":"800-1000","note":""},
        {"item":"Swing Jaw Plate",           "material":"Mn13Cr2 Cast Manganese Steel","unit":"Nos","qty":2,"wt_kg":850, "life_hrs":"600-800", "note":""},
        {"item":"Cheek Plates (Side Liners)","material":"Mn13 Cast Steel",             "unit":"Set","qty":2,"wt_kg":65,  "life_hrs":"1500",    "note":""},
        {"item":"Toggle Plate (Safety Fuse)","material":"Grey Cast Iron",              "unit":"Nos","qty":2,"wt_kg":55,  "life_hrs":"—",       "note":""},
        {"item":"Toggle Seat",               "material":"Bronze / UHMWPE",             "unit":"Nos","qty":2,"wt_kg":12,  "life_hrs":"—",       "note":""},
    ],
    "PROJaw 49x38 (Hcy-1250x950)": [
        {"item":"Fixed Jaw Plate",           "material":"Mn18Cr2 Cast Manganese Steel","unit":"Nos","qty":2,"wt_kg":1800,"life_hrs":"600-800", "note":"Hydraulic jaw"},
        {"item":"Swing Jaw Plate",           "material":"Mn18Cr2 Cast Manganese Steel","unit":"Nos","qty":2,"wt_kg":1650,"life_hrs":"600-800", "note":""},
        {"item":"Cheek Plates (Side Liners)","material":"Mn18 Cast Steel",             "unit":"Set","qty":2,"wt_kg":120, "life_hrs":"1200",    "note":""},
        {"item":"Toggle Plate (Safety Fuse)","material":"Grey Cast Iron",              "unit":"Nos","qty":2,"wt_kg":90,  "life_hrs":"—",       "note":""},
        {"item":"Toggle Seat",               "material":"Bronze / UHMWPE",             "unit":"Nos","qty":2,"wt_kg":20,  "life_hrs":"—",       "note":""},
    ],
}

# ---------------------------------------------------------------------------
# WEAR PARTS — Cone Crusher
# ---------------------------------------------------------------------------
_CONE_WEAR: dict[str, list] = {
    "PROCone-3510": [
        {"item":"Mantle (Inner Crushing Cone)","material":"Mn18Cr2 Cast Steel","unit":"Nos","qty":2,"wt_kg":580, "life_hrs":"800",  "note":""},
        {"item":"Bowl Liner (Concave Ring)",   "material":"Mn18Cr2 Cast Steel","unit":"Nos","qty":2,"wt_kg":520, "life_hrs":"600-800","note":""},
        {"item":"Feed Plate / Distributor",    "material":"UHMWPE",            "unit":"Nos","qty":2,"wt_kg":8,   "life_hrs":"—",    "note":""},
        {"item":"Main Thrust Bearing Set",     "material":"—",                 "unit":"Set","qty":1,"wt_kg":5,   "life_hrs":"5000", "note":"Annual check"},
    ],
    "PROCone-4510": [
        {"item":"Mantle (Inner Crushing Cone)","material":"Mn18Cr2 Cast Steel","unit":"Nos","qty":2,"wt_kg":950, "life_hrs":"800",  "note":""},
        {"item":"Bowl Liner (Concave Ring)",   "material":"Mn18Cr2 Cast Steel","unit":"Nos","qty":2,"wt_kg":850, "life_hrs":"600-800","note":""},
        {"item":"Feed Plate / Distributor",    "material":"UHMWPE",            "unit":"Nos","qty":2,"wt_kg":12,  "life_hrs":"—",    "note":""},
        {"item":"Main Thrust Bearing Set",     "material":"—",                 "unit":"Set","qty":1,"wt_kg":8,   "life_hrs":"5000", "note":""},
    ],
    "PROCone-5010": [
        {"item":"Mantle (Inner Crushing Cone)","material":"Mn18Cr2 Cast Steel","unit":"Nos","qty":2,"wt_kg":1650,"life_hrs":"600",  "note":"Higher wear — hard rock"},
        {"item":"Bowl Liner (Concave Ring)",   "material":"Mn18Cr2 Cast Steel","unit":"Nos","qty":2,"wt_kg":1500,"life_hrs":"600",  "note":""},
        {"item":"Feed Plate / Distributor",    "material":"UHMWPE",            "unit":"Nos","qty":2,"wt_kg":18,  "life_hrs":"—",    "note":""},
        {"item":"Main Thrust Bearing Set",     "material":"—",                 "unit":"Set","qty":1,"wt_kg":12,  "life_hrs":"5000", "note":""},
    ],
    "2x PROCone-5010 (twin, 50-50 split)": [
        {"item":"Mantle (Inner Crushing Cone)","material":"Mn18Cr2 Cast Steel","unit":"Nos","qty":4,"wt_kg":1650,"life_hrs":"600",  "note":"2 units × 2 sets"},
        {"item":"Bowl Liner (Concave Ring)",   "material":"Mn18Cr2 Cast Steel","unit":"Nos","qty":4,"wt_kg":1500,"life_hrs":"600",  "note":""},
        {"item":"Feed Plate / Distributor",    "material":"UHMWPE",            "unit":"Nos","qty":4,"wt_kg":18,  "life_hrs":"—",    "note":""},
        {"item":"Main Thrust Bearing Set",     "material":"—",                 "unit":"Set","qty":2,"wt_kg":12,  "life_hrs":"5000", "note":""},
    ],
}

# ---------------------------------------------------------------------------
# WEAR PARTS — VSI Crusher
# ---------------------------------------------------------------------------
_VSI_WEAR: dict[str, list] = {
    "PROMAN REMco VSI-200": [
        {"item":"Rotor Tip Inserts (Tungsten Carbide)","material":"WC-Co Sintered Carbide","unit":"Set","qty":2,"wt_kg":6,  "life_hrs":"500-800","note":"Replace before fracture"},
        {"item":"Anvil Ring Segments",                 "material":"Chrome-Moly Alloy Cast","unit":"Set","qty":2,"wt_kg":18, "life_hrs":"1000",  "note":""},
        {"item":"Feed Tube / Entry Tube",              "material":"Mn Steel / AR400 Plate", "unit":"Nos","qty":2,"wt_kg":4,  "life_hrs":"1500",  "note":""},
        {"item":"Rotor Shoes / Distributor Plates",   "material":"Chrome-Moly Alloy Cast","unit":"Set","qty":2,"wt_kg":8,  "life_hrs":"800",   "note":""},
        {"item":"Rotor Body (Spare)",                  "material":"Fabricated Steel",        "unit":"Nos","qty":1,"wt_kg":45, "life_hrs":"—",     "note":"Spare rotor for rapid changeover"},
    ],
    "PROMAN REMco VSI-300": [
        {"item":"Rotor Tip Inserts (Tungsten Carbide)","material":"WC-Co Sintered Carbide","unit":"Set","qty":2,"wt_kg":10, "life_hrs":"500-800","note":""},
        {"item":"Anvil Ring Segments",                 "material":"Chrome-Moly Alloy Cast","unit":"Set","qty":2,"wt_kg":28, "life_hrs":"1000",  "note":""},
        {"item":"Feed Tube / Entry Tube",              "material":"Mn Steel / AR400 Plate", "unit":"Nos","qty":2,"wt_kg":6,  "life_hrs":"1500",  "note":""},
        {"item":"Rotor Shoes / Distributor Plates",   "material":"Chrome-Moly Alloy Cast","unit":"Set","qty":2,"wt_kg":12, "life_hrs":"800",   "note":""},
        {"item":"Rotor Body (Spare)",                  "material":"Fabricated Steel",        "unit":"Nos","qty":1,"wt_kg":65, "life_hrs":"—",     "note":""},
    ],
    "PROMAN REMco VSI-4060": [
        {"item":"Rotor Tip Inserts (Tungsten Carbide)","material":"WC-Co Sintered Carbide","unit":"Set","qty":2,"wt_kg":18, "life_hrs":"500-800","note":""},
        {"item":"Anvil Ring Segments",                 "material":"Chrome-Moly Alloy Cast","unit":"Set","qty":2,"wt_kg":55, "life_hrs":"1000",  "note":""},
        {"item":"Feed Tube / Entry Tube",              "material":"Mn Steel / AR400 Plate", "unit":"Nos","qty":2,"wt_kg":10, "life_hrs":"1500",  "note":""},
        {"item":"Rotor Shoes / Distributor Plates",   "material":"Chrome-Moly Alloy Cast","unit":"Set","qty":2,"wt_kg":22, "life_hrs":"800",   "note":""},
        {"item":"Rotor Body (Spare)",                  "material":"Fabricated Steel",        "unit":"Nos","qty":1,"wt_kg":120,"life_hrs":"—",     "note":""},
    ],
    "PROMAN REMco VSI-5080": [
        {"item":"Rotor Tip Inserts (Tungsten Carbide)","material":"WC-Co Sintered Carbide","unit":"Set","qty":2,"wt_kg":28, "life_hrs":"400-600","note":"Higher wear for hard rock"},
        {"item":"Anvil Ring Segments",                 "material":"Chrome-Moly Alloy Cast","unit":"Set","qty":2,"wt_kg":90, "life_hrs":"800",   "note":""},
        {"item":"Feed Tube / Entry Tube",              "material":"Mn Steel / AR400 Plate", "unit":"Nos","qty":2,"wt_kg":16, "life_hrs":"1200",  "note":""},
        {"item":"Rotor Shoes / Distributor Plates",   "material":"Chrome-Moly Alloy Cast","unit":"Set","qty":2,"wt_kg":35, "life_hrs":"700",   "note":""},
        {"item":"Rotor Body (Spare)",                  "material":"Fabricated Steel",        "unit":"Nos","qty":1,"wt_kg":180,"life_hrs":"—",     "note":""},
    ],
}

# Screen media area & deck data
_SCREEN_INFO: dict[str, dict] = {
    "Screen 1.2m x 4.0m 3-Deck":    {"w":1.2,"l":4.0,"decks":3},
    "Screen 2.0m x 5.0m 3-Deck":    {"w":2.0,"l":5.0,"decks":3},
    "Screen 2.0m x 5.0m 4-Deck":    {"w":2.0,"l":5.0,"decks":4},
    "Screen 2.0m x 6.0m 4-Deck":    {"w":2.0,"l":6.0,"decks":4},
    "Screen 2.0m x 7.0m 4-Deck":    {"w":2.0,"l":7.0,"decks":4},
    "Screen 2.4m x 8.1m 3-Deck":    {"w":2.4,"l":8.1,"decks":3},
    "2x Screen 2.4m x 8.1m 3-Deck": {"w":2.4,"l":8.1,"decks":3,"twin":2},
}

# ---------------------------------------------------------------------------
# STRUCTURAL STEEL — estimated tonnage table
# ---------------------------------------------------------------------------
_STRUCTURAL_MT: list[tuple] = [
    # (stages, tph_max,  total_mt)
    (1, 150,   10),
    (2, 175,   18),
    (2, 280,   28),
    (2, 400,   38),
    (3, 175,   32),
    (3, 280,   50),
    (3, 350,   68),
    (3, 650,  130),
    (4, 650,  180),
]

def _structural_mt(stages: int, tph: float) -> float:
    for stg, t, mt in _STRUCTURAL_MT:
        if stg == stages and tph <= t:
            return float(mt)
    return float(_STRUCTURAL_MT[-1][2])

# ---------------------------------------------------------------------------
# BELT WIDTH TABLE
# ---------------------------------------------------------------------------
def _belt_width_mm(tph: float) -> int:
    for t, w in [(150,600),(250,800),(350,900),(500,1000),(650,1200)]:
        if tph <= t: return w
    return 1200

def _conveyor_length_table(stages: int, tph: float = 250) -> list[tuple[str, int]]:
    """
    Return list of (conveyor name, approx length m).
    Calibrated from PROMAN layout drawings:
      300 TPH 3-stage: BC-01(10) BC-02(29) BC-03(28) BC-04(19) BC-05(20)
                       BC-06(29) BC-07(28) BC-08(40) BC-09(34) BC-10(18)
                       BC-11(18) BC-12(18) BC-13(18) BC-14(18) BC-15(18) BC-16(15)
      600 TPH 3-stage: BC-01(10) BC-02(36) BC-03(28) BC-04(28) BC-05(8)
                       BC-06(36) BC-07(38) BC-08(36) BC-09(28) BC-10(38)
                       BC-11(35) BC-12(18) BC-13(18) BC-14(18) BC-15(18) BC-16(15)
    """
    if stages <= 2:
        # 2-stage: ~12 belts estimated
        return [
            ("BC-01 — ROM Hopper to VGF",                   10),
            ("BC-02 — Jaw Product (main belt)",              28),
            ("BC-03 — Jaw to Cone Feed Bin",                 20),
            ("BC-04 — Cone Feed to Cone",                     8),
            ("BC-05 — Cone Product to Screen",               28),
            ("BC-06 — Screen Oversize Recycle to Cone",      18),
            ("BC-07 — Product #1 Stockpile (40mm)",          35),
            ("BC-08 — Product #2 Stockpile (20mm)",          30),
            ("BC-09 — Product #3 Stockpile (10mm)",          25),
            ("BC-10 — Product #4 Stockpile (Dust)",          22),
            ("BC-11 — Secondary Product Belt",               18),
            ("BC-12 — GSB/Fines Product",                    15),
        ]
    else:
        # 3-stage: 16 belts (confirmed by 300 TPH & 600 TPH layouts)
        # Use larger lengths for higher TPH plants
        sf = 1.25 if tph > 400 else 1.0   # scale factor for 600 TPH
        return [
            ("BC-01 — ROM Hopper to VGF",                   10),
            ("BC-02 — VGF / Jaw Product Main Belt",          int(29 * sf)),
            ("BC-03 — Jaw Product to Cone Feed",             int(28 * sf)),
            ("BC-04 — Cone Surge to Cone Feeders",           19),
            ("BC-05 — Cone Feed Belt",                        int(8 if tph > 400 else 20)),
            ("BC-06 — Cone Product to Int. Screen",          int(29 * sf)),
            ("BC-07 — Int. Screen Oversize Recycle",         int(28 * sf)),
            ("BC-08 — VSI / Int. Screen Product to Final",   int(40 * sf)),
            ("BC-09 — Final Screen Product #1 (coarse)",     int(34 * sf)),
            ("BC-10 — Product Stockpile #1",                 18),
            ("BC-11 — Product Stockpile #2",                 18),
            ("BC-12 — Product Stockpile #3",                 18),
            ("BC-13 — Product Stockpile #4",                 18),
            ("BC-14 — Secondary Product Belt",               18),
            ("BC-15 — M-Sand / BC Product Belt",             18),
            ("BC-16 — GSB / Quarry Fines (500mm belt)",      15),
        ]

def _conveyor_components(name: str, length_m: int, width_mm: int) -> list[dict]:
    spacing_c, spacing_r = 1.2, 2.5
    n_c = max(1, math.ceil(length_m / spacing_c))
    n_r = max(1, math.ceil(length_m / spacing_r))
    belt_m = round(length_m * 2 * 1.12, 0)   # x2 (top+return) + 12% splice waste
    pulley_dia = 500 if width_mm <= 800 else 630
    return [
        {"item": f"Rubber Belt — {width_mm}mm EP315/3 ply",       "unit":"m",   "qty": belt_m, "note": name},
        {"item": f"Carrying Idler Set — {width_mm}mm 3-Roll",      "unit":"Set", "qty": n_c,    "note": f"@{spacing_c}m spacing"},
        {"item": f"Return Idler — {width_mm}mm Flat Disc",         "unit":"Nos", "qty": n_r,    "note": f"@{spacing_r}m spacing"},
        {"item": f"Impact Idler Set — {width_mm}mm",               "unit":"Set", "qty": 2,      "note": "At loading point"},
        {"item": f"Head Pulley — {pulley_dia}mm dia, lagged",      "unit":"Nos", "qty": 1,      "note": "Rubber lagging"},
        {"item": f"Tail Pulley — {pulley_dia}mm dia",              "unit":"Nos", "qty": 1,      "note": ""},
        {"item": f"Snub/Bend Pulleys",                             "unit":"Nos", "qty": 1,      "note": "As required"},
        {"item": "Take-up Assembly (Gravity / Screw)",             "unit":"Set", "qty": 1,      "note": ""},
        {"item": "Belt Cleaner — Primary Polyurethane Scraper",    "unit":"Nos", "qty": 1,      "note": ""},
        {"item": "Skirt Boards with Rubber Sealing (Pair)",        "unit":"Set", "qty": 1,      "note": ""},
        {"item": "Loading Chute — MS with 6mm AR400 Liner",        "unit":"Nos", "qty": 1,      "note": ""},
        {"item": "Discharge Chute — MS with Liner",                "unit":"Nos", "qty": 1,      "note": ""},
        {"item": "Drive Motor + Gearbox Unit",                     "unit":"Set", "qty": 1,      "note": f"~{max(5,math.ceil(length_m*0.3))} kW est."},
    ]


# ---------------------------------------------------------------------------
# MASTER FUNCTION
# ---------------------------------------------------------------------------
def build_procurement_bom(schedule: dict, tph: float, stages: int) -> dict:
    """
    Build a structured, multi-category procurement BOM from an equipment schedule.
    Returns a dict with keys: manufactured, bought_out, wear_parts, structural,
    conveyor_components, consumables, summary_stats.
    """
    vgf_  = schedule.get("vgf")   or {}
    jaw_  = schedule.get("jaw")   or {}
    cone_ = schedule.get("cone")  or {}
    vsi_  = schedule.get("vsi")   or {}
    scr_  = schedule.get("screens") or {}
    scr_int = scr_.get("intermediate") or {}
    scr_fin = scr_.get("final")       or {}
    twin_cone = cone_.get("twin", False)
    belt_w = _belt_width_mm(tph)
    # Conveyor count calibrated from PFD layouts:
    # 3-stage plants always have 16 belts (300 TPH & 600 TPH confirmed)
    # 2-stage plants estimated at 12 belts
    conv_count = {1:6, 2:12, 3:16, 4:16}.get(stages, 12)
    # MVF feeder count scales with TPH and stages:
    # 150-250 TPH 3-stage → 2 MVF | 300 TPH → 4 MVF | 600 TPH → 6 MVF
    if stages >= 3:
        mvf_count = 6 if tph > 400 else (4 if tph > 250 else 2)
    elif stages == 2:
        mvf_count = 2
    else:
        mvf_count = 1

    # ----------------------------------------------------------------
    # 1. MANUFACTURED ITEMS
    # ----------------------------------------------------------------
    manufactured: list[dict] = []
    sl = 1
    def _add_mfg(category, description, model, qty, specs=""):
        nonlocal sl
        manufactured.append({"sl":sl,"category":category,"description":description,
                              "model":model or "—","qty":qty,"unit":"Nos","specs":specs})
        sl += 1

    _add_mfg("HOPPER",   "ROM Feed Hopper",            "40T Heavy Duty Hopper w/ Grating",  1, "10mm MS plate, dump height 5m")
    if vgf_:
        _add_mfg("VGF",  "Vibrating Grizzly Feeder",   vgf_.get("model",""), 1,
                 f"Feed cap: {vgf_.get('feed_capacity_mtph','—')} mt/h | Max feed: {vgf_.get('max_feed_mm','—')}mm")
    if jaw_:
        _add_mfg("JAW",  "Primary Jaw Crusher",         jaw_.get("model",""), 1,
                 f"CSS {jaw_.get('css_mm','—')}mm | {jaw_.get('tph_capacity','—')} TPH")
    if cone_:
        qty_c = 2 if twin_cone else 1
        _add_mfg("CONE", "Secondary Cone Crusher",      cone_.get("model",""), qty_c,
                 f"CSS {cone_.get('css_mm','—')}mm{'  ×2 units' if twin_cone else ''}")
    if stages >= 2:
        _add_mfg("BIN",  "Surge Bin (Primary Stage)",   "30T Conical Surge Bin", 1, "MS plate, cone bottom, MVF discharge")
    if stages >= 3:
        _add_mfg("BIN",  "Intermediate Surge Bin",      "15T Conical Surge Bin", 1, "Between cone and VSI")
        if vsi_:
            _add_mfg("VSI","Tertiary VSI Crusher",       vsi_.get("model",""), 1,
                     f"Max feed: {vsi_.get('max_feed_mm','—')}mm | {vsi_.get('motor_hp','—')} HP")
    if scr_int:
        n = 2 if scr_int.get("twin") else 1
        _add_mfg("SCREEN","Intermediate Vibrating Screen", scr_int.get("model",""), n,
                 f"{scr_int.get('decks',3)}-Deck")
    if scr_fin:
        n = 2 if scr_fin.get("twin") else 1
        _add_mfg("SCREEN","Final Vibrating Screen",     scr_fin.get("model",""), n,
                 f"{scr_fin.get('decks',4)}-Deck")
    _add_mfg("CONVEYOR","Belt Conveyor System",          f"Rubber Belt, {belt_w}mm wide (main)", conv_count,
             f"Various widths 500-{belt_w}mm — see Conveyor sheet")
    if stages >= 2:
        _add_mfg("FEEDER","Mechanical Vibro-Feeder MVF 100-160 (Surge Bin Discharge)",
                 "MVF 100-160 (1.0×1.6m)",
                 mvf_count,
                 f"{mvf_count} nos — below surge bin(s) feeding cone/VSI")

    # ----------------------------------------------------------------
    # 2. BOUGHT-OUT ITEMS — motors, drives, electrical
    # ----------------------------------------------------------------
    bought_out: list[dict] = []
    sl = 1
    total_kw = 0.0

    def _add_bo(category, description, model, qty, unit="Nos", specs=""):
        nonlocal sl
        bought_out.append({"sl":sl,"category":category,"description":description,
                           "model":model,"qty":qty,"unit":unit,"specs":specs})
        sl += 1

    def _add_motor(eq_model: str, equip_name: str):
        nonlocal total_kw
        m = MOTOR_SPECS.get(eq_model)
        if not m: return
        kw_total = m["kw"] * m["qty"]
        total_kw += kw_total
        _add_bo("MOTOR", f"Electric Motor — {m['kw']}kW / {m['hp']}HP",
                f"{m['type']}, 415V 3Ph 50Hz, IP55",
                m["qty"], specs=f"{equip_name} | {m['start']} starting | {kw_total}kW total")
        # V-belt drive for jaw
        if "Jaw" in equip_name:
            _add_bo("DRIVE","V-Belt Drive Set + Sheaves",
                    f"Classical V-Belt — {m['kw']}kW rating", 1,
                    specs=f"For {equip_name} — single drive")
        # Lube unit for cone
        if "Cone" in equip_name:
            _add_bo("LUBE", "Lubrication & Hydraulic Power Unit",
                    "Oil Lube Unit with heat exchanger + filter",
                    1 if not twin_cone else 2,
                    specs=f"For {equip_name} — auto-circulation, 200L tank")

    if vgf_:  _add_motor(vgf_.get("model",""),  "VGF")
    if jaw_:  _add_motor(jaw_.get("model",""),  "Jaw Crusher")
    if cone_: _add_motor(cone_.get("model",""), "Cone Crusher")
    if vsi_:  _add_motor(vsi_.get("model",""),  "VSI Crusher")
    if scr_int: _add_motor(scr_int.get("model",""), "Intermediate Screen")
    if scr_fin: _add_motor(scr_fin.get("model",""), "Final Screen")

    # Conveyor drive motors (per conveyor, estimated)
    cv_motor_kw = max(5, math.ceil(tph * 0.04))
    total_kw += cv_motor_kw * conv_count
    _add_bo("MOTOR", f"Conveyor Drive Motors — {cv_motor_kw}kW each (estimated)",
            "SCIM TEFC, 415V, foot-mtd + Helical Gearbox",
            conv_count, specs=f"One per belt | DOL/Soft-start | {cv_motor_kw*conv_count}kW total")
    # MVF feeder motors
    if stages >= 2:
        _add_bo("MOTOR", f"MVF Feeder Motors — 5.5kW each",
                "SCIM TEFC, 415V, with exciter mechanism",
                mvf_count, specs="One per MVF feeder unit | DOL")

    # MCC
    mcc_kva = math.ceil(total_kw * 1.25 / 0.85)
    _add_bo("ELECTRICAL","Motor Control Centre (MCC) Panel",
            f"CRCA sheet, IP54, 415V MCC with MPCB+Contactor/SS per feeder",
            1, specs=f"Est. {int(total_kw)}kW connected | {mcc_kva} kVA panel")
    _add_bo("ELECTRICAL","Power & Control Cable (LOT)",
            "XLPE/SWA/PVC Armoured Cables — HT + LT",
            1, unit="Lot", specs="Including cable trays, conduits, lugs")
    _add_bo("ELECTRICAL","Local Control Stations (Push Button Box)",
            "IP65 GI Box — E-Stop + Start/Stop",
            conv_count + 6, specs="One per conveyor + each crusher")
    _add_bo("ELECTRICAL","Belt Speed Switches",
            "Rotary speed switch (belt protection)",
            conv_count, specs="One per conveyor — underspeed trip")
    _add_bo("ELECTRICAL","Pull-Key Emergency Switches",
            "Stainless cable pull-key switch",
            conv_count * 2, specs="Both sides of each conveyor")
    _add_bo("ELECTRICAL","Earthing & Lightning Protection System",
            "GI Earth Plate + Conductors as per IS 3043",
            1, unit="Lot", specs="Min 4 earth pits")
    _add_bo("INSTRUMENT","Bearing Temperature Sensors (RTD PT100)",
            "PT100 RTD, 4-20mA output",
            4 if stages >= 3 else 2, specs="Crusher main bearings")
    if stages >= 2:
        _add_bo("LUBE","Hydraulic Oil — ISO VG 68 (Initial Fill)",
                "OEM approved grade",
                200 * (2 if twin_cone else 1), unit="Litres",
                specs="Cone HPU initial fill")

    # ----------------------------------------------------------------
    # 3. WEAR PARTS (initial supply — 2 sets each)
    # ----------------------------------------------------------------
    wear_parts: list[dict] = []
    sl = 1
    def _add_wp(equipment, item, material, qty, unit, wt_kg, life_hrs, note, cat="WEAR_PARTS"):
        nonlocal sl
        wear_parts.append({"sl":sl,"equipment":equipment,"item":item,"material":material,
                           "qty":qty,"unit":unit,"wt_kg":wt_kg,"life_hrs":life_hrs,
                           "note":note,"category":cat})
        sl += 1

    # Jaw wear
    jaw_key = next((k for k in _JAW_WEAR if jaw_.get("model","").startswith(k) or k in jaw_.get("model","")), None)
    if jaw_key:
        for w in _JAW_WEAR[jaw_key]:
            _add_wp("Jaw Crusher",w["item"],w["material"],w["qty"],w["unit"],w["wt_kg"],w["life_hrs"],w["note"])

    # Cone wear
    cone_key = next((k for k in _CONE_WEAR if k in cone_.get("model","")), None)
    if cone_key:
        mfact = 2 if twin_cone else 1
        for w in _CONE_WEAR[cone_key]:
            _add_wp("Cone Crusher",w["item"],w["material"],w["qty"]*mfact,w["unit"],
                    w["wt_kg"],w["life_hrs"],w["note"])

    # VSI wear
    vsi_key = next((k for k in _VSI_WEAR if k in vsi_.get("model","")), None)
    if vsi_key:
        for w in _VSI_WEAR[vsi_key]:
            _add_wp("VSI Crusher",w["item"],w["material"],w["qty"],w["unit"],w["wt_kg"],w["life_hrs"],w["note"])

    # Screen media
    cuts = (schedule.get("gradation") or {}).get("cuts_mm", [40,20,10,4.75])
    for screen_obj, label in [(scr_int,"Intermediate Screen"),(scr_fin,"Final Screen")]:
        if not screen_obj: continue
        m = screen_obj.get("model","")
        info = _SCREEN_INFO.get(m) or {"w":2.0,"l":6.0,"decks":4,"twin":1}
        mult = info.get("twin",1)
        area = info["w"] * info["l"] * mult
        for i, cut in enumerate(cuts[:info["decks"]]):
            panels = math.ceil(area * 1.12)
            _add_wp(label, f"Screen Media — {cut}mm aperture",
                    f"Crimped Wire Mesh (GI) / PU Panels",
                    panels, "Sq.m", round(panels*3.5,1),
                    "500-800", f"Deck {i+1} | Replace per condition")

    # ----------------------------------------------------------------
    # 4. CONSUMABLES
    # ----------------------------------------------------------------
    consumables: list[dict] = []
    sl = 1
    def _add_cons(item, material, qty, unit, note):
        nonlocal sl
        consumables.append({"sl":sl,"item":item,"material":material,
                            "qty":qty,"unit":unit,"note":note,"category":"CONSUMABLE"})
        sl += 1

    _add_cons("Bearing Grease — Initial Fill + 3 Month Supply",
              "Lithium Complex EP2 (Shell Gadus / Mobil Mobilux)", 50, "Kg",
              "All crusher + screen bearings")
    if cone_:
        _add_cons("Gear/Lube Oil — Cone Crusher HPU",
                  "ISO VG 220 Mineral Gear Oil (OEM approved)",
                  200 * (2 if twin_cone else 1), "Litres",
                  "Initial fill; change at 2000 hrs")
    if vsi_:
        _add_cons("Belt Drive Grease (VSI)",
                  "Lithium Complex EP2", 10, "Kg", "V-belt sheave bearings")
    _add_cons("Conveyor Belt Dressing / Anti-Slip Compound",
              "Rubber-based belt dressing", 20, "Litres", "Initial application on all belts")
    _add_cons("Gasket Sheet (Assorted)",
              "Compressed Fibre / PTFE", 5, "Sq.m", "Maintenance spares")
    _add_cons("O-Ring & Seal Kit (Assorted)",
              "Nitrile / Viton per OEM spec", 1, "Lot", "First year maintenance")
    _add_cons("Hydraulic Oil — Cone HPU",
              "ISO VG 68 Anti-Wear HLP (OEM approved)",
              50 * (2 if twin_cone else 1), "Litres", "Top-up / reserve supply")
    _add_cons("Air Filter Elements (Assorted)", "OEM specified", conv_count + 4, "Nos",
              "Annual replacement — all motors")
    _add_cons("Safety Signage & Guards (LOT)", "Steel + Safety Yellow Paint", 1, "Lot",
              "IS 2379 compliant safety marking")

    # ----------------------------------------------------------------
    # 5. STRUCTURAL STEEL
    # ----------------------------------------------------------------
    structural: list[dict] = []
    sl = 1
    total_mt = _structural_mt(stages, tph)

    def _add_str(section, item, profile, qty_mt, unit="MT", note=""):
        nonlocal sl
        structural.append({"sl":sl,"section":section,"item":item,"profile":profile,
                           "qty_mt":round(qty_mt,1),"unit":unit,"note":note,"category":"STRUCTURAL"})
        sl += 1

    def _stage_steel(section, frac):
        t = total_mt * frac
        _add_str(section, "Columns & Main Beams", "ISMB 200/250/300 as reqd", t * 0.38, note="IS 2062 E250")
        _add_str(section, "Secondary Beams & Purlins", "ISMB 150/ISMC 150",     t * 0.22, note="")
        _add_str(section, "Bracing (Horizontal + Diagonal)", "ISA 75×75×6 / 100×100×8", t * 0.18, note="")
        _add_str(section, "Gussets & Base Plates", "MS Plate 10-16mm",            t * 0.10, note="")
        _add_str(section, "Chequered Plate Flooring", "6mm MS Chqrd Plate IS 3502", t * 0.12, note="")

    _stage_steel("Primary Crushing Stage", 0.30)
    if stages >= 2: _stage_steel("Secondary Crushing Stage", 0.28)
    if stages >= 3: _stage_steel("Tertiary VSI Stage", 0.22)
    _stage_steel("Access Platforms, Walkways & Staircases", 0.14)

    _add_str("Hardware", "Foundation Anchor Bolts (HT)",
             "IS 1367 Grade 8.8 M24/M30", total_mt * 8, unit="Nos", note="All equipment foundations")
    _add_str("Hardware", "Structural Fasteners (Bolts, Nuts, Washers)",
             "IS 1367 Grade 8.8 (Hot-dip Galvanised)", total_mt * 35, unit="Nos", note="")
    _add_str("Finish", "Surface Prep (SSPC-SP6 / Hand tool clean)",
             "Wire brush + Power tool", total_mt * 12, unit="Sq.m", note="")
    _add_str("Finish", "Epoxy Primer Coat",
             "2K Epoxy Primer, DFT 50μm", total_mt * 12, unit="Sq.m", note="")
    _add_str("Finish", "PU Finish Coat (Safety Yellow + Grey)",
             "PU Top Coat, DFT 75μm", total_mt * 12, unit="Sq.m", note="IS 5 Shade 309 Yellow")

    # ----------------------------------------------------------------
    # 6. CONVEYOR COMPONENTS
    # ----------------------------------------------------------------
    conveyor_components: list[dict] = []
    sl = 1
    for name, length in _conveyor_length_table(stages, tph):
        for comp in _conveyor_components(name, length, belt_w):
            conveyor_components.append({
                "sl": sl, "conveyor": name, "item": comp["item"],
                "qty": comp["qty"], "unit": comp["unit"],
                "note": comp["note"], "category": "CONVEYOR"
            })
            sl += 1

    return {
        "manufactured":        manufactured,
        "bought_out":          bought_out,
        "wear_parts":          wear_parts,
        "consumables":         consumables,
        "structural":          structural,
        "conveyor_components": conveyor_components,
        "summary_stats": {
            "total_structural_mt":  total_mt,
            "belt_width_mm":        belt_w,
            "conveyor_count":       conv_count,
            "est_connected_kw":     round(total_kw, 0),
        },
    }
