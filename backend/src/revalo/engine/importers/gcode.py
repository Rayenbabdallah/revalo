"""G-code importer.

Every CNC machine runs G-code, so this importer covers workshops that have no
nesting software and only keep the program they send to the machine (routers on
NcStudio or Mach3, plasma tables, many fibre lasers).

The program is replayed to recover the cutting paths. A move counts as a cut
when it is a feed move (G1/G2/G3), the tool is on, and, for routers, the tool is
at full depth. Contours are tool-centre paths, so the job uses a centred kerf.
"""

from __future__ import annotations

import math
import re

from revalo.engine.contours import assemble_loops
from revalo.engine.importers.common import ImportOptions, split_into_sheets
from revalo.engine.importers.gcode_macro import expand
from revalo.engine.model import Job, JobImportError, KerfSide, SourceFormat

ARC_TOLERANCE_MM = 0.05
DEPTH_TOLERANCE_MM = 0.5
MAX_LINES = 3_000_000


def _arc_points(
    start: tuple[float, float],
    end: tuple[float, float],
    center: tuple[float, float],
    clockwise: bool,
) -> list[tuple[float, float]]:
    radius = math.dist(start, center)
    if radius < 1e-9:
        return [end]
    a0 = math.atan2(start[1] - center[1], start[0] - center[0])
    a1 = math.atan2(end[1] - center[1], end[0] - center[0])
    sweep = a1 - a0
    if clockwise:
        if sweep >= -1e-9:
            sweep -= 2 * math.pi
    elif sweep <= 1e-9:
        sweep += 2 * math.pi
    ratio = max(-1.0, min(1.0, 1 - ARC_TOLERANCE_MM / radius))
    step = 2 * math.acos(ratio) if radius > ARC_TOLERANCE_MM else math.pi / 4
    n = max(2, math.ceil(abs(sweep) / max(step, 1e-3)))
    pts = [
        (
            center[0] + radius * math.cos(a0 + sweep * i / n),
            center[1] + radius * math.sin(a0 + sweep * i / n),
        )
        for i in range(1, n)
    ]
    pts.append(end)
    return pts


def _center_from_radius(start, end, r, clockwise):
    """Arc centre from the R word (positive R: minor arc, negative: major arc)."""
    dx, dy = end[0] - start[0], end[1] - start[1]
    chord = math.hypot(dx, dy)
    if chord < 1e-9 or abs(r) < chord / 2 - 1e-6:
        return None
    h = math.sqrt(max(r * r - (chord / 2) ** 2, 0.0))
    mx, my = (start[0] + end[0]) / 2, (start[1] + end[1]) / 2
    ux, uy = -dy / chord, dx / chord  # left normal of the chord
    sign = -1 if clockwise else 1
    if r < 0:
        sign = -sign
    return (mx + sign * h * ux, my + sign * h * uy)


def import_gcode(data: bytes, source_name: str, options: ImportOptions | None = None) -> Job:
    options = options or ImportOptions()
    text = data.decode("utf-8", errors="replace")
    if text.count("\n") > MAX_LINES:
        raise JobImportError("G-code file is too large.")
    blocks = expand(text)

    upper = text.upper()
    # FastCAM/CypCut-style programs switch the beam or torch with M07/M08.
    use_m7_m8 = bool(re.search(r"\bM0?7\b", upper)) and not re.search(r"\bM0?[34]\b", upper)
    has_switch = use_m7_m8 or bool(re.search(r"\bM0?[345]\b", upper))

    # First pass: deepest Z of feed moves. Negative Z means Z0 is the stock top (router).
    min_feed_z: float | None = None
    mode = 0
    for words, _ in blocks:
        for letter, value in words:
            if letter == "G" and value in (0, 1, 2, 3):
                mode = int(value)
        if mode in (1, 2, 3):
            for letter, value in words:
                if letter == "Z":
                    min_feed_z = value if min_feed_z is None else min(min_feed_z, value)
    use_depth = min_feed_z is not None and min_feed_z < 0

    scale = 1.0
    absolute = True
    arc_absolute = False
    tool_on = not has_switch
    mode = 0
    x = y = 0.0
    z: float | None = None
    paths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    comments: list[str] = []
    saw_motion = False

    def end_path() -> None:
        nonlocal current
        if len(current) >= 2:
            paths.append(current)
        current = []

    for words, comment in blocks:
        if comment and len(comments) < 200:
            comments.append(comment)
        if not words:
            continue
        params: dict[str, float] = {}
        for letter, num in words:
            if letter == "G":
                if num == 20:
                    scale = 25.4
                elif num == 21:
                    scale = 1.0
                elif num == 90:
                    absolute = True
                elif num == 91:
                    absolute = False
                elif num == 90.1:
                    arc_absolute = True
                elif num == 91.1:
                    arc_absolute = False
                elif num in (0, 1, 2, 3):
                    mode = int(num)
            elif letter == "M":
                m = int(num)
                if use_m7_m8:
                    if m == 7:
                        tool_on = True
                    elif m == 8:
                        tool_on = False
                        end_path()
                elif m in (3, 4):
                    tool_on = True
                elif m == 5:
                    tool_on = False
                    end_path()
            else:
                params[letter] = num

        moves = any(k in params for k in ("X", "Y", "Z"))
        full_circle = mode in (2, 3) and ("I" in params or "J" in params)
        if not (moves or full_circle) or mode not in (0, 1, 2, 3):
            continue
        saw_motion = True

        nx, ny = x, y
        if "X" in params:
            nx = params["X"] * scale if absolute else x + params["X"] * scale
        if "Y" in params:
            ny = params["Y"] * scale if absolute else y + params["Y"] * scale
        if "Z" in params:
            raw_z = params["Z"] * scale
            z = raw_z if absolute or z is None else z + raw_z

        at_depth = not use_depth or (z is not None and z <= min_feed_z * scale + DEPTH_TOLERANCE_MM)
        cutting = mode in (1, 2, 3) and tool_on and at_depth

        if not cutting:
            end_path()
            x, y = nx, ny
            continue

        if not current:
            current = [(x, y)]
        if mode == 1:
            if (nx, ny) != (x, y):
                current.append((nx, ny))
        else:
            clockwise = mode == 2
            if "R" in params:
                center = _center_from_radius((x, y), (nx, ny), params["R"] * scale, clockwise)
            elif "I" in params or "J" in params:
                i, j = params.get("I", 0.0) * scale, params.get("J", 0.0) * scale
                center = (i, j) if arc_absolute else (x + i, y + j)
            else:
                center = None
            if center is None:
                current.append((nx, ny))
            else:
                current.extend(_arc_points((x, y), (nx, ny), center, clockwise))
        x, y = nx, ny
    end_path()

    if not saw_motion:
        raise JobImportError("No motion commands found; this does not look like G-code.")

    loops = assemble_loops(paths, tol=0.1)
    warnings: list[str] = []
    if loops.open_paths:
        warnings.append(
            f"{loops.open_paths} open cut path(s) (slots or partial cuts) were ignored."
        )
    sheets, sheet_warnings = split_into_sheets(loops.loops, [], options, source_name)
    warnings.extend(sheet_warnings)
    if not sheets:
        raise JobImportError("No closed cutting contours were found in this G-code.")

    return Job(
        source_format=SourceFormat.GCODE,
        source_name=source_name,
        sheets=sheets,
        kerf_side=KerfSide.CENTERED,
        material_code=options.material_code,
        thickness_mm=options.thickness_mm,
        warnings=warnings,
        metadata_text=" ".join(comments),
    )
