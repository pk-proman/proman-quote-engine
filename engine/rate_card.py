"""
PROMAN Rate Card — Master Equipment Price Database
Source: Final Aggregate Price List 2022.pdf (confirmed current)
All prices in Rs. Lakhs (List / Best).
Last updated: 2026-08-31
"""

# ---------------------------------------------------------------------------
# VIBRATING GRIZZLY FEEDERS (VGF)
# ---------------------------------------------------------------------------
VGF = {
    "1000x4000": {"hp": 20,  "list": 15.00, "best": 12.00},
    "1200x5000": {"hp": 30,  "list": 21.00, "best": 17.00},
    "1300x5600": {"hp": 50,  "list": 26.00, "best": 22.00},
    "1600x6000": {"hp": 60,  "list":  9.80, "best":  9.80,
                  "flag": "⚠️ Price 9.8L supplied by sales — confirm List vs Best split"},
}

# ---------------------------------------------------------------------------
# PRIMARY JAW CRUSHERS
# ---------------------------------------------------------------------------
JAW = {
    "36x24": {"hp": 100, "list": 42.00, "best": 36.00,
              "starter_elec": {"list": 2.00, "best": 1.50},
              "feed_mm": 600, "css_range": (75, 175), "tph_range": (80, 120)},
    "36x30": {"hp": 120, "list": None, "best": None,
              "starter_elec": {"list": 2.50, "best": 1.75},
              "feed_mm": 600, "css_range": (75, 175), "tph_range": (100, 150),
              "flag": "⚠️ Lippman model — no equipment price in rate card; engineering quote required"},
    "42x30": {"hp": 150, "list": 69.00, "best": 55.00,
              "starter_elec": {"list": 2.50, "best": 1.75},
              "feed_mm": 650, "css_range": (100, 250), "tph_range": (180, 260)},
    "50x40": {"hp": 200, "list": 3.20, "best": 3.20,
              "starter_elec": {"list": 3.20, "best": 3.20},
              "feed_mm": 900, "css_range": (125, 300), "tph_range": (400, 600),
              "flag": "⚠️ Price confirmed by sales as 3.2L — unusually low vs. 42x30 at 69L; verify this is complete equipment price and not liner/plates only"},
}

# ---------------------------------------------------------------------------
# SECONDARY CONE CRUSHERS
# Prices include sub-base frame for 5010 only; others need external frame in Sub C.
# Starter prices: electric (elec) and soft starter (soft).
# ---------------------------------------------------------------------------
CONE = {
    "3506": {"hp": 120, "aux_hp": 5, "list": 51.00, "best": 45.00,
             "starter_elec": {"list": 2.00, "best": 1.50},
             "starter_soft": {"list": 3.00, "best": 2.47},
             "feed_mm": 180, "css_range": (19, 38), "tph_range": (60, 100)},
    "3508": {"hp": 120, "aux_hp": 5, "list": 59.00, "best": 48.00,
             "starter_elec": {"list": 2.00, "best": 1.50},
             "starter_soft": {"list": 3.00, "best": 2.47},
             "feed_mm": 180, "css_range": (24, 40), "tph_range": (100, 150)},
    "3510": {"hp": 120, "aux_hp": 5, "list": 59.00, "best": 48.00,
             "starter_elec": {"list": 2.00, "best": 1.50},
             "starter_soft": {"list": 3.00, "best": 2.47},
             "feed_mm": 180, "css_range": (26, 45), "tph_range": (120, 180)},
    "4510": {"hp": 220, "aux_hp": 10, "list": 76.00, "best": 64.00,
             "starter_elec": {"list": 2.75, "best": 2.00},
             "starter_soft": {"list": 4.43, "best": 3.65},
             "feed_mm": 220, "css_range": (26, 45), "tph_range": (200, 260)},
    "5010": {"hp": 300, "aux_hp": 10, "list": 99.00, "best": 81.00,
             "includes_base_frame": True,
             "starter_elec": {"list": 4.00, "best": 3.25},
             "starter_soft": {"list": 6.15, "best": 5.07},
             "feed_mm": 250, "css_range": (32, 51), "tph_range": (380, 500)},
}

