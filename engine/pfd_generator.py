"""
PROMAN Process Flow Diagram (PFD) Generator
Generates a self-contained HTML+SVG PFD for any plant configuration.

Style: AggFlow-inspired — dark navy background, coloured equipment boxes,
       flow arrows, tonnage labels, product stockpile icons.

Usage:
    from engine.pfd_generator import generate_pfd_html
    html = generate_pfd_html(schedule, tph, stages)
"""

from __future__ import annotations
import html as _html
import math


# ---------------------------------------------------------------------------
# Colour palette (AggFlow-inspired)
# ---------------------------------------------------------------------------
C_BG        = "#0F1C2E"   # page background
C_GRID      = "#1A2D42"   # faint grid lines
C_HOPPER    = "#B45309"   # amber — ROM hopper
C_VGF       = "#D97706"   # amber-yellow — vibrating feeder
C_JAW       = "#DC2626"   # red — jaw crusher
C_CONE      = "#2563EB"   # blue — cone crusher
C_VSI       = "#7C3AED"   # purple — VSI
C_SCREEN    = "#059669"   # green — screens
C_BIN       = "#4B5563"   # grey — surge bins
C_BELT      = "#374151"   # dark belt
C_STOCK     = "#92400E"   # brown — stockpiles
C_ARROW     = "#60A5FA"   # light blue arrows
C_TONNAGE   = "#FCD34D"   # yellow tonnage labels
C_TEXT      = "#F1F5F9"   # main text
C_SUBTEXT   = "#94A3B8"   # secondary text
C_WHITE     = "#FFFFFF"
C_BORDER    = "#334155"


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _esc(s: str) -> str:
    return _html.escape(str(s))

def _rect(x, y, w, h, fill, rx=4, stroke=C_BORDER, sw=1.5, opacity=1.0):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}"/>')

def _text(x, y, txt, fill=C_TEXT, size=11, bold=False, anchor="middle", dy=0):
    weight = "bold" if bold else "normal"
    return (f'<text x="{x}" y="{y}" dy="{dy}" text-anchor="{anchor}" '
            f'fill="{fill}" font-size="{size}" font-weight="{weight}" '
            f'font-family="\'Segoe UI\',Arial,sans-serif">{_esc(txt)}</text>')

def _arrow_h(x1, y, x2, color=C_ARROW, label="", lbl_color=C_TONNAGE):
    """Horizontal flow arrow from x1 to x2 at height y."""
    parts = []
    mid_x = (x1 + x2) / 2
    parts.append(f'<line x1="{x1}" y1="{y}" x2="{x2-8}" y2="{y}" '
                 f'stroke="{color}" stroke-width="2" marker-end="url(#arrowH)"/>')
    if label:
        parts.append(_text(mid_x, y - 4, label, fill=lbl_color, size=9))
    return "\n".join(parts)

def _arrow_v(x, y1, y2, color=C_ARROW, label="", lbl_color=C_TONNAGE):
    """Vertical flow arrow from y1 to y2 at column x."""
    parts = []
    mid_y = (y1 + y2) / 2
    parts.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2-8}" '
                 f'stroke="{color}" stroke-width="2" marker-end="url(#arrowV)"/>')
    if label:
        parts.append(_text(x + 6, mid_y, label, fill=lbl_color, size=9, anchor="start"))
    return "\n".join(parts)

def _equipment_box(x, y, w, h, fill, label, sub="", icon=""):
    """Labelled equipment box with optional sub-label."""
    parts = [_rect(x, y, w, h, fill, rx=5, stroke=C_WHITE, sw=1)]
    cy = y + h / 2
    if icon:
        parts.append(_text(x + w / 2, cy - 7, icon, size=14, anchor="middle"))
        parts.append(_text(x + w / 2, cy + 7, label, bold=True, size=10, anchor="middle"))
        if sub:
            parts.append(_text(x + w / 2, cy + 20, sub, fill=C_SUBTEXT, size=8, anchor="middle"))
    else:
        parts.append(_text(x + w / 2, cy - (5 if sub else 0), label, bold=True, size=10, anchor="middle"))
        if sub:
            parts.append(_text(x + w / 2, cy + 10, sub, fill=C_SUBTEXT, size=8, anchor="middle"))
    return "\n".join(parts)

