"""
PROMAN Enquiry Triage Engine
Routes each enquiry to the correct action before any quote is built.
"""

import re
import sys
import json

# ---------------------------------------------------------------------------
# KEYWORD FLAGS
# ---------------------------------------------------------------------------
SPECIAL_DUTY_FLAGS = {
    "washing":      "Washing plant — check WSG scope; client may also need thickener/tailing pond (exclusions apply)",
    "quartz":       "Quartz / silica — abrasion factor may require upgraded wear parts; engineering review needed",
    "gost":         "GOST specification — non-standard grading; confirm mesh sizes with engineering",
    "dry mortar":   "Dry mortar — specialist output size, may need Sizer; confirm product spec",
    "limestone":    "Limestone — softer rock; capacity may be higher; check if jaw size can step down",
    "coal":         "Coal — non-aggregate application; out of PROMAN standard scope",
    "river sand":   "River sand — no crushing needed; route to WSG-only enquiry",
    "m sand":       "M-sand / manufactured sand — VSI mandatory as tertiary stage",
    "marble":       "Marble — soft rock with high silica; confirm abrasion impact with engineering",
    "portable":     "Portable / skid / track — quote_with_structural_addon path",
    "skid":         "Portable / skid / track — quote_with_structural_addon path",
    "track":        "Portable / skid / track — quote_with_structural_addon path",
    "mobile":       "Portable / skid / track — quote_with_structural_addon path",
}

OUT_OF_SCOPE_KEYWORDS = [
    "coal", "river sand", "gold", "iron ore", "copper",
    "oil seed", "crushing mill", "ball mill",
]

STANDALONE_KEYWORDS = {
    "VSI":    r"\bVSI[-\s]?(\d+(?:[-_]\d+[xX]\d+)?)\b",
    "JAW":    r"\b(?:jaw|PROjaw)[-\s]?(\d+[xX]\d+)\b",
    "CONE":   r"\b(?:cone|PROcone)[-\s]?(\d+)\b",
    "VGF":    r"\bVGF[-\s]?(\d+[xX]\d+)\b",
    "WSG":    r"\bWSG[-\s]?(\d+)\b",
    "SCREEN": r"\bscreen[-\s]?(\d+[xX]\d+[-_]\d+[dD])\b",
}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    return text.lower().replace("-", " ").replace("_", " ")


def _detect_standalone(raw_text: str):
    """
    If the enquiry mentions only a single equipment model (no TPH, no plant type),
    return (category, model) — else return None.
    """
    for category, pattern in STANDALONE_KEYWORDS.items():
        m = re.search(pattern, raw_text, re.IGNORECASE)
        if m:
            # Check that there is no plant-type language
            norm = _normalise(raw_text)
            plant_words = ["stage", "plant", "tph", "t/h", "stationary",
                           "portable", "crushing plant", "screening plant"]
            if not any(pw in norm for pw in plant_words):
                model = m.group(1).replace(" ", "").upper()
                return category, model
    return None


