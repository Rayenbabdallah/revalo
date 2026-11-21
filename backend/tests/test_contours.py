import pytest

from revalo.engine.contours import assemble_loops, build_parts, containment_depths


def square(x, y, s, close=True):
    pts = [(x, y), (x + s, y), (x + s, y + s), (x, y + s)]
    return pts + [pts[0]] if close else pts


def test_closed_paths_become_loops():
    result = assemble_loops([square(0, 0, 10), square(20, 0, 5)])
    assert len(result.loops) == 2
    assert result.open_paths == 0


def test_chain_of_segments_with_small_gaps_is_closed():
    gap = 0.01
    segments = [
        [(0, 0), (100, 0)],
        [(100 + gap, 0), (100, 50)],
        [(100, 50 + gap), (0, 50)],
        [(0, 50), (0, gap)],
    ]
    result = assemble_loops(segments, tol=0.05)
    assert len(result.loops) == 1
    assert result.loops[0].area == pytest.approx(5000, rel=1e-3)


def test_unclosable_path_is_reported():
    result = assemble_loops([[(0, 0), (10, 0), (10, 10)]])
    assert result.loops == []
    assert result.open_paths == 1


def test_duplicate_loops_are_removed():
    result = assemble_loops([square(0, 0, 10), square(0, 0, 10)])
    assert len(result.loops) == 1


def test_tiny_loops_are_ignored():
    result = assemble_loops([square(0, 0, 0.1)])
    assert result.loops == []


def test_depths_and_part_with_hole_and_nested_part():
    outer = square(0, 0, 100)
    hole = square(20, 20, 60)
    nested_part = square(40, 40, 20)
    loops = assemble_loops([outer, hole, nested_part]).loops
    depth, _ = containment_depths(loops)
    assert sorted(depth) == [0, 1, 2]

    parts = build_parts(loops)
    assert len(parts) == 2
    areas = sorted(p.area for p in parts)
    assert areas[0] == pytest.approx(400)  # nested 20x20 part
    assert areas[1] == pytest.approx(100 * 100 - 60 * 60)  # outer part minus its hole
