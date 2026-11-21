"""Generate the synthetic sample jobs in samples/synthetic.

Each file imitates what a real workshop exports: a fibre-laser nest with parts
placed as blocks and a washer nested inside a flange, a stainless nest exploded
into loose lines and arcs, a plasma program with lead-ins, a router program
with multiple depth passes and hinge bores, and a French panel-saw cut list.

Usage: uv run python scripts/make_samples.py
"""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf

OUT = Path(__file__).resolve().parents[2] / "samples" / "synthetic"


# --- DXF helpers -----------------------------------------------------------------


def _poly(layout, pts, layer="0"):
    layout.add_lwpolyline(pts, close=True, dxfattribs={"layer": layer})


def _rect(layout, x, y, w, h, layer="0"):
    _poly(layout, [(x, y), (x + w, y), (x + w, y + h), (x, y + h)], layer)


def laser_nest() -> None:
    """3000 x 1500 S235 3 mm fibre-laser nest, parts as block references."""
    doc = ezdxf.new("R2013")
    doc.header["$INSUNITS"] = 4
    for name in ("SHEET", "CUT", "MARKING", "TEXT"):
        doc.layers.add(name)

    bracket = doc.blocks.new("BRACKET_200x120")
    _rect(bracket, 0, 0, 200, 120, "CUT")
    for x in (25, 175):
        bracket.add_circle((x, 60), 6.5, dxfattribs={"layer": "CUT"})
    bracket.add_line((90, 60), (110, 60), dxfattribs={"layer": "MARKING"})

    flange = doc.blocks.new("FLANGE_D250")
    flange.add_circle((0, 0), 125, dxfattribs={"layer": "CUT"})
    flange.add_circle((0, 0), 60, dxfattribs={"layer": "CUT"})
    for k in range(6):
        a = math.radians(60 * k)
        flange.add_circle((95 * math.cos(a), 95 * math.sin(a)), 9, dxfattribs={"layer": "CUT"})

    washer = doc.blocks.new("WASHER_D80")
    washer.add_circle((0, 0), 40, dxfattribs={"layer": "CUT"})
    washer.add_circle((0, 0), 8.5, dxfattribs={"layer": "CUT"})

    gusset = doc.blocks.new("GUSSET_150")
    _poly(gusset, [(0, 0), (150, 0), (0, 150)], "CUT")
    gusset.add_circle((35, 35), 8.5, dxfattribs={"layer": "CUT"})

    l_plate = doc.blocks.new("L_PLATE_300x200")
    _poly(l_plate, [(0, 0), (300, 0), (300, 80), (80, 80), (80, 200), (0, 200)], "CUT")

    msp = doc.modelspace()
    _rect(msp, 0, 0, 3000, 1500, "SHEET")
    gap = 6
    # Column of flanges, each with a washer nested in its centre hole.
    for row in range(5):
        cx, cy = 10 + 125, 10 + 125 + row * (250 + gap)
        if cy + 125 > 1490:
            break
        msp.add_blockref("FLANGE_D250", (cx, cy), dxfattribs={"layer": "CUT"})
        msp.add_blockref("WASHER_D80", (cx, cy), dxfattribs={"layer": "CUT"})
    # Brackets in a grid.
    for col in range(3):
        for row in range(11):
            x = 280 + col * (200 + gap)
            y = 10 + row * (120 + gap)
            if y + 120 > 1490:
                break
            msp.add_blockref("BRACKET_200x120", (x, y), dxfattribs={"layer": "CUT"})
    # L-plates and gussets.
    for row in range(6):
        y = 10 + row * (200 + gap + 30)
        if y + 200 > 1490:
            break
        msp.add_blockref("L_PLATE_300x200", (910, y), dxfattribs={"layer": "CUT"})
        msp.add_blockref("GUSSET_150", (1220, y), dxfattribs={"layer": "CUT"})
        msp.add_blockref(
            "GUSSET_150", (1530, y + 150), dxfattribs={"layer": "CUT", "rotation": 180}
        )
    msp.add_text(
        "JOB 2026-118  S235JR 3mm  3000x1500",
        dxfattribs={"layer": "TEXT", "height": 20, "insert": (1600, 1450)},
    )
    doc.saveas(OUT / "laser_S235_3mm_3000x1500.dxf")


