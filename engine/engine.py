"""
PROMAN Quotation Engine
Builds Sub-Total A, B, C, D, E from a PlantSpec.
All monetary values in Rs. Lakhs.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import math
import rate_card as rc


# ---------------------------------------------------------------------------
# DATA STRUCTURES
# ---------------------------------------------------------------------------

@dataclass
class ConveyorSpec:
    tag: str          # e.g. "BC-01"
    width_mm: int     # 500 / 650 / 800 / 1000 / 1200
    length_m: float
    hp: float
    purpose: str      # e.g. "jaw_to_surge", "product_gsb"

    @property
    def cost_lakhs(self):
        rate = rc.CONVEYOR_RATE_PER_M.get(self.width_mm, 40_000)
        return round(self.length_m * rate / 1_00_000, 3)


@dataclass
class PlantSpec:
    client_name:    str
    tph:            int                       # target throughput TPH
    stages:         int                       # 2 or 3
    feed_size_mm:   int    = 650              # max feed boulder size
    material:       str    = "Granite/Basalt"
    products:       List[str] = field(default_factory=list)
    mobile:         bool   = False            # porta/skid?
    wsg_size:       Optional[str] = None      # "40" / "70" / "120" or None
    wsg_config:     str    = "bare"           # "bare" / "with_hopper_conv" / "with_thickener"
    jaw_discharge_h: float = rc.JAW_DISCHARGE_HEIGHT_DEFAULT
    # Optional overrides — leave None to let engine auto-select
    jaw_model:      Optional[str] = None
    cone_model:     Optional[str] = None
    vsi_model:      Optional[str] = None
    vgf_model:      Optional[str] = None
    ref_no:         str    = "PR/XX-26/N-XXX"
    date:           str    = ""

    # ── Site geometry ─────────────────────────────────────────────────────────
    # Overall plant footprint.  If left None the engine uses TPH-scaled defaults.
    # Source: layout drawings from PFD & LAYOUT folder.
    site_length_m:      Optional[float] = None   # plant area length (along flow direction)
    site_width_m:       Optional[float] = None   # plant area width (perpendicular)

    # Platform / equipment elevations above finished floor level (m).
    # Each elevation is the top-of-structure (operating floor) height.
    # Conveyors and structural steel are derived from these values.
    # Defaults are typical PROMAN stationary plant values; override per project.
    elevation_vgf:          float = 0.0    # VGF + jaw — ground level (ROM area)
    elevation_surge1:       float = 0.0    # surge bin 1 / jaw discharge area
    elevation_cone:         float = 5.5    # secondary cone platform
    elevation_prescreen:    float = 5.0    # intermediate screen (3-stage; above jaw discharge)
    elevation_surge2:       float = 3.0    # surge bin 2 / VSI feed bin (3-stage)
    elevation_vsi:          float = 7.5    # VSI platform (3-stage; above cone)
    elevation_screen:       float = 4.5    # final screen platform
    elevation_stockpile:    float = 0.0    # product stockpile area (ground)

    # Horizontal distances between major equipment centroids along the flow axis (m).
    # Used to determine horizontal belt run lengths.
    # None → engine auto-distributes across site_length_m.
    spacing_hopper_to_jaw:  Optional[float] = None
    spacing_jaw_to_cone:    Optional[float] = None
    spacing_cone_to_screen: Optional[float] = None
    spacing_cone_to_vsi:    Optional[float] = None    # 3-stage only
    spacing_vsi_to_screen:  Optional[float] = None    # 3-stage only
    spacing_screen_to_stock: Optional[float] = None

    def _site_len(self) -> float:
        """Effective site length — explicit or TPH-scaled default."""
        if self.site_length_m:
            return self.site_length_m
        # Empirical: from 4 confirmed PROMAN layout drawings
        # 150 TPH ≈ 90m | 250 TPH ≈ 105m | 300 TPH ≈ 120m | 600 TPH ≈ 145m
        return 75 + self.tph * 0.115

    def _site_wid(self) -> float:
        """Effective site width."""
        if self.site_width_m:
            return self.site_width_m
        # Width scales more slowly — crushers are in-line
        return 30 + self.tph * 0.065

    def _spacing(self, key: str, default: float) -> float:
        """Return explicit horizontal spacing or the given default."""
        val = getattr(self, key, None)
        return val if val is not None else default


@dataclass
class LineItem:
    sl: str
    description: str
    qty: int
    hp: float
    list_price: Optional[float]
    best_price: Optional[float]
    motor_cost: Optional[float] = None   # internal — starter cost
    flags: List[str] = field(default_factory=list)


@dataclass
class Quotation:
    spec: PlantSpec
    sub_a_items: List[LineItem] = field(default_factory=list)
    sub_b_conveyors: List[ConveyorSpec] = field(default_factory=list)
    sub_b_chutes_list: float = 0.0
    sub_b_chutes_best: float = 0.0
    sub_c_structural_list: float = 0.0
    sub_c_structural_best: float = 0.0
    sub_d_list: float = 0.0
    sub_d_best: float = 0.0
    erection: float = 0.0
    warnings: List[str] = field(default_factory=list)

    # Sub-total helpers
    def sub_a_list(self):
        return round(sum(i.list_price or 0 for i in self.sub_a_items), 2)

    def sub_a_best(self):
        return round(sum(i.best_price or 0 for i in self.sub_a_items), 2)

    def sub_a_hp(self):
        return round(sum(i.hp for i in self.sub_a_items), 1)

    def sub_b_equipment_list(self):
        return round(sum(c.cost_lakhs for c in self.sub_b_conveyors), 2)

    def sub_b_equipment_best(self):
        return self.sub_b_equipment_list()  # conveyors have no list/best split

    def sub_b_total_list(self):
        return round(self.sub_b_equipment_list() + self.sub_b_chutes_list, 2)

    def sub_b_total_best(self):
        return round(self.sub_b_equipment_best() + self.sub_b_chutes_best, 2)

    def sub_b_hp(self):
        return round(sum(c.hp for c in self.sub_b_conveyors), 1)

    def total_list(self):
        return round(self.sub_a_list() + self.sub_b_total_list()
                     + self.sub_c_structural_list + self.sub_d_list, 2)

    def total_best(self):
        return round(self.sub_a_best() + self.sub_b_total_best()
                     + self.sub_c_structural_best + self.sub_d_best, 2)

    def grand_total_list(self):
        return round(self.total_list() + self.erection, 2)

    def grand_total_best(self):
        return round(self.total_best() + self.erection, 2)

    def total_hp(self):
        return round(self.sub_a_hp() + self.sub_b_hp(), 1)


# ---------------------------------------------------------------------------
# EQUIPMENT SELECTION LOGIC
# ---------------------------------------------------------------------------

def _select_vgf(tph: int) -> str:
    if tph <= 150:  return "1000x4000"
    if tph <= 250:  return "1200x5000"
    if tph <= 400:  return "1300x5600"
    return "1600x6000"

def _select_jaw(tph: int, feed_mm: int) -> str:
    if tph <= 130:  return "36x24"
    if tph <= 260:  return "42x30"
    if tph <= 600:  return "50x40"
    return None   # outside range

def _select_cone(tph: int) -> str:
    if tph <= 100:  return "3506"
    if tph <= 150:  return "3508"
    if tph <= 180:  return "3510"
    if tph <= 260:  return "4510"
    if tph <= 500:  return "5010"
    return None

def _select_vsi(tph: int) -> str:
    if tph <= 80:   return "100"
    if tph <= 150:  return "200"
    if tph <= 250:  return "300"
    if tph <= 380:  return "4060_2x200"
    if tph <= 500:  return "4060_2x250"
    if tph <= 600:  return "5080_2x300"
    if tph <= 750:  return "5080_2x400"
    return None

def _select_screen_primary(tph: int, decks: int = 4) -> str:
    """Primary (final product) screen — choose size to handle full TPH."""
    d = f"_{decks}d"
    if tph <= 150:  return f"1800x5000{d}" if decks <= 3 else f"2000x5000{d}"
    if tph <= 250:  return f"2000x6000{d}"
    if tph <= 350:  return f"2100x7300{d}" if decks <= 3 else f"2000x7000{d}"
    return f"2400x8100{d}" if decks <= 3 else f"2400x8100_3d"

def _select_screen_pre(tph: int) -> str:
    """Pre-screen between jaw and cone (3-stage plants): 2-3 deck, smaller."""
    if tph <= 150:  return "1200x4000_3d"
    if tph <= 300:  return "1200x4000_3d"
    return "1800x5000_2d"

def _select_mvf(tph: int) -> str:
    if tph <= 120:  return "70-120"
    if tph <= 160:  return "100-160"
    if tph <= 180:  return "120-180"
    return "100-300"

def _conveyor_width(tph: int, role: str) -> int:
    """Select belt width by TPH and role (main / product / short)."""
    if role == "product":
        if tph <= 200:  return 500
        if tph <= 350:  return 650
        return 800
    else:  # main line
        if tph <= 250:  return 800
        if tph <= 400:  return 1000
        return 1200

def _conveyor_hp(width_mm: int, length_m: float) -> float:
    """Approximate drive motor HP for a belt conveyor."""
    if width_mm <= 500:
        return 7.5 if length_m <= 15 else 10
    if width_mm <= 650:
        return 10 if length_m <= 20 else 15
    if width_mm <= 800:
        if length_m <= 10:  return 10
        if length_m <= 20:  return 15
        if length_m <= 32:  return 25
        return 30
    if width_mm <= 1000:
        if length_m <= 15:  return 15
        if length_m <= 25:  return 20
        if length_m <= 35:  return 30
        return 40
    # 1200mm
    return 15 if length_m <= 12 else 40


# ---------------------------------------------------------------------------
# STRUCTURAL STEEL ESTIMATION — geometry-aware
# ---------------------------------------------------------------------------
# Platform component footprints (length × width, m²) for area-based grating calc
_PLATFORM_FOOTPRINTS = {
    "hopper_30t": (5.0, 4.0),       # ROM hopper + VGF + jaw platform
    "hopper_50t": (6.0, 5.0),
    "cone_3506_3508_3510": (4.0, 3.5),
    "cone_4510": (4.5, 4.0),
    "cone_5010": (5.0, 4.5),
    "prescreen": (4.5, 3.0),        # intermediate screen (3-stage)
    "vsi_200_300": (3.0, 3.0),
    "vsi_4060": (3.5, 3.5),
    "vsi_5080": (4.0, 4.0),
    "screen_2000": (7.0, 4.0),      # final 2m-wide screen
    "screen_2400": (9.5, 4.5),      # 2.4m × 8.1m screen
    "surge_bin": (3.0, 3.0),
}

# Column weight per metre height per column (kg): 203UC section
_COLUMN_KG_PER_M = 86   # 203×203 UC, typical PROMAN structure
# Grating/chequered plate: 40 kg/m²
_GRATING_KG_M2   = 40
# Bracing: 15% of column+platform weight (X-brace, tie beams)
_BRACING_FACTOR  = 0.15
# Staircase: 180 kg per metre height per flight
_STAIR_KG_PER_M  = 180
# Walkway rail: 25 kg/m perimeter
_RAIL_KG_PER_M   = 25
# Sheet-metal chutes / guards: 22 kg/m² estimated surface
_CHUTE_KG_M2     = 22


def _platform_struct_tons(footprint_m2: float, height_m: float, n_columns: int = 4) -> tuple:
    """
    Estimate structural (tons) and sheet (tons) for one elevated platform.

    footprint_m2: grating platform area
    height_m:     operating floor height above grade
    n_columns:    number of supporting columns (4 for most equipment, 6 for long screens)

    Returns (struct_tons, sheet_tons)
    """
    # Columns
    col_kg = n_columns * height_m * _COLUMN_KG_PER_M
    # Beams at top (both axes) — approximate as 30% of column weight
    beam_kg = col_kg * 0.30
    # Bracing
    brace_kg = (col_kg + beam_kg) * _BRACING_FACTOR
    # Mid-height tie beams for h > 4 m
    if height_m > 4.0:
        brace_kg += col_kg * 0.12
    # Platform grating
    grating_kg = footprint_m2 * _GRATING_KG_M2
    # Staircase (1 flight per platform, going up from grade)
    stair_kg = height_m * _STAIR_KG_PER_M
    # Handrail perimeter (3 sides — one side open to equipment)
    perim = 2 * math.sqrt(footprint_m2) * 0.75   # rough perimeter proxy
    rail_kg = perim * _RAIL_KG_PER_M

    struct_tons = (col_kg + beam_kg + brace_kg + stair_kg + rail_kg) / 1000
    sheet_tons  = (grating_kg) / 1000
    return struct_tons, sheet_tons


def _calc_structural(spec: PlantSpec) -> tuple:
    """
    Geometry-aware structural steel estimation.

    Uses platform elevations and equipment footprints from PlantSpec to compute
    structural tonnage bottom-up:
      — Column weight  = height × section weight × number of columns
      — Beam weight    = 30% of column weight (both-axis top frames)
      — Bracing        = 15% of column+beam (X-brace + tie beams)
      — Grating        = platform area × 40 kg/m²
      — Staircases     = 180 kg/m height
      — Chutes/guards  = estimated from screen + VSI count

    Returns (list_price, best_price) in Rs. Lakhs (structural is lump sum, no split).
    """
    s_total = 0.0   # structural steel tons
    p_total = 0.0   # sheet metal (grating + chutes) tons

    tph = spec.tph

    # ── ROM Hopper + VGF + Jaw platform ──────────────────────────────────────
    # This is at grade (elevation_vgf) but has a raised steel hopper shell
    hopper_fp = _PLATFORM_FOOTPRINTS["hopper_50t" if tph > 350 else "hopper_30t"]
    hopper_area = hopper_fp[0] * hopper_fp[1]
    # Hopper walls: sheet metal (4 sides × avg height 3m × avg width 4m)
    hopper_shell_t = (4 * 3.0 * 4.0 * _CHUTE_KG_M2) / 1000
    p_total += hopper_shell_t
    # Platform at jaw discharge height
    jdh = max(2.0, spec.elevation_surge1 or spec.jaw_discharge_h)
    s, p = _platform_struct_tons(hopper_area, jdh, n_columns=6)
    s_total += s; p_total += p

    # ── Surge Bin 1 (between jaw and cone) ───────────────────────────────────
    sb_area = _PLATFORM_FOOTPRINTS["surge_bin"][0] * _PLATFORM_FOOTPRINTS["surge_bin"][1]
    s, p = _platform_struct_tons(sb_area, spec.elevation_cone, n_columns=4)
    s_total += s; p_total += p

    # ── Cone platform ─────────────────────────────────────────────────────────
    if spec.cone_model in ("5010",):
        cone_fp_key = "cone_5010"
    elif spec.cone_model in ("4510",):
        cone_fp_key = "cone_4510"
    else:
        cone_fp_key = "cone_3506_3508_3510"
    cone_fp  = _PLATFORM_FOOTPRINTS[cone_fp_key]
    cone_area = cone_fp[0] * cone_fp[1]
    twin = getattr(spec, "_twin_cone", False)
    cone_cols = 8 if twin else 4    # twin cones need double column grid
    cone_area_eff = cone_area * (2 if twin else 1)
    s, p = _platform_struct_tons(cone_area_eff, spec.elevation_cone, n_columns=cone_cols)
    s_total += s; p_total += p

    # ── 3-stage additions: pre-screen + surge bin 2 + VSI ────────────────────
    if spec.stages == 3:
        # Intermediate screen
        ps_area = _PLATFORM_FOOTPRINTS["prescreen"][0] * _PLATFORM_FOOTPRINTS["prescreen"][1]
        s, p = _platform_struct_tons(ps_area, spec.elevation_prescreen, n_columns=4)
        s_total += s; p_total += p

        # Surge bin 2 (VSI feed)
        s, p = _platform_struct_tons(sb_area, spec.elevation_surge2, n_columns=4)
        s_total += s; p_total += p

        # VSI platform
        vsi_key = spec.vsi_model or ""
        if "5080" in vsi_key:
            vsi_fp_key = "vsi_5080"
        elif "4060" in vsi_key:
            vsi_fp_key = "vsi_4060"
        else:
            vsi_fp_key = "vsi_200_300"
        vsi_fp   = _PLATFORM_FOOTPRINTS[vsi_fp_key]
        vsi_area = vsi_fp[0] * vsi_fp[1]
        s, p = _platform_struct_tons(vsi_area, spec.elevation_vsi, n_columns=4)
        s_total += s; p_total += p

        # VSI chutes + guards (sheet metal)
        p_total += (vsi_area * 1.5 * _CHUTE_KG_M2) / 1000

    # ── Final screen platform ─────────────────────────────────────────────────
    scr_key = _select_screen_primary(spec.tph, decks=4)
    if "2400" in scr_key:
        scr_fp_key = "screen_2400"
        scr_cols   = 6
    else:
        scr_fp_key = "screen_2000"
        scr_cols   = 4
    scr_fp   = _PLATFORM_FOOTPRINTS[scr_fp_key]
    scr_area = scr_fp[0] * scr_fp[1]
    scr_qty  = 2 if twin else 1
    s, p = _platform_struct_tons(scr_area * scr_qty, spec.elevation_screen,
                                 n_columns=scr_cols * scr_qty)
    s_total += s; p_total += p

    # Screen chutes (multi-product discharge)
    n_products = max(4, len(spec.products))
    p_total += (n_products * 1.2 * scr_area * _CHUTE_KG_M2) / 1000 * 0.15

    # ── Conveyor support trestles ─────────────────────────────────────────────
    # Trestles at every 6m interval along the site length; each ~0.15T structural
    site_len = spec._site_len()
    n_trestles = int(site_len / 6)
    s_total += n_trestles * 0.15

    # ── Mobile plants: most structure on skids (−65%) ─────────────────────────
    if spec.mobile:
        s_total *= 0.35
        p_total *= 0.35

    # ── Costing ───────────────────────────────────────────────────────────────
    struct_cost = (s_total * rc.STRUCTURAL_STEEL_RATE) / 1_00_000
    sheet_cost  = (p_total * rc.SHEET_METAL_RATE)      / 1_00_000
    total = round(struct_cost + sheet_cost, 2)
    return total, total


# ---------------------------------------------------------------------------
# ELECTRICAL COST
# ---------------------------------------------------------------------------

def _calc_electrical(spec: PlantSpec) -> tuple:
    """Returns (list_price, best_price)."""
    if spec.mobile:
        key = "2stage_cone_elec"
    elif spec.stages == 2:
        key = "2stage_cone_soft"
    else:
        vsi = spec.vsi_model or _select_vsi(spec.tph)
        if vsi in ("5080_2x300", "5080_2x400"):
            key = "3stage_vsi5080_soft"
        elif vsi in ("4060_2x200", "4060_2x250"):
            key = "3stage_vsi4060_soft"
        else:
            key = "3stage_vsi300_soft"

    panel, cables = rc.ELECTRICAL[key]
    total = panel + cables
    return round(total, 2), round(total, 2)


# ---------------------------------------------------------------------------
# CONVEYOR LAYOUT BUILDER
# ---------------------------------------------------------------------------

def _belt_len(horiz_m: float, rise_m: float) -> float:
    """True belt length from horizontal run + rise (Pythagorean, rounded up to 0.5m)."""
    raw = math.sqrt(horiz_m**2 + rise_m**2)
    return math.ceil(raw * 2) / 2   # round up to nearest 0.5m


def _build_conveyors_2stage(spec: PlantSpec) -> List[ConveyorSpec]:
    """
    Build conveyor set for a 2-stage stationary plant.
    Belt lengths are derived from PlantSpec site geometry + platform elevations.
    """
    tph = spec.tph
    mw  = _conveyor_width(tph, "main")
    pw  = _conveyor_width(tph, "product")

    # Resolve elevations from spec
    el_jaw    = spec.elevation_vgf        # jaw / VGF ground area
    el_cone   = spec.elevation_cone       # cone platform top
    el_screen = spec.elevation_screen     # screen platform top

    # Horizontal distances — use explicit spacing or distribute proportionally
    site_len = spec._site_len()
    # Approximate: hopper occupies ~12% of site, jaw→cone 28%, cone→screen 20%
    d_jaw_cone   = spec._spacing("spacing_jaw_to_cone",   site_len * 0.28)
    d_cone_scr   = spec._spacing("spacing_cone_to_screen",site_len * 0.20)
    d_scr_stock  = spec._spacing("spacing_screen_to_stock",site_len * 0.28)

    conveyors = []
    bc = 1

    # BC-01: Under jaw — horizontal transfer from jaw discharge to main feed belt
    l = max(8.0, spec._spacing("spacing_hopper_to_jaw", site_len * 0.12))
    conveyors.append(ConveyorSpec(f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l),
                                  "jaw_discharge_feed_belt")); bc += 1

    # BC-02, 03: Jaw to cone surge (rise: cone platform - jaw discharge)
    rise_to_cone = max(0, el_cone - el_jaw)
    l_j2c = max(18.0, _belt_len(d_jaw_cone * 0.5, rise_to_cone))
    for _ in range(2):
        conveyors.append(ConveyorSpec(f"BC-{bc:02d}", mw, l_j2c,
                                      _conveyor_hp(mw, l_j2c), "jaw_to_cone_surge")); bc += 1

    # BC-03b: VGF fines bypass to final screen (horizontal, along site width)
    site_wid = spec._site_wid()
    l_fines  = max(12.0, site_wid * 0.45)
    conveyors.append(ConveyorSpec(f"BC-{bc:02d}", pw, l_fines,
                                  _conveyor_hp(pw, l_fines), "vgf_fines_to_screen")); bc += 1

    # BC-04: Cone to final screen
    rise_to_scr = max(0, el_screen - el_cone + 1.5)   # +1.5m: discharge above screen feed
    l_c2s = max(15.0, _belt_len(d_cone_scr, rise_to_scr))
    conveyors.append(ConveyorSpec(f"BC-{bc:02d}", mw, l_c2s,
                                  _conveyor_hp(mw, l_c2s), "cone_to_screen")); bc += 1

    # BC-05: Oversize return (screen oversize back to cone surge — inclined)
    l_ovr = max(10.0, _belt_len(d_cone_scr * 0.6, el_screen))
    conveyors.append(ConveyorSpec(f"BC-{bc:02d}", mw, l_ovr,
                                  _conveyor_hp(mw, l_ovr), "oversize_return")); bc += 1

    # Product stackers: one per product fraction
    n_products = max(4, len(spec.products))
    l_prod = max(15.0, d_scr_stock / n_products * 1.1)
    for i in range(n_products):
        conveyors.append(ConveyorSpec(f"BC-{bc:02d}", pw, l_prod,
                                      _conveyor_hp(pw, l_prod), f"product_{i+1}")); bc += 1

    return conveyors


def _build_conveyors_3stage(spec: PlantSpec) -> List[ConveyorSpec]:
    """
    Build conveyor set for a 3-stage plant (jaw + cone + VSI).
    Belt lengths computed from PlantSpec site geometry + platform elevations.
    """
    tph = spec.tph
    mw  = _conveyor_width(tph, "main")
    pw  = _conveyor_width(tph, "product")

    # Platform elevations
    el_jaw       = spec.elevation_vgf
    el_prescrn   = spec.elevation_prescreen
    el_cone      = spec.elevation_cone
    el_surge2    = spec.elevation_surge2
    el_vsi       = spec.elevation_vsi
    el_screen    = spec.elevation_screen

    # Horizontal distances along the flow axis
    site_len = spec._site_len()
    site_wid = spec._site_wid()
    d_h2j    = spec._spacing("spacing_hopper_to_jaw",   site_len * 0.08)
    d_j2ps   = spec._spacing("spacing_jaw_to_cone",     site_len * 0.20)  # jaw → pre-screen
    d_ps2cn  = site_len * 0.08                                              # pre-screen → cone (short)
    d_cn2vsi = spec._spacing("spacing_cone_to_vsi",     site_len * 0.18)
    d_vsi2sc = spec._spacing("spacing_vsi_to_screen",   site_len * 0.12)
    d_sc2stk = spec._spacing("spacing_screen_to_stock", site_len * 0.22)

    conveyors = []
    bc = 1

    # BC-01: VGF feed belt (hopper → jaw, near-horizontal)
    l = max(10.0, _belt_len(d_h2j, max(0, el_jaw)))
    conveyors.append(ConveyorSpec(f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l),
                                  "vgf_to_jaw_feed")); bc += 1

    # BC-02: Jaw to pre-screen (inclined: jaw discharge up to pre-screen platform)
    l = max(25.0, _belt_len(d_j2ps, max(0, el_prescrn - el_jaw)))
    conveyors.append(ConveyorSpec(f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l),
                                  "jaw_to_prescreen")); bc += 1

    # BC-03: Pre-screen to cone surge (oversize fraction)
    l = max(18.0, _belt_len(d_ps2cn, max(0, el_cone - el_prescrn)))
    conveyors.append(ConveyorSpec(f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l),
                                  "prescreen_oversize_to_cone")); bc += 1

    # BC-04: Pre-screen bypass fines (undersize → final screen, nearly horizontal)
    l = max(18.0, _belt_len(site_wid * 0.35, max(0, el_screen - el_prescrn + 1.5)))
    conveyors.append(ConveyorSpec(f"BC-{bc:02d}", pw, l, _conveyor_hp(pw, l),
                                  "prescreen_fines_to_screen")); bc += 1

    # BC-05: Cone to MVF / surge bin 2 (VSI feed preparation)
    l = max(20.0, _belt_len(d_cn2vsi * 0.5, max(0, el_surge2 - el_cone + 2.0)))
    conveyors.append(ConveyorSpec(f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l),
                                  "cone_to_vsi_surge")); bc += 1

    # BC-06: MVF surge bin to VSI (short — surge bin sits adjacent to VSI platform)
    l = max(10.0, _belt_len(site_wid * 0.15, max(0, el_vsi - el_surge2)))
    conveyors.append(ConveyorSpec(f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l),
                                  "mvf_to_vsi")); bc += 1

    # BC-07: VSI discharge to final screen
    l = max(18.0, _belt_len(d_vsi2sc, max(0, el_screen - el_vsi + 1.5)))
    conveyors.append(ConveyorSpec(f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l),
                                  "vsi_to_screen")); bc += 1

    # BC-08: Oversize recirculation (screen → back to VSI or cone)
    l = max(28.0, _belt_len(d_vsi2sc + d_cn2vsi * 0.5, el_vsi))
    conveyors.append(ConveyorSpec(f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l),
                                  "oversize_recirculation")); bc += 1

    # BC-09: VGF fines (grizzly pass-through to product area, horizontal)
    l = max(18.0, d_sc2stk * 0.6)
    conveyors.append(ConveyorSpec(f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l),
                                  "vgf_fines")); bc += 1

    # Product stackers (one per product fraction)
    n_products = max(5, len(spec.products))
    l_prod = max(15.0, d_sc2stk / n_products * 1.1)
    for i in range(n_products):
        conveyors.append(ConveyorSpec(f"BC-{bc:02d}", pw, l_prod,
                                      _conveyor_hp(pw, l_prod), f"product_{i+1}")); bc += 1

    # BC-n+1: Pre-screen fines distribution (short cross-belt)
    conveyors.append(ConveyorSpec(f"BC-{bc:02d}", pw, 12.0,
                                  _conveyor_hp(pw, 12.0), "prescreen_fines_dist")); bc += 1

    # BC-n+2: Second jaw-to-prescreen (parallel line for high-TPH plants)
    if tph >= 300:
        conveyors.append(ConveyorSpec(f"BC-{bc:02d}", mw,
                                      max(25.0, _belt_len(d_j2ps, el_prescrn - el_jaw)),
                                      _conveyor_hp(mw, max(25.0, _belt_len(d_j2ps, el_prescrn - el_jaw))),
                                      "jaw_to_prescreen_2")); bc += 1

    # BC-n+3: Second cone-to-VSI (parallel — for twin cones 600 TPH)
    if getattr(spec, "_twin_cone", False):
        conveyors.append(ConveyorSpec(f"BC-{bc:02d}", mw, l,
                                      _conveyor_hp(mw, l),
                                      "cone_B_to_vsi_surge")); bc += 1

    # WSG feed conveyors (if washing)
    if spec.wsg_size:
        l_wsg = 24.0
        conveyors.append(ConveyorSpec(f"BC-{bc:02d}", pw, l_wsg,
                                      _conveyor_hp(pw, l_wsg), "wsg_feed")); bc += 1
        conveyors.append(ConveyorSpec(f"BC-{bc:02d}", pw, 15.0,
                                      _conveyor_hp(pw, 15.0), "wsg_product")); bc += 1

    return conveyors


def _chutes_and_supports_cost(conveyors: List[ConveyorSpec]) -> tuple:
    """
    Chutes & supports ≈ 17–20% of total conveyor belt cost (from observed data).
    Returns (list, best) — same value, no split.
    """
    belt_total = sum(c.cost_lakhs for c in conveyors)
    chutes = round(belt_total * 0.17, 2)
    return chutes, chutes


# ---------------------------------------------------------------------------
# MAIN QUOTATION BUILDER
# ---------------------------------------------------------------------------

def build_quotation(spec: PlantSpec) -> Quotation:
    """
    Build a full plant quotation from a PlantSpec.
    Returns a Quotation object with all sub-totals and warnings.
    """
    q = Quotation(spec=spec)

    # ------------------------------------------------------------------
    # Select equipment models
    # ------------------------------------------------------------------
    vgf_key  = spec.vgf_model  or _select_vgf(spec.tph)
    jaw_key  = spec.jaw_model  or _select_jaw(spec.tph, spec.feed_size_mm)
    cone_key = spec.cone_model or _select_cone(spec.tph)
    vsi_key  = spec.vsi_model  or _select_vsi(spec.tph)
    mvf_key  = _select_mvf(spec.tph)
    pre_screen_key  = _select_screen_pre(spec.tph)
    main_screen_key = _select_screen_primary(spec.tph, decks=4)

    # ------------------------------------------------------------------
    # Sub A — Main Mechanical Equipment
    # ------------------------------------------------------------------
    sl = 1

    # VGF
    vgf = rc.get_vgf(vgf_key)
    if not vgf:
        q.warnings.append(f"VGF model {vgf_key} not found in rate card.")
    else:
        li = LineItem(str(sl), f"VGF {vgf_key.replace('x', 'mm x ')}mm",
                      1, vgf["hp"], vgf["list"], vgf["best"])
        if "flag" in vgf:
            li.flags.append(vgf["flag"]); q.warnings.append(f"VGF {vgf_key}: {vgf['flag']}")
        q.sub_a_items.append(li); sl += 1

    # Jaw
    jaw = rc.get_jaw(jaw_key)
    if not jaw:
        q.warnings.append(f"Jaw model {jaw_key} not found. TPH {spec.tph} may be out of range.")
    elif jaw.get("list") is None:
        q.warnings.append(f"Jaw {jaw_key}: no price — engineering/sales quote required.")
    else:
        jaw_display = jaw_key.replace('x', '"x') + '"'
        li = LineItem(str(sl), f"Primary Jaw Crusher PROjaw-{jaw_display}",
                      1, jaw["hp"], jaw["list"], jaw["best"])
        if "flag" in jaw: li.flags.append(jaw["flag"]); q.warnings.append(jaw["flag"])
        q.sub_a_items.append(li); sl += 1

    # Pre-screen (3-stage only)
    if spec.stages == 3:
        ps = rc.get_screen(pre_screen_key)
        if ps:
            q.sub_a_items.append(LineItem(str(sl),
                f"Vibratory Screen {pre_screen_key.replace('_', ' ').replace('x', 'mm x ').upper()} (Pre-screen)",
                1, ps["hp"], ps["list"], ps["best"])); sl += 1

    # Cone — support twin-cone flag (e.g. 600 TPH gabro: 2× PROCone-5010 in 50-50 split)
    twin_cone = getattr(spec, "_twin_cone", False)
    cone_qty  = 2 if twin_cone else 1
    cone = rc.get_cone(cone_key)
    if not cone:
        q.warnings.append(f"Cone model {cone_key} not in range for {spec.tph} TPH.")
    else:
        twin_note = " (Twin — 50-50 feed split)" if twin_cone else " with Sub-Base Frame"
        desc = f"PROcone-{cone_key}{twin_note}"
        cone_lp = round((cone["list"] or 0) * cone_qty, 2) if cone["list"] else None
        cone_bp = round((cone["best"] or 0) * cone_qty, 2) if cone["best"] else None
        li = LineItem(str(sl), desc, cone_qty,
                      (cone["hp"] + cone.get("aux_hp", 0)) * cone_qty,
                      cone_lp, cone_bp)
        if twin_cone:
            q.warnings.append(f"Twin PROCone-{cone_key}: qty × 2, cost × 2 (50-50 split arrangement).")
        q.sub_a_items.append(li); sl += 1

    # VSI (3-stage only)
    if spec.stages == 3:
        vsi = rc.get_vsi(vsi_key)
        if not vsi:
            q.warnings.append(f"VSI model {vsi_key} not found.")
        elif vsi.get("list") is None:
            q.warnings.append(f"VSI {vsi_key}: no price — engineering/sales quote required.")
        else:
            li = LineItem(str(sl), f"REMCO VSI-{vsi_key} with IP Protection",
                          1, vsi["hp"], vsi["list"], vsi["best"])
            if "flag" in vsi: li.flags.append(vsi["flag"]); q.warnings.append(vsi["flag"])
            q.sub_a_items.append(li); sl += 1

    # Main (final product) screen
    # 600 TPH gabro uses twin final screens (2× 2400x8100_3d per layout)
    twin_screen = twin_cone  # same flag: if twin cones → twin final screens
    scr_qty = 2 if twin_screen else 1
    ms = rc.get_screen(main_screen_key)
    if ms:
        scr_lp = round((ms["list"] or 0) * scr_qty, 2) if ms.get("list") else None
        scr_bp = round((ms["best"] or 0) * scr_qty, 2) if ms.get("best") else None
        scr_desc = f"Vibratory Screen {main_screen_key.replace('_', ' ').upper()}"
        if twin_screen:
            scr_desc = "2× " + scr_desc + " (Twin Final Screens)"
        q.sub_a_items.append(LineItem(str(sl), scr_desc,
            scr_qty, ms["hp"] * scr_qty, scr_lp, scr_bp)); sl += 1
        if twin_screen:
            q.warnings.append("Twin final screens (qty 2): cost × 2 — per 600 TPH gabro layout.")
    else:
        q.warnings.append(f"Screen {main_screen_key} not found.")

    # MVF(s)
    mvf = rc.get_mvf(mvf_key)
    n_mvf = 3 if spec.stages == 3 else 1
    if spec.wsg_size: n_mvf += 1
    if mvf:
        q.sub_a_items.append(LineItem(str(sl),
            f"Mechanical Vibratory Feeder MVF {mvf_key}",
            n_mvf, 3.4 * n_mvf,
            round(mvf["list"] * n_mvf, 2),
            round(mvf["best"] * n_mvf, 2))); sl += 1

    # Metal Detector(s)
    n_md = 2 if spec.stages == 3 else 1
    md = rc.METAL_DETECTOR
    q.sub_a_items.append(LineItem(str(sl), "Metal Detector",
        n_md, 0, round(md["list"] * n_md, 2), round(md["best"] * n_md, 2))); sl += 1

    # WSG
    if spec.wsg_size:
        wsg_price = rc.get_wsg(spec.wsg_size, spec.wsg_config)
        if wsg_price:
            q.sub_a_items.append(LineItem(str(sl),
                f"WSG-{spec.wsg_size} ({spec.wsg_config.replace('_', ' ')})",
                1, 0, wsg_price["list"], wsg_price["best"])); sl += 1
        else:
            q.warnings.append(f"WSG size {spec.wsg_size} / config {spec.wsg_config} not found.")

    # Electrical drive motors (lump sum — from observed 14-42L range, scale with HP)
    total_a_hp = sum(i.hp for i in q.sub_a_items)
    motor_cost = round(total_a_hp * 0.033, 2)   # ~3.3% of HP ≈ approx motor cost scaling
    q.sub_a_items.append(LineItem(str(sl),
        "Electrical Drive Motors for Main Equipment",
        sl - 1, 0, motor_cost, motor_cost)); sl += 1

    # ------------------------------------------------------------------
    # Sub B — Belt Conveyors
    # ------------------------------------------------------------------
    if spec.mobile:
        # Porta: fewer add-on conveyors, lighter
        conveyors = _build_conveyors_2stage(spec)[:9]
    elif spec.stages == 2:
        conveyors = _build_conveyors_2stage(spec)
    else:
        conveyors = _build_conveyors_3stage(spec)

    q.sub_b_conveyors = conveyors
    q.sub_b_chutes_list, q.sub_b_chutes_best = _chutes_and_supports_cost(conveyors)

    # ------------------------------------------------------------------
    # Sub C — Structural Steel
    # ------------------------------------------------------------------
    q.sub_c_structural_list, q.sub_c_structural_best = _calc_structural(spec)
    if spec.mobile:
        q.sub_c_structural_list = round(q.sub_c_structural_list * 0.35, 2)
        q.sub_c_structural_best = q.sub_c_structural_list

    # ------------------------------------------------------------------
    # Sub D — Electrical
    # ------------------------------------------------------------------
    q.sub_d_list, q.sub_d_best = _calc_electrical(spec)

    # ------------------------------------------------------------------
    # Sub E — Erection & Commissioning
    # ------------------------------------------------------------------
    if spec.mobile:
        q.erection = rc.ERECTION["2stage_porta"]
    elif spec.stages == 3:
        q.erection = rc.ERECTION["3stage"]
    else:
        q.erection = rc.ERECTION["2stage_stationary"]

    return q


# ---------------------------------------------------------------------------
# TERTIARY-ONLY QUOTATION  (no jaw/cone — just VSI + screen + feeders)
# Used for the "Tertiary Standalone VSI-5080" config (stages=1 / _tertiary_only=True)
# ---------------------------------------------------------------------------

def build_tertiary_quotation(spec: PlantSpec) -> Quotation:
    """
    Build a quotation for a tertiary-only (standalone VSI) plant.
    No VGF, jaw crusher, or cone crusher.
    Equipment: Surge Bin (structural) + 2× MVF + VSI + Vibrating Screen + 4 conveyors.
    """
    q = Quotation(spec=spec)
    q.warnings.append("Tertiary-only plant: no VGF / jaw / cone in this quotation.")

    vsi_key = spec.vsi_model or "5080_2x400"
    sl = 1

    # VSI
    vsi = rc.get_vsi(vsi_key)
    if not vsi:
        q.warnings.append(f"VSI model {vsi_key} not found in rate card.")
    elif vsi.get("list") is None:
        q.warnings.append(
            f"⚠️ REMco VSI-{vsi_key}: NO PRICE in rate card — "
            "engineering / sales quote required before sending this proposal."
        )
        # Add a zero-price placeholder so the schedule is visible
        q.sub_a_items.append(LineItem(
            str(sl), f"REMCO VSI-{vsi_key} with IP55 Enclosure (2×400HP)",
            1, vsi["hp"], None, None,
            flags=["Engineering quote required — no rate card price"]
        )); sl += 1
    else:
        li = LineItem(str(sl), f"REMCO VSI-{vsi_key} with IP Protection",
                      1, vsi["hp"], vsi["list"], vsi["best"])
        if "flag" in vsi:
            li.flags.append(vsi["flag"]); q.warnings.append(vsi["flag"])
        q.sub_a_items.append(li); sl += 1

    # MVF feeders (2 units feed VSI from surge bin)
    mvf_key = _select_mvf(spec.tph)
    mvf = rc.get_mvf(mvf_key)
    if mvf:
        q.sub_a_items.append(LineItem(str(sl),
            f"Mechanical Vibratory Feeder MVF {mvf_key}",
            2, 3.4 * 2, round(mvf["list"] * 2, 2), round(mvf["best"] * 2, 2))); sl += 1

    # Final screen (3-deck for M-sand production, single unit)
    scr_key = "2400x8100_3d"   # per PFD for 600 mt/h tertiary
    ms = rc.get_screen(scr_key)
    if ms:
        q.sub_a_items.append(LineItem(str(sl),
            f"Vibratory Screen {scr_key.upper()} (Final 3-Deck)",
            1, ms["hp"], ms["list"], ms["best"])); sl += 1

    # Metal detector
    md = rc.METAL_DETECTOR
    q.sub_a_items.append(LineItem(str(sl), "Metal Detector", 1, 0,
        md["list"], md["best"])); sl += 1

    # Motors for main equipment
    total_a_hp = sum(i.hp for i in q.sub_a_items)
    motor_cost = round(total_a_hp * 0.033, 2)
    q.sub_a_items.append(LineItem(str(sl),
        "Electrical Drive Motors for Main Equipment",
        sl - 1, 0, motor_cost, motor_cost)); sl += 1

    # Sub B — 4 belt conveyors (feed, VSI discharge, screen u/f, product stacker)
    tph  = spec.tph
    pw   = _conveyor_width(tph, "product")
    mw   = _conveyor_width(tph, "main")
    conv = [
        ConveyorSpec("BC-01", mw,  10, _conveyor_hp(mw,  10), "surge_bin_to_vsi"),
        ConveyorSpec("BC-02", mw,  18, _conveyor_hp(mw,  18), "vsi_discharge_to_screen"),
        ConveyorSpec("BC-03", pw,  15, _conveyor_hp(pw,  15), "screen_underflow_product"),
        ConveyorSpec("BC-04", mw,  30, _conveyor_hp(mw,  30), "product_stacker"),
    ]
    q.sub_b_conveyors = conv
    q.sub_b_chutes_list, q.sub_b_chutes_best = _chutes_and_supports_cost(conv)

    # Sub C — structural (lighter: just surge bin platform + screen frame + VSI frame)
    struct_cost = round(
        (rc.STRUCTURAL_TONNAGE.get("surge_hopper_30t_for_vsi", (9, 4))[0] * rc.STRUCTURAL_STEEL_RATE +
         rc.STRUCTURAL_TONNAGE.get("screen_frame_zframe_walkway_stairs", (10, 6))[0] * rc.STRUCTURAL_STEEL_RATE +
         rc.STRUCTURAL_TONNAGE.get("vsi_chutes_guards_misc", (3, 1))[0] * rc.STRUCTURAL_STEEL_RATE)
        / 1_00_000, 2)
    q.sub_c_structural_list = struct_cost
    q.sub_c_structural_best = struct_cost

    # Sub D — electrical (tertiary: simpler panel, fewer starters)
    elec_list, elec_best = rc.ELECTRICAL.get("3stage_vsi5080_soft", (52, 36))
    q.sub_d_list = round(elec_list * 0.55, 2)   # ~55% of full 3-stage (no primary/secondary section)
    q.sub_d_best = round(elec_best * 0.55, 2)

    # Sub E — erection (lighter than full 3-stage)
    q.erection = round(rc.ERECTION.get("3stage", 12) * 0.4, 2)

    return q


# ---------------------------------------------------------------------------
# STANDALONE EQUIPMENT QUOTE
# ---------------------------------------------------------------------------

def quote_standalone_equipment(category: str, model: str) -> dict:
    """
    Quote a single piece of equipment (not a full plant).
    category: "VSI" / "JAW" / "CONE" / "SCREEN" / "VGF" / "WSG"
    model:    e.g. "300" for VSI, "4510" for cone
    """
    cat = category.upper()
    result = {"category": cat, "model": model, "status": "no_price",
              "list": None, "best": None, "hp": None, "flags": []}

    if cat == "VSI":
        data = rc.get_vsi(model)
        if data:
            result["hp"]     = data.get("hp")
            result["list"]   = data.get("list")
            result["best"]   = data.get("best")
            result["starter_soft"] = data.get("starter_soft")
            result["status"] = "priced" if data.get("list") else "no_price"
            if "flag" in data: result["flags"].append(data["flag"])

    elif cat == "JAW":
        data = rc.get_jaw(model)
        if data:
            result["hp"]     = data.get("hp")
            result["list"]   = data.get("list")
            result["best"]   = data.get("best")
            result["status"] = "priced" if data.get("list") else "no_price"
            if "flag" in data: result["flags"].append(data["flag"])

    elif cat == "CONE":
        data = rc.get_cone(model)
        if data:
            result["hp"]     = data.get("hp")
            result["list"]   = data.get("list")
            result["best"]   = data.get("best")
            result["status"] = "priced" if data.get("list") else "no_price"

    elif cat == "VGF":
        data = rc.get_vgf(model)
        if data:
            result["hp"]     = data.get("hp")
            result["list"]   = data.get("list")
            result["best"]   = data.get("best")
            result["status"] = "priced" if data.get("list") else "no_price"
            if "flag" in data: result["flags"].append(data["flag"])

    elif cat == "SCREEN":
        data = rc.get_screen(model)
        if data:
            result["hp"]   = data.get("hp")
            result["list"] = data.get("list")
            result["best"] = data.get("best")
            result["status"] = "priced"

    elif cat == "WSG":
        data = rc.get_wsg(model)
        if data:
            result["list"] = data.get("list")
            result["best"] = data.get("best")
            result["status"] = "priced"

    else:
        result["flags"].append(f"Unknown category: {cat}")

    return result


# ---------------------------------------------------------------------------
# SMOKE TEST
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Standalone VSI-300 quote (Chiman Bhai enquiry)
    r = quote_standalone_equipment("VSI", "300")
    print("=== Standalone VSI-300 ===")
    print(f"  List: {r['list']}L  |  Best: {r['best']}L  |  HP: {r['hp']}")
    print(f"  Soft Starter: {r.get('starter_soft')}")
    print(f"  Status: {r['status']}")
    if r['flags']: print(f"  ⚠️  {r['flags']}")

    print()

    # Full 2-stage 250TPH plant
    spec = PlantSpec(
        client_name="Test Client",
        tph=250,
        stages=2,
        feed_size_mm=650,
        products=["GSB", "-20+10mm", "-10+6mm", "-6+4.75mm", "0-4.75mm"],
    )
    q = build_quotation(spec)
    print("=== 2-Stage 250TPH Plant ===")
    print(f"  Sub A (List): {q.sub_a_list()}L  | Sub A (Best): {q.sub_a_best()}L")
    print(f"  Sub B (List): {q.sub_b_total_list()}L | conveyors: {len(q.sub_b_conveyors)}")
    print(f"  Sub C: {q.sub_c_structural_list}L")
    print(f"  Sub D: {q.sub_d_list}L")
    print(f"  Erection: {q.erection}L")
    print(f"  GRAND TOTAL List: {q.grand_total_list()}L")
    print(f"  GRAND TOTAL Best: {q.grand_total_best()}L")
    print(f"  Total HP: {q.total_hp()}")
    if q.warnings:
        print("\n  WARNINGS:")
        for w in q.warnings: print(f"    ⚠️  {w}")
