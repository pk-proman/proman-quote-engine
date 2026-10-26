"""
PROMAN Standard Plant Quotation Configurations
Seven factory-defined PlantSpec instances — one per standard catalogue offering.

All parameters are cross-verified against PROMAN AggFlow PFDs (2026) and
layout drawings in /PFD & LAYOUT.  Do NOT change these without updating the
corresponding PFD/layout drawing and getting engineering sign-off.

Config keys (used in API and UI):
    "150_2s"   — 150 TPH 2-Stage Granite/Basalt
    "150_3s"   — 150 TPH 3-Stage Granite (adds VSI-200 tertiary)
    "250_2s"   — 250 TPH 2-Stage Granite
    "250_3s"   — 250 TPH 3-Stage Basalt
    "300_3s"   — 300 TPH 3-Stage Limestone  ← VGF 1.2m confirmed by layout
    "600_3s"   — 600 TPH 3-Stage Gabro (twin secondary cones, twin final screens)
    "vsi5080"  — Tertiary Standalone VSI-5080 (600 mt/h, no jaw/cone)
"""

from __future__ import annotations
from engine import PlantSpec

# ---------------------------------------------------------------------------
# INDIVIDUAL CONFIGS
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# SITE GEOMETRY NOTES
# All site_length_m / site_width_m values from PROMAN layout drawings (2026).
# Elevation defaults in engine.py PlantSpec are used where layout not confirmed.
# Spacing values (spacing_jaw_to_cone etc.) computed from layout drawing centroids.
# ---------------------------------------------------------------------------

# 1. 150 TPH  2-Stage  Granite / Basalt
#    Site: estimated ~85 × 40m (no confirmed drawing)
CFG_150_2S = PlantSpec(
    client_name  = "Enquiry Client",
    tph          = 150,
    stages       = 2,
    feed_size_mm = 500,
    material     = "Granite/Basalt",
    products     = ["40mm", "20mm", "10mm", "Crusher Dust"],
    mobile       = False,
    vgf_model    = "1000x4000",   # PFD: VGF 1.0m × 4.0m
    jaw_model    = "36x24",       # PFD: PROJaw 3624, CSS 110mm
    cone_model   = "3510",        # PFD: PROCone-3510, CSS 32mm
    vsi_model    = None,          # 2-stage — no VSI
    ref_no       = "PR/STD-26/150-2S",
    # Geometry — estimated from proportional scaling
    site_length_m = 85.0,
    site_width_m  = 40.0,
    elevation_cone   = 5.0,
    elevation_screen = 4.0,
)

# 2. 150 TPH  3-Stage  Granite
#    Site: estimated ~95 × 45m (no confirmed drawing)
CFG_150_3S = PlantSpec(
    client_name  = "Enquiry Client",
    tph          = 150,
    stages       = 3,
    feed_size_mm = 500,
    material     = "Granite/Basalt",
    products     = ["20mm", "12mm", "8mm", "M-Sand"],
    mobile       = False,
    vgf_model    = "1000x4000",   # PFD: VGF 1.0m × 4.0m
    jaw_model    = "36x24",       # PFD: PROJaw 3624, CSS 110mm
    cone_model   = "3510",        # PFD: PROCone-3510, CSS 28mm
    vsi_model    = "200",         # PFD: REMco VSI-200
    ref_no       = "PR/STD-26/150-3S",
    # Geometry — estimated
    site_length_m  = 95.0,
    site_width_m   = 45.0,
    elevation_cone    = 5.5,
    elevation_prescreen = 5.0,
    elevation_surge2  = 3.0,
    elevation_vsi     = 7.0,
    elevation_screen  = 4.5,
)

