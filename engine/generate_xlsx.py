"""
PROMAN Price Schedule Generator
Produces an Annexure-4-style Excel workbook from a Quotation object.
Requires: openpyxl
"""

import openpyxl
from openpyxl.styles import (Font, Alignment, PatternFill, Border, Side,
                              numbers as xl_numbers)
from openpyxl.utils import get_column_letter
from datetime import date as dt_date
import math
import sys
import os

# Add parent dir to path if running standalone
sys.path.insert(0, os.path.dirname(__file__))

from engine import Quotation, build_quotation, PlantSpec, quote_standalone_equipment


# ---------------------------------------------------------------------------
# STYLE CONSTANTS
# ---------------------------------------------------------------------------
HEADER_FILL   = PatternFill("solid", fgColor="1F3864")   # dark navy
SUBHDR_FILL   = PatternFill("solid", fgColor="2E75B6")   # PROMAN blue
SECTION_FILL  = PatternFill("solid", fgColor="BDD7EE")   # light blue
TOTAL_FILL    = PatternFill("solid", fgColor="F2CC0C")   # yellow
WARNING_FILL  = PatternFill("solid", fgColor="FFD966")   # amber
WHITE_FILL    = PatternFill("solid", fgColor="FFFFFF")
ALT_FILL      = PatternFill("solid", fgColor="EBF3FB")   # very light blue

WHITE_FONT    = Font(name="Calibri", color="FFFFFF", bold=True, size=10)
BOLD_FONT     = Font(name="Calibri", bold=True, size=10)
NORMAL_FONT   = Font(name="Calibri", size=10)
SMALL_FONT    = Font(name="Calibri", size=9, italic=True, color="595959")

THIN_BORDER   = Border(
    left=Side(style="thin"),  right=Side(style="thin"),
    top=Side(style="thin"),   bottom=Side(style="thin"),
)
CENTRE        = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT          = Alignment(horizontal="left",   vertical="center", wrap_text=True)

LAKH_FMT      = '#,##0.00'


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _set(ws, row, col, value, font=None, fill=None, align=None, num_fmt=None, border=True):
    cell = ws.cell(row=row, column=col, value=value)
    if font:    cell.font    = font
    if fill:    cell.fill    = fill
    if align:   cell.alignment = align
    if num_fmt: cell.number_format = num_fmt
    if border:  cell.border  = THIN_BORDER
    return cell


def _merge(ws, r1, c1, r2, c2, value="", font=None, fill=None, align=CENTRE, border=True):
    ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)
    cell = ws.cell(row=r1, column=c1, value=value)
    if font:   cell.font   = font
    if fill:   cell.fill   = fill
    if align:  cell.alignment = align
    if border: cell.border = THIN_BORDER
    return cell


def _section_header(ws, row, col_span, label):
    """Draw a coloured section header spanning the full width."""
    _merge(ws, row, 1, row, col_span, label,
           font=WHITE_FONT, fill=SUBHDR_FILL, align=LEFT)


def _row_fill(row_idx):
    return ALT_FILL if row_idx % 2 == 0 else WHITE_FILL


# ---------------------------------------------------------------------------
# MAIN WORKBOOK BUILDER
# ---------------------------------------------------------------------------

COLS = {
    "sl":    1,   # A
    "desc":  2,   # B
    "size":  3,   # C
    "qty":   4,   # D
    "hp":    5,   # E — Drive Motors in HP
    "list":  6,   # F — Price List Rs. Lakhs
    "best":  7,   # G — Price Best Rs. Lakhs
}
N_COLS = 7


