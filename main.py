"""
PROMAN Quotation Engine — FastAPI Web Application
Run:  uvicorn main:app --reload --port 8000
"""

import sys, os, uuid, tempfile, json
from datetime import date
from pathlib import Path
from typing import Optional, List

sys.path.insert(0, str(Path(__file__).parent / "engine"))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import rate_card as rc
from engine import PlantSpec, Quotation, build_quotation, quote_standalone_equipment
from triage import triage_enquiry
from generate_xlsx import build_workbook
from generate_offer_letter import build_offer_letter, build_standalone_letter
from bundle import (BundleSpec, BundleEquipmentItem, BundleConveyorItem,
                    build_bundle_quotation, infer_tph)

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
    return PlantSpec(
        client_name   = r.client_name,
        tph           = r.tph,
        stages        = r.stages,
        feed_size_mm  = r.feed_size_mm,
        material      = r.material,
        products      = r.products,
        mobile        = r.mobile,
        wsg_size      = r.wsg_size,
        wsg_config    = r.wsg_config,
        jaw_discharge_h = r.jaw_discharge_h,
        jaw_model     = r.jaw_model,
        cone_model    = r.cone_model,
        vsi_model     = r.vsi_model,
        vgf_model     = r.vgf_model,
        ref_no        = ref,
        date          = r.date or date.today().strftime("%d-%m-%Y"),
    )


# ---------------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def root():
    return (STATIC / "index.html").read_text()


@app.post("/api/triage")
async def triage(req: TriageRequest):
    result = triage_enquiry(req.enquiry_text)
    return result


@app.post("/api/quote")
async def quote(req: QuoteRequest):
    try:
        spec = _make_spec(req)
        q    = build_quotation(spec)
        return _quotation_to_dict(q)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quote/standalone")
async def quote_standalone(req: StandaloneRequest):
    result = quote_standalone_equipment(req.category, req.model)
    return result


@app.post("/api/quote/download/xlsx")
async def download_xlsx(req: QuoteRequest):
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
async def download_docx(req: QuoteRequest):
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
async def download_standalone_docx(req: StandaloneRequest):
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
async def get_equipment_list():
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
    return {"status": "ok", "version": "1.1.0"}


# ---------------------------------------------------------------------------
# BUNDLE QUOTE ENDPOINTS
# ---------------------------------------------------------------------------

@app.post("/api/quote/bundle")
async def quote_bundle(req: BundleRequest):
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
