import pytest
from shapely.geometry import Point, box

from revalo.engine.fit import PartSize, StockRemnant, part_size, plan_fit


def test_parts_go_on_the_smallest_remnant_that_fits():
    remnants = [
        StockRemnant("big", "RV-BIG", 1469, 1500),
        StockRemnant("small", "RV-SML", 228, 154),
    ]
    plan = plan_fit([PartSize("tab", 200, 120)], remnants, kerf=0.2)
    assert [u.remnant.id for u in plan.uses] == ["small"]
    assert not plan.unplaced


def test_several_parts_share_a_remnant_without_overlap():
    remnants = [StockRemnant("r1", "RV-1", 1000, 500)]
    parts = [PartSize(f"p{i}", 300, 200) for i in range(6)]
    plan = plan_fit(parts, remnants, kerf=3)
    assert plan.placed_count == 6 and not plan.unplaced
    boxes = [box(p.x, p.y, p.x + p.width, p.y + p.height) for p in plan.uses[0].placements]
    for i, a in enumerate(boxes):
        assert box(0, 0, 1000, 500).buffer(1e-6).contains(a)
        for b in boxes[i + 1 :]:
            assert a.distance(b) >= 3 - 1e-6


def test_parts_too_big_for_any_remnant_are_reported():
    plan = plan_fit([PartSize("door", 2000, 600)], [StockRemnant("r", "RV", 1469, 1500)], kerf=0.2)
    assert [p.label for p in plan.unplaced] == ["door"]
    assert plan.uses == []


def test_rotation_is_used_unless_grain_forbids_it():
    remnant = [StockRemnant("strip", "RV", 1530, 109)]
    assert plan_fit([PartSize("rail", 100, 1200)], remnant, kerf=0.2).placed_count == 1
    fixed = PartSize("rail", 100, 1200, rotatable=False)
    assert plan_fit([fixed], remnant, kerf=0.2).placed_count == 0


def test_part_size_uses_the_tightest_rectangle():
    assert part_size("disc", Point(0, 0).buffer(50)).length == pytest.approx(100, abs=1)
    rotated = box(0, 0, 300, 100)
    from shapely import affinity

    size = part_size("bar", affinity.rotate(rotated, 30))
    assert (size.length, size.width) == pytest.approx((300, 100), abs=0.5)
