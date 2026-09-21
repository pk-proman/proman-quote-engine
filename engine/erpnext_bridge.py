"""
PROMAN ↔ ERPNext Bridge
=======================
Handles two directions:
  1. ERPNext → PROMAN  : parse a Lead payload, triage + quote it
  2. PROMAN  → ERPNext : push quote summary back to the Lead record

ERPNext custom fields required on the Lead doctype
(Customise Form → Lead → Add fields):
  - custom_requirements      (Long Text)   — enquiry text / plant requirements
  - custom_tph               (Int)         — detected or overridden TPH
  - custom_plant_stages      (Int)         — 2 / 3
  - custom_quote_ref         (Data)        — e.g. PR/09-26/N-AB12
  - custom_quote_list_price  (Currency)    — Grand Total List (₹ Lakhs)
  - custom_quote_best_price  (Currency)    — Grand Total Best (₹ Lakhs)
  - custom_quote_hp          (Int)         — Total connected HP
  - custom_quote_status      (Select)      — Triaged / Quoted / Routed Out / Needs Review
  - custom_quote_warnings    (Long Text)   — Engineering flags

Set ERPNext connection in environment variables:
  ERPNEXT_URL        https://your-site.erpnext.com
  ERPNEXT_API_KEY    xxxxxxxxxxxxxxxx
  ERPNEXT_API_SECRET xxxxxxxxxxxxxxxx
"""

import os
import json
import logging
from datetime import date
from typing import Optional

import requests as _req

logger = logging.getLogger("proman.erpnext")


# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------

def _erpnext_cfg() -> dict:
    url    = os.getenv("ERPNEXT_URL", "").rstrip("/")
    key    = os.getenv("ERPNEXT_API_KEY", "")
    secret = os.getenv("ERPNEXT_API_SECRET", "")
    if not (url and key and secret):
        raise RuntimeError(
            "ERPNext not configured. Set ERPNEXT_URL, ERPNEXT_API_KEY, "
            "ERPNEXT_API_SECRET environment variables."
        )
    return {"url": url, "headers": {"Authorization": f"token {key}:{secret}"}}


# ---------------------------------------------------------------------------
# PARSE LEAD → PlantSpec inputs
# ---------------------------------------------------------------------------

def parse_lead_payload(lead: dict) -> dict:
    """
    Convert an ERPNext Lead document dict into PROMAN quote inputs.
    Returns a dict compatible with QuoteRequest / triage_enquiry.
    """
    # Enquiry text: prefer custom_requirements, fall back to notes
    enquiry = (
        lead.get("custom_requirements")
        or lead.get("notes")
        or lead.get("lead_name", "")
    )

    return {
        "lead_id":     lead.get("name", ""),
        "client_name": lead.get("company_name") or lead.get("lead_name", "Client"),
        "email":       lead.get("email_id", ""),
        "phone":       lead.get("mobile_no") or lead.get("phone", ""),
        "enquiry":     enquiry,
        "tph":         int(lead.get("custom_tph") or 0),
        "stages":      int(lead.get("custom_plant_stages") or 0),
        "ref_no":      lead.get("custom_quote_ref", ""),
    }


# ---------------------------------------------------------------------------
# PUSH QUOTE → ERPNext Lead
# ---------------------------------------------------------------------------

def push_quote_to_lead(lead_id: str, quote_data: dict, triage_result: dict = None) -> dict:
    """
    Update ERPNext Lead custom fields with the quote summary.

    quote_data: the _quotation_to_dict() output from main.py
    Returns the ERPNext API response dict.
    """
    cfg = _erpnext_cfg()

    totals   = quote_data.get("totals", {})
    warnings = quote_data.get("warnings", [])
    spec     = quote_data.get("spec", {})

    # Determine status
    if triage_result:
        action = triage_result.get("action", "")
        if action == "route_out":
            status = "Routed Out"
        elif action == "qualify":
            status = "Needs Review"
        else:
            status = "Quoted"
    else:
        status = "Quoted"

    payload = {
        "custom_quote_ref":        spec.get("ref_no", ""),
        "custom_tph":              spec.get("tph", 0),
        "custom_plant_stages":     spec.get("stages", 0),
        "custom_quote_list_price": totals.get("grand_total_list", 0),
        "custom_quote_best_price": totals.get("grand_total_best", 0),
        "custom_quote_hp":         totals.get("total_hp", 0),
        "custom_quote_status":     status,
        "custom_quote_warnings":   "\n".join(warnings) if warnings else "",
    }

    url = f"{cfg['url']}/api/resource/Lead/{lead_id}"
    resp = _req.put(url, json=payload, headers=cfg["headers"], timeout=15)
    resp.raise_for_status()
    logger.info("Pushed quote to Lead %s: status=%s", lead_id, status)
    return resp.json()


# ---------------------------------------------------------------------------
# FETCH LEAD FROM ERPNEXT
# ---------------------------------------------------------------------------

def fetch_lead(lead_id: str) -> dict:
    """Fetch a single Lead document from ERPNext."""
    cfg = _erpnext_cfg()
    url = f"{cfg['url']}/api/resource/Lead/{lead_id}"
    resp = _req.get(url, headers=cfg["headers"], timeout=15)
    resp.raise_for_status()
    return resp.json().get("data", {})


def list_new_leads(limit: int = 20) -> list:
    """
    Fetch recent Leads with custom_quote_status blank (not yet quoted).
    Useful for polling mode.
    """
    cfg = _erpnext_cfg()
    filters = json.dumps([["custom_quote_status", "in", ["", None]]])
    fields  = json.dumps([
        "name", "company_name", "lead_name", "email_id", "mobile_no",
        "notes", "custom_requirements", "custom_tph", "custom_plant_stages",
        "custom_quote_ref", "creation",
    ])
    url = (
        f"{cfg['url']}/api/resource/Lead"
        f"?filters={filters}&fields={fields}&limit={limit}&order_by=creation desc"
    )
    resp = _req.get(url, headers=cfg["headers"], timeout=15)
    resp.raise_for_status()
    return resp.json().get("data", [])