def _stockpile(cx, top_y, label, product_no):
    """Triangle stockpile icon."""
    h = 40
    w = 50
    pts = f"{cx},{top_y} {cx-w//2},{top_y+h} {cx+w//2},{top_y+h}"
    color_map = {1:"#B45309",2:"#D97706",3:"#059669",4:"#2563EB",5:"#7C3AED"}
    fill = color_map.get(product_no, C_STOCK)
    return (f'<polygon points="{pts}" fill="{fill}" stroke="{C_WHITE}" stroke-width="1" opacity="0.85"/>'
            f'\n{_text(cx, top_y+h+14, label, fill=C_TEXT, size=8, anchor="middle")}')

def _defs():
    return """
<defs>
  <marker id="arrowH" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
    <polygon points="0 0, 8 3, 0 6" fill="#60A5FA"/>
  </marker>
  <marker id="arrowV" markerWidth="6" markerHeight="8" refX="3" refY="8" orient="90">
    <polygon points="0 0, 6 0, 3 8" fill="#60A5FA"/>
  </marker>
</defs>"""


# ---------------------------------------------------------------------------
# Layout helpers — coordinate system
# ---------------------------------------------------------------------------

# Row Y positions (top of box)
ROW1 = 40    # ROM hopper / feed
ROW2 = 160   # primary crushing / VSI (tertiary)
ROW3 = 300   # surge + secondary
ROW4 = 430   # VSI tertiary
ROW5 = 560   # final screen / products

BOX_H = 80   # default box height
COL_W = 110  # column spacing

def _col(n: int) -> int:
    """Left-x for column n (0-indexed)."""
    return 30 + n * COL_W


# ---------------------------------------------------------------------------
# Per-plant layout builders
# ---------------------------------------------------------------------------

def _build_two_stage(schedule: dict, tph: int) -> tuple[str, int, int]:
    """2-stage plant SVG body. Returns (svg_content, width, height)."""
    parts = []
    W, H = 820, 660

    vgf   = schedule["vgf"]["model"]
    jaw   = schedule["jaw"]["model"]
    cone  = (schedule.get("cone") or {}).get("model", "PROCone")
    fin   = ((schedule.get("screens") or {}).get("final") or {}).get("model", "Screen")
    cuts  = schedule.get("gradation", {}).get("cuts_mm", [40, 20, 10, 4.75])
    prods = schedule.get("gradation", {}).get("products", [])

    # — Row 1: ROM → VGF
    parts.append(_equipment_box(30, ROW1, 90, BOX_H, C_HOPPER, "ROM Hopper", f"Feed ≤750mm", "🪨"))
    parts.append(_arrow_h(120, ROW1+40, 200, label=f"{tph} mt/h"))
    parts.append(_equipment_box(200, ROW1, 110, BOX_H, C_VGF, vgf, "Vibrating Grizzly", "〰"))

    # — grizzly bypass (oversize → jaw)
    parts.append(_arrow_h(310, ROW1+40, 390, label=f"−{cuts[0]}mm U/S"))
    parts.append(_equipment_box(390, ROW1, 110, BOX_H, C_JAW, jaw, f"CSS {schedule['jaw']['css_mm']}mm", "⚙"))

    # — jaw discharge → surge bin
    parts.append(_arrow_v(445, ROW1+BOX_H, ROW3, label=f"{tph} mt/h"))
    parts.append(_equipment_box(390, ROW3, 110, BOX_H, C_BIN, "Surge Bin", "30T capacity", "🗄"))

    # — surge bin → cone
    parts.append(_arrow_h(500, ROW3+40, 580, label=f"{tph} mt/h"))
    parts.append(_equipment_box(580, ROW3, 110, BOX_H, C_CONE, cone,
                                f"CSS {schedule['cone']['css_mm']}mm" if schedule.get('cone') else "", "🔄"))

    # — cone discharge → final screen
    parts.append(_arrow_v(635, ROW3+BOX_H, ROW5, label=f"{tph} mt/h"))
    parts.append(_equipment_box(580, ROW5, 120, BOX_H, C_SCREEN, fin, "4-Deck final", "📏"))

    # — also: VGF fines (<25mm) → belt → final screen
    parts.append(_arrow_h(310, ROW1+65, 700, label=f"Fines bypass"))
    parts.append(f'<line x1="700" y1="{ROW1+65}" x2="700" y2="{ROW5+40}" stroke="{C_ARROW}" '
                 f'stroke-width="1.5" stroke-dasharray="5,3"/>')
    parts.append(f'<line x1="700" y1="{ROW5+40}" x2="700" y2="{ROW5+40}" stroke="{C_ARROW}" stroke-width="1.5"/>')

    # — stockpiles
    stock_y = ROW5 + BOX_H + 30
    for i, (cut, prod) in enumerate(zip(cuts, prods)):
        cx = 560 + i * 60
        parts.append(_stockpile(cx, stock_y, prod, i+1))
        parts.append(_arrow_v(cx, ROW5+BOX_H, stock_y, label=f"{cut}mm"))

    return "\n".join(parts), W, H


