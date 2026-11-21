"""Options and sheet detection shared by the importers."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from shapely import affinity
from shapely.geometry import Polygon, box

from revalo.engine.contours import build_parts
from revalo.engine.materials import infer_sheet_size
from revalo.engine.model import SheetLayout


@dataclass
class ImportOptions:
    """Facts the file may not contain, supplied by the user or a machine preset."""

    sheet_width_mm: float | None = None
    sheet_height_mm: float | None = None
    material_code: str | None = None
    thickness_mm: float | None = None
    kerf_mm: float | None = None
    """Cut width. For G-code this is the tool or beam diameter."""
    trim_mm: float = 0.0
    """Edge trim removed from each panel before packing a cut list."""
    allow_rotation: bool = True
    """Cut lists only: allow parts to be rotated 90 degrees (no grain direction)."""

    @property
    def sheet_size(self) -> tuple[float, float] | None:
        if self.sheet_width_mm and self.sheet_height_mm:
            w, h = self.sheet_width_mm, self.sheet_height_mm
            return (max(w, h), min(w, h))
        return None


# Common commercial sheet and panel sizes in millimetres (long side, short side).
STANDARD_SHEETS: tuple[tuple[float, float], ...] = (
    (2000, 1000),
    (2500, 1250),
    (3000, 1500),
    (4000, 2000),
    (6000, 2000),
    (2440, 1220),
    (2500, 1220),
    (2800, 2070),
    (2750, 1830),
    (3050, 1525),
)


def is_rectangle(poly: Polygon, tolerance: float = 0.01) -> bool:
    mrr = poly.minimum_rotated_rectangle
    return mrr.area > 0 and abs(poly.area / mrr.area - 1.0) <= tolerance


def _rect_dims(poly: Polygon) -> tuple[float, float]:
    coords = list(poly.minimum_rotated_rectangle.exterior.coords)
    a = math.dist(coords[0], coords[1])
    b = math.dist(coords[1], coords[2])
    return (max(a, b), min(a, b))


def matches_size(poly: Polygon, size: tuple[float, float], rel: float = 0.01) -> bool:
    w, h = _rect_dims(poly)
    return abs(w - size[0]) <= size[0] * rel and abs(h - size[1]) <= size[1] * rel


def is_standard_sheet(poly: Polygon) -> bool:
    return is_rectangle(poly) and any(matches_size(poly, s) for s in STANDARD_SHEETS)


def normalize_sheet(layout: SheetLayout) -> SheetLayout:
    """Rotate a sheet to be axis-aligned and move its corner to the origin."""
    outline, parts = layout.outline, layout.parts
    coords = list(outline.minimum_rotated_rectangle.exterior.coords)
    angle = math.degrees(math.atan2(coords[1][1] - coords[0][1], coords[1][0] - coords[0][0]))
    angle = ((angle + 45) % 90) - 45  # smallest rotation that makes edges axis-aligned
    if abs(angle) > 0.01:
        origin = outline.centroid
        outline = affinity.rotate(outline, -angle, origin=origin)
        parts = [affinity.rotate(p, -angle, origin=origin) for p in parts]
    minx, miny, _, _ = outline.bounds
    if abs(minx) > 1e-9 or abs(miny) > 1e-9:
        outline = affinity.translate(outline, -minx, -miny)
        parts = [affinity.translate(p, -minx, -miny) for p in parts]
    return SheetLayout(outline=outline, parts=parts, sheet_detected=layout.sheet_detected)


def _inside(container: Polygon, poly: Polygon) -> bool:
    return container.buffer(0.5).contains(poly)


def assumed_sheet(
    loops: Sequence[Polygon], options: ImportOptions, source_name: str
) -> tuple[Polygon, str]:
    """Sheet outline when the file has none: given size, size in the name, or bounding box."""
    minx = min(p.bounds[0] for p in loops)
    miny = min(p.bounds[1] for p in loops)
    maxx = max(p.bounds[2] for p in loops)
    maxy = max(p.bounds[3] for p in loops)
    size = options.sheet_size or infer_sheet_size(source_name)
    if size:
        span_w, span_h = maxx - minx, maxy - miny
        w, h = size if span_w >= span_h else (size[1], size[0])
        ox = 0.0 if minx >= -0.5 and maxx <= w + 0.5 else minx
        oy = 0.0 if miny >= -0.5 and maxy <= h + 0.5 else miny
        return box(ox, oy, ox + w, oy + h), (
            f"No sheet outline in the file; assumed a {w:.0f} x {h:.0f} mm sheet."
        )
    return box(minx, miny, maxx, maxy), (
        "No sheet outline or sheet size; used the parts' bounding box, so remnants "
        "outside the cut area are not counted. Enter the sheet size for a full result."
    )


def split_into_sheets(
    loops: list[Polygon],
    sheet_candidates: list[Polygon],
    options: ImportOptions,
    source_name: str,
) -> tuple[list[SheetLayout], list[str]]:
    """Decide which loops are sheets and assign every other loop to its sheet.

    `sheet_candidates` are loops found on a layer named like a sheet. Without
    them, top-level rectangles that enclose other loops are treated as sheets
    when they look like stock (standard size, matching the given size, or
    holding a substantial share of cut area).
    """
    warnings: list[str] = []
    if not loops and not sheet_candidates:
        return [], ["No closed contours found in the file."]

    sheets: list[Polygon] = list(sheet_candidates)
    remaining = list(loops)

    if not sheets and remaining:
        top = [p for p in remaining if not any(o is not p and _inside(o, p) for o in remaining)]
        given = options.sheet_size or infer_sheet_size(source_name)

        def sheet_like(p: Polygon) -> bool:
            if not is_rectangle(p):
                return False
            children = [o for o in remaining if o is not p and _inside(p, o)]
            if not children:
                return False
            if (given and matches_size(p, given)) or is_standard_sheet(p):
                return True
            return sum(c.area for c in children) >= 0.15 * p.area and len(children) >= 2

        if top and all(sheet_like(p) for p in top):
            sheets = top
            remaining = [p for p in remaining if all(p is not s for s in sheets)]

    layouts: list[SheetLayout] = []
    if sheets:
        sheets.sort(key=lambda s: (round(s.bounds[1]), s.bounds[0]))
        unassigned = list(remaining)
        for sheet in sheets:
            inside = [p for p in unassigned if _inside(sheet, p)]
            unassigned = [p for p in unassigned if all(p is not q for q in inside)]
            layouts.append(SheetLayout(outline=sheet, parts=build_parts(inside)))
        if unassigned:
            warnings.append(
                f"{len(unassigned)} contour(s) lie outside every sheet and were ignored."
            )
    else:
        outline, note = assumed_sheet(remaining, options, source_name)
        warnings.append(note)
        layouts.append(
            SheetLayout(outline=outline, parts=build_parts(remaining), sheet_detected=False)
        )

    return [normalize_sheet(layout) for layout in layouts], warnings