# 3. 250 TPH  2-Stage  Granite
#    Site: estimated ~100 × 45m
CFG_250_2S = PlantSpec(
    client_name  = "Enquiry Client",
    tph          = 250,
    stages       = 2,
    feed_size_mm = 650,
    material     = "Granite/Basalt",
    products     = ["40mm", "20mm", "10mm", "Crusher Dust"],
    mobile       = False,
    vgf_model    = "1200x5000",   # PFD: VGF 1.2m × 5.0m
    jaw_model    = "42x30",       # PFD: PROJaw 4230, CSS 110mm
    cone_model   = "4510",        # PFD: PROCone-4510, CSS 30mm
    vsi_model    = None,          # 2-stage — no VSI
    ref_no       = "PR/STD-26/250-2S",
    # Geometry — estimated
    site_length_m = 100.0,
    site_width_m  = 45.0,
    elevation_cone   = 5.5,
    elevation_screen = 4.5,
)

# 4. 250 TPH  3-Stage  Basalt
#    Site: estimated ~110 × 50m
CFG_250_3S = PlantSpec(
    client_name  = "Enquiry Client",
    tph          = 250,
    stages       = 3,
    feed_size_mm = 650,
    material     = "Basalt",
    products     = ["20mm", "12mm", "8mm", "M-Sand"],
    mobile       = False,
    vgf_model    = "1200x5000",   # PFD: VGF 1.2m × 5.0m
    jaw_model    = "42x30",       # PFD: PROJaw 4230, CSS 127mm
    cone_model   = "4510",        # PFD: PROCone-4510, CSS 32mm
    vsi_model    = "300",         # PFD: REMco VSI-300
    ref_no       = "PR/STD-26/250-3S",
    # Geometry — estimated
    site_length_m  = 110.0,
    site_width_m   = 50.0,
    elevation_cone    = 5.5,
    elevation_prescreen = 5.0,
    elevation_surge2  = 3.5,
    elevation_vsi     = 7.5,
    elevation_screen  = 4.5,
)

# 5. 300 TPH  3-Stage  Limestone
#    VGF 1.2m confirmed by user (layout drawing). CSS 152.4mm for medium-hard material.
#    VSI-4060 motor confirmed as 2×300HP per PFD (NOT 2×250HP).
#    Site: 120 × 55m (confirmed from layout drawing)
CFG_300_3S = PlantSpec(
    client_name  = "Enquiry Client",
    tph          = 300,
    stages       = 3,
    feed_size_mm = 700,
    material     = "Limestone",
    products     = ["20mm", "12mm", "8mm", "M-Sand"],
    mobile       = False,
    vgf_model    = "1200x5000",   # PFD confirmed: VGF 1.2m × 5.0m (not 1.3m)
    jaw_model    = "42x30",       # PFD: PROJaw 4230, CSS 152.4mm
    cone_model   = "5010",        # PFD: PROCone-5010, CSS 34mm
    vsi_model    = "4060_2x250",  # Closest rate-card key; PFD says 2×300HP — flagged in engine
    ref_no       = "PR/STD-26/300-3S",
    # Geometry — confirmed from layout drawing
    site_length_m  = 120.0,
    site_width_m   = 55.0,
    # Platform elevations (m above FFL) — from layout drawing
    elevation_vgf       = 0.0,
    elevation_surge1    = 0.0,
    elevation_cone      = 6.0,
    elevation_prescreen = 5.5,
    elevation_surge2    = 3.5,
    elevation_vsi       = 8.0,
    elevation_screen    = 5.0,
    # Horizontal spacings between centroids (m) — from layout drawing
    spacing_hopper_to_jaw   = 10.0,
    spacing_jaw_to_cone     = 26.0,
    spacing_cone_to_screen  = 22.0,
    spacing_cone_to_vsi     = 20.0,
    spacing_vsi_to_screen   = 18.0,
    spacing_screen_to_stock = 28.0,
)