def _build_three_stage(schedule: dict, tph: int) -> tuple[str, int, int]:
    """3-stage plant SVG body. Returns (svg_content, width, height)."""
    parts = []
    W, H = 980, 720

    vgf   = schedule["vgf"]["model"]
    jaw   = schedule["jaw"]["model"]
    cone  = (schedule.get("cone") or {}).get("model", "PROCone")
    cone_css = (schedule.get("cone") or {}).get("css_mm", "—")
    twin  = (schedule.get("cone") or {}).get("twin", False)
    vsi   = (schedule.get("vsi") or {}).get("model", "VSI")
    vsi_motor = (schedule.get("vsi") or {}).get("motor_hp", "—")
    int_scr = ((schedule.get("screens") or {}).get("intermediate") or {}).get("model", "Int. Screen")
    fin_scr = ((schedule.get("screens") or {}).get("final") or {}).get("model", "Final Screen")
    cuts  = schedule.get("gradation", {}).get("cuts_mm", [20, 12, 8, 4.75])
    prods = schedule.get("gradation", {}).get("products", [])

    # ---- Stage 1: Feed → Primary ----
    # ROM Hopper
    parts.append(_equipment_box(30, ROW1, 90, BOX_H, C_HOPPER, "ROM Hopper", "Feed ≤750mm", "🪨"))
    # VGF
    parts.append(_arrow_h(120, ROW1+40, 195, label=f"{tph} mt/h"))
    parts.append(_equipment_box(195, ROW1, 115, BOX_H, C_VGF, vgf, "Vibrating Grizzly", "〰"))
    # Jaw
    parts.append(_arrow_h(310, ROW1+40, 385, label="Oversize"))
    cone_label = f"2× {cone} (twin)" if twin else cone
    parts.append(_equipment_box(385, ROW1, 120, BOX_H, C_JAW, jaw, f"CSS {schedule['jaw']['css_mm']}mm", "⚙"))

    # Jaw discharge → Surge Bin 1 (vertical drop)
    parts.append(_arrow_v(445, ROW1+BOX_H, ROW2+10, label=f"{tph} mt/h"))

    # ---- Stage 2: Secondary Cone ----
    parts.append(_equipment_box(385, ROW2, 120, BOX_H, C_CONE, cone_label, f"CSS {cone_css}mm", "🔄"))
    # Cone → Intermediate Screen
    parts.append(_arrow_h(505, ROW2+40, 575, label=f"{tph} mt/h"))
    parts.append(_equipment_box(575, ROW2, 130, BOX_H, C_SCREEN, int_scr, "Intermediate 3-Deck", "📏"))

    # Int. Screen u/f → Surge Bin 2
    parts.append(_arrow_v(640, ROW2+BOX_H, ROW3+10, label="VSI Feed"))
    parts.append(_equipment_box(590, ROW3, 100, BOX_H, C_BIN, "Surge Bin 2", "15T", "🗄"))

    # Int. Screen oversize → back to cone (recirculation arrow)
    parts.append(
        f'<path d="M 705 {ROW2+40} C 750 {ROW2+40} 750 {ROW2+10} 510 {ROW2+10}" '
        f'fill="none" stroke="{C_ARROW}" stroke-width="1.5" stroke-dasharray="6,3" '
        f'marker-end="url(#arrowH)"/>'
    )
    parts.append(_text(730, ROW2+30, "Oversize → Recirculate", fill=C_SUBTEXT, size=8))

    # ---- Stage 3: VSI ----
    parts.append(_arrow_h(690, ROW3+40, 760, label="MVF Feed"))
    parts.append(_equipment_box(760, ROW3, 130, BOX_H, C_VSI, vsi, f"Motor: {vsi_motor}", "🌀"))

    # VSI → Final Screen
    parts.append(_arrow_v(825, ROW3+BOX_H, ROW5+10, label=f"{tph} mt/h"))

    # ---- Final Screen ----
    parts.append(_equipment_box(755, ROW5, 140, BOX_H, C_SCREEN, fin_scr, "Final 4-Deck", "📏"))

    # ---- Stockpiles ----
    stock_y = ROW5 + BOX_H + 30
    for i, (cut, prod) in enumerate(zip(cuts, prods)):
        cx = 700 + i * 65
        parts.append(_stockpile(cx, stock_y, prod, i+1))
        parts.append(_arrow_v(cx, ROW5+BOX_H, stock_y, label=f"{cut}mm"))

    return "\n".join(parts), W, H


