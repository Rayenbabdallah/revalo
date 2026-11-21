"""SVG preview of an analysis: sheet, parts, remnants and scrap."""

from __future__ import annotations

from html import escape

from shapely.geometry import MultiPolygon, Polygon

from revalo.engine.pipeline import AnalysisResult

SHEET_GAP_MM = 60.0
COLORS = {
    "sheet": "#e7e5e4",
    "sheet_stroke": "#a8a29e",
    "part": "#334155",
    "scrap": "#f59e0b",
    "remnant": "#10b981",
    "remnant_stroke": "#047857",
    "text": "#0f172a",
}


def _ring_path(coords, flip_y: float, offset_y: float) -> str:
    pts = [(x, offset_y + flip_y - y) for x, y in coords]
    if not pts:
        return ""
    head = f"M{pts[0][0]:.2f},{pts[0][1]:.2f}"
    return head + "".join(f"L{x:.2f},{y:.2f}" for x, y in pts[1:]) + "Z"


def _poly_path(poly: Polygon, flip_y: float, offset_y: float) -> str:
    rings = [poly.exterior, *poly.interiors]
    return "".join(_ring_path(r.coords, flip_y, offset_y) for r in rings)


def _geom_path(geom: Polygon | MultiPolygon | None, flip_y: float, offset_y: float) -> str:
    if geom is None or geom.is_empty:
        return ""
    polys = [g for g in getattr(geom, "geoms", [geom]) if isinstance(g, Polygon)]
    return "".join(_poly_path(p, flip_y, offset_y) for p in polys)


def render_svg(result: AnalysisResult, width_px: int = 1200) -> str:
    if not result.sheets:
        return '<svg xmlns="http://www.w3.org/2000/svg"/>'
    max_w = max(s.width for s in result.sheets)
    total_h = sum(s.height for s in result.sheets) + SHEET_GAP_MM * (len(result.sheets) - 1)
    height_px = int(width_px * total_h / max_w)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {max_w:.1f} {total_h:.1f}" '
        f'width="{width_px}" height="{height_px}" font-family="Inter, Arial, sans-serif">'
    ]
    offset = 0.0
    for sheet in result.sheets:
        h = sheet.height
        lo = sheet.leftover
        stroke = max(sheet.width, h) / 1500
        out.append(
            f'<path d="{_poly_path(sheet.outline, h, offset)}" fill="{COLORS["sheet"]}" '
            f'stroke="{COLORS["sheet_stroke"]}" stroke-width="{stroke * 2:.2f}"/>'
        )
        scrap = _geom_path(lo.scrap_geometry, h, offset)
        if scrap:
            out.append(
                f'<path d="{scrap}" fill="{COLORS["scrap"]}" fill-opacity="0.35" '
                'fill-rule="evenodd"/>'
            )
        parts = "".join(_poly_path(p, h, offset) for p in lo.part_geometry)
        if parts:
            out.append(f'<path d="{parts}" fill="{COLORS["part"]}" fill-rule="evenodd"/>')
        for i, rem in enumerate(lo.remnants):
            x, y = rem.x, offset + h - rem.y - rem.height
            out.append(
                f'<rect x="{x:.2f}" y="{y:.2f}" width="{rem.width:.2f}" height="{rem.height:.2f}" '
                f'fill="{COLORS["remnant"]}" fill-opacity="0.55" '
                f'stroke="{COLORS["remnant_stroke"]}" '
                f'stroke-width="{stroke * 2:.2f}"/>'
            )
            size = min(rem.short_side / 5, max(sheet.width, h) / 30)
            weight = result.weight(rem.area)
            label = f"R{i + 1}  {rem.width:.0f} x {rem.height:.0f}"
            if weight is not None:
                label += f"  {weight:.1f} kg"
            out.append(
                f'<text x="{x + rem.width / 2:.2f}" y="{y + rem.height / 2:.2f}" '
                f'font-size="{size:.1f}" fill="{COLORS["text"]}" text-anchor="middle" '
                f'dominant-baseline="middle">{escape(label)}</text>'
            )
        offset += h + SHEET_GAP_MM
    out.append("</svg>")
    return "".join(out)
