# ============================================================
# PROMAN Quotation Engine — ERPNext Server Script
# ============================================================
# Install in ERPNext:
#   Settings → Server Script → New
#   DocType : Lead
#   Event   : After Save
#   Name    : PROMAN Auto Quote on Lead
#
# Also set these System Settings (or Site Config):
#   proman_engine_url   = "https://proman-quote-engine.onrender.com"
#   proman_engine_token = ""   (leave blank; engine has no auth by default)
#
# Custom fields to add on Lead (Customise Form → Lead):
#   custom_requirements      Long Text
#   custom_tph               Int
#   custom_plant_stages      Int
#   custom_quote_ref         Data
#   custom_quote_list_price  Currency
#   custom_quote_best_price  Currency
#   custom_quote_hp          Int
#   custom_quote_status      Select  Options: Triaged\nQuoted\nRouted Out\nNeeds Review
#   custom_quote_warnings    Long Text
# ============================================================

import requests
import frappe

PROMAN_URL = frappe.db.get_single_value("System Settings", "proman_engine_url") \
             or "https://proman-quote-engine.onrender.com"

def after_save(doc, method=None):
    # Only run if there are requirements to quote
    enquiry = doc.get("custom_requirements") or doc.get("notes") or ""
    if not enquiry.strip():
        return

    # Skip if already quoted and nothing changed
    if doc.custom_quote_status == "Quoted" and not doc.is_new():
        return

    payload = {
        "lead": {
            "name":                doc.name,
            "company_name":        doc.company_name or doc.lead_name,
            "lead_name":           doc.lead_name,
            "email_id":            doc.email_id or "",
            "mobile_no":           doc.mobile_no or doc.phone or "",
            "notes":               doc.notes or "",
            "custom_requirements": doc.custom_requirements or "",
            "custom_tph":          doc.custom_tph or 0,
            "custom_plant_stages": doc.custom_plant_stages or 0,
            "custom_quote_ref":    doc.custom_quote_ref or "",
        },
        "auto_push_back": False,  # We update fields ourselves below
    }

    try:
        resp = requests.post(
            f"{PROMAN_URL}/api/erpnext/quote-lead-direct",
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        triage    = data.get("triage", {})
        quotation = data.get("quotation")
        action    = triage.get("action", "")

        # Map action → status
        status_map = {
            "route_out": "Routed Out",
            "qualify":   "Needs Review",
            "quote":     "Quoted",
            "quote_standalone":            "Quoted",
            "quote_with_structural_addon": "Quoted",
        }
        status = status_map.get(action, "Triaged")

        update = {"custom_quote_status": status}

        if quotation:
            totals = quotation.get("totals", {})
            spec   = quotation.get("spec", {})
            update.update({
                "custom_quote_ref":        spec.get("ref_no", ""),
                "custom_tph":              spec.get("tph", 0),
                "custom_plant_stages":     spec.get("stages", 0),
                "custom_quote_list_price": totals.get("grand_total_list", 0),
                "custom_quote_best_price": totals.get("grand_total_best", 0),
                "custom_quote_hp":         totals.get("total_hp", 0),
                "custom_quote_warnings":   "\n".join(quotation.get("warnings", [])),
            })

        if triage.get("engineering_review_flags"):
            flags = "\n".join(triage["engineering_review_flags"])
            existing = update.get("custom_quote_warnings", "")
            update["custom_quote_warnings"] = (existing + "\n" + flags).strip()

        # Use db_set to avoid recursive after_save trigger
        for field, value in update.items():
            doc.db_set(field, value, update_modified=False)

        frappe.db.commit()
        frappe.msgprint(
            f"PROMAN Quote: {status} | List ₹{update.get('custom_quote_list_price', 0):.2f}L",
            alert=True,
        )

    except Exception as e:
        frappe.log_error(f"PROMAN quote error for Lead {doc.name}: {e}", "PROMAN Engine")
        doc.db_set("custom_quote_status", "Needs Review", update_modified=False)
        frappe.db.commit()
