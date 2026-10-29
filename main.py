"""
PROMAN Quotation Engine — FastAPI Web Application
Run:  uvicorn main:app --reload --port 8000
"""

import sys, os, uuid, tempfile, json, traceback, math
from datetime import date
from pathlib import Path
from typing import Optional, List

sys.path.insert(0, str(Path(__file__).parent / "engine"))

from fastapi import FastAPI, HTTPException, Depends, Response, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from auth import (
    authenticate_user, create_token, require_login, require_admin,
    list_users, create_user, update_user, delete_user,
    TOKEN_EXPIRE_HOURS,
)

import rate_card as rc
from engine import (PlantSpec, Quotation, build_quotation, quote_standalone_equipment,
                    build_tertiary_quotation)
from triage import triage_enquiry
from generate_xlsx import build_workbook
from generate_offer_letter import build_offer_letter, build_standalone_letter
from bundle import (BundleSpec, BundleEquipmentItem, BundleConveyorItem,
                    build_bundle_quotation, infer_tph)
from erpnext_bridge import (parse_lead_payload, push_quote_to_lead,
                             fetch_lead, list_new_leads)
import masters_manager as mm
from equipment_selector import build_equipment_schedule, build_tertiary_schedule
from procurement_bom import build_procurement_bom
from pfd_generator import generate_pfd_html
from quotation_configs import ALL_CONFIGS, get_config

# ---------------------------------------------------------------------------
app = FastAPI(title="PROMAN Quotation Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

STATIC = Path(__file__).parent / "static"
TMP    = Path(tempfile.gettempdir()) / "proman_quotes"
TMP.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


# Global handler: always return JSON for unhandled 500s
@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print(f"UNHANDLED EXCEPTION on {request.url}:\n{tb}", flush=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}: {exc}"},
    )


# ---------------------------------------------------------------------------
# PYDANTIC MODELS
# ---------------------------------------------------------------------------

class TriageRequest(BaseModel):
    enquiry_text: str

class QuoteRequest(BaseModel):
    client_name: str
    tph: int
    stages: int = 2
    feed_size_mm: int = 650
    material: str = "Granite/Basalt"
    products: List[str] = []
    mobile: bool = False
    wsg_size: Optional[str] = None
    wsg_config: str = "bare"
    jaw_discharge_h: float = 1.83
    jaw_model: Optional[str] = None
    cone_model: Optional[str] = None
    vsi_model: Optional[str] = None
    vgf_model: Optional[str] = None
    ref_no: str = ""
    date: str = ""
    # ── Site geometry (optional — engine uses smart defaults when absent) ──
    site_length_m:       Optional[float] = None  # overall plant footprint length (m)
    site_width_m:        Optional[float] = None  # overall plant footprint width  (m)
    # Platform elevations above FFL (m)
    elevation_cone:      Optional[float] = None
    elevation_prescreen: Optional[float] = None
    elevation_surge2:    Optional[float] = None
    elevation_vsi:       Optional[float] = None
    elevation_screen:    Optional[float] = None
    # Key centroid spacings (m) — leave blank to let engine auto-distribute
    spacing_jaw_to_cone:     Optional[float] = None
    spacing_cone_to_vsi:     Optional[float] = None
    spacing_vsi_to_screen:   Optional[float] = None
    spacing_screen_to_stock: Optional[float] = None

class StandaloneRequest(BaseModel):
    category: str   # VSI / JAW / CONE / VGF / SCREEN / WSG
    model: str
    client_name: str = "Client"
    ref_no: str = ""


class BundleEquipmentItemReq(BaseModel):
    category: str
    model: str
    qty: int = 1
    note: str = ""

class BundleConveyorItemReq(BaseModel):
    width_mm: int
    length_m: float
    qty: int = 1
    note: str = ""

class BundleRequest(BaseModel):
    client_name: str
    ref_no: str = ""
    date: str = ""
    equipment: List[BundleEquipmentItemReq] = []
    conveyors: List[BundleConveyorItemReq] = []
    include_chutes: bool = True
    include_erection: bool = False
    erection_lump: float = 0.0

class InferTPHRequest(BaseModel):
    jaw_model:    Optional[str] = None
    cone_model:   Optional[str] = None
    vsi_model:    Optional[str] = None
    feed_size_mm: Optional[int] = None
    material:     Optional[str] = None
    stages:       Optional[int] = None

class QuoteNoTPHRequest(QuoteRequest):
    tph: int = 0   # 0 = auto-infer


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _quotation_to_dict(q: Quotation) -> dict:
    spec = q.spec
    return {
        "spec": {
            "client_name":  spec.client_name,
            "tph":          spec.tph,
            "stages":       spec.stages,
            "material":     spec.material,
            "products":     spec.products,
            "mobile":       spec.mobile,
            "ref_no":       spec.ref_no,
            "date":         spec.date or date.today().isoformat(),
        },
        "sub_a": [
            {
                "sl":         item.sl,
                "description":item.description,
                "qty":        item.qty,
                "hp":         item.hp,
                "list_price": item.list_price,
                "best_price": item.best_price,
                "flags":      item.flags,
            }
            for item in q.sub_a_items
        ],
        "sub_b_conveyors": [
            {
                "tag":      c.tag,
                "width_mm": c.width_mm,
                "length_m": c.length_m,
                "hp":       c.hp,
                "purpose":  c.purpose,
                "cost":     c.cost_lakhs,
            }
            for c in q.sub_b_conveyors
        ],
        "sub_b_chutes_list": q.sub_b_chutes_list,
        "sub_c_list":        q.sub_c_structural_list,
        "sub_c_best":        q.sub_c_structural_best,
        "sub_d_list":        q.sub_d_list,
        "sub_d_best":        q.sub_d_best,
        "erection":          q.erection,
        "totals": {
            "sub_a_list":       q.sub_a_list(),
            "sub_a_best":       q.sub_a_best(),
            "sub_a_hp":         q.sub_a_hp(),
            "sub_b_list":       q.sub_b_total_list(),
            "sub_b_hp":         q.sub_b_hp(),
            "total_list":       q.total_list(),
            "total_best":       q.total_best(),
            "grand_total_list": q.grand_total_list(),
            "grand_total_best": q.grand_total_best(),
            "total_hp":         q.total_hp(),
        },
        "warnings": q.warnings,
    }


