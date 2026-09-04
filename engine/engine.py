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
# STRUCTURAL STEEL ESTIMATION
# ---------------------------------------------------------------------------

def _calc_structural(spec: PlantSpec) -> tuple:
    """Returns (list_price, best_price) for Sub C."""
    struct_tons = 0
    sheet_tons = 0
    T = rc.STRUCTURAL_TONNAGE

    # Hopper size depends on TPH
    hopper_key = "rom_hopper_50t_with_vgf_jaw_platform" if spec.tph > 350 \
                 else "rom_hopper_30t_with_vgf_jaw_platform"
    s, sm = T[hopper_key]
    struct_tons += s; sheet_tons += sm

    # Cone feed tunnel or surge hopper
    s, sm = T["tunnel_for_cone_feed"]
    struct_tons += s; sheet_tons += sm

    s, sm = T["surge_hopper_30t_for_cone"]
    struct_tons += s; sheet_tons += sm

    # Cone frame
    s, sm = T["cone_frame_walkway_stairs"]
    struct_tons += s; sheet_tons += sm

    if spec.stages == 3:
        # Pre-screen support (small, reuse screen_frame at half)
        s, sm = T["screen_frame_zframe_walkway_stairs"]
        struct_tons += s * 0.6; sheet_tons += sm * 0.6

        s, sm = T["surge_hopper_30t_for_vsi"]
        struct_tons += s; sheet_tons += sm

    # Main screen frame
    s, sm = T["screen_frame_zframe_walkway_stairs"]
    struct_tons += s; sheet_tons += sm

    if spec.stages == 3:
        s, sm = T["vsi_chutes_guards_misc"]
        struct_tons += s; sheet_tons += sm
    else:
        s, sm = T["transfer_tower_product_chutes"]
        struct_tons += s * 0.5; sheet_tons += sm * 0.5

    if spec.mobile:
        struct_tons *= 0.35    # most structure integrated into skids

    struct_cost = (struct_tons * rc.STRUCTURAL_STEEL_RATE) / 1_00_000
    sheet_cost  = (sheet_tons  * rc.SHEET_METAL_RATE)      / 1_00_000
    total = round(struct_cost + sheet_cost, 2)
    return total, total   # list == best for structural (lump sum)


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

def _build_conveyors_2stage(spec: PlantSpec) -> List[ConveyorSpec]:
    """Build standard conveyor set for a 2-stage stationary plant."""
    tph = spec.tph
    mw = _conveyor_width(tph, "main")    # main line width
    pw = _conveyor_width(tph, "product") # product line width
    jh = spec.jaw_discharge_h

    conveyors = []
    bc = 1

    # BC-01: Under jaw (short transfer, jaw discharge to first main belt)
    rise = 0  # horizontal or near-flat under jaw
    l = max(8, rc.conveyor_length_from_rise(rise, horizontal_offset_m=6))
    conveyors.append(ConveyorSpec(
        f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l), "jaw_discharge_to_feed_belt")); bc += 1

    # BC-02, 03, 04: Jaw output to surge hopper (3 parallel routes allow recirculation)
    # Rise = cone platform height - jaw discharge height
    cone_h = max(5.0, jh + 3.5)
    l = rc.conveyor_length_from_rise(cone_h - jh, horizontal_offset_m=8)
    for _ in range(3):
        conveyors.append(ConveyorSpec(
            f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l), "jaw_to_cone_surge")); bc += 1

    # BC-05: Cone discharge to final screen
    screen_h = cone_h + 1.5  # screen sits above cone discharge
    l = rc.conveyor_length_from_rise(screen_h - cone_h, horizontal_offset_m=5)
    l = max(l, 18)
    conveyors.append(ConveyorSpec(
        f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l), "cone_to_screen")); bc += 1

    # Product conveyors: typically 4 products, one for quarry fines (VGF undersize)
    n_products = max(4, len(spec.products))
    for i in range(n_products):
        l = 15 if tph <= 250 else 18
        conveyors.append(ConveyorSpec(
            f"BC-{bc:02d}", pw, l, _conveyor_hp(pw, l), f"product_{i+1}")); bc += 1

    # VGF quarry fines conveyor
    conveyors.append(ConveyorSpec(
        f"BC-{bc:02d}", mw, 15, _conveyor_hp(mw, 15), "vgf_fines")); bc += 1

    # Recirculation / oversize return (short)
    conveyors.append(ConveyorSpec(
        f"BC-{bc:02d}", pw, 10, _conveyor_hp(pw, 10), "oversize_return")); bc += 1

    return conveyors