# ---------------------------------------------------------------------------
# TERTIARY CRUSHERS — REMCO VSI
# ---------------------------------------------------------------------------
VSI = {
    "100":  {"hp": 100, "lube": "grease", "list": 23.00, "best": 20.00,
             "starter_elec": {"list": 2.00, "best": 1.50},
             "starter_soft": {"list": 3.00, "best": 2.50},
             "starter_vfd":  {"list": 5.50, "best": 4.25},
             "tph_range": (40, 80)},
    "200":  {"hp": 200, "lube": "grease", "list": 29.00, "best": 25.00,
             "starter_elec": {"list": 4.00, "best": 3.25},
             "starter_soft": {"list": 8.50, "best": 7.50},
             "tph_range": (80, 150)},
    "300":  {"hp": 300, "lube": "grease", "list": 46.00, "best": 41.00,
             "starter_elec": {"list": 6.50, "best": 5.25},
             "starter_soft": {"list": 11.50, "best": 9.75},
             "tph_range": (150, 250)},
    "1530": {"hp": 300, "lube": "oil",    "list": 55.00, "best": 48.00,
             "starter_elec": {"list": 6.50, "best": 5.25},
             "starter_soft": {"list": 11.50, "best": 9.75},
             "tph_range": (150, 250)},
    "4060_2x200": {"hp": 400, "lube": "oil", "dual_drive": True,
                   "list": 65.00, "best": 59.00,
                   "starter_elec": {"list": 10.00, "best": 8.25},
                   "starter_soft": {"list": 17.00, "best": 14.50},
                   "tph_range": (250, 380)},
    "4060_2x250": {"hp": 500, "lube": "oil", "dual_drive": True,
                   "list": 65.00, "best": 59.00,
                   "starter_soft": {"list": 22.00, "best": 18.50},
                   "tph_range": (300, 420)},
    "5080_2x300": {"hp": 600, "lube": "oil", "dual_drive": True,
                   "list": 87.00, "best": 87.00,
                   "starter_soft": {"list": 32.00, "best": 27.00},
                   "tph_range": (400, 600),
                   "flag": "⚠️ 87L confirmed as selling price (single tier) — no separate List/Best; confirm"},
    "5080_2x400": {"hp": 800, "lube": "oil", "dual_drive": True,
                   "list": None, "best": None,
                   "starter_elec": {"list": 23.00, "best": 19.00},
                   "tph_range": (500, 750),
                   "flag": "⚠️ Equipment price not in rate card — engineering/sales quote required"},
}

# ---------------------------------------------------------------------------
# VIBRATING SCREENS (Screen + Motor combined price)
# ---------------------------------------------------------------------------
SCREEN = {
    "1200x4000_2d": {"hp": 20,   "decks": 2, "list": 11.00, "best":  8.30, "tph_cap": 120},
    "1200x4000_3d": {"hp": 22,   "decks": 3, "list": 12.00, "best":  9.45, "tph_cap": 120},
    "1200x4000_4d": {"hp": 25,   "decks": 4, "list": 14.00, "best": 11.70, "tph_cap": 120},
    "1800x5000_2d": {"hp": 25,   "decks": 2, "list": 16.00, "best": 13.20, "tph_cap": 180},
    "1800x5000_3d": {"hp": 25,   "decks": 3, "list": 20.00, "best": 15.45, "tph_cap": 180},
    "2000x5000_2d": {"hp": 25,   "decks": 2, "list": 19.00, "best": 14.70, "tph_cap": 220},
    "2000x5000_3d": {"hp": 30,   "decks": 3, "list": 21.00, "best": 16.30, "tph_cap": 220},
    "2000x5000_4d": {"hp": 30,   "decks": 4, "list": 24.00, "best": 19.55, "tph_cap": 220},
    "2000x6000_2d": {"hp": 30,   "decks": 2, "list": 21.00, "best": 16.30, "tph_cap": 250},
    "2000x6000_3d": {"hp": 30,   "decks": 3, "list": 24.00, "best": 19.55, "tph_cap": 250},
    "2000x6000_4d": {"hp": 40,   "decks": 4, "list": 29.00, "best": 23.85, "tph_cap": 250},
    "2000x7000_4d": {"hp": 40,   "decks": 4, "list": 33.00, "best": 27.10, "tph_cap": 300},
    "2100x7300_2d": {"hp": 40,   "decks": 2, "list": 27.00, "best": 20.60, "tph_cap": 350},
    "2100x7300_3d": {"hp": 50,   "decks": 3, "list": 31.00, "best": 25.75, "tph_cap": 350},
    "2400x8100_2d": {"hp": 50,   "decks": 2, "list": 34.00, "best": 26.45, "tph_cap": 500},
    "2400x8100_3d": {"hp": 60,   "decks": 3, "list": 41.00, "best": 31.60, "tph_cap": 500},
}

