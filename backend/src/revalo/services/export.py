"""Remnants as DXF, so nesting software can use them as sheets.

Each remnant is a closed rectangle at its real size in millimetres, on layer
REMNANT, laid out in rows with a gap between pieces. Its code, size and
material are written on layer LABEL, so the outline layer stays clean for
import as remnant sheets.
"""

from __future__ import annotations

import io
import math

import ezdxf

from revalo.db.models import Piece
from revalo.engine.materials import materials

GAP_MM = 50.0
ROW_WIDTH_MM = 6000.0


def remnants_dxf(pieces: list[Piece]) -> bytes:
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 4  # millimetres
    doc.layers.add("REMNANT", color=3)
    doc.layers.add("LABEL", color=7)
    msp = doc.modelspace()

    x = y = row_height = 0.0
    for piece in pieces:
        w, h = piece.width_mm or 0.0, piece.height_mm or 0.0
        if w <= 0 or h <= 0:
            continue
        if x > 0 and x + w > ROW_WIDTH_MM:
            x, y = 0.0, y + row_height + GAP_MM
            row_height = 0.0
        msp.add_lwpolyline(
            [(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
            close=True,
            dxfattribs={"layer": "REMNANT"},
        )
        mat = materials().get(piece.material_code or "")
        thickness = f" {piece.thickness_mm:g} mm" if piece.thickness_mm else ""
        text_h = max(min(40.0, min(w, h) / 6), 4.0)
        msp.add_text(
            f"{piece.code} {w:.0f}x{h:.0f}",
            height=text_h,
            dxfattribs={"layer": "LABEL", "insert": (x + text_h, y + text_h)},
        )
        msp.add_text(
            f"{mat.name_en if mat else piece.material_code or ''}{thickness}",
            height=text_h * 0.7,
            dxfattribs={"layer": "LABEL", "insert": (x + text_h, y + text_h * 2.4)},
        )
        x += w + GAP_MM
        row_height = max(row_height, h)

    out = io.StringIO()
    doc.write(out)
    return out.getvalue().encode("utf-8")


def export_name(pieces: list[Piece]) -> str:
    if len(pieces) == 1:
        return f"{pieces[0].code}.dxf"
    first = pieces[0]
    thickness = f"_{first.thickness_mm:g}mm" if first.thickness_mm else ""
    return f"remnants_{first.material_code}{thickness}_{len(pieces)}.dxf".replace(" ", "")


def total_area(pieces: list[Piece]) -> float:
    return math.fsum((p.width_mm or 0) * (p.height_mm or 0) for p in pieces)