def build_workbook(q: Quotation, out_path: str) -> str:
    """
    Write the price schedule workbook and return the file path.
    q        : Quotation object from engine.build_quotation()
    out_path : full path including filename, e.g. ".../Quote_Dakshayini.xlsx"
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Price Schedule"

    # Column widths
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 52
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 8
    ws.column_dimensions["E"].width = 12
    ws.column_dimensions["F"].width = 14
    ws.column_dimensions["G"].width = 14

    spec  = q.spec
    today = spec.date or dt_date.today().strftime("%d-%m-%Y")

    row = 1

    # -----------------------------------------------------------------------
    # Title block
    # -----------------------------------------------------------------------
    _merge(ws, row, 1, row, N_COLS,
           "PROMAN INFRASTRUCTURE SERVICES PVT. LTD., BANGALORE-560074",
           font=Font(name="Calibri", bold=True, size=13, color="FFFFFF"),
           fill=HEADER_FILL, align=CENTRE)
    ws.row_dimensions[row].height = 22
    row += 1

    _merge(ws, row, 1, row, N_COLS, "PRICE SCHEDULE — ANNEXURE 4",
           font=Font(name="Calibri", bold=True, size=11, color="FFFFFF"),
           fill=HEADER_FILL, align=CENTRE)
    ws.row_dimensions[row].height = 18
    row += 1

    # Ref / Client / Date row
    meta_font = Font(name="Calibri", bold=True, size=10)
    _merge(ws, row, 1, row, 3, f"Ref. No.: {spec.ref_no}", font=meta_font, fill=SECTION_FILL, align=LEFT)
    _merge(ws, row, 4, row, N_COLS, f"Date: {today}", font=meta_font, fill=SECTION_FILL, align=LEFT)
    row += 1

    _merge(ws, row, 1, row, 3, f"Client: M/s. {spec.client_name}", font=meta_font, fill=SECTION_FILL, align=LEFT)
    stages_text = "Porta" if spec.mobile else "Stationary"
    _merge(ws, row, 4, row, N_COLS,
           f"Plant: {spec.tph} TPH, {spec.stages}-Stage, {stages_text}, Aggregate Crushing & Screening Plant",
           font=meta_font, fill=SECTION_FILL, align=LEFT)
    row += 1

    # Column headers
    headers = ["Sl.", "Description", "Size/Model", "Qty", "HP", "List (₹ L)", "Best (₹ L)"]
    for ci, hdr in enumerate(headers, 1):
        _set(ws, row, ci, hdr, font=WHITE_FONT, fill=HEADER_FILL, align=CENTRE)
    ws.row_dimensions[row].height = 20
    row += 1

    # -----------------------------------------------------------------------
    # SUB A — Main Mechanical Equipment
    # -----------------------------------------------------------------------
    _section_header(ws, row, N_COLS, "A   MAIN MECHANICAL EQUIPMENT")
    ws.row_dimensions[row].height = 18
    row += 1

    alt = 0
    for item in q.sub_a_items:
        fill = _row_fill(alt)
        has_flag = bool(item.flags)
        row_fill = WARNING_FILL if has_flag else fill

        _set(ws, row, COLS["sl"],   item.sl,           font=NORMAL_FONT, fill=row_fill, align=CENTRE)
        desc_val = item.description
        if has_flag:
            desc_val += "  ⚠️"
        _set(ws, row, COLS["desc"], desc_val,           font=NORMAL_FONT, fill=row_fill, align=LEFT)
        _set(ws, row, COLS["size"], "",                 font=NORMAL_FONT, fill=row_fill, align=CENTRE)
        _set(ws, row, COLS["qty"],  item.qty,           font=NORMAL_FONT, fill=row_fill, align=CENTRE)
        _set(ws, row, COLS["hp"],   item.hp if item.hp else "", font=NORMAL_FONT, fill=row_fill, align=CENTRE)

        if item.list_price is not None:
            _set(ws, row, COLS["list"], item.list_price,
                 font=NORMAL_FONT, fill=row_fill, align=CENTRE, num_fmt=LAKH_FMT)
        else:
            _set(ws, row, COLS["list"], "Engineering quote",
                 font=Font(name="Calibri", size=9, color="C00000"), fill=WARNING_FILL, align=CENTRE)

        if item.best_price is not None:
            _set(ws, row, COLS["best"], item.best_price,
                 font=NORMAL_FONT, fill=row_fill, align=CENTRE, num_fmt=LAKH_FMT)
        else:
            _set(ws, row, COLS["best"], "Engineering quote",
                 font=Font(name="Calibri", size=9, color="C00000"), fill=WARNING_FILL, align=CENTRE)

        row += 1; alt += 1

    # Sub Total A
    _merge(ws, row, 1, row, COLS["qty"], "Sub Total A", font=BOLD_FONT, fill=TOTAL_FILL, align=LEFT)
    _set(ws, row, COLS["hp"],   q.sub_a_hp(),   font=BOLD_FONT, fill=TOTAL_FILL, align=CENTRE)
    _set(ws, row, COLS["list"], q.sub_a_list(), font=BOLD_FONT, fill=TOTAL_FILL, align=CENTRE, num_fmt=LAKH_FMT)
    _set(ws, row, COLS["best"], q.sub_a_best(), font=BOLD_FONT, fill=TOTAL_FILL, align=CENTRE, num_fmt=LAKH_FMT)
    ws.row_dimensions[row].height = 16
    row += 1

    # -----------------------------------------------------------------------
    # SUB B — Belt Conveyor System
    # -----------------------------------------------------------------------
    _section_header(ws, row, N_COLS, "B   BELT CONVEYOR SYSTEM")
    ws.row_dimensions[row].height = 18
    row += 1

    alt = 0
    for i, conv in enumerate(q.sub_b_conveyors, 1):
        fill = _row_fill(alt)
        _set(ws, row, COLS["sl"],   str(i),                   font=NORMAL_FONT, fill=fill, align=CENTRE)
        _set(ws, row, COLS["desc"], f"Inclined Belt Conveyor {conv.tag}", font=NORMAL_FONT, fill=fill, align=LEFT)
        _set(ws, row, COLS["size"], f"{conv.width_mm}mm × {conv.length_m}m", font=NORMAL_FONT, fill=fill, align=CENTRE)
        _set(ws, row, COLS["qty"],  1,                         font=NORMAL_FONT, fill=fill, align=CENTRE)
        _set(ws, row, COLS["hp"],   conv.hp,                   font=NORMAL_FONT, fill=fill, align=CENTRE)
        _set(ws, row, COLS["list"], conv.cost_lakhs,           font=NORMAL_FONT, fill=fill, align=CENTRE, num_fmt=LAKH_FMT)
        _set(ws, row, COLS["best"], conv.cost_lakhs,           font=NORMAL_FONT, fill=fill, align=CENTRE, num_fmt=LAKH_FMT)
        row += 1; alt += 1

    # Supports & Chutes
    fill = _row_fill(alt)
    _set(ws, row, COLS["sl"],   str(len(q.sub_b_conveyors) + 1), font=NORMAL_FONT, fill=fill, align=CENTRE)
    _merge(ws, row, COLS["desc"], row, COLS["size"],
           "Supports and Chutes for Belt Conveyor System", font=NORMAL_FONT, fill=fill, align=LEFT)
    _set(ws, row, COLS["qty"],  "1 lot",                font=NORMAL_FONT, fill=fill, align=CENTRE)
    _set(ws, row, COLS["hp"],   "",                     font=NORMAL_FONT, fill=fill, align=CENTRE)
    _set(ws, row, COLS["list"], q.sub_b_chutes_list,    font=NORMAL_FONT, fill=fill, align=CENTRE, num_fmt=LAKH_FMT)
    _set(ws, row, COLS["best"], q.sub_b_chutes_best,    font=NORMAL_FONT, fill=fill, align=CENTRE, num_fmt=LAKH_FMT)
    row += 1

    # Sub Total B
    _merge(ws, row, 1, row, COLS["qty"], "Sub Total B", font=BOLD_FONT, fill=TOTAL_FILL, align=LEFT)
    _set(ws, row, COLS["hp"],   q.sub_b_hp(),           font=BOLD_FONT, fill=TOTAL_FILL, align=CENTRE)
    _set(ws, row, COLS["list"], q.sub_b_total_list(),   font=BOLD_FONT, fill=TOTAL_FILL, align=CENTRE, num_fmt=LAKH_FMT)
    _set(ws, row, COLS["best"], q.sub_b_total_best(),   font=BOLD_FONT, fill=TOTAL_FILL, align=CENTRE, num_fmt=LAKH_FMT)
    ws.row_dimensions[row].height = 16
    row += 1

    # -----------------------------------------------------------------------
    # SUB C — Structural Steel
    # -----------------------------------------------------------------------
    _section_header(ws, row, N_COLS, "C   STRUCTURAL STEEL FABRICATED ITEMS")
    ws.row_dimensions[row].height = 18
    row += 1

    struct_items = _structural_line_items(q.spec)
    alt = 0
    for si, (desc, qty_str) in enumerate(struct_items, 1):
        fill = _row_fill(alt)
        _set(ws, row, COLS["sl"],   str(si),  font=NORMAL_FONT, fill=fill, align=CENTRE)
        _merge(ws, row, COLS["desc"], row, COLS["size"], desc, font=NORMAL_FONT, fill=fill, align=LEFT)
        _set(ws, row, COLS["qty"],  qty_str,  font=NORMAL_FONT, fill=fill, align=CENTRE)
        _set(ws, row, COLS["hp"],   "",       font=NORMAL_FONT, fill=fill, align=CENTRE)
        _set(ws, row, COLS["list"], "",       font=NORMAL_FONT, fill=fill, align=CENTRE)
        _set(ws, row, COLS["best"], "",       font=NORMAL_FONT, fill=fill, align=CENTRE)
        row += 1; alt += 1

    # Sub Total C
    _merge(ws, row, 1, row, COLS["qty"], "Sub Total C", font=BOLD_FONT, fill=TOTAL_FILL, align=LEFT)
    _set(ws, row, COLS["hp"],   "",                          font=BOLD_FONT, fill=TOTAL_FILL, align=CENTRE)
    _set(ws, row, COLS["list"], q.sub_c_structural_list,     font=BOLD_FONT, fill=TOTAL_FILL, align=CENTRE, num_fmt=LAKH_FMT)
    _set(ws, row, COLS["best"], q.sub_c_structural_best,     font=BOLD_FONT, fill=TOTAL_FILL, align=CENTRE, num_fmt=LAKH_FMT)
    ws.row_dimensions[row].height = 16
    row += 1

    # -----------------------------------------------------------------------
    # SUB D — Electrical
    # -----------------------------------------------------------------------
    _section_header(ws, row, N_COLS, "D   ELECTRICAL SCOPE OF WORK")
    ws.row_dimensions[row].height = 18
    row += 1

    elec_items = [
        ("MCC Panel for Plant Operation (with Soft Starter for largest drive)", "1 set"),
        ("Cable Tray, Power & Control Cables — MCC Panel to Individual Motors", "1 set"),
    ]
    alt = 0
    for ei, (desc, qty_str) in enumerate(elec_items, 1):
        fill = _row_fill(alt)
        _set(ws, row, COLS["sl"],   str(ei),  font=NORMAL_FONT, fill=fill, align=CENTRE)
        _merge(ws, row, COLS["desc"], row, COLS["size"], desc, font=NORMAL_FONT, fill=fill, align=LEFT)
        _set(ws, row, COLS["qty"],  qty_str,  font=NORMAL_FONT, fill=fill, align=CENTRE)
        _set(ws, row, COLS["hp"],   "",       font=NORMAL_FONT, fill=fill, align=CENTRE)
        _set(ws, row, COLS["list"], "",       font=NORMAL_FONT, fill=fill, align=CENTRE)
        _set(ws, row, COLS["best"], "",       font=NORMAL_FONT, fill=fill, align=CENTRE)
        row += 1; alt += 1

    # Sub Total D
    _merge(ws, row, 1, row, COLS["qty"], "Sub Total D", font=BOLD_FONT, fill=TOTAL_FILL, align=LEFT)
    _set(ws, row, COLS["hp"],   "",              font=BOLD_FONT, fill=TOTAL_FILL, align=CENTRE)
    _set(ws, row, COLS["list"], q.sub_d_list,    font=BOLD_FONT, fill=TOTAL_FILL, align=CENTRE, num_fmt=LAKH_FMT)
    _set(ws, row, COLS["best"], q.sub_d_best,    font=BOLD_FONT, fill=TOTAL_FILL, align=CENTRE, num_fmt=LAKH_FMT)
    ws.row_dimensions[row].height = 16
    row += 1

    # -----------------------------------------------------------------------
    # TOTAL A+B+C+D
    # -----------------------------------------------------------------------
    total_fill = PatternFill("solid", fgColor="1F3864")
    _merge(ws, row, 1, row, COLS["hp"]-1, "TOTAL  (A + B + C + D)",
           font=WHITE_FONT, fill=total_fill, align=LEFT)
    _set(ws, row, COLS["hp"],   q.total_hp(),       font=WHITE_FONT, fill=total_fill, align=CENTRE)
    _set(ws, row, COLS["list"], q.total_list(),      font=WHITE_FONT, fill=total_fill, align=CENTRE, num_fmt=LAKH_FMT)
    _set(ws, row, COLS["best"], q.total_best(),      font=WHITE_FONT, fill=total_fill, align=CENTRE, num_fmt=LAKH_FMT)
    ws.row_dimensions[row].height = 18
    row += 1

    # -----------------------------------------------------------------------
    # SUB E — Erection & Commissioning
    # -----------------------------------------------------------------------
    _merge(ws, row, 1, row, COLS["hp"]-1, "E   ERECTION & COMMISSIONING",
           font=BOLD_FONT, fill=SECTION_FILL, align=LEFT)
    _set(ws, row, COLS["hp"],   "",             font=BOLD_FONT, fill=SECTION_FILL, align=CENTRE)
    _set(ws, row, COLS["list"], q.erection,     font=BOLD_FONT, fill=SECTION_FILL, align=CENTRE, num_fmt=LAKH_FMT)
    _set(ws, row, COLS["best"], q.erection,     font=BOLD_FONT, fill=SECTION_FILL, align=CENTRE, num_fmt=LAKH_FMT)
    ws.row_dimensions[row].height = 18
    row += 1

    # Grand Total
    gt_fill = PatternFill("solid", fgColor="375623")
    _merge(ws, row, 1, row, COLS["hp"]-1, "GRAND TOTAL  (A + B + C + D + E)",
           font=Font(name="Calibri", bold=True, color="FFFFFF", size=11), fill=gt_fill, align=LEFT)
    _set(ws, row, COLS["hp"],   "",                     font=WHITE_FONT, fill=gt_fill, align=CENTRE)
    _set(ws, row, COLS["list"], q.grand_total_list(),   font=Font(name="Calibri", bold=True, color="FFFFFF", size=11),
         fill=gt_fill, align=CENTRE, num_fmt=LAKH_FMT)
    _set(ws, row, COLS["best"], q.grand_total_best(),   font=Font(name="Calibri", bold=True, color="FFFFFF", size=11),
         fill=gt_fill, align=CENTRE, num_fmt=LAKH_FMT)
    ws.row_dimensions[row].height = 20
    row += 1

    # -----------------------------------------------------------------------
    # NOTES & WARNINGS
    # -----------------------------------------------------------------------
    row += 1
    if q.warnings:
        _merge(ws, row, 1, row, N_COLS, "⚠️  ITEMS REQUIRING ENGINEERING / SALES REVIEW  ⚠️",
               font=Font(name="Calibri", bold=True, color="C00000", size=10),
               fill=WARNING_FILL, align=LEFT, border=False)
        row += 1
        for w in q.warnings:
            ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=N_COLS)
            cell = ws.cell(row=row, column=1, value=f"  •  {w}")
            cell.font = Font(name="Calibri", size=9, color="C00000")
            cell.alignment = LEFT
            row += 1

    row += 1
    notes = [
        "Note 1: Prices are Ex-Works Bangalore. GST as applicable at time of dispatch is extra.",
        "Note 2: Freight, Transit insurance, and Transportation charges are extra — payable by client.",
        "Note 3: Crane for erection activity is in client's scope.",
        "Note 4: Delivery: 12–14 weeks from receipt of technically & commercially clear purchase order and advance.",
        "Note 5: Payment: 40% non-refundable advance with PO; balance 60% + 100% GST against Proforma Invoice prior to dispatch.",
        "Note 6: This offer is valid for 30 days from date of issue.",
    ]
    for note in notes:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=N_COLS)
        cell = ws.cell(row=row, column=1, value=note)
        cell.font = SMALL_FONT
        cell.alignment = LEFT
        row += 1

    # -----------------------------------------------------------------------
    # Freeze panes & save
    # -----------------------------------------------------------------------
    ws.freeze_panes = "B7"   # freeze title rows, keep columns scrollable

    wb.save(out_path)
    return out_path


# ---------------------------------------------------------------------------
# STRUCTURAL ITEMS DESCRIPTION BUILDER
# ---------------------------------------------------------------------------

def _structural_line_items(spec):
    """Returns list of (description, qty_str) for Sub C narrative."""
    items = []
    cap = 50 if spec.tph > 350 else 30
    items.append((
        f"{cap}-Ton Capacity ROM Hopper — Common Frame, Supports, Feed & Discharge Chutes, "
        "Platform for VGF and Jaw Crusher",
        "1 lot"
    ))
    items.append((
        "Tunnel / Under-crusher Hopper with Gate for Cone Feed — Supports & Chutes for MVF",
        "1 lot"
    ))
    items.append((
        "30-Ton Capacity Surge Hopper with Gate — Feed Cone with Supports & Chutes for Mech. Feeder",
        "1 lot"
    ))
    items.append((
        "Common Frame for Cone Crusher — Feed & Discharge Chutes; "
        "Supports, Z-Frame, Walkway, Platform, Handrails, Staircase, Feed & Discharge Chutes for Vibratory Screen",
        "1 lot"
    ))
    if spec.stages == 3:
        items.append((
            "Supports, Z-Frame, Walkway, Platform, Handrails, Staircase — Pre-Screen & VSI-stage",
            "1 lot"
        ))
        items.append((
            "Transfer Tower, Discharge Chutes for VSI — Guards, Diverting Chutes, VSI Bypass Chutes",
            "1 lot"
        ))
    else:
        items.append((
            "Miscellaneous Guards, Diverting Chutes, Transfer Chutes, etc.",
            "1 lot"
        ))
    return items


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys, os

    out_dir = os.path.dirname(__file__)

    # Test 1: Standalone VSI-300 (Chiman Bhai)
    r = quote_standalone_equipment("VSI", "300")
    print("=== VSI-300 Standalone ===")
    print(f"  Status: {r['status']}  |  List: {r['list']}L  |  Best: {r['best']}L  |  HP: {r['hp']}")
    if r.get('starter_soft'):
        s = r['starter_soft']
        print(f"  Soft Starter: List {s['list']}L  /  Best {s['best']}L")

    print()

    # Test 2: Full 2-stage 250TPH plant
    spec = PlantSpec(
        client_name="Test Client — 2 Stage",
        tph=250,
        stages=2,
        products=["GSB", "-20+10mm", "-10+6mm", "-6+4.75mm", "0-4.75mm"],
        ref_no="PR/08-26/N-TEST",
    )
    q = build_quotation(spec)
    out_path = os.path.join(out_dir, "test_quote_2stage_250tph.xlsx")
    build_workbook(q, out_path)
    print(f"=== 2-Stage 250TPH ===")
    print(f"  Grand Total List: ₹{q.grand_total_list()} Lakhs")
    print(f"  Grand Total Best: ₹{q.grand_total_best()} Lakhs")
    print(f"  File: {out_path}")
    if q.warnings:
        print("  WARNINGS:")
        for w in q.warnings: print(f"    ⚠️  {w}")
