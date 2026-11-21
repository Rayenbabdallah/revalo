"""Check stock before cutting: place a coming job's parts on stored remnants.

Each part is treated as its bounding rectangle (the conservative choice: a part
always fits where its rectangle fits). Remnants are filled with guillotine cuts,
the same way a panel saw or a simple nest would, so the layout is cuttable.
Smallest suitable remnants are used first, keeping large remnants whole for
large parts.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely.geometry import Polygon

from revalo.engine.importers.cutlist import CutPart, _Rect


@dataclass(frozen=True)
class PartSize:
    label: str
    length: float
    width: float
    rotatable: bool = True

    @property
    def area(self) -> float:
        return self.length * self.width


@dataclass(frozen=True)
class StockRemnant:
    id: str
    code: str
    width: float
    height: float


@dataclass
class Placement:
    part: PartSize
    x: float
    y: float
    width: float
    height: float


@dataclass
class RemnantUse:
    remnant: StockRemnant
    placements: list[Placement] = field(default_factory=list)

    @property
    def used_area(self) -> float:
        return sum(p.width * p.height for p in self.placements)

    @property
    def fill(self) -> float:
        return self.used_area / (self.remnant.width * self.remnant.height)


@dataclass
class FitPlan:
    uses: list[RemnantUse]
    unplaced: list[PartSize]

    @property
    def placed_count(self) -> int:
        return sum(len(u.placements) for u in self.uses)

    @property
    def placed_area(self) -> float:
        return sum(u.used_area for u in self.uses)


def part_size(label: str, poly: Polygon) -> PartSize:
    """The smallest rectangle around a part, at any angle."""
    rect = poly.minimum_rotated_rectangle
    coords = list(rect.exterior.coords)
    a = math.dist(coords[0], coords[1])
    b = math.dist(coords[1], coords[2])
    return PartSize(label, round(max(a, b), 1), round(min(a, b), 1))


# Packing rules: how to rank free rectangles for a part, and how to cut what is left.
# No single rule wins every time, so each plan is tried with all of them.
_RULES = [
    (fit, split, orient)
    for fit in ("short_side", "area")
    for split in ("shorter", "longer")
    for orient in ("free", "upright")
]


def _choose(
    free: list[_Rect], sizes: list[tuple[float, float]], kerf: float, rule: str, orient: str
):
    best = None
    for index, rect in enumerate(free):
        fitting = [
            (w, h) for w, h in sizes if w + kerf <= rect.w + 1e-9 and h + kerf <= rect.h + 1e-9
        ]
        if orient == "upright":
            fitting = fitting[:1]  # turn the part only where upright does not fit
        for w, h in fitting:
            cw, ch = w + kerf, h + kerf
            waste = rect.w * rect.h - cw * ch
            short = min(rect.w - cw, rect.h - ch)
            score = (short, waste) if rule == "short_side" else (waste, short)
            if best is None or score < best[0]:
                best = (score, index, w, h)
    return None if best is None else best[1:]


def _cut(rect: _Rect, cw: float, ch: float, rule: str) -> list[_Rect]:
    right_w, top_h = rect.w - cw, rect.h - ch
    horizontal = right_w < top_h if rule == "shorter" else right_w >= top_h
    if horizontal:
        new = [_Rect(rect.x + cw, rect.y, right_w, ch), _Rect(rect.x, rect.y + ch, rect.w, top_h)]
    else:
        new = [_Rect(rect.x + cw, rect.y, right_w, rect.h), _Rect(rect.x, rect.y + ch, cw, top_h)]
    return [r for r in new if r.w > 1e-6 and r.h > 1e-6]


def _plan(parts, remnants, kerf, fit_rule, split_rule, orient) -> FitPlan:
    order = sorted(parts, key=lambda p: (p.area, max(p.length, p.width)), reverse=True)
    free: dict[str, list[_Rect]] = {}
    uses: dict[str, RemnantUse] = {}
    unplaced: list[PartSize] = []
    for part in order:
        sizes = [(part.length, part.width)]
        if part.rotatable and part.length != part.width:
            sizes.append((part.width, part.length))
        placed = False
        # Remnants already started come first, so parts share a remnant instead of
        # opening a new one each; then the smallest unopened remnant that fits.
        for remnant in sorted(remnants, key=lambda r: (r.id not in uses, r.width * r.height)):
            rects = free.setdefault(
                remnant.id, [_Rect(0.0, 0.0, remnant.width + kerf, remnant.height + kerf)]
            )
            fit = _choose(rects, sizes, kerf, fit_rule, orient)
            if fit is None:
                continue
            index, w, h = fit
            rect = rects.pop(index)
            rects.extend(_cut(rect, w + kerf, h + kerf, split_rule))
            uses.setdefault(remnant.id, RemnantUse(remnant)).placements.append(
                Placement(part, rect.x, rect.y, w, h)
            )
            placed = True
            break
        if not placed:
            unplaced.append(part)
    return FitPlan(sorted(uses.values(), key=lambda u: -u.used_area), unplaced)


def plan_fit(parts: list[PartSize], remnants: list[StockRemnant], kerf: float) -> FitPlan:
    """Best plan over all packing rules: most area placed, then fewest remnants opened."""
    plans = [_plan(parts, remnants, kerf, f, s, o) for f, s, o in _RULES]
    return max(plans, key=lambda plan: (round(plan.placed_area, 3), -len(plan.uses)))


def parts_from_cutlist(parts: list[CutPart]) -> list[PartSize]:
    return [PartSize(p.label, p.length, p.width, p.rotatable) for p in parts]