def _make_spec(r: QuoteRequest) -> PlantSpec:
    ref = r.ref_no or f"PR/{date.today().strftime('%m-%y')}/N-{str(uuid.uuid4())[:4].upper()}"

    # Build kwargs — only pass geometry fields that were actually supplied
    # so PlantSpec dataclass defaults (smart fallbacks) take over for missing ones.
    kw: dict = dict(
        client_name     = r.client_name,
        tph             = r.tph,
        stages          = r.stages,
        feed_size_mm    = r.feed_size_mm,
        material        = r.material,
        products        = r.products,
        mobile          = r.mobile,
        wsg_size        = r.wsg_size,
        wsg_config      = r.wsg_config,
        jaw_discharge_h = r.jaw_discharge_h,
        jaw_model       = r.jaw_model,
        cone_model      = r.cone_model,
        vsi_model       = r.vsi_model,
        vgf_model       = r.vgf_model,
        ref_no          = ref,
        date            = r.date or date.today().strftime("%d-%m-%Y"),
    )

    # Optional geometry overrides — skip if None (let engine use defaults)
    _geo = {
        "site_length_m":       r.site_length_m,
        "site_width_m":        r.site_width_m,
        "elevation_cone":      r.elevation_cone,
        "elevation_prescreen": r.elevation_prescreen,
        "elevation_surge2":    r.elevation_surge2,
        "elevation_vsi":       r.elevation_vsi,
        "elevation_screen":    r.elevation_screen,
        "spacing_jaw_to_cone":     r.spacing_jaw_to_cone,
        "spacing_cone_to_vsi":     r.spacing_cone_to_vsi,
        "spacing_vsi_to_screen":   r.spacing_vsi_to_screen,
        "spacing_screen_to_stock": r.spacing_screen_to_stock,
    }
    kw.update({k: v for k, v in _geo.items() if v is not None})

    return PlantSpec(**kw)


# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# AUTH ENDPOINTS
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str

class CreateUserRequest(BaseModel):
    username: str
    password: str
    name: str
    role: str = "user"

class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    active: Optional[bool] = None
    password: Optional[str] = None

@app.get("/login", response_class=HTMLResponse)
async def login_page():
    return (STATIC / "login.html").read_text()

@app.post("/api/auth/login")
async def login(req: LoginRequest, response: Response):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password.")
    token = create_token(req.username, user["role"])
    response.set_cookie(
        key="proman_token", value=token,
        httponly=True, samesite="lax", secure=False,  # set secure=True on HTTPS
        max_age=TOKEN_EXPIRE_HOURS * 3600,
    )
    return {
        "username": req.username,
        "role": user["role"],
        "name": user.get("name", ""),
        "must_change_password": user.get("must_change_password", False),
        "redirect": "/",
    }

@app.post("/api/auth/logout")
async def logout(response: Response):
    response.delete_cookie("proman_token")
    return {"status": "logged out"}

@app.get("/api/auth/me")
async def me(current_user: dict = Depends(require_login)):
    return {k: v for k, v in current_user.items() if k != "hashed_password"}

# User management (admin only)
@app.get("/api/users")
async def get_users(_: dict = Depends(require_admin)):
    return list_users()

@app.post("/api/users")
async def add_user(req: CreateUserRequest, _: dict = Depends(require_admin)):
    try:
        return create_user(req.username, req.password, req.name, req.role)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.put("/api/users/{username}")
async def edit_user(username: str, req: UpdateUserRequest, _: dict = Depends(require_admin)):
    try:
        updates = {k: v for k, v in req.dict().items() if v is not None}
        return update_user(username, updates)
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.delete("/api/users/{username}")
async def remove_user(username: str, _: dict = Depends(require_admin)):
    try:
        delete_user(username)
        return {"status": "deleted", "username": username}
    except ValueError as e:
        raise HTTPException(400, str(e))

@app.post("/api/auth/change-password")
async def change_password(req: UpdateUserRequest, current_user: dict = Depends(require_login)):
    if not req.password:
        raise HTTPException(400, "New password required.")
    update_user(current_user["username"], {"password": req.password})
    return {"status": "password updated"}


# ---------------------------------------------------------------------------
# PAGES
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root(current_user: dict = Depends(require_login)):
    return (STATIC / "index.html").read_text()


@app.post("/api/triage")
async def triage(req: TriageRequest, _: dict = Depends(require_login)):
    result = triage_enquiry(req.enquiry_text)
    return result


@app.post("/api/quote")
async def quote(req: QuoteRequest, _: dict = Depends(require_login)):
    try:
        spec = _make_spec(req)
        q    = build_quotation(spec)
        return _quotation_to_dict(q)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quote/standalone")
async def quote_standalone(req: StandaloneRequest, _: dict = Depends(require_login)):
    result = quote_standalone_equipment(req.category, req.model)
    return result