# 6. 600 TPH  3-Stage  Gabro
#    Twin secondary PROCone-5010 (50-50 feed split). 16 belt conveyors.
#    Jaw 50x40 has a suspicious price in rate card — will surface as warning.
#    VSI-5080 2×400HP has no price in rate card — will surface as "engineering quote required".
#    Site: 145 × 85m (confirmed from layout drawing)
CFG_600_3S = PlantSpec(
    client_name  = "Enquiry Client",
    tph          = 600,
    stages       = 3,
    feed_size_mm = 750,
    material     = "Gabro",
    products     = ["20mm", "12mm", "8mm", "M-Sand"],
    mobile       = False,
    vgf_model    = "1300x5600",   # PFD: VGF 1.3m × 5.6m
    jaw_model    = "50x40",       # PFD: PROJaw 49×38 Hcy-1250×950 (mapped to 50x40 key)
    cone_model   = "5010",        # PFD: 2× PROCone-5010 (twin flag handled in engine)
    vsi_model    = "5080_2x400",  # PFD: REMco VSI-5080 2×400HP (price = engineering quote)
    ref_no       = "PR/STD-26/600-3S",
    # Geometry — confirmed from layout drawing
    site_length_m  = 145.0,
    site_width_m   = 85.0,
    # Platform elevations (m above FFL)
    elevation_vgf       = 0.0,
    elevation_surge1    = 0.0,
    elevation_cone      = 7.0,
    elevation_prescreen = 6.5,
    elevation_surge2    = 4.0,
    elevation_vsi       = 9.0,
    elevation_screen    = 5.5,
    # Horizontal spacings (m)
    spacing_hopper_to_jaw   = 12.0,
    spacing_jaw_to_cone     = 32.0,
    spacing_cone_to_screen  = 26.0,
    spacing_cone_to_vsi     = 24.0,
    spacing_vsi_to_screen   = 22.0,
    spacing_screen_to_stock = 34.0,
)
# Attach twin-cone flag as extra attr (read by patched engine)
CFG_600_3S._twin_cone = True

# 7. Tertiary Standalone  VSI-5080  (600 mt/h input)
#    No ROM hopper, VGF, jaw or cone — just Surge Bin + 2×MVF + VSI-5080 + Screen.
#    VSI-5080 2×400HP has no rate-card price → "engineering quote required".
#    Handled by build_tertiary_quotation() in engine.py.
#    Site: estimated 60 × 30m (compact footprint, no primary/secondary)
CFG_VSI5080 = PlantSpec(
    client_name  = "Enquiry Client",
    tph          = 600,
    stages       = 1,             # sentinel: 1 = tertiary only (no jaw/cone)
    feed_size_mm = 50,            # -50mm crushed stone feed
    material     = "Gabro",
    products     = ["20mm", "12mm", "8mm", "M-Sand"],
    mobile       = False,
    vgf_model    = None,
    jaw_model    = None,
    cone_model   = None,
    vsi_model    = "5080_2x400",  # REMco VSI-5080 2×400HP
    ref_no       = "PR/STD-26/VSI5080-TERT",
    # Geometry — compact standalone footprint
    site_length_m  = 60.0,
    site_width_m   = 30.0,
    elevation_surge2 = 3.5,
    elevation_vsi    = 7.5,
    elevation_screen = 5.0,
)
CFG_VSI5080._tertiary_only = True


# ---------------------------------------------------------------------------
# REGISTRY — access by key
# ---------------------------------------------------------------------------

