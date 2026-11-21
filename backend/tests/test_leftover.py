import random
import time

import pytest
from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from revalo.engine.leftover import LeftoverOptions, compute_leftover
from revalo.engine.model import KerfSide, SheetLayout


def sheet(parts, w=3000, h=1500):
    return SheetLayout(outline=box(0, 0, w, h), parts=parts)


def check_invariants(layout, result, kerf, side=KerfSide.OUTSIDE):
    blocked = unary_union(layout.parts)
    blocked = blocked.buffer(kerf if side is KerfSide.OUTSIDE else kerf / 2, join_style="mitre")
    for rem in result.remnants:
        poly = rem.polygon.buffer(-0.002, join_style="mitre")  # whole-mm snapping tolerance
        assert layout.outline.covers(poly), "remnant leaves the sheet"
        assert poly.intersection(blocked).area < 1e-6, "remnant overlaps a part or its cut"
    for i, a in enumerate(result.remnants):
        for b in result.remnants[i + 1 :]:
            assert a.polygon.distance(b.polygon) >= kerf - 1e-6, "remnants need a cut between them"
    total = result.parts_area + result.remnant_area + result.kerf_area + result.scrap_area
    assert total == pytest.approx(result.sheet_area, rel=1e-6)


def test_empty_sheet_is_one_full_remnant():
    layout = sheet([])
    result = compute_leftover(layout, KerfSide.OUTSIDE, LeftoverOptions(kerf_mm=0.2))
    assert len(result.remnants) == 1
    rem = result.remnants[0]
    assert (rem.width, rem.height) == (3000, 1500)
    assert result.scrap_area == pytest.approx(0)


def test_classic_end_of_sheet_remnant():
    # Parts fill the first 1000 mm; the rest of the sheet is one clean remnant.
    parts = [box(0, y, 1000, y + 290) for y in range(0, 1500, 300)]
    layout = sheet(parts)
    result = compute_leftover(layout, KerfSide.OUTSIDE, LeftoverOptions(kerf_mm=0.2))
    big = result.remnants[0]
    assert (big.x, big.width, big.height) == (1001, 1999, 1500)
    check_invariants(layout, result, 0.2)


def test_narrow_gaps_are_scrap_not_remnants():
    parts = [box(0, 0, 3000, 1450)]
    layout = sheet(parts)
    result = compute_leftover(layout, KerfSide.OUTSIDE, LeftoverOptions(kerf_mm=1, min_side_mm=100))
    assert result.remnants == []
    assert result.scrap_area > 0
    check_invariants(layout, result, 1)


def test_large_hole_slug_can_be_a_remnant():
    frame = Polygon(
        [(0, 0), (1000, 0), (1000, 1000), (0, 1000)],
        [[(100, 100), (900, 100), (900, 900), (100, 900)]],
    )
    layout = sheet([frame, box(1010, 0, 3000, 1500)])
    result = compute_leftover(layout, KerfSide.OUTSIDE, LeftoverOptions(kerf_mm=0.5))
    inside = [r for r in result.remnants if r.polygon.within(box(100, 100, 900, 900))]
    assert inside and inside[0].width >= 798
    check_invariants(layout, result, 0.5)


def test_part_nested_in_a_hole_blocks_that_space():
    frame = Polygon(
        [(0, 0), (1000, 0), (1000, 1000), (0, 1000)],
        [[(100, 100), (900, 100), (900, 900), (100, 900)]],
    )
    nested = box(150, 150, 850, 850)
    layout = sheet([frame, nested, box(1010, 0, 3000, 1500)])
    result = compute_leftover(layout, KerfSide.OUTSIDE, LeftoverOptions(kerf_mm=0.5))
    assert not any(r.polygon.intersects(box(100, 100, 900, 900)) for r in result.remnants)
    check_invariants(layout, result, 0.5)


def test_centered_kerf_shrinks_part_material():
    loop = box(100, 100, 200, 200)
    layout = sheet([loop], w=1000, h=1000)
    result = compute_leftover(layout, KerfSide.CENTERED, LeftoverOptions(kerf_mm=6))
    assert result.parts_area == pytest.approx(94 * 94)
    check_invariants(layout, result, 6, KerfSide.CENTERED)


def test_random_laser_nest_invariants_and_speed():
    rng = random.Random(7)
    parts = []
    for _ in range(180):
        x, y = rng.uniform(0, 2000), rng.uniform(0, 1400)
        candidate = (
            Point(x, y).buffer(rng.uniform(15, 60))
            if rng.random() < 0.3
            else box(x, y, x + rng.uniform(30, 160), y + rng.uniform(30, 100))
        )
        if all(candidate.distance(p) > 2 for p in parts) and box(0, 0, 3000, 1500).contains(
            candidate
        ):
            parts.append(candidate)
    layout = sheet(parts)
    start = time.perf_counter()
    result = compute_leftover(layout, KerfSide.OUTSIDE, LeftoverOptions(kerf_mm=0.3))
    elapsed = time.perf_counter() - start
    assert result.remnants, "the untouched end of the sheet must be found"
    assert result.remnants[0].x >= 2000
    check_invariants(layout, result, 0.3)
    assert elapsed < 5.0