def _extract_tph(raw_text: str):
    """Try to pull a TPH figure from free text."""
    m = re.search(r"(\d{2,4})\s*(?:tph|t/h|ton[s]?\s*(?:per|/)\s*hour)", raw_text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None


def _detect_mobile(raw_text: str) -> bool:
    norm = _normalise(raw_text)
    return any(w in norm for w in ["portable", "skid", "track", "mobile", "porta"])


def _detect_special_flags(raw_text: str) -> list:
    norm = _normalise(raw_text)
    found = []
    for kw, msg in SPECIAL_DUTY_FLAGS.items():
        if kw in norm:
            found.append(msg)
    return found


def _detect_out_of_scope(raw_text: str) -> str:
    norm = _normalise(raw_text)
    for kw in OUT_OF_SCOPE_KEYWORDS:
        if kw in norm:
            return kw
    return None


def _build_qualification_draft(raw_text: str, tph: int = None) -> str:
    name_m = re.search(r"(?:dear|attn|attention|mr|ms|mrs|shri)\.?\s+([A-Za-z\s]+?)(?:\n|,|$)",
                        raw_text, re.IGNORECASE)
    salutation = name_m.group(1).strip() if name_m else "Sir/Madam"
    tph_str = f"{tph} TPH" if tph else "[please specify TPH]"
    return f"""Subject: Requirement Qualification — Aggregate Crushing Plant

Dear {salutation},

Thank you for your enquiry. To prepare an accurate techno-commercial offer for your
{tph_str} crushing and screening plant, we would request the following details:

1. Type of feed material (Granite / Basalt / Limestone / other)
2. Maximum feed boulder size (mm)
3. Required output gradations / finished products
4. Site location and ground conditions (level / sloped)
5. Availability of power supply (kVA / kW, 415V 3-phase)
6. Plant type: Stationary / Portable-Skid
7. Any specific requirements (washing, dust suppression, GST registration state)

We will revert with our offer within 2–3 working days of receiving the above.

Thanking you,
For PROMAN Infrastructure Services Pvt. Ltd.
"""


# ---------------------------------------------------------------------------
# MAIN TRIAGE FUNCTION
# ---------------------------------------------------------------------------

def triage_enquiry(raw_text: str, extracted: dict = None) -> dict:
    """
    Route an enquiry.

    Returns a dict with:
      action:   "route_out" | "qualify" | "quote" | "quote_standalone"
                | "quote_with_structural_addon"
      reason:   (str) explanation
      draft:    (str | None) ready-to-send qualification email, if action=="qualify"
      engineering_review_flags: list of warning strings (non-empty even for "quote")
    """
    if extracted is None:
        extracted = {}

    result = {
        "action": None,
        "reason": "",
        "draft": None,
        "engineering_review_flags": [],
        "detected_tph": None,
        "detected_mobile": False,
    }

    # 1. Out-of-scope check
    oos = _detect_out_of_scope(raw_text)
    if oos:
        result["action"] = "route_out"
        result["reason"] = (
            f"Material '{oos}' is outside PROMAN's standard aggregate crushing scope. "
            "Route to an appropriate specialist or decline politely."
        )
        return result

    # 2. Standalone equipment check
    standalone = _detect_standalone(raw_text)
    if standalone:
        cat, model = standalone
        result["action"] = "quote_standalone"
        result["reason"] = f"Single-equipment enquiry detected: {cat} {model}"
        result["detected_category"] = cat
        result["detected_model"] = model
        return result

    # 3. Mobile / portable detection → structural addon
    is_mobile = _detect_mobile(raw_text) or extracted.get("mobile", False)
    result["detected_mobile"] = is_mobile

    # 4. TPH detection
    tph = extracted.get("tph") or _extract_tph(raw_text)
    result["detected_tph"] = tph

    # 5. Special-duty flags
    flags = _detect_special_flags(raw_text)
    result["engineering_review_flags"] = flags

    # 6. Qualify if essential info is missing
    missing = []
    if not tph:
        missing.append("TPH / capacity not specified")

    norm = _normalise(raw_text)
    material_words = ["granite", "basalt", "limestone", "marble", "quartzite",
                      "sandstone", "dolomite", "slag"]
    if not any(w in norm for w in material_words) and "material" not in str(extracted):
        missing.append("feed material type not specified")

    if missing:
        result["action"] = "qualify"
        result["reason"] = "Cannot quote without: " + "; ".join(missing)
        result["draft"] = _build_qualification_draft(raw_text, tph)
        return result

    # 7. Route to quote
    if is_mobile:
        result["action"] = "quote_with_structural_addon"
        result["reason"] = (
            "Portable / skid-mounted plant detected. Structural additions (skid frames, "
            "transport bolting) need engineering sign-off before finalising quote."
        )
    else:
        result["action"] = "quote"
        result["reason"] = f"Standard stationary plant, {tph} TPH. Proceed to build quotation."

    return result


# ---------------------------------------------------------------------------
# CLI for quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        "Chiman Bhai Sapariya / SR Petrol Pump, VSI 300",
        "Need 250 TPH granite crushing plant, 2 stage stationary",
        "Looking for 150 TPH portable crushing plant for limestone",
        "We want coal crushing equipment",
        "Need river sand washing setup",
        "Enquiry for 200 TPH basalt crushing, washing required, GST Karnataka",
        "Looking for a crushing plant",   # should qualify
    ]

    for t in tests:
        r = triage_enquiry(t)
        print(f"\nENQUIRY: {t}")
        print(f"  ACTION: {r['action']}")
        print(f"  REASON: {r['reason']}")
        if r.get("engineering_review_flags"):
            for f in r["engineering_review_flags"]:
                print(f"  ⚠️  {f}")
        if r.get("draft"):
            print("  [Draft qualification letter prepared — not printed here]")
