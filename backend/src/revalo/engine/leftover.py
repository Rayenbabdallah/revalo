"""Leftover geometry: reusable remnants and skeleton scrap for one sheet.

What a workshop can reuse or sell is a clean rectangle, not an arbitrary
shape. The free area of the sheet (sheet minus parts minus the cut band) is
searched for the largest rectangle whose shorter side is still useful, that
rectangle is set aside with one more kerf for the separating cut, and the
search repeats. Everything else (the skeleton between parts, the slugs from
holes, slivers too small to use) is scrap that only sells by weight.

The search runs on a coarse grid for speed, then each rectangle is grown back
to exact edges with real geometry checks, so results are precise to well under
a millimetre and never overlap a part.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import shapely
from shapely.geometry import MultiPolygon, Polygon, box
from shapely.ops import unary_union

from revalo.engine.model import KerfSide, SheetLayout

MAX_GRID_CELLS = 120_000
SNAP_MM = 0.001


@dataclass
class LeftoverOptions:
    kerf_mm: float
    min_side_mm: float = 100.0
    """Shorter side a remnant needs to be worth keeping."""
    min_area_mm2: float = 0.0
    max_remnants: int = 12
    grid_mm: float = 2.0
    """Finest search grid; coarsened automatically on large sheets."""


@dataclass
class Remnant:
    x: float
    y: float
    width: float
    height: float

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def polygon(self) -> Polygon:
        return box(self.x, self.y, self.x + self.width, self.y + self.height)

    @property
    def long_side(self) -> float:
        return max(self.width, self.height)

    @property
    def short_side(self) -> float:
        return min(self.width, self.height)


@dataclass
class SheetLeftover:
    sheet_area: float
    parts_area: float
    kerf_area: float
    remnants: list[Remnant]
    scrap_area: float
    part_geometry: list[Polygon] = field(default_factory=list)
    scrap_geometry: Polygon | MultiPolygon | None = None

    @property
    def remnant_area(self) -> float:
        return sum(r.area for r in self.remnants)

    @property
    def utilization(self) -> float:
        return self.parts_area / self.sheet_area if self.sheet_area else 0.0


def _largest_rectangle(mask: np.ndarray, min_cells: int) -> tuple[int, int, int, int] | None:
    """Largest all-true rectangle whose shorter side spans at least `min_cells`.

    Classic histogram method: each row is the base of a histogram of how many
    true cells stand above it. Returns (row, col, n_rows, n_cols) or None.
    """
    rows, cols = mask.shape
    heights = np.zeros(cols, dtype=np.int32)
    best_area = 0
    best: tuple[int, int, int, int] | None = None
    for r in range(rows):
        heights = np.where(mask[r], heights + 1, 0)
        if heights.max(initial=0) < min_cells:
            continue
        stack: list[tuple[int, int]] = []
        for c, h in enumerate([*heights.tolist(), 0]):
            start = c
            while stack and stack[-1][1] >= h:
                s, sh = stack.pop()
                width = c - s
                if sh >= min_cells and width >= min_cells and sh * width > best_area:
                    best_area = sh * width
                    best = (r - sh + 1, s, sh, width)
                start = s
            stack.append((start, h))
    return best


def _grow(rect: tuple[float, float, float, float], free: Polygon | MultiPolygon, step: float):
    """Push each edge of a rectangle outward as far as the free area allows."""
    x0, y0, x1, y1 = rect
    for side in range(4):
        lo, hi = 0.0, step
        for _ in range(22):
            mid = (lo + hi) / 2
            cand = [x0, y0, x1, y1]
            cand[side] += -mid if side < 2 else mid
            if free.covers(box(*cand)):
                lo = mid
            else:
                hi = mid
        if side == 0:
            x0 -= lo
        elif side == 1:
            y0 -= lo
        elif side == 2:
            x1 += lo
        else:
            y1 += lo
    return x0, y0, x1, y1


def _whole_mm(x0: float, y0: float, x1: float, y1: float) -> tuple[float, float, float, float]:
    """Snap inward to whole millimetres, the precision a workshop measures in."""
    t = SNAP_MM
    return math.ceil(x0 - t), math.ceil(y0 - t), math.floor(x1 + t), math.floor(y1 + t)


def compute_leftover(
    sheet: SheetLayout, kerf_side: KerfSide, options: LeftoverOptions
) -> SheetLeftover:
    outline = sheet.outline
    kerf = max(options.kerf_mm, 0.0)
    # Holes stay open: a large cut-out drops a slug that can itself be a remnant.
    # Parts nested inside another part's hole are separate parts, so they block it.
    parts = unary_union(sheet.parts) if sheet.parts else Polygon()

    if kerf_side is KerfSide.CENTERED:
        # Contours are tool-centre paths: half the kerf lies on each side.
        material = [p.buffer(-kerf / 2, join_style="mitre") for p in sheet.parts]
        blocked = parts.buffer(kerf / 2, join_style="mitre") if kerf else parts
    else:
        # Contours are finished edges: the kerf lies outside the part and inside holes.
        material = list(sheet.parts)
        blocked = parts.buffer(kerf, join_style="mitre") if kerf else parts
    material = [m for m in material if not m.is_empty]
    parts_area = sum(m.area for m in material)
    cut_length = sum(p.length for p in sheet.parts)  # outer edges and holes
    kerf_area = min(cut_length * kerf, max(outline.area - parts_area, 0.0))

    free = outline.difference(blocked)
    remnants: list[Remnant] = []
    min_side = max(options.min_side_mm, 1.0)

    if not free.is_empty and free.area >= min_side * min_side:
        minx, miny, maxx, maxy = outline.bounds
        grid = max(options.grid_mm, math.sqrt(outline.area / MAX_GRID_CELLS))
        cols, rows = int((maxx - minx) // grid), int((maxy - miny) // grid)
        cx = minx + (np.arange(cols) + 0.5) * grid
        cy = miny + (np.arange(rows) + 0.5) * grid
        xx, yy = np.meshgrid(cx, cy)
        # A cell counts as free only if the whole cell is inside the free area.
        eroded = free.buffer(-grid * 0.71, join_style="mitre")
        if eroded.is_empty:
            mask = np.zeros_like(xx, dtype=bool)
        else:
            mask = shapely.contains_xy(eroded, xx, yy)
        shapely.prepare(free)
        min_cells = max(1, math.ceil(min_side / grid) - 1)

        while len(remnants) < options.max_remnants:
            found = _largest_rectangle(mask, min_cells)
            if found is None:
                break
            r, c, nr, nc = found
            rect = (
                minx + c * grid,
                miny + r * grid,
                minx + (c + nc) * grid,
                miny + (r + nr) * grid,
            )
            # Cells were tested by centre on an eroded area; confirm and grow exactly.
            if not free.covers(box(*rect)):
                shrink = grid * 0.75
                rect = (rect[0] + shrink, rect[1] + shrink, rect[2] - shrink, rect[3] - shrink)
            x0, y0, x1, y1 = _whole_mm(*_grow(rect, free, grid * 1.5))
            # Clear the chosen cells first so a rejected rectangle is not found again.
            mask[r : r + nr, c : c + nc] = False
            width, height = x1 - x0, y1 - y0
            if (
                min(width, height) >= min_side
                and width * height >= options.min_area_mm2
                and free.covers(box(x0, y0, x1, y1).buffer(-SNAP_MM, join_style="mitre"))
            ):
                remnants.append(Remnant(x0, y0, width, height))
                # The separating cut takes one more kerf around the remnant.
                reserve = box(x0, y0, x1, y1).buffer(kerf + grid * 0.71, join_style="mitre")
                rb = reserve.bounds
                c0 = max(int((rb[0] - minx) // grid), 0)
                r0 = max(int((rb[1] - miny) // grid), 0)
                c1 = min(int(math.ceil((rb[2] - minx) / grid)), cols)
                r1 = min(int(math.ceil((rb[3] - miny) / grid)), rows)
                mask[r0:r1, c0:c1] = False
                free = free.difference(box(x0, y0, x1, y1).buffer(kerf, join_style="mitre"))
                shapely.prepare(free)

    remnants.sort(key=lambda rem: rem.area, reverse=True)
    remnant_area = sum(r.area for r in remnants)
    scrap_area = max(outline.area - parts_area - remnant_area - kerf_area, 0.0)
    keep = unary_union([*material, *(rem.polygon for rem in remnants)])
    scrap_geometry = outline.difference(keep) if not keep.is_empty else outline

    return SheetLeftover(
        sheet_area=outline.area,
        parts_area=parts_area,
        kerf_area=kerf_area,
        remnants=remnants,
        scrap_area=scrap_area,
        part_geometry=material,
        scrap_geometry=scrap_geometry,
    )