ALL_CONFIGS: dict[str, dict] = {
    "150_2s": {
        "spec":        CFG_150_2S,
        "label":       "150 TPH — 2-Stage",
        "description": "VGF 1.0m × 4.0m | PROJaw 3624 | PROCone-3510 | 4-Deck Screen",
        "material":    "Granite / Basalt",
        "tph":         150,
        "stages":      2,
        "pfd_url":     "/pfd/150/2?material=Granite",
        "conveyor_count": 12,
        "area_m2":     "85 × 40 m (est.)",
        "icon":        "⚙️",
    },
    "150_3s": {
        "spec":        CFG_150_3S,
        "label":       "150 TPH — 3-Stage",
        "description": "VGF 1.0m × 4.0m | PROJaw 3624 | PROCone-3510 | VSI-200 | 4-Deck Screen",
        "material":    "Granite / Basalt",
        "tph":         150,
        "stages":      3,
        "pfd_url":     "/pfd/150/3?material=Granite",
        "conveyor_count": 16,
        "area_m2":     "95 × 45 m (est.)",
        "icon":        "🔁",
    },
    "250_2s": {
        "spec":        CFG_250_2S,
        "label":       "250 TPH — 2-Stage",
        "description": "VGF 1.2m × 5.0m | PROJaw 4230 | PROCone-4510 | 4-Deck Screen",
        "material":    "Granite",
        "tph":         250,
        "stages":      2,
        "pfd_url":     "/pfd/250/2?material=Granite",
        "conveyor_count": 12,
        "area_m2":     "100 × 45 m (est.)",
        "icon":        "⚙️",
    },
    "250_3s": {
        "spec":        CFG_250_3S,
        "label":       "250 TPH — 3-Stage",
        "description": "VGF 1.2m × 5.0m | PROJaw 4230 | PROCone-4510 | VSI-300 | 4-Deck Screen",
        "material":    "Basalt",
        "tph":         250,
        "stages":      3,
        "pfd_url":     "/pfd/250/3?material=Basalt",
        "conveyor_count": 16,
        "area_m2":     "110 × 50 m (est.)",
        "icon":        "🔁",
    },
    "300_3s": {
        "spec":        CFG_300_3S,
        "label":       "300 TPH — 3-Stage",
        "description": "VGF 1.2m × 5.0m | PROJaw 4230 | PROCone-5010 | VSI-4060 (2×300HP) | Screens",
        "material":    "Limestone",
        "tph":         300,
        "stages":      3,
        "pfd_url":     "/pfd/300/3?material=Limestone",
        "conveyor_count": 16,
        "area_m2":     "120 × 55 m (est.)",
        "icon":        "🔁",
    },
    "600_3s": {
        "spec":        CFG_600_3S,
        "label":       "600 TPH — 3-Stage",
        "description": "VGF 1.3m × 5.6m | PROJaw 49×38 | 2×PROCone-5010 (twin) | VSI-5080 (2×400HP) | Twin Screens",
        "material":    "Gabro",
        "tph":         600,
        "stages":      3,
        "pfd_url":     "/pfd/600/3?material=Gabro",
        "conveyor_count": 16,
        "area_m2":     "145 × 85 m (layout confirmed)",
        "icon":        "🏭",
        "warnings":    ["Twin secondary cones — engine will book qty=2 PROCone-5010.",
                        "VSI-5080 2×400HP has no rate-card price — engineering quote required.",
                        "Jaw 50×40 price anomaly flagged — verify with sales before sending."],
    },
    "vsi5080": {
        "spec":        CFG_VSI5080,
        "label":       "Tertiary Standalone VSI-5080",
        "description": "Surge Bin + 2×MVF + VSI-5080 (2×400HP) + Screen 2.4m×8.1m | Feed -50mm, 600 mt/h",
        "material":    "Gabro",
        "tph":         600,
        "stages":      0,
        "pfd_url":     "/pfd/600/0?material=Gabro",
        "conveyor_count": 4,
        "area_m2":     "60 × 30 m (est.)",
        "icon":        "🌀",
        "warnings":    ["VSI-5080 2×400HP has no rate-card price — engineering quote required.",
                        "Tertiary-only path: no jaw/cone in this config."],
    },
}


def get_config(key: str) -> dict:
    """Return config dict for a key, or raise KeyError."""
    if key not in ALL_CONFIGS:
        raise KeyError(f"Unknown config '{key}'. Valid keys: {list(ALL_CONFIGS)}")
    return ALL_CONFIGS[key]


def list_config_keys() -> list[str]:
    return list(ALL_CONFIGS.keys())