def _build_tertiary_standalone(schedule: dict, tph: int) -> tuple[str, int, int]:
    """Tertiary-only VSI plant SVG body."""
    parts = []
    W, H = 760, 540

    vsi = (schedule.get("vsi") or {}).get("model", "VSI-5080")
    vsi_motor = (schedule.get("vsi") or {}).get("motor_hp", "2×400 HP")
    fin_scr = ((schedule.get("screens") or {}).get("final") or {}).get("model", "Screen 2.4m×8.1m")
    cuts  = schedule.get("gradation", {}).get("cuts_mm", [20, 12, 8, 4.75])
    prods = schedule.get("gradation", {}).get("products", [])

    # Feed (-50mm crushed stone)
    parts.append(_equipment_box(30, ROW1, 110, BOX_H, C_BIN, "Surge Bin", "Feed -50mm", "🗄"))
    parts.append(_text(85, ROW1-10, f"Feed: {tph} mt/h", fill=C_TONNAGE, size=9, anchor="middle"))

    # 2× MVF Feeders
    parts.append(_arrow_h(140, ROW1+40, 210, label="Regulated"))
    parts.append(_equipment_box(210, ROW1, 110, BOX_H, C_VGF, "2× MVF Feeder", "Mechanical Vibratory", "〰"))

    # VSI
    parts.append(_arrow_h(320, ROW1+40, 395, label=f"{tph} mt/h"))
    parts.append(_equipment_box(395, ROW1, 130, BOX_H, C_VSI, vsi, f"Motor: {vsi_motor}", "🌀"))

    # VSI → Screen
    parts.append(_arrow_v(460, ROW1+BOX_H, ROW3+10, label=f"{tph} mt/h"))
    parts.append(_equipment_box(390, ROW3, 140, BOX_H, C_SCREEN, fin_scr, "Final Screen 3-Deck", "📏"))

    # Stockpiles
    stock_y = ROW3 + BOX_H + 30
    for i, (cut, prod) in enumerate(zip(cuts, prods)):
        cx = 350 + i * 70
        parts.append(_stockpile(cx, stock_y, prod, i+1))
        parts.append(_arrow_v(cx, ROW3+BOX_H, stock_y, label=f"{cut}mm"))

    return "\n".join(parts), W, H


# ---------------------------------------------------------------------------
# Title + metadata header
# ---------------------------------------------------------------------------