def _rounded_rect_entities(msp, x, y, w, h, r, gap=0.004):
    """Rounded rectangle as loose LINE and ARC entities with tiny gaps, as exploded exports."""
    msp.add_line((x + r, y), (x + w - r, y))
    msp.add_arc((x + w - r, y + r), r, 270, 360)
    msp.add_line((x + w, y + r + gap), (x + w, y + h - r))
    msp.add_arc((x + w - r, y + h - r), r, 0, 90)
    msp.add_line((x + w - r, y + h), (x + r + gap, y + h))
    msp.add_arc((x + r, y + h - r), r, 90, 180)
    msp.add_line((x, y + h - r), (x, y + r - gap))
    msp.add_arc((x + r, y + r), r, 180, 270)


def inox_exploded() -> None:
    """2500 x 1250 stainless nest exploded to lines/arcs, no sheet layer."""
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4
    msp = doc.modelspace()
    for a, b in [
        ((0, 0), (2500, 0)),
        ((2500, 0), (2500, 1250)),
        ((2500, 1250), (0, 1250)),
        ((0, 1250), (0, 0)),
    ]:
        msp.add_line(a, b)
    for col in range(3):
        for row in range(4):
            x, y = 10 + col * 406, 10 + row * 256
            _rounded_rect_entities(msp, x, y, 400, 250, 15)
            msp.add_circle((x + 200, y + 125), 40)
    for k in range(6):
        msp.add_circle((1300 + 60, 70 + k * 125), 55)
    doc.saveas(OUT / "inox_304_1.5mm_2500x1250.dxf")


# --- G-code helpers ----------------------------------------------------------------


