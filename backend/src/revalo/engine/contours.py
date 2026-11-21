"""Assemble raw cut paths into closed loops and organize them into parts.

CNC files rarely hand over clean polygons. A part outline can be one closed
polyline, or a chain of lines and arcs whose endpoints almost meet. This module
turns any mix of paths into closed loops, then uses containment to tell part
outlines from holes (and from parts nested inside other parts' holes).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from shapely import STRtree
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import linemerge, polygonize, unary_union
from shapely.validation import make_valid

Point = tuple[float, float]
Path = Sequence[Point]

MIN_LOOP_AREA_MM2 = 0.5


@dataclass
class LoopSet:
    loops: list[Polygon]
    open_paths: int
    """Paths that could not be closed into a loop (ignored)."""


def _dist2(a: Point, b: Point) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _clean_polygon(points: Sequence[Point]) -> Polygon | None:
    if len(points) < 3:
        return None
    poly = Polygon(points)
    if not poly.is_valid:
        fixed = make_valid(poly)
        candidates = [g for g in getattr(fixed, "geoms", [fixed]) if isinstance(g, Polygon)]
        if not candidates:
            return None
        poly = max(candidates, key=lambda g: g.area)
    if poly.area < MIN_LOOP_AREA_MM2:
        return None
    # Loops are outlines only; holes are rebuilt later from containment.
    return Polygon(poly.exterior)


def _snap_endpoints(paths: list[list[Point]], tol: float) -> list[list[Point]]:
    """Move path endpoints that lie within `tol` of each other onto one point."""
    cell = max(tol, 1e-9)
    grid: dict[tuple[int, int], list[Point]] = {}

    def snap(p: Point) -> Point:
        gx, gy = int(p[0] // cell), int(p[1] // cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for rep in grid.get((gx + dx, gy + dy), ()):
                    if _dist2(rep, p) <= tol * tol:
                        return rep
        grid.setdefault((gx, gy), []).append(p)
        return p

    out = []
    for path in paths:
        if len(path) < 2:
            continue
        snapped = list(path)
        snapped[0] = snap(path[0])
        snapped[-1] = snap(path[-1])
        out.append(snapped)
    return out


def assemble_loops(paths: Iterable[Path], tol: float = 0.05) -> LoopSet:
    """Turn closed and open paths into closed loops.

    A path whose ends are within `tol` is treated as closed. Open paths are
    snapped end to end and merged; whatever still does not close is counted in
    `open_paths` and dropped.
    """
    loops: list[Polygon] = []
    open_paths: list[list[Point]] = []
    for path in paths:
        pts = [(float(x), float(y)) for x, y in path]
        if len(pts) < 2:
            continue
        if len(pts) >= 3 and _dist2(pts[0], pts[-1]) <= tol * tol:
            poly = _clean_polygon(pts[:-1] if pts[0] == pts[-1] else pts)
            if poly is not None:
                loops.append(poly)
        else:
            open_paths.append(pts)

    unclosed = 0
    if open_paths:
        snapped = _snap_endpoints(open_paths, tol)
        merged = linemerge(MultiLineString([LineString(p) for p in snapped]))
        lines = list(getattr(merged, "geoms", [merged]))
        leftovers: list[LineString] = []
        for line in lines:
            coords = list(line.coords)
            if len(coords) >= 4 and _dist2(coords[0], coords[-1]) <= tol * tol:
                poly = _clean_polygon(coords[:-1])
                if poly is not None:
                    loops.append(poly)
            else:
                leftovers.append(line)
        if leftovers:
            # Some outlines close only through T-junctions or carry a lead-in move
            # (plasma and laser programs); noding the lines lets polygonize find them.
            faces = list(polygonize(unary_union(leftovers)))
            for face in faces:
                poly = _clean_polygon(list(face.exterior.coords)[:-1])
                if poly is not None:
                    loops.append(poly)
            if not faces:
                unclosed = len(leftovers)

    return LoopSet(loops=_dedupe(loops), open_paths=unclosed)


def _dedupe(loops: list[Polygon]) -> list[Polygon]:
    """Drop loops drawn twice (a common artifact of nest exports)."""
    seen: set[tuple[float, ...]] = set()
    out = []
    for poly in loops:
        minx, miny, maxx, maxy = poly.bounds
        key = (round(minx, 1), round(miny, 1), round(maxx, 1), round(maxy, 1), round(poly.area))
        if key in seen:
            continue
        seen.add(key)
        out.append(poly)
    return out


def containment_depths(loops: Sequence[Polygon]) -> tuple[list[int], list[int | None]]:
    """For each loop, its nesting depth and the index of its direct parent.

    Depth 0 means not inside any other loop.
    """
    n = len(loops)
    order = sorted(range(n), key=lambda i: loops[i].area, reverse=True)
    tree = STRtree(list(loops))
    parent: list[int | None] = [None] * n
    depth = [0] * n
    rank = {idx: r for r, idx in enumerate(order)}
    for idx in order:
        probe = loops[idx].representative_point()
        best: int | None = None
        for cand in tree.query(loops[idx]):
            cand = int(cand)
            if cand == idx or rank[cand] >= rank[idx]:
                continue  # only strictly larger loops can be parents
            if loops[cand].contains(probe) and (
                best is None or loops[cand].area < loops[best].area
            ):
                best = cand
        parent[idx] = best
    for idx in order:  # parents are processed first because they are larger
        p = parent[idx]
        depth[idx] = 0 if p is None else depth[p] + 1
    return depth, parent


def build_parts(loops: Sequence[Polygon]) -> list[Polygon]:
    """Group loops into parts with holes using the even-odd rule.

    Even-depth loops are part outlines and their odd-depth children are holes.
    A part sitting inside another part's hole (part-in-part nesting) has depth 2
    and becomes a part of its own.
    """
    if not loops:
        return []
    depth, parent = containment_depths(loops)
    holes: dict[int, list[Polygon]] = {}
    for idx, d in enumerate(depth):
        if d % 2 == 1 and parent[idx] is not None:
            holes.setdefault(parent[idx], []).append(loops[idx])
    parts = []
    for idx, d in enumerate(depth):
        if d % 2 == 0:
            shell = loops[idx]
            part = Polygon(shell.exterior, [h.exterior for h in holes.get(idx, [])])
            if not part.is_valid:
                part = make_valid(part)
                if not isinstance(part, Polygon):
                    part = Polygon(shell.exterior)
            parts.append(part)
    return parts