def _build_conveyors_3stage(spec: PlantSpec) -> List[ConveyorSpec]:
    """Build standard conveyor set for a 3-stage plant (jaw + cone + VSI)."""
    tph = spec.tph
    mw = _conveyor_width(tph, "main")
    pw = _conveyor_width(tph, "product")
    jh = spec.jaw_discharge_h

    conveyors = []
    bc = 1

    # BC-01: Feed belt under VGF (horizontal, short)
    l = max(10, rc.conveyor_length_from_rise(0, horizontal_offset_m=8))
    conveyors.append(ConveyorSpec(
        f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l), "vgf_to_jaw_feed")); bc += 1

    # BC-02, 03: Jaw to pre-screen
    cone_h = max(6.0, jh + 4.0)
    l = rc.conveyor_length_from_rise(cone_h - jh, horizontal_offset_m=8)
    l = max(l, 25)
    for _ in range(2):
        conveyors.append(ConveyorSpec(
            f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l), "jaw_to_prescreen")); bc += 1

    # BC-04: Pre-screen to cone surge hopper
    l = rc.conveyor_length_from_rise(1.5, horizontal_offset_m=5)
    l = max(l, 18)
    conveyors.append(ConveyorSpec(
        f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l), "prescreen_to_cone_surge")); bc += 1

    # BC-05: Cone discharge to VSI feed
    vsi_h = cone_h + 2.5
    l = rc.conveyor_length_from_rise(vsi_h - cone_h, horizontal_offset_m=8)
    l = max(l, 20)
    conveyors.append(ConveyorSpec(
        f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l), "cone_to_vsi")); bc += 1

    # BC-06: Pre-screen undersize bypass (fine fraction bypasses cone, goes direct to final screen)
    conveyors.append(ConveyorSpec(
        f"BC-{bc:02d}", pw, 10, _conveyor_hp(pw, 10), "prescreen_bypass_fines")); bc += 1

    # BC-07, 08: VSI discharge to final screen
    screen_h = vsi_h + 1.0
    l = rc.conveyor_length_from_rise(screen_h - vsi_h, horizontal_offset_m=6)
    l = max(l, 18)
    for _ in range(2):
        conveyors.append(ConveyorSpec(
            f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l), "vsi_to_final_screen")); bc += 1

    # BC-09: Oversize recirculation (final screen → VSI or cone)
    l = rc.conveyor_length_from_rise(vsi_h, horizontal_offset_m=10)
    l = max(l, 30)
    conveyors.append(ConveyorSpec(
        f"BC-{bc:02d}", mw, l, _conveyor_hp(mw, l), "oversize_recirculation")); bc += 1

    # Pre-screen fines distribution belt
    conveyors.append(ConveyorSpec(
        f"BC-{bc:02d}", pw, 15, _conveyor_hp(pw, 15), "prescreen_fines_dist")); bc += 1

    # Product conveyors
    n_products = max(5, len(spec.products))
    for i in range(n_products):
        l = 10 if tph <= 250 else 15
        conveyors.append(ConveyorSpec(
            f"BC-{bc:02d}", pw, l, _conveyor_hp(pw, l), f"product_{i+1}")); bc += 1

    # VGF quarry fines
    conveyors.append(ConveyorSpec(
        f"BC-{bc:02d}", mw, 10, _conveyor_hp(mw, 10), "vgf_fines")); bc += 1

    # WSG feed conveyor (if washing)
    if spec.wsg_size:
        l = 24
        conveyors.append(ConveyorSpec(
            f"BC-{bc:02d}", pw, l, _conveyor_hp(pw, l), "wsg_feed")); bc += 1
        conveyors.append(ConveyorSpec(
            f"BC-{bc:02d}", pw, 15, _conveyor_hp(pw, 15), "wsg_product")); bc += 1

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

    # Cone
    cone = rc.get_cone(cone_key)
    if not cone:
        q.warnings.append(f"Cone model {cone_key} not in range for {spec.tph} TPH.")
    else:
        desc = f"PROcone-{cone_key} with Sub-Base Frame"
        li = LineItem(str(sl), desc, 1, cone["hp"] + cone.get("aux_hp", 0),
                      cone["list"], cone["best"])
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
    ms = rc.get_screen(main_screen_key)
    if ms:
        q.sub_a_items.append(LineItem(str(sl),
            f"Vibratory Screen {main_screen_key.replace('_', ' ').upper()}",
            1, ms["hp"], ms["list"], ms["best"])); sl += 1
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