def _header(tph, stages, material, schedule, svg_w) -> str:
    plant_type = schedule.get("plant_type", "")
    if plant_type == "tertiary_standalone":
        title = f"PROMAN Tertiary Standalone VSI Plant — {tph} mt/h"
        sub   = "Feed: -50mm crushed aggregate | VSI impact crushing + screening"
    elif stages == 2:
        title = f"PROMAN {tph} TPH 2-Stage Crushing & Screening Plant"
        sub   = f"Material: {material.title()} | Primary Jaw + Secondary Cone + Final Screen"
    else:
        title = f"PROMAN {tph} TPH 3-Stage Crushing & Screening Plant"
        sub   = f"Material: {material.title()} | Primary Jaw + Secondary Cone + Tertiary VSI"

    logo = "PROMAN"
    return (
        f'<rect x="0" y="0" width="{svg_w}" height="30" fill="{C_GRID}"/>'
        f'\n{_text(10, 20, logo, fill="#60A5FA", size=13, bold=True, anchor="start")}'
        f'\n{_text(svg_w//2, 20, title, fill=C_WHITE, size=12, bold=True)}'
        f'\n{_text(svg_w-10, 20, "AggFlow PFD", fill=C_SUBTEXT, size=9, anchor="end")}'
        f'\n<rect x="0" y="30" width="{svg_w}" height="20" fill="{C_BG}"/>'
        f'\n{_text(svg_w//2, 45, sub, fill=C_SUBTEXT, size=9)}'
    )


# ---------------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------------

def _legend(x, y) -> str:
    items = [
        (C_HOPPER, "ROM Hopper/Bin"),
        (C_VGF,    "Vibrating Feeder"),
        (C_JAW,    "Jaw Crusher"),
        (C_CONE,   "Cone Crusher"),
        (C_VSI,    "VSI Crusher"),
        (C_SCREEN, "Vibrating Screen"),
    ]
    parts = [f'<rect x="{x}" y="{y}" width="130" height="{14*len(items)+10}" '
             f'rx="4" fill="{C_GRID}" stroke="{C_BORDER}" stroke-width="1"/>',
             _text(x+65, y+12, "Legend", fill=C_TEXT, size=8, bold=True)]
    for i, (color, label) in enumerate(items):
        iy = y + 22 + i * 14
        parts.append(f'<rect x="{x+6}" y="{iy}" width="12" height="8" rx="2" fill="{color}"/>')
        parts.append(_text(x+22, iy+7, label, fill=C_SUBTEXT, size=7, anchor="start"))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