@app.post("/api/quote/download/xlsx")
async def download_xlsx(req: QuoteRequest, _: dict = Depends(require_login)):
    spec = _make_spec(req)
    q    = build_quotation(spec)
    slug = req.client_name.replace(" ", "_").replace("/", "-")[:30]
    path = TMP / f"{slug}_{req.tph}TPH_PriceSchedule.xlsx"
    build_workbook(q, str(path))
    return FileResponse(
        path        = str(path),
        filename    = path.name,
        media_type  = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.post("/api/quote/download/docx")
async def download_docx(req: QuoteRequest, _: dict = Depends(require_login)):
    spec = _make_spec(req)
    q    = build_quotation(spec)
    slug = req.client_name.replace(" ", "_").replace("/", "-")[:30]
    path = TMP / f"{slug}_{req.tph}TPH_OfferLetter.docx"
    build_offer_letter(q, str(path))
    return FileResponse(
        path        = str(path),
        filename    = path.name,
        media_type  = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.post("/api/quote/standalone/download/docx")
async def download_standalone_docx(req: StandaloneRequest, _: dict = Depends(require_login)):
    slug = req.client_name.replace(" ", "_").replace("/", "-")[:30]
    ref  = req.ref_no or f"PR/{date.today().strftime('%m-%y')}/N-SA"
    path = TMP / f"{slug}_{req.category}{req.model}_Offer.docx"
    build_standalone_letter(req.category, req.model, req.client_name, ref, str(path))
    return FileResponse(
        path        = str(path),
        filename    = path.name,
        media_type  = "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/api/rate-card/equipment")
async def get_equipment_list(_: dict = Depends(require_login)):
    """Return available models from rate card for UI dropdowns."""
    return {
        "vgf":    list(rc.VGF.keys()),
        "jaw":    list(rc.JAW.keys()),
        "cone":   list(rc.CONE.keys()),
        "vsi":    list(rc.VSI.keys()),
        "screen": list(rc.SCREEN.keys()),
        "wsg":    list(rc.WSG.keys()),
    }


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.2.0"}


# ---------------------------------------------------------------------------
# MASTERS ENDPOINTS
# ---------------------------------------------------------------------------

class MasterSaveRequest(BaseModel):
    data: dict
    updated_by: str = "web_user"


@app.get("/api/masters/{name}")
async def get_master(name: str, _: dict = Depends(require_login)):
    if name not in mm.MASTER_NAMES:
        raise HTTPException(404, f"Unknown master '{name}'. Valid: {mm.MASTER_NAMES}")
    return mm.load(name)


@app.put("/api/masters/{name}")
async def save_master(name: str, req: MasterSaveRequest, admin: dict = Depends(require_admin)):
    if name not in mm.MASTER_NAMES:
        raise HTTPException(404, f"Unknown master '{name}'.")
    try:
        req.updated_by = admin["username"]
        saved = mm.save(name, req.data, updated_by=req.updated_by)
        return {"status": "saved", "name": name, "meta": saved.get("_meta", {})}
    except Exception as e:
        raise HTTPException(500, str(e))


# Convenience flat-list endpoints for UI tables
@app.get("/api/masters/footprints/flat")
async def footprints_flat(_: dict = Depends(require_login)):
    return mm.get_all_footprints_flat()

@app.get("/api/masters/materials/list")
async def materials_list(_: dict = Depends(require_login)):
    return mm.get_all_materials_list()

@app.get("/api/masters/gradations/list")
async def gradations_list(_: dict = Depends(require_login)):
    return mm.get_all_gradations_list()

@app.get("/api/masters/stages/list")
async def stages_list(_: dict = Depends(require_login)):
    master = mm.load("stages")
    return [{"stage": k, **v} for k, v in master.items() if not k.startswith("_")]

@app.get("/masters", response_class=HTMLResponse)
async def masters_ui(current_user: dict = Depends(require_admin)):
    masters_page = STATIC / "masters.html"
    if masters_page.exists():
        return masters_page.read_text()
    return HTMLResponse("<h2>masters.html not found in static/</h2>", status_code=404)


# ---------------------------------------------------------------------------
# 3D LAYOUT + BOM ENDPOINTS
# ---------------------------------------------------------------------------

def _compute_plant_positions(schedule: dict, spec: "PlantSpec | None" = None) -> list:
    """
    Compute 3D positions (x,y,z) and visual properties for each equipment item.
    When `spec` is provided, platform elevations are read from PlantSpec geometry
    fields so the 3D view stays consistent with the cost engine.
    """
    items = []
    x     = 0.0
    stages = schedule["stages"]

    # ── Resolve elevations ──────────────────────────────────────────────────
    # Prefer spec fields; fall back to sensible fixed defaults so the viewer
    # works even when called from the generic /api/layout/3d-data endpoint
    # (which doesn't have a pre-configured PlantSpec).
    def _el(attr: str, default: float) -> float:
        return getattr(spec, attr, default) if spec else default

    el_cone    = _el("elevation_cone",      5.5)
    el_prescrn = _el("elevation_prescreen", 5.0)
    el_surge2  = _el("elevation_surge2",    3.0)
    el_vsi     = _el("elevation_vsi",       7.5)
    el_screen  = _el("elevation_screen",    4.5)

    # ── Horizontal spacing ──────────────────────────────────────────────────
    def _sp(attr: str, default: float) -> float:
        if spec:
            v = getattr(spec, attr, None)
            return v if v is not None else default
        return default

    dx_h2j   = _sp("spacing_hopper_to_jaw",   8.0)
    dx_j2c   = _sp("spacing_jaw_to_cone",      14.0)
    dx_c2sc  = _sp("spacing_cone_to_screen",   12.0)
    dx_c2v   = _sp("spacing_cone_to_vsi",      12.0)
    dx_v2sc  = _sp("spacing_vsi_to_screen",    10.0)

    # ROM Hopper
    items.append({"id":"hopper","category":"HOPPER","label":"ROM Hopper",
        "model":"40T Surge Hopper","pos":[x, 0, 0],"size":[3.5, 5, 4.5],
        "color":"#D97706","stage":0,"elevation":0,"bom_include":False})
    x += dx_h2j

    # VGF
    vgf = schedule["vgf"]
    items.append({"id":"vgf","category":"VGF","label":vgf["model"],
        "model":vgf["model"],"pos":[x, 0.5, 0],"size":[5, 1, 1.5],
        "color":"#F59E0B","stage":1,"elevation":0,"bom_include":True,
        "specs":f"Feed cap: {vgf.get('feed_capacity_mtph')} mt/h | Max feed: {vgf.get('max_feed_mm')}mm"})
    x += 10

    # JAW
    jaw = schedule["jaw"]
    items.append({"id":"jaw","category":"JAW","label":jaw["model"],
        "model":jaw["model"],"pos":[x, 1.5, 0],"size":[4, 3, 3],
        "color":"#DC2626","stage":1,"elevation":0,"bom_include":True,
        "specs":f"CSS: {jaw.get('css_mm')}mm"})
    x += dx_j2c

    # Surge Bin 1
    items.append({"id":"surge1","category":"BIN","label":"Surge Bin 1",
        "model":"Surge Bin 30T","pos":[x, 0, 0],"size":[2.5, 4, 2.5],
        "color":"#6B7280","stage":1,"elevation":0,"bom_include":True,
        "specs":"30T capacity"})
    x += 8

    if schedule.get("cone"):
        cone = schedule["cone"]
        items.append({"id":"cone","category":"CONE","label":cone["model"],
            "model":cone["model"],"pos":[x, el_cone, 0],"size":[3.5, 3.5, 3.5],
            "color":"#2563EB","stage":2,"elevation":el_cone,"bom_include":True,
            "specs":f"CSS: {cone.get('css_mm')}mm {'| Twin unit' if cone.get('twin') else ''}"})
        x += dx_c2sc

        if stages >= 3 and schedule.get("vsi"):
            int_scr = (schedule["screens"] or {}).get("intermediate")
            if int_scr:
                items.append({"id":"screen_int","category":"SCREEN",
                    "label":int_scr["model"],"model":int_scr["model"],
                    "pos":[x, el_prescrn, 0],"size":[6, 2, 2.8],
                    "color":"#059669","stage":2,"elevation":el_prescrn,"bom_include":True,
                    "specs":f"{int_scr.get('decks',3)}-Deck intermediate"})
                x += 12

            # Surge Bin 2
            items.append({"id":"surge2","category":"BIN","label":"Surge Bin 2",
                "model":"Surge Bin 15T","pos":[x, el_surge2, 0],"size":[2, 3.5, 2],
                "color":"#6B7280","stage":2,"elevation":el_surge2,"bom_include":True,
                "specs":"15T capacity"})
            x += 7

            vsi = schedule["vsi"]
            items.append({"id":"vsi","category":"VSI","label":vsi["model"],
                "model":vsi["model"],"pos":[x, el_vsi, 0],"size":[2.8, 2.5, 2.8],
                "color":"#7C3AED","stage":3,"elevation":el_vsi,"bom_include":True,
                "specs":f"Max feed: {vsi.get('max_feed_mm')}mm | {vsi.get('motor_hp','')} HP"})
            x += dx_v2sc

    # Final screen
    fin_scr = (schedule["screens"] or {}).get("final")
    if fin_scr:
        cuts = ", ".join(str(c) for c in schedule["gradation"]["cuts_mm"])
        items.append({"id":"screen_final","category":"SCREEN",
            "label":fin_scr["model"],"model":fin_scr["model"],
            "pos":[x, el_screen, 0],"size":[7, 2.4, 2.8],
            "color":"#059669","stage":stages,"elevation":el_screen,"bom_include":True,
            "specs":f"{fin_scr.get('decks',4)}-Deck | Cuts: {cuts}mm"})
        x += 12

    # Stockpile area marker
    items.append({"id":"stockpile","category":"STOCKPILE","label":"Product Stockpiles",
        "model":"Conical Stockpile","pos":[x, 0, 0],"size":[8, 0.1, 12],
        "color":"#92400E","stage":stages,"elevation":0,"bom_include":False,
        "stockpile":True})

    # Compute plant footprint
    schedule["_plant_length_m"] = round(x, 1)
    return items


def _build_bom(schedule: dict, positions: list) -> list:
    """Structured BOM from equipment positions."""
    stage_labels = {
        0:"Feed", 1:"Stage 1 — Primary", 2:"Stage 2 — Secondary",
        3:"Stage 3 — Tertiary VSI"
    }
    bom, sl = [], 1
    for item in positions:
        if not item.get("bom_include"):
            continue
        qty = 2 if (item.get("category") == "CONE" and schedule.get("cone",{}).get("twin")) else 1
        bom.append({"sl":sl,"stage":stage_labels.get(item["stage"],f"Stage {item['stage']}"),
            "category":item["category"],"description":item["label"],
            "model":item["model"],"qty":qty,"specs":item.get("specs","")})
        sl += 1
    # Conveyors — calibrated from PROMAN layout drawings (3-stage = 16 belts)
    conv_count = {1:6,2:12,3:16}.get(schedule["stages"],12)
    bom.append({"sl":sl,"stage":"Conveyor System","category":"CONVEYOR",
        "description":"Belt Conveyor (various)","model":"Rubber Belt Conveyor",
        "qty":conv_count,"specs":"Width: 600/800/1000mm"})
    sl += 1
    bom.append({"sl":sl,"stage":"Electrical","category":"ELECTRICAL",
        "description":"MCC Panel + Motor Cables","model":"Motor Control Centre",
        "qty":1,"specs":f"Est. {schedule.get('_total_hp','—')} HP connected load"})
    return bom


@app.get("/api/layout/3d-data")
async def get_3d_layout_data(
    tph: int, stages: int = 2, material: str = "Granite",
    _: dict = Depends(require_login)
):
    """Return equipment schedule with 3D positions and deep procurement BOM."""
    schedule = build_equipment_schedule(tph, stages, material)
    positions = _compute_plant_positions(schedule)
    bom = _build_bom(schedule, positions)
    proc_bom = build_procurement_bom(schedule, tph, stages)
    return {"tph": tph, "stages": stages, "material": material,
            "schedule": schedule, "positions": positions, "bom": bom,
            "procurement_bom": proc_bom,
            "plant_length_m": schedule.get("_plant_length_m", 0)}


@app.get("/quotes", response_class=HTMLResponse)
async def quotes_page(_: dict = Depends(require_login)):
    """Serve the standard quotation dashboard."""
    p = STATIC / "quotes.html"
    return HTMLResponse(content=p.read_text())


@app.get("/api/quotes/list")
async def list_quotes(_: dict = Depends(require_login)):
    """Return metadata for all 7 standard configurations (no pricing computed)."""
    return [
        {
            "key":      k,
            "label":    v["label"],
            "tph":      v["tph"],
            "stages":   v["stages"],
            "material": v["material"],
            "belts":    v.get("conveyor_count"),
            "area":     v.get("area_m2"),
            "pfd_url":  v.get("pfd_url"),
            "warnings": v.get("warnings", []),
        }
        for k, v in ALL_CONFIGS.items()
    ]


@app.get("/api/quotes/summary")
async def quote_summary(config: str, _: dict = Depends(require_login)):
    """
    Return a lightweight summary (total HP, best price total) for one config.
    Runs the engine but does NOT write any file — used to populate card chips on the UI.
    """
    try:
        cfg = get_config(config)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    spec = cfg["spec"]
    try:
        if getattr(spec, "_tertiary_only", False):
            q = build_tertiary_quotation(spec)
        else:
            q = build_quotation(spec)

        best = q.grand_total_best()
        return {
            "config":      config,
            "total_hp":    q.total_hp(),
            "best_price":  best if best > 0 else None,
            "list_price":  q.grand_total_list() or None,
            "sub_a_best":  q.sub_a_best(),
            "warnings":    q.warnings,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Engine error: {exc}")


@app.get("/api/quotes/excel")
async def download_quote_excel(
    config: str,
    client: str = "Enquiry Client",
    _: dict = Depends(require_login),
):
    """
    Generate and download a price schedule Excel for one of the 7 standard configs.
    Query param: config=150_2s | 150_3s | 250_2s | 250_3s | 300_3s | 600_3s | vsi5080
    Optional:    client=<client name> (appears in sheet header)
    """
    import io, tempfile
    from generate_xlsx import build_workbook

    try:
        cfg_meta = get_config(config)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    spec = cfg_meta["spec"]
    # Override client name if supplied — use dataclasses.replace for a clean copy
    if client and client != "Enquiry Client":
        import dataclasses
        spec = dataclasses.replace(spec, client_name=client)

    try:
        if getattr(spec, "_tertiary_only", False):
            q = build_tertiary_quotation(spec)
        else:
            q = build_quotation(spec)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Engine error: {exc}")

    # Write to temp file then stream back
    tmp = TMP / f"PROMAN_{config}_{date.today().strftime('%Y%m%d')}.xlsx"
    try:
        build_workbook(q, str(tmp))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Excel build error: {exc}")

    safe_config = config.replace("/", "-").replace(" ", "_")
    fname = f"PROMAN_{safe_config}_{spec.tph}TPH_{date.today().strftime('%d%b%Y')}.xlsx"
    return FileResponse(
        str(tmp),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.get("/pfd/{tph}/{stages}", response_class=HTMLResponse)
async def get_pfd(
    tph: int,
    stages: int,
    material: str = "Granite",
    _: dict = Depends(require_login),
):
    """
    Serve an interactive SVG Process Flow Diagram for the given plant configuration.

    stages=0  → Tertiary standalone VSI plant (no jaw/cone)
    stages=2  → 2-stage plant (jaw + cone + screen)
    stages=3  → 3-stage plant (jaw + cone + VSI + screens)
    """
    if stages == 0:
        schedule = build_tertiary_schedule(tph, material)
    else:
        schedule = build_equipment_schedule(tph, stages, material)
    html_content = generate_pfd_html(schedule, tph, stages, material)
    return HTMLResponse(content=html_content)


@app.get("/api/layout/bom-excel")
async def download_bom_excel(
    tph: int, stages: int = 2, material: str = "Granite", client: str = "Client",
    _: dict = Depends(require_login)
):
    """Download deep multi-sheet procurement BOM as Excel."""
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

    schedule = build_equipment_schedule(tph, stages, material)
    proc = build_procurement_bom(schedule, tph, stages)

    wb = openpyxl.Workbook()

    navy_hex  = "1F3864"
    green_hex = "1E4620"
    navy  = PatternFill("solid", fgColor=navy_hex)
    green = PatternFill("solid", fgColor=green_hex)
    wht   = Font(color="FFFFFF", bold=True, size=10)
    thin  = Side(style="thin", color="CBD5E1")
    bdr   = Border(left=thin, right=thin, top=thin, bottom=thin)

    CAT_COLOR = {
        "HOPPER":"FEF3C7","VGF":"FEF3C7","JAW":"FEE2E2","CONE":"DBEAFE",
        "VSI":"EDE9FE","SCREEN":"D1FAE5","BIN":"F8FAFC","CONVEYOR":"FFF7ED",
        "FEEDER":"FFF7ED","MOTOR":"E0F2FE","DRIVE":"E0F2FE","LUBE":"FEF3C7",
        "ELECTRICAL":"EDE9FE","INSTRUMENT":"E0F2FE",
        "WEAR_PARTS":"FEF2F2","CONSUMABLE":"FFF7ED","STRUCTURAL":"F0FDF4",
    }

    def col_letter(n): return chr(64 + n)

    def write_title(ws, title, cols):
        ws.merge_cells(f"A1:{col_letter(cols)}1")
        ws["A1"] = title
        ws["A1"].font = Font(bold=True, size=12, color=navy_hex)
        ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 24

    def write_headers(ws, headers, row=2, fill=navy):
        for ci, h in enumerate(headers, 1):
            c = ws.cell(row=row, column=ci, value=h)
            c.fill = fill; c.font = wht
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = bdr
        ws.row_dimensions[row].height = 20

    def write_rows(ws, rows, start_row, color_key_col=None, color_map=None):
        for ri, row in enumerate(rows, start_row):
            cat = row.get("category","")
            bg  = (color_map or CAT_COLOR).get(cat, "FFFFFF")
            fill = PatternFill("solid", fgColor=bg)
            for ci, v in enumerate(row.values(), 1):
                c = ws.cell(row=ri, column=ci, value=v)
                c.fill = fill; c.border = bdr
                c.alignment = Alignment(wrap_text=True, vertical="center")
            ws.row_dimensions[ri].height = 15

    def freeze_and_autofit(ws, freeze="A3"):
        ws.freeze_panes = freeze

    note_font = Font(italic=True, size=9, color="64748B")

    # ── SHEET 0: COVER ──────────────────────────────────────────────
    ws0 = wb.active; ws0.title = "Cover"
    stats = proc["summary_stats"]
    rows_cover = [
        ("PROMAN — Deep Procurement BOM",""),
        (f"Client","  {client}"),
        (f"Capacity","  {tph} TPH"),
        (f"Stages","  {stages}-Stage"),
        (f"Material","  {material}"),
        ("",""),
        ("Total Structural Steel",f"  {stats['total_structural_mt']} MT"),
        ("Belt Width",f"  {stats['belt_width_mm']}mm"),
        ("Conveyor Count",f"  {stats['conveyor_count']} belts"),
        ("Est. Connected Load",f"  {int(stats['est_connected_kw'])} kW"),
        ("",""),
        ("Sheets","  1-Manufactured | 2-Bought-Out | 3-Wear Parts | 4-Consumables | 5-Structural | 6-Conveyor Components"),
        ("Note","  All quantities are indicative. Confirm with PROMAN Engineering."),
    ]
    ws0.column_dimensions["A"].width = 28
    ws0.column_dimensions["B"].width = 70
    ws0.merge_cells("A1:B1")
    ws0["A1"] = "PROMAN — Deep Procurement Bill of Materials"
    ws0["A1"].font = Font(bold=True, size=14, color=navy_hex)
    ws0["A1"].alignment = Alignment(horizontal="center"); ws0.row_dimensions[1].height = 28
    for ri, (k, v) in enumerate(rows_cover[1:], 2):
        ws0.cell(row=ri, column=1, value=k).font = Font(bold=True, size=11)
        ws0.cell(row=ri, column=2, value=v).font  = Font(size=11)
        ws0.row_dimensions[ri].height = 16

    # ── SHEET 1: MANUFACTURED ───────────────────────────────────────
    ws1 = wb.create_sheet("1-Manufactured")
    hdrs = ["Sl","Category","Description","Model / Spec","Qty","Unit","Technical Specs"]
    write_title(ws1, f"Main Manufactured Equipment — {tph}TPH {stages}-Stage | {material}", len(hdrs))
    write_headers(ws1, hdrs)
    for ri, item in enumerate(proc["manufactured"], 3):
        vals = [item["sl"],item["category"],item["description"],item["model"],item["qty"],item["unit"],item["specs"]]
        bg = CAT_COLOR.get(item["category"],"FFFFFF")
        fill = PatternFill("solid",fgColor=bg)
        for ci,v in enumerate(vals,1):
            c=ws1.cell(row=ri,column=ci,value=v); c.fill=fill; c.border=bdr
            c.alignment=Alignment(wrap_text=True,vertical="center")
        ws1.row_dimensions[ri].height=15
    for w,col in zip([5,14,32,28,6,8,50],range(1,8)): ws1.column_dimensions[col_letter(col)].width=w
    freeze_and_autofit(ws1)

    # ── SHEET 2: BOUGHT-OUT ─────────────────────────────────────────
    ws2 = wb.create_sheet("2-Bought-Out")
    hdrs2 = ["Sl","Category","Description","Model / Spec","Qty","Unit","Technical Specs"]
    write_title(ws2, f"Bought-Out Items (Motors, Drives, Electrical) — {tph}TPH {stages}-Stage", len(hdrs2))
    write_headers(ws2, hdrs2)
    for ri, item in enumerate(proc["bought_out"], 3):
        vals = [item["sl"],item["category"],item["description"],item["model"],item["qty"],item["unit"],item["specs"]]
        bg = CAT_COLOR.get(item["category"],"FFFFFF")
        fill = PatternFill("solid",fgColor=bg)
        for ci,v in enumerate(vals,1):
            c=ws2.cell(row=ri,column=ci,value=v); c.fill=fill; c.border=bdr
            c.alignment=Alignment(wrap_text=True,vertical="center")
        ws2.row_dimensions[ri].height=15
    for w,col in zip([5,14,32,28,6,8,55],range(1,8)): ws2.column_dimensions[col_letter(col)].width=w
    freeze_and_autofit(ws2)

    # ── SHEET 3: WEAR PARTS ─────────────────────────────────────────
    ws3 = wb.create_sheet("3-Wear Parts")
    hdrs3 = ["Sl","Equipment","Wear Item","Material Spec","Qty","Unit","Wt (kg)","Life (hrs)","Notes"]
    write_title(ws3, f"Wear Parts — Initial Supply (2 Sets) — {tph}TPH {stages}-Stage | {material}", len(hdrs3))
    write_headers(ws3, hdrs3)
    for ri, item in enumerate(proc["wear_parts"], 3):
        vals = [item["sl"],item["equipment"],item["item"],item["material"],
                item["qty"],item["unit"],item["wt_kg"],item["life_hrs"],item["note"]]
        bg = "FEF2F2"
        fill = PatternFill("solid",fgColor=bg)
        for ci,v in enumerate(vals,1):
            c=ws3.cell(row=ri,column=ci,value=v); c.fill=fill; c.border=bdr
            c.alignment=Alignment(wrap_text=True,vertical="center")
        ws3.row_dimensions[ri].height=14
    for w,col in zip([5,18,32,24,6,8,10,12,28],range(1,10)): ws3.column_dimensions[col_letter(col)].width=w
    freeze_and_autofit(ws3)

    # ── SHEET 4: CONSUMABLES ────────────────────────────────────────
    ws4 = wb.create_sheet("4-Consumables")
    hdrs4 = ["Sl","Item","Material / Grade","Qty","Unit","Notes"]
    write_title(ws4, f"Consumables (Lubricants, Filters, Seals) — {tph}TPH {stages}-Stage", len(hdrs4))
    write_headers(ws4, hdrs4)
    for ri, item in enumerate(proc["consumables"], 3):
        vals = [item["sl"],item["item"],item["material"],item["qty"],item["unit"],item["note"]]
        bg = "FFF7ED"
        fill = PatternFill("solid",fgColor=bg)
        for ci,v in enumerate(vals,1):
            c=ws4.cell(row=ri,column=ci,value=v); c.fill=fill; c.border=bdr
            c.alignment=Alignment(wrap_text=True,vertical="center")
        ws4.row_dimensions[ri].height=14
    for w,col in zip([5,42,28,8,10,38],range(1,7)): ws4.column_dimensions[col_letter(col)].width=w
    freeze_and_autofit(ws4)

    # ── SHEET 5: STRUCTURAL STEEL ───────────────────────────────────
    ws5 = wb.create_sheet("5-Structural")
    hdrs5 = ["Sl","Section","Item","Profile / Grade","Qty","Unit","Notes"]
    write_title(ws5, f"Structural Steel & Fabrication — Est. {stats['total_structural_mt']} MT Total | {tph}TPH {stages}-Stage", len(hdrs5))
    write_headers(ws5, hdrs5)
    for ri, item in enumerate(proc["structural"], 3):
        vals = [item["sl"],item["section"],item["item"],item["profile"],item["qty_mt"],item["unit"],item.get("note","")]
        bg = "F0FDF4"
        fill = PatternFill("solid",fgColor=bg)
        for ci,v in enumerate(vals,1):
            c=ws5.cell(row=ri,column=ci,value=v); c.fill=fill; c.border=bdr
            c.alignment=Alignment(wrap_text=True,vertical="center")
        ws5.row_dimensions[ri].height=14
    for w,col in zip([5,30,32,24,10,8,32],range(1,8)): ws5.column_dimensions[col_letter(col)].width=w
    freeze_and_autofit(ws5)

    # ── SHEET 6: CONVEYOR COMPONENTS ────────────────────────────────
    ws6 = wb.create_sheet("6-Conveyor")
    hdrs6 = ["Sl","Conveyor","Component","Qty","Unit","Notes"]
    write_title(ws6, f"Conveyor Components (Per Conveyor Breakdown) — {stats['conveyor_count']} Conveyors | {stats['belt_width_mm']}mm belt", len(hdrs6))
    write_headers(ws6, hdrs6)
    prev_conv = None
    for ri, item in enumerate(proc["conveyor_components"], 3):
        is_new = item["conveyor"] != prev_conv
        bg = "FFF7ED" if not is_new else "FED7AA"
        fill = PatternFill("solid",fgColor=bg)
        vals = [item["sl"],item["conveyor"],item["item"],item["qty"],item["unit"],item["note"]]
        for ci,v in enumerate(vals,1):
            c=ws6.cell(row=ri,column=ci,value=v); c.fill=fill; c.border=bdr
            c.alignment=Alignment(wrap_text=True,vertical="center")
        ws6.row_dimensions[ri].height=14
        prev_conv = item["conveyor"]
    for w,col in zip([5,32,42,8,8,28],range(1,7)): ws6.column_dimensions[col_letter(col)].width=w
    freeze_and_autofit(ws6)

    out = TMP / f"DeepBOM_{client}_{tph}TPH_{stages}STG.xlsx"
    wb.save(str(out))
    filename = f"DeepBOM_{client}_{tph}TPH_{stages}STG.xlsx"
    return FileResponse(str(out),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/layout3d", response_class=HTMLResponse)
async def layout3d_page(_: dict = Depends(require_login)):
    p = STATIC / "layout3d.html"
    return p.read_text() if p.exists() else HTMLResponse("<h2>layout3d.html not found</h2>", 404)


# ---------------------------------------------------------------------------
# BELT CONVEYOR DRAWING ENDPOINTS
# ---------------------------------------------------------------------------

@app.get("/conveyor-drawing", response_class=HTMLResponse)
async def conveyor_drawing_page(_: dict = Depends(require_login)):
    p = STATIC / "conveyor-drawing.html"
    return p.read_text() if p.exists() else HTMLResponse("<h2>conveyor-drawing.html not found</h2>", 404)


@app.get("/api/conveyor-drawing/belts")
async def get_conveyor_belts(
    tph: int = 300,
    stages: int = 3,
    material: str = "granite",
    _: dict = Depends(require_login)
):
    """Return belt conveyor specs with drawing parameters for the given plant config."""
    from engine.engine import build_quotation
    spec = _make_spec_from_params(tph, stages, material)
    q = build_quotation(spec)

    belts = []
    for c in q.sub_b_conveyors:
        horiz_m = c.length_m  # length_m is already slant/true length; approximate horizontal
        # Derive inclination from purpose tag
        incline_deg = _infer_inclination(c.purpose)
        true_len = c.length_m
        horiz_m = round(true_len * math.cos(math.radians(incline_deg)), 1)
        rise_m  = round(true_len * math.sin(math.radians(incline_deg)), 1)

        belt = {
            "tag":           c.tag,
            "purpose":       c.purpose,
            "width_mm":      c.width_mm,
            "length_m":      true_len,
            "horiz_m":       horiz_m,
            "rise_m":        rise_m,
            "incline_deg":   incline_deg,
            "hp":            c.hp,
            "motor_kw":      round(c.hp * 0.7457, 1),
            # derived drawing parameters
            "head_pulley_dia_mm":  _head_pulley_dia(c.width_mm),
            "tail_pulley_dia_mm":  _tail_pulley_dia(c.width_mm),
            "snub_pulley_dia_mm":  _snub_pulley_dia(c.width_mm),
            "bend_pulley_dia_mm":  _bend_pulley_dia(c.width_mm),
            "carrying_idler_pitch_mm":  _idler_pitch(c.width_mm, "carry"),
            "return_idler_pitch_mm":    _idler_pitch(c.width_mm, "return"),
            "impact_idler_pitch_mm":    150,
            "troughing_angle_deg": 35,
            "belt_speed_mps":      _belt_speed(c.width_mm, tph),
            "skirt_length_m":      min(3.0, round(true_len * 0.15, 1)),
            "take_up_type":        "gravity" if true_len > 30 else "screw",
            "take_up_travel_mm":   _take_up_travel(true_len),
            "num_idler_sets":      int(horiz_m / (_idler_pitch(c.width_mm, "carry") / 1000)) + 1,
            "frame_type":          "truss" if true_len > 20 else "channel",
            "cost_lakhs":          c.cost_lakhs,
        }
        belts.append(belt)

    return {"tph": tph, "stages": stages, "material": material, "belts": belts}


def _make_spec_from_params(tph: int, stages: int, material: str):
    """Build a PlantSpec from basic params (no override fields)."""
    from engine.quotation_configs import get_spec
    try:
        return get_spec(tph, stages)
    except Exception:
        from engine.engine import PlantSpec
        return PlantSpec(client_name="drawing", tph=tph, stages=stages, material=material)


def _infer_inclination(purpose: str) -> float:
    """Infer typical inclination angle from conveyor purpose tag."""
    p = purpose.lower()
    if "reclaim" in p or "hopper" in p or "feeder" in p:
        return 0.0
    if "product" in p or "stacker" in p or "stock" in p:
        return 12.0
    if "jaw_to" in p or "to_cone" in p or "to_screen" in p or "to_vsi" in p:
        return 18.0
    if "surge" in p and "from" in p:
        return 0.0
    if "oversize" in p or "return" in p or "recircul" in p:
        return 16.0
    if "under" in p:
        return 0.0
    return 14.0  # typical inclined


def _head_pulley_dia(w: int) -> int:
    return {500: 400, 650: 500, 800: 630, 1000: 800, 1200: 1000}.get(w, 630)

def _tail_pulley_dia(w: int) -> int:
    return {500: 315, 650: 400, 800: 500, 1000: 630, 1200: 800}.get(w, 500)

def _snub_pulley_dia(w: int) -> int:
    return {500: 250, 650: 315, 800: 400, 1000: 500, 1200: 630}.get(w, 315)

def _bend_pulley_dia(w: int) -> int:
    return {500: 250, 650: 315, 800: 400, 1000: 500, 1200: 630}.get(w, 315)

def _idler_pitch(w: int, kind: str) -> int:
    if kind == "return":
        return {500: 3000, 650: 3000, 800: 3000, 1000: 3000, 1200: 3000}.get(w, 3000)
    # carrying idler pitch (mm)
    return {500: 1200, 650: 1200, 800: 1000, 1000: 1000, 1200: 900}.get(w, 1200)

def _belt_speed(w: int, tph: int) -> float:
    # approximate belt speed (m/s) for given width and capacity
    if w <= 500:  return 1.25
    if w <= 650:  return 1.5
    if w <= 800:  return 1.75 if tph <= 200 else 2.0
    if w <= 1000: return 2.0  if tph <= 400 else 2.5
    return 2.5

def _take_up_travel(length_m: float) -> int:
    # gravity take-up travel = ~1.5% of centre-to-centre, min 500mm
    return max(500, int(length_m * 0.015 * 1000))


# ---------------------------------------------------------------------------
# BUNDLE QUOTE ENDPOINTS
# ---------------------------------------------------------------------------

@app.post("/api/quote/bundle")
async def quote_bundle(req: BundleRequest, _: dict = Depends(require_login)):
    """Quote any mix of equipment + conveyors (no full plant required)."""
    try:
        spec = BundleSpec(
            client_name     = req.client_name,
            ref_no          = req.ref_no or f"PR/{date.today().strftime('%m-%y')}/B-{str(uuid.uuid4())[:4].upper()}",
            date            = req.date or date.today().strftime("%d-%m-%Y"),
            equipment       = [BundleEquipmentItem(e.category, e.model, e.qty, e.note) for e in req.equipment],
            conveyors       = [BundleConveyorItem(c.width_mm, c.length_m, c.qty, c.note) for c in req.conveyors],
            include_chutes  = req.include_chutes,
            include_erection= req.include_erection,
            erection_lump   = req.erection_lump,
        )
        q = build_bundle_quotation(spec)
        return _quotation_to_dict(q)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quote/bundle/download/xlsx")
async def download_bundle_xlsx(req: BundleRequest):
    spec = BundleSpec(
        client_name     = req.client_name,
        ref_no          = req.ref_no or f"PR/{date.today().strftime('%m-%y')}/B-001",
        date            = req.date or date.today().strftime("%d-%m-%Y"),
        equipment       = [BundleEquipmentItem(e.category, e.model, e.qty, e.note) for e in req.equipment],
        conveyors       = [BundleConveyorItem(c.width_mm, c.length_m, c.qty, c.note) for c in req.conveyors],
        include_chutes  = req.include_chutes,
        include_erection= req.include_erection,
        erection_lump   = req.erection_lump,
    )
    q   = build_bundle_quotation(spec)
    slug = req.client_name.replace(" ", "_").replace("/", "-")[:30]
    path = TMP / f"{slug}_Bundle_PriceSchedule.xlsx"
    build_workbook(q, str(path))
    return FileResponse(path=str(path), filename=path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ---------------------------------------------------------------------------
# TPH INFERENCE ENDPOINT
# ---------------------------------------------------------------------------

@app.post("/api/infer-tph")
async def api_infer_tph(req: InferTPHRequest):
    """Estimate TPH range from available equipment models / context."""
    result = infer_tph(
        jaw_model    = req.jaw_model,
        cone_model   = req.cone_model,
        vsi_model    = req.vsi_model,
        feed_size_mm = req.feed_size_mm,
        material     = req.material,
        stages       = req.stages,
    )
    return result


@app.post("/api/quote/smart")
async def smart_quote(req: QuoteNoTPHRequest):
    """
    Quote with optional TPH. If tph=0 or missing, auto-infers from
    selected equipment models and material context.
    """
    try:
        tph = req.tph
        infer_result = None

        if not tph:
            infer_result = infer_tph(
                jaw_model    = req.jaw_model,
                cone_model   = req.cone_model,
                vsi_model    = req.vsi_model,
                feed_size_mm = req.feed_size_mm,
                material     = req.material,
                stages       = req.stages,
            )
            tph = infer_result["tph_mid"]

        req.tph = tph
        spec = _make_spec(req)
        q    = build_quotation(spec)

        result = _quotation_to_dict(q)
        if infer_result:
            result["tph_inferred"] = infer_result
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# ERPNEXT INTEGRATION ENDPOINTS
# ---------------------------------------------------------------------------

class ERPNextLeadWebhookRequest(BaseModel):
    """
    Payload ERPNext sends via Webhook (Settings → Webhooks).
    ERPNext sends the full Lead document as JSON.
    Set the Webhook URL to: https://your-render-url/api/erpnext/webhook
    """
    doc: dict                          # full Lead document
    doctype: str = "Lead"
    event: str = "on_submit"
    auto_push_back: bool = True        # update Lead fields after quoting


class ERPNextFromLeadRequest(BaseModel):
    """Manual: pass a lead_id to fetch from ERPNext and quote it."""
    lead_id: str
    auto_push_back: bool = True


class ERPNextDirectQuoteRequest(BaseModel):
    """
    Quote using a Lead dict directly (no ERPNext connection needed).
    Useful for testing or when ERPNext is on a private network.
    """
    lead: dict
    auto_push_back: bool = False


def _quote_from_parsed(parsed: dict, triage_result: dict = None) -> dict:
    """
    Given a parsed lead dict, run triage + quote and return combined result.
    """
    enquiry  = parsed["enquiry"]
    triage   = triage_result or triage_enquiry(enquiry)
    action   = triage.get("action", "")

    result = {
        "lead_id":      parsed["lead_id"],
        "client_name":  parsed["client_name"],
        "triage":       triage,
        "quotation":    None,
    }

    if action in ("quote", "quote_standalone", "quote_with_structural_addon"):
        try:
            # Prefer explicit TPH from lead; else infer
            tph = parsed.get("tph") or triage.get("detected_tph") or 0
            stages = parsed.get("stages") or 3

            if not tph:
                infer = infer_tph(stages=stages)
                tph   = infer["tph_mid"]
                result["tph_inferred"] = infer

            ref = (parsed.get("ref_no")
                   or f"PR/{date.today().strftime('%m-%y')}/CRM-{parsed['lead_id'][-4:]}")

            spec = PlantSpec(
                client_name = parsed["client_name"],
                tph         = tph,
                stages      = stages,
                mobile      = triage.get("detected_mobile", False),
                ref_no      = ref,
                date        = date.today().strftime("%d-%m-%Y"),
            )
            q = build_quotation(spec)
            result["quotation"] = _quotation_to_dict(q)
        except Exception as e:
            result["quote_error"] = str(e)

    return result


@app.post("/api/erpnext/webhook")
async def erpnext_webhook(req: ERPNextLeadWebhookRequest):
    """
    ERPNext Webhook receiver.
    Configure in ERPNext: Settings → Webhooks → New
      DocType: Lead
      Events:  on_update, after_insert
      URL:     https://<render-url>/api/erpnext/webhook
      Request Structure: Form Data (JSON body)
    """
    try:
        lead   = req.doc
        parsed = parse_lead_payload(lead)
        result = _quote_from_parsed(parsed)

        if req.auto_push_back and result.get("quotation"):
            try:
                push_quote_to_lead(
                    parsed["lead_id"],
                    result["quotation"],
                    result.get("triage"),
                )
                result["pushed_to_erpnext"] = True
            except Exception as e:
                result["push_error"] = str(e)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/erpnext/from-lead")
async def erpnext_from_lead(req: ERPNextFromLeadRequest):
    """
    Fetch a Lead from ERPNext by ID, triage it, generate quote,
    and optionally push the summary back to ERPNext.
    Requires ERPNEXT_URL / ERPNEXT_API_KEY / ERPNEXT_API_SECRET env vars.
    """
    try:
        lead   = fetch_lead(req.lead_id)
        parsed = parse_lead_payload(lead)
        result = _quote_from_parsed(parsed)

        if req.auto_push_back and result.get("quotation"):
            try:
                push_quote_to_lead(
                    req.lead_id,
                    result["quotation"],
                    result.get("triage"),
                )
                result["pushed_to_erpnext"] = True
            except Exception as e:
                result["push_error"] = str(e)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/erpnext/quote-lead-direct")
async def erpnext_quote_direct(req: ERPNextDirectQuoteRequest):
    """
    Quote a Lead passed directly as JSON (no ERPNext connection needed).
    Useful for testing from Postman or a private ERPNext instance.
    """
    try:
        parsed = parse_lead_payload(req.lead)
        result = _quote_from_parsed(parsed)

        if req.auto_push_back and result.get("quotation"):
            try:
                push_quote_to_lead(
                    parsed["lead_id"],
                    result["quotation"],
                    result.get("triage"),
                )
                result["pushed_to_erpnext"] = True
            except Exception as e:
                result["push_error"] = str(e)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/erpnext/pending-leads")
async def erpnext_pending_leads(limit: int = 20):
    """
    List Leads in ERPNext that have not been quoted yet
    (custom_quote_status is blank).
    Requires ERPNext env vars.
    """
    try:
        leads = list_new_leads(limit=limit)
        return {"count": len(leads), "leads": leads}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/erpnext/process-pending")
async def erpnext_process_pending(limit: int = 10):
    """
    Batch process all unquoted Leads — fetches, triages, quotes,
    and pushes summaries back. Run manually or via a cron job.
    """
    try:
        leads   = list_new_leads(limit=limit)
        results = []
        for lead in leads:
            parsed = parse_lead_payload(lead)
            res    = _quote_from_parsed(parsed)
            if res.get("quotation"):
                try:
                    push_quote_to_lead(
                        parsed["lead_id"],
                        res["quotation"],
                        res.get("triage"),
                    )
                    res["pushed_to_erpnext"] = True
                except Exception as e:
                    res["push_error"] = str(e)
            results.append({
                "lead_id":     parsed["lead_id"],
                "client":      parsed["client_name"],
                "action":      res.get("triage", {}).get("action"),
                "grand_total": res.get("quotation", {}).get("totals", {}).get("grand_total_list"),
                "pushed":      res.get("pushed_to_erpnext", False),
                "error":       res.get("quote_error") or res.get("push_error"),
            })
        return {"processed": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