def _fmt(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def plasma_program() -> None:
    """2000 x 1000 S355 10 mm plasma program, M07/M08 torch, lead-ins on every contour."""
    lines = ["%", "(PLASMA S355 10MM  SHEET 2000X1000)", "G21", "G90", "G91.1"]

    def hole(cx, cy, r):
        lines.append(f"G0 X{_fmt(cx)} Y{_fmt(cy)}")
        lines.append("M07")
        lines.append(f"G1 X{_fmt(cx + r)} Y{_fmt(cy)} F1800")  # lead-in from centre
        lines.append(f"G3 X{_fmt(cx + r)} Y{_fmt(cy)} I{_fmt(-r)} J0")
        lines.append("M08")

    def plate(x, y, w, h):
        lines.append(f"G0 X{_fmt(x - 8)} Y{_fmt(y + 20)}")
        lines.append("M07")
        lines.append(f"G1 X{_fmt(x)} Y{_fmt(y + 20)} F1500")  # lead-in from outside
        for px, py in [(x, y), (x + w, y), (x + w, y + h), (x, y + h), (x, y + 20)]:
            lines.append(f"G1 X{_fmt(px)} Y{_fmt(py)}")
        lines.append("M08")

    for col in range(4):
        for row in range(3):
            x, y = 20 + col * 320, 20 + row * 320
            for hx, hy in [(40, 40), (260, 40), (40, 260), (260, 260)]:
                hole(x + hx, y + hy, 11)
            plate(x, y, 300, 300)
    lines += ["G0 X0 Y0", "M30", "%"]
    (OUT / "plasma_S355_10mm_2000x1000.nc").write_text("\n".join(lines) + "\n")


def router_program() -> None:
    """2440 x 1220 MDF 18 mm router program: 6 mm tool, two depth passes, hinge bores."""
    r_tool = 3.0
    lines = ["(MDF 18MM 2440X1220 - TOOL T1 D6 FLAT)", "G21 G90 G17", "M3 S18000", "G0 Z15"]

    def bore(cx, cy, d=35, depth=-13):
        r = d / 2 - r_tool
        lines.append(f"G0 X{_fmt(cx + r)} Y{_fmt(cy)}")
        lines.append(f"G1 Z{depth} F600")
        lines.append(f"G2 X{_fmt(cx + r)} Y{_fmt(cy)} I{_fmt(-r)} J0 F3000")
        lines.append("G0 Z15")

    def profile(x, y, w, h, corner):
        # Tool-centre path outside the finished part (climb cut).
        x0, y0, x1, y1 = x - r_tool, y - r_tool, x + w + r_tool, y + h + r_tool
        rc = corner + r_tool
        for depth in (-9, -18.3):
            lines.append(f"G0 X{_fmt(x0 + rc)} Y{_fmt(y0)}")
            lines.append(f"G1 Z{depth} F800")
            lines.append(f"G1 X{_fmt(x1 - rc)} Y{_fmt(y0)} F6000")
            lines.append(f"G3 X{_fmt(x1)} Y{_fmt(y0 + rc)} R{_fmt(rc)}")
            lines.append(f"G1 X{_fmt(x1)} Y{_fmt(y1 - rc)}")
            lines.append(f"G3 X{_fmt(x1 - rc)} Y{_fmt(y1)} R{_fmt(rc)}")
            lines.append(f"G1 X{_fmt(x0 + rc)} Y{_fmt(y1)}")
            lines.append(f"G3 X{_fmt(x0)} Y{_fmt(y1 - rc)} R{_fmt(rc)}")
            lines.append(f"G1 X{_fmt(x0)} Y{_fmt(y0 + rc)}")
            lines.append(f"G3 X{_fmt(x0 + rc)} Y{_fmt(y0)} R{_fmt(rc)}")
            lines.append("G0 Z15")

    space = 2 * r_tool + 6
    # Two cabinet doors with hinge bores, then side panels and shelves.
    for i in range(2):
        x, y = 15 + i * (447 + space), 15
        bore(x + 22.5, y + 100)
        bore(x + 22.5, y + 616)
        profile(x, y, 447, 716, corner=3)
    for i in range(2):
        profile(15 + 2 * (447 + space) + i * (560 + space), 15, 560, 720, corner=0)
    for i in range(3):
        profile(15, 15 + 716 + space + i * (120 + space), 900, 120, corner=0)
    lines += ["G0 Z25", "M5", "G0 X0 Y0", "M30"]
    (OUT / "router_MDF_18mm_2440x1220.nc").write_text("\n".join(lines) + "\n")


def cut_list() -> None:
    """French kitchen cabinet cut list as exported from a spreadsheet (semicolons)."""
    rows = [
        "Désignation;Longueur;Largeur;Qté;Fil;Matière;Épaisseur",
        "Panneau;2800;2070;1;;MDF;18",
        "Côté caisson bas;720;560;4;oui;MDF;18",
        "Fond caisson bas;764;560;2;oui;MDF;18",
        "Étagère;762;520;4;non;MDF;18",
        "Traverse;764;100;4;non;MDF;18",
        "Façade tiroir;596,5;140;6;oui;MDF;18",
        "Porte haute;715;396;4;oui;MDF;18",
        "Plinthe;2400;120;1;oui;MDF;18",
    ]
    (OUT / "cuisine_MDF_18mm.csv").write_bytes(("\r\n".join(rows) + "\r\n").encode("utf-8-sig"))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    laser_nest()
    inox_exploded()
    plasma_program()
    router_program()
    cut_list()
    for path in sorted(OUT.iterdir()):
        print(f"{path.name:<38} {path.stat().st_size:>8} bytes")


if __name__ == "__main__":
    main()