# ---------------------------------------------------------------------------
# MECHANICAL VIBRO FEEDERS (MVF)
# ---------------------------------------------------------------------------
MVF = {
    "50-90":   {"list": 1.50, "best": 1.20, "tph_range": (50,  90)},
    "70-120":  {"list": 2.50, "best": 1.75, "tph_range": (70, 120)},
    "100-160": {"list": 3.60, "best": 2.90, "tph_range": (100, 160)},
    "120-180": {"list": 4.90, "best": 3.50, "tph_range": (120, 180)},
    "80-300":  {"list": 4.75, "best": 3.50, "tph_range": (80,  300)},
    "100-300": {"list": 6.50, "best": 5.00, "tph_range": (100, 300)},
}

# ---------------------------------------------------------------------------
# WASH SAND GENERATORS (WSG / ORTNER)
# Prices: bare unit / with hopper+conveyors / with hopper+conveyors+thickener
# ---------------------------------------------------------------------------
WSG = {
    "40": {
        "bare":             {"list": 39.00,  "best": 30.00},
        "with_hopper_conv": {"list": 89.00,  "best": 68.00},
        "with_thickener":   {"list": 163.00, "best": 125.00},
    },
    "70": {
        "bare":             {"list": 46.00,  "best": 35.00},
        "with_hopper_conv": {"list": 96.00,  "best": 74.00},
        "with_thickener":   {"list": 170.00, "best": 131.00},
    },
    "120": {
        "bare":             {"list":  54.00, "best":  42.00},
        "with_hopper_conv": {"list": 109.00, "best":  84.00},
        "with_thickener":   {"list": 192.00, "best": 148.00},
    },
}

# ---------------------------------------------------------------------------
# METAL DETECTOR
# ---------------------------------------------------------------------------
METAL_DETECTOR = {"list": 3.50, "best": 3.25}

# ---------------------------------------------------------------------------
# BELT CONVEYOR RATES (Rs. per metre, inclusive of motor)
# Source: reverse-engineered from all 4 costing files.
# ---------------------------------------------------------------------------
CONVEYOR_RATE_PER_M = {
    500:  34_500,   # Rs/m
    650:  38_000,
    800:  40_000,
    1000: 46_000,
    1200: 55_000,
}

# Width selection guide by TPH:
#   ≤120 TPH main line → 800mm  |  product/short → 500mm
#   ≤250 TPH main line → 800mm  |  product/short → 500–650mm
#   ≤400 TPH main line → 1000mm |  product/short → 650mm
#   >400 TPH main line → 1200mm |  product/short → 800mm

# ---------------------------------------------------------------------------
# STRUCTURAL STEEL RATES (Rs./ton) — 2025-26 rates
# ---------------------------------------------------------------------------
STRUCTURAL_STEEL_RATE  = 115_000   # Rs/ton for structural fabrication
SHEET_METAL_RATE       = 120_000   # Rs/ton for chutes / hoppers

# Typical tonnage per component (structural tons, sheet metal tons):
STRUCTURAL_TONNAGE = {
    "rom_hopper_30t_with_vgf_jaw_platform": (35, 10),   # (struct_T, sheetmetal_T)
    "rom_hopper_50t_with_vgf_jaw_platform": (60, 16),
    "tunnel_for_cone_feed":                 ( 3,  1),
    "surge_hopper_30t_for_cone":            (10,  4),
    "surge_hopper_30t_for_vsi":             ( 9,  4),
    "cone_frame_walkway_stairs":            (16,  5),
    "screen_frame_zframe_walkway_stairs":   (17,  6),   # per screen
    "vsi_chutes_guards_misc":               ( 3,  1),
    "transfer_tower_product_chutes":        ( 4,  2),
}