def generate_pfd_html(
    schedule: dict,
    tph: int,
    stages: int,
    material: str = "granite",
) -> str:
    """
    Generate a complete self-contained HTML page with an SVG PFD.

    Args:
        schedule: output of build_equipment_schedule() or build_tertiary_schedule()
        tph: nominal throughput
        stages: number of stages (0 = tertiary standalone)
        material: feed material name

    Returns:
        str: complete HTML document
    """
    plant_type = schedule.get("plant_type", "")

    if plant_type == "tertiary_standalone" or stages == 0:
        svg_body, svg_w, svg_h = _build_tertiary_standalone(schedule, tph)
    elif stages <= 2:
        svg_body, svg_w, svg_h = _build_two_stage(schedule, tph)
    else:
        svg_body, svg_w, svg_h = _build_three_stage(schedule, tph)

    total_h = svg_h + 60  # header offset

    header_svg = _header(tph, stages, material, schedule, svg_w)
    legend_svg = _legend(svg_w - 145, svg_h - 115)
    cuts = schedule.get("gradation", {}).get("cuts_mm", [])
    prods = schedule.get("gradation", {}).get("products", [])

    # Gradation table HTML
    grad_rows = "".join(
        f"<tr><td>{i+1}</td><td>{c} mm</td><td>{p}</td></tr>"
        for i, (c, p) in enumerate(zip(cuts, prods))
    )

    # Notes
    notes_html = "".join(f"<li>{_esc(n)}</li>" for n in schedule.get("notes", []))

    vgf_html  = _esc((schedule.get("vgf")  or {}).get("model", "—"))
    jaw_html  = _esc((schedule.get("jaw")  or {}).get("model", "—"))
    cone_html = _esc((schedule.get("cone") or {}).get("model", "—"))
    vsi_html  = _esc((schedule.get("vsi")  or {}).get("model", "—"))

    svg_full = (
        f'<svg viewBox="0 0 {svg_w} {total_h}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;max-width:{svg_w}px;display:block;margin:0 auto;">'
        + _defs()
        + f'<rect x="0" y="0" width="{svg_w}" height="{total_h}" fill="{C_BG}"/>'
        # background grid
        + "".join(
            f'<line x1="0" y1="{gy}" x2="{svg_w}" y2="{gy}" stroke="{C_GRID}" stroke-width="0.5"/>'
            for gy in range(0, total_h, 40)
        )
        + header_svg
        + f'<g transform="translate(0,55)">'
        + svg_body
        + legend_svg
        + "</g>"
        + "</svg>"
    )

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PROMAN PFD — {tph} TPH {stages}-Stage</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:{C_BG};color:{C_TEXT};font-family:'Segoe UI',Arial,sans-serif;min-height:100vh}}
  .wrap{{max-width:1100px;margin:0 auto;padding:16px}}
  .pfd-container{{background:{C_GRID};border:1px solid {C_BORDER};border-radius:8px;
    padding:12px;overflow-x:auto;margin-bottom:16px}}
  .info-grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px}}
  .card{{background:{C_GRID};border:1px solid {C_BORDER};border-radius:6px;padding:12px}}
  .card h3{{font-size:11px;text-transform:uppercase;letter-spacing:.06em;
    color:#60A5FA;margin-bottom:8px}}
  table{{width:100%;border-collapse:collapse;font-size:11px}}
  th{{background:#1E3A5F;padding:5px 8px;text-align:left;color:{C_WHITE}}}
  td{{padding:4px 8px;border-bottom:1px solid {C_BORDER};color:{C_SUBTEXT}}}
  tr:last-child td{{border-bottom:none}}
  ul{{padding-left:18px;font-size:11px;color:{C_SUBTEXT};line-height:1.7}}
  .badge{{display:inline-block;padding:2px 8px;border-radius:12px;font-size:10px;
    font-weight:bold;margin-right:4px}}
  .badge-tph{{background:#1E3A5F;color:#93C5FD}}
  .badge-stg{{background:#1A2D1A;color:#6EE7B7}}
  .badge-mat{{background:#2D1A1A;color:#FCA5A5}}
</style>
</head>
<body>
<div class="wrap">
  <div style="margin-bottom:10px">
    <span class="badge badge-tph">{tph} TPH</span>
    <span class="badge badge-stg">{stages if stages>0 else "Tertiary"}-Stage</span>
    <span class="badge badge-mat">{material.title()}</span>
  </div>
  <div class="pfd-container">{svg_full}</div>
  <div class="info-grid">
    <div class="card">
      <h3>Equipment Schedule</h3>
      <table>
        <tr><th>Item</th><th>Model</th></tr>
        {'<tr><td>VGF</td><td>' + vgf_html + '</td></tr>' if schedule.get('vgf') else ''}
        {'<tr><td>Jaw Crusher</td><td>' + jaw_html + '</td></tr>' if schedule.get('jaw') else ''}
        {'<tr><td>Cone Crusher</td><td>' + cone_html + '</td></tr>' if schedule.get('cone') else ''}
        {'<tr><td>VSI Crusher</td><td>' + vsi_html + '</td></tr>' if schedule.get('vsi') else ''}
      </table>
    </div>
    <div class="card">
      <h3>Product Gradation</h3>
      <table>
        <tr><th>#</th><th>Cut Size</th><th>Product</th></tr>
        {grad_rows}
      </table>
    </div>
  </div>
  <div class="card">
    <h3>Design Notes</h3>
    <ul>{notes_html}</ul>
  </div>
</div>
</body>
</html>"""

    return html_doc


# ---------------------------------------------------------------------------
# Quick standalone test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from engine.equipment_selector import build_equipment_schedule, build_tertiary_schedule

    configs = [
        (150, 2, "granite"), (150, 3, "granite"),
        (250, 2, "granite"), (250, 3, "basalt"),
        (300, 3, "limestone"), (600, 3, "gabro"),
    ]
    for tph, stg, mat in configs:
        sched = build_equipment_schedule(tph, stg, mat)
        html  = generate_pfd_html(sched, tph, stg, mat)
        fname = f"/tmp/pfd_{tph}_{stg}stage.html"
        with open(fname, "w") as f:
            f.write(html)
        print(f"Written: {fname}  ({len(html)//1024} KB)")

    # Tertiary standalone
    sched = build_tertiary_schedule(600, "gabro")
    html  = generate_pfd_html(sched, 600, 0, "gabro")
    with open("/tmp/pfd_600_tertiary.html", "w") as f:
        f.write(html)
    print("Written: /tmp/pfd_600_tertiary.html")
