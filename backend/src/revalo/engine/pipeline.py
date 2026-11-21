"""End-to-end analysis: file bytes in, leftover records out."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePath
from typing import Any

from shapely.geometry import MultiPolygon, Polygon

from revalo.engine.importers.common import ImportOptions
from revalo.engine.importers.cutlist import import_cutlist
from revalo.engine.importers.dxf import import_dxf
from revalo.engine.importers.gcode import import_gcode
from revalo.engine.leftover import LeftoverOptions, SheetLeftover, compute_leftover
from revalo.engine.materials import (
    Material,
    default_kerf,
    infer_material,
    infer_thickness,
    materials,
)
from revalo.engine.model import Job, JobImportError, SourceFormat

DXF_EXTENSIONS = {".dxf"}
GCODE_EXTENSIONS = {".nc", ".gcode", ".ngc", ".tap", ".cnc", ".gc", ".g", ".eia", ".mpf"}
CUTLIST_EXTENSIONS = {".csv", ".tsv"}
MAX_FILE_BYTES = 25 * 1024 * 1024

MIN_SIDE_BY_FAMILY = {"metal": 100.0, "wood": 150.0, "plastic": 100.0}


@dataclass
class AnalysisOptions(ImportOptions):
    process: str | None = None
    """Cutting process code (fiber_laser, plasma, router, panel_saw, ...)."""
    min_side_mm: float | None = None
    max_remnants: int = 12


def detect_format(data: bytes, filename: str) -> SourceFormat:
    ext = PurePath(filename).suffix.lower()
    if ext in DXF_EXTENSIONS:
        return SourceFormat.DXF
    if ext in GCODE_EXTENSIONS:
        return SourceFormat.GCODE
    if ext in CUTLIST_EXTENSIONS:
        return SourceFormat.CUTLIST
    head = data[:4096].decode("utf-8", errors="ignore").upper()
    if head.startswith("AUTOCAD BINARY DXF") or ("SECTION" in head[:200] and "HEADER" in head):
        return SourceFormat.DXF
    if any(token in head for token in ("G0 ", "G1 ", "G00", "G01", "G21", "G90")):
        return SourceFormat.GCODE
    if head.count(";") + head.count(",") >= 2:
        return SourceFormat.CUTLIST
    raise JobImportError(
        "Unsupported file. Upload a DXF nest, a G-code program (.nc, .gcode, .tap) "
        "or a CSV cut list."
    )


@dataclass
class SheetResult:
    index: int
    width: float
    height: float
    sheet_detected: bool
    part_count: int
    leftover: SheetLeftover
    outline: Polygon


@dataclass
class AnalysisResult:
    job: Job
    material: Material | None
    thickness_mm: float | None
    kerf_mm: float
    min_side_mm: float
    material_source: str
    thickness_source: str
    sheets: list[SheetResult] = field(default_factory=list)

    @property
    def warnings(self) -> list[str]:
        return self.job.warnings

    def weight(self, area_mm2: float) -> float | None:
        if self.material is None or self.thickness_mm is None:
            return None
        return round(self.material.weight_kg(area_mm2, self.thickness_mm), 3)

    def to_dict(self, include_geometry: bool = True) -> dict[str, Any]:
        sheets = []
        totals = {
            "sheet_area_m2": 0.0,
            "parts_area_m2": 0.0,
            "remnant_area_m2": 0.0,
            "scrap_area_m2": 0.0,
            "kerf_area_m2": 0.0,
            "remnant_count": 0,
        }
        for s in self.sheets:
            lo = s.leftover
            remnants = [
                {
                    "id": f"S{s.index + 1}-R{i + 1}",
                    "x": r.x,
                    "y": r.y,
                    "width": r.width,
                    "height": r.height,
                    "area_m2": round(r.area / 1e6, 4),
                    "weight_kg": self.weight(r.area),
                }
                for i, r in enumerate(lo.remnants)
            ]
            sheet: dict[str, Any] = {
                "index": s.index,
                "width": round(s.width, 2),
                "height": round(s.height, 2),
                "sheet_detected": s.sheet_detected,
                "part_count": s.part_count,
                "utilization": round(lo.utilization, 4),
                "area_m2": round(lo.sheet_area / 1e6, 4),
                "parts_area_m2": round(lo.parts_area / 1e6, 4),
                "kerf_area_m2": round(lo.kerf_area / 1e6, 4),
                "scrap_area_m2": round(lo.scrap_area / 1e6, 4),
                "sheet_weight_kg": self.weight(lo.sheet_area),
                "parts_weight_kg": self.weight(lo.parts_area),
                "scrap_weight_kg": self.weight(lo.scrap_area),
                "remnants": remnants,
            }
            if include_geometry:
                sheet["geometry"] = {
                    "outline": polygon_to_json(s.outline),
                    "parts": [polygon_to_json(p) for p in lo.part_geometry],
                    "scrap": geometry_to_json(lo.scrap_geometry),
                }
            sheets.append(sheet)
            totals["sheet_area_m2"] += lo.sheet_area / 1e6
            totals["parts_area_m2"] += lo.parts_area / 1e6
            totals["remnant_area_m2"] += lo.remnant_area / 1e6
            totals["scrap_area_m2"] += lo.scrap_area / 1e6
            totals["kerf_area_m2"] += lo.kerf_area / 1e6
            totals["remnant_count"] += len(lo.remnants)

        total_sheet = sum(s.leftover.sheet_area for s in self.sheets)
        total_remnant = sum(s.leftover.remnant_area for s in self.sheets)
        total_scrap = sum(s.leftover.scrap_area for s in self.sheets)
        totals = {k: (round(v, 4) if isinstance(v, float) else v) for k, v in totals.items()}
        totals.update(
            {
                "remnant_weight_kg": self.weight(total_remnant),
                "scrap_weight_kg": self.weight(total_scrap),
                "sheet_weight_kg": self.weight(total_sheet),
            }
        )
        return {
            "source": {
                "name": self.job.source_name,
                "format": self.job.source_format.value,
                "layout_estimated": self.job.layout_estimated,
            },
            "material": None
            if self.material is None
            else {
                "code": self.material.code,
                "name": {"en": self.material.name_en, "fr": self.material.name_fr},
                "family": self.material.family,
                "density_kg_m3": self.material.density_kg_m3,
                "source": self.material_source,
            },
            "thickness_mm": self.thickness_mm,
            "thickness_source": self.thickness_source,
            "kerf_mm": self.kerf_mm,
            "min_side_mm": self.min_side_mm,
            "totals": totals,
            "sheets": sheets,
            "warnings": self.warnings,
        }


def _round_coords(coords) -> list[list[float]]:
    return [[round(x, 2), round(y, 2)] for x, y in coords]


def polygon_to_json(poly: Polygon) -> dict[str, Any]:
    poly = poly.simplify(0.05, preserve_topology=True)
    return {
        "exterior": _round_coords(poly.exterior.coords),
        "holes": [_round_coords(ring.coords) for ring in poly.interiors],
    }


def geometry_to_json(geom: Polygon | MultiPolygon | None) -> list[dict[str, Any]]:
    if geom is None or geom.is_empty:
        return []
    polys = [g for g in getattr(geom, "geoms", [geom]) if isinstance(g, Polygon)]
    return [polygon_to_json(p) for p in polys if p.area >= 1.0]


def _resolve_material(job: Job, options: AnalysisOptions) -> tuple[Material | None, str]:
    if options.material_code:
        if options.material_code not in materials():
            raise JobImportError(f"Unknown material code: {options.material_code}")
        return materials()[options.material_code], "given"
    for text, source in ((job.source_name, "file_name"), (job.metadata_text, "file_content")):
        code = infer_material(text) if text else None
        if code:
            return materials()[code], source
    return None, "unknown"


def _resolve_thickness(job: Job, options: AnalysisOptions) -> tuple[float | None, str]:
    if options.thickness_mm:
        return options.thickness_mm, "given"
    for text, source in ((job.source_name, "file_name"), (job.metadata_text, "file_content")):
        value = infer_thickness(text) if text else None
        if value:
            return value, source
    return None, "unknown"


def analyze(data: bytes, filename: str, options: AnalysisOptions | None = None) -> AnalysisResult:
    options = options or AnalysisOptions()
    if len(data) > MAX_FILE_BYTES:
        raise JobImportError("File is larger than 25 MB.")
    if not data.strip():
        raise JobImportError("The file is empty.")

    fmt = detect_format(data, filename)
    if fmt is SourceFormat.DXF:
        job = import_dxf(data, filename, options)
    elif fmt is SourceFormat.GCODE:
        job = import_gcode(data, filename, options)
    else:
        job = import_cutlist(data, filename, options)

    material, material_source = _resolve_material(job, options)
    thickness, thickness_source = _resolve_thickness(job, options)
    code = material.code if material else None
    process = options.process or ("panel_saw" if fmt is SourceFormat.CUTLIST else None)
    if options.kerf_mm is not None:
        kerf = options.kerf_mm
    elif fmt is SourceFormat.GCODE and (material is None or material.family != "metal"):
        kerf = default_kerf(process or "router", code)
    else:
        kerf = default_kerf(process, code)
    min_side = options.min_side_mm or MIN_SIDE_BY_FAMILY.get(
        material.family if material else "", 100.0
    )

    if material is None:
        job.warnings.append("Material not recognised; choose it to get weights.")
    if thickness is None:
        job.warnings.append("Thickness not found; enter it to get weights.")

    leftover_options = LeftoverOptions(
        kerf_mm=kerf, min_side_mm=min_side, max_remnants=options.max_remnants
    )
    result = AnalysisResult(
        job=job,
        material=material,
        thickness_mm=thickness,
        kerf_mm=kerf,
        min_side_mm=min_side,
        material_source=material_source,
        thickness_source=thickness_source,
    )
    for index, sheet in enumerate(job.sheets):
        result.sheets.append(
            SheetResult(
                index=index,
                width=sheet.width,
                height=sheet.height,
                sheet_detected=sheet.sheet_detected,
                part_count=len(sheet.parts),
                leftover=compute_leftover(sheet, job.kerf_side, leftover_options),
                outline=sheet.outline,
            )
        )
    return result