# ---------------------------------------------------------------------------
# ELECTRICAL PANEL COSTS (Rs. Lakhs) — MCC + Cables
# Driven by largest drive in the plant.
# ---------------------------------------------------------------------------
ELECTRICAL = {
    # (mcc_panel, cable_tray_cables) in Rs. Lakhs
    "2stage_cone_soft":   (14, 10),   # 2-stage, soft starter for cone
    "2stage_cone_elec":   (13,  7),   # 2-stage, electric starter for cone (porta)
    "3stage_vsi300_soft": (29, 20),   # 3-stage, soft starter for VSI-300
    "3stage_vsi4060_soft":(38, 26),   # 3-stage, soft starter for VSI-4060 (interpolated)
    "3stage_vsi5080_soft":(52, 36),   # 3-stage, soft starter for VSI-5080
}

# ---------------------------------------------------------------------------
# ERECTION & COMMISSIONING (Rs. Lakhs) — flat rates
# ---------------------------------------------------------------------------
ERECTION = {
    "2stage_stationary": 8,
    "2stage_porta":      6,
    "3stage":           12,
}

# ---------------------------------------------------------------------------
# CONVEYOR GEOMETRY CONSTANTS
# ---------------------------------------------------------------------------
CONVEYOR_INCLINATION_DEG = 18          # degrees (standard PROMAN design)
import math
CONVEYOR_SIN = math.sin(math.radians(CONVEYOR_INCLINATION_DEG))  # ≈ 0.309
CONVEYOR_TAN = math.tan(math.radians(CONVEYOR_INCLINATION_DEG))  # ≈ 0.3249

# Platform / discharge heights (metres):
JAW_DISCHARGE_HEIGHT_DEFAULT = 1.83    # 6 ft — typical; can be overridden
HOPPER_DEPTH                 = 2.50    # depth of surge hopper below cone feed
CONE_PLATFORM_HEIGHT_DEFAULT = 6.00   # cone sits ~6m above ground in 2-stage
VSI_PLATFORM_HEIGHT_DEFAULT  = 8.00   # VSI sits higher (post-cone)

def conveyor_length_from_rise(rise_m, horizontal_offset_m=0):
    """
    Calculate conveyor length from required rise and horizontal feed offset.
    rise_m           : vertical height to climb (metres)
    horizontal_offset: horizontal distance from discharge to crusher feed (metres)
    Returns: conveyor length in metres (rounded up to nearest metre)
    """
    slant_from_rise = rise_m / CONVEYOR_SIN
    # Add horizontal offset as additional horizontal run at same angle:
    extra_slant = horizontal_offset_m / math.cos(math.radians(CONVEYOR_INCLINATION_DEG))
    total = slant_from_rise + extra_slant
    return math.ceil(total)


# ---------------------------------------------------------------------------
# HELPER: get equipment price by tier
# ---------------------------------------------------------------------------
def price(equipment_dict, tier="best"):
    """Return List or Best price; returns None if not priced (no_price)."""
    return equipment_dict.get(tier)


def get_vgf(model_key):
    return VGF.get(model_key)

def get_jaw(model_key):
    return JAW.get(model_key)

def get_cone(model_key):
    return CONE.get(model_key)

def get_vsi(model_key):
    return VSI.get(model_key)

def get_screen(model_key):
    return SCREEN.get(model_key)

def get_mvf(model_key):
    return MVF.get(model_key)

def get_wsg(size, config="bare"):
    w = WSG.get(str(size))
    if w:
        return w.get(config)
    return None


if __name__ == "__main__":
    # Quick smoke-test
    print("VSI-300:", get_vsi("300"))
    print("Cone 4510:", get_cone("4510"))
    print("Conveyor length for 4m rise:", conveyor_length_from_rise(4.0, 2.0), "m")
    print("VGF 1600x6000:", get_vgf("1600x6000"))
    # Report any flagged items
    print("\n--- FLAGGED ITEMS ---")
    for cat, items in [("VGF", VGF), ("JAW", JAW), ("VSI", VSI)]:
        for k, v in items.items():
            if "flag" in v:
                print(f"  {cat} {k}: {v['flag']}")
