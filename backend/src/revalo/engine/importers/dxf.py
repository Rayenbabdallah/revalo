"""DXF nest importer.

Reads the DXF that nesting and CAM software export (CypNest, SigmaNEST, Lantek,
Deepnest, AutoCAD drawings, ...). Handles block references (parts placed as
INSERTs), arcs and splines, unit headers, files with small gaps between
segments, and marking or text layers that are not real cuts.
"""

from __future__ import annotations

import io
import re

import ezdxf
from ezdxf import disassemble, recover
from ezdxf.path import make_path

from revalo.engine.contours import assemble_loops
from revalo.engine.importers.common import ImportOptions, split_into_sheets
from revalo.engine.model import Job, JobImportError, KerfSide, SourceFormat
from revalo.engine.units import insunits_to_mm

CUT_ENTITY_TYPES = {"LINE", "ARC", "CIRCLE", "ELLIPSE", "LWPOLYLINE", "POLYLINE", "SPLINE"}

# Layers that carry annotations, marking, fold lines or construction geometry,
# never through-cuts.
IGNORED_LAYER = re.compile(
    r"(TEXT|DIM|COTE|MARK|ENGRAV|GRAV|ETCH|ANNOT|TITLE|CARTOUCHE|DEFPOINTS|HATCH"
    r"|CONSTRUCT|CONSTR|HELPER|GUIDE|REFERENCE|HIDDEN|CENTERLINE|BEND|FOLD"
    r"|\bAUX\b|\bAXE\b|\bAXIS\b|\bPLI\b|\bBED\b|\bMACHINE\b|\bLIT\b)",
    re.IGNORECASE,
)
# Layers that hold the raw stock outline: the first word names the stock
# ("SHEET", "sheet 49x97", "TOLE_3MM"); short generic names must match exactly.
SHEET_LAYER_FIRST_WORD = {
    "sheet",
    "sheets",
    "stock",
    "blank",
    "brut",
    "tole",
    "blech",
    "panneau",
    "plaque",
    "raw",
    "format",
    "feuille",
}
SHEET_LAYER_EXACT = {"plate", "panel", "board", "material", "matiere"}


def is_sheet_layer(name: str) -> bool:
    norm = name.strip().lower().replace("ô", "o")
    words = re.split(r"[^a-z0-9]+", norm)
    return norm in SHEET_LAYER_EXACT or (bool(words) and words[0] in SHEET_LAYER_FIRST_WORD)


FLATTEN_TOLERANCE_MM = 0.05
MAX_TEXT_SNIPPETS = 200


def _read(data: bytes):
    try:
        doc, _auditor = recover.read(io.BytesIO(data))
    except (ezdxf.DXFStructureError, ezdxf.DXFError, OSError, UnicodeDecodeError) as exc:
        raise JobImportError(f"Not a readable DXF file: {exc}") from exc
    return doc


def import_dxf(data: bytes, source_name: str, options: ImportOptions | None = None) -> Job:
    options = options or ImportOptions()
    doc = _read(data)
    scale = insunits_to_mm(doc.header.get("$INSUNITS", 0))
    flatten = FLATTEN_TOLERANCE_MM / scale

    part_paths: list[list[tuple[float, float]]] = []
    sheet_paths: list[list[tuple[float, float]]] = []
    texts: list[str] = []
    layers_seen: set[str] = set()

    for entity in disassemble.recursive_decompose(doc.modelspace()):
        kind = entity.dxftype()
        layer = str(entity.dxf.get("layer", "0"))
        layers_seen.add(layer)
        if kind in ("TEXT", "MTEXT") and len(texts) < MAX_TEXT_SNIPPETS:
            texts.append(entity.plain_text() if kind == "MTEXT" else entity.dxf.get("text", ""))
            continue
        if kind not in CUT_ENTITY_TYPES or IGNORED_LAYER.search(layer):
            continue
        if kind == "POLYLINE" and (entity.is_3d_polyline or entity.is_poly_face_mesh):
            continue
        try:
            path = make_path(entity)
        except (TypeError, ValueError, ezdxf.DXFError):
            continue
        subpaths = path.sub_paths() if path.has_sub_paths else [path]
        target = sheet_paths if is_sheet_layer(layer) else part_paths
        for sub in subpaths:
            pts = [(v.x * scale, v.y * scale) for v in sub.flattening(distance=flatten)]
            if len(pts) >= 2:
                target.append(pts)

    loops = assemble_loops(part_paths)
    sheet_loops = assemble_loops(sheet_paths).loops if sheet_paths else []
    warnings: list[str] = []
    if loops.open_paths:
        warnings.append(f"{loops.open_paths} open contour(s) could not be closed and were ignored.")

    sheets, sheet_warnings = split_into_sheets(loops.loops, sheet_loops, options, source_name)
    warnings.extend(sheet_warnings)
    if not sheets:
        raise JobImportError("No closed cut contours were found in this DXF file.")

    return Job(
        source_format=SourceFormat.DXF,
        source_name=source_name,
        sheets=sheets,
        kerf_side=KerfSide.OUTSIDE,
        material_code=options.material_code,
        thickness_mm=options.thickness_mm,
        warnings=warnings,
        metadata_text=" ".join([*sorted(layers_seen), *texts]),
    )
