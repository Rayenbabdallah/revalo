"""Normalized job model shared by every importer.

All lengths are millimetres and all geometry lives in the sheet's coordinate
system. Importers convert whatever the source file uses into this model, so the
leftover engine never needs to know where a job came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from shapely.geometry import Polygon


class SourceFormat(StrEnum):
    DXF = "dxf"
    GCODE = "gcode"
    CUTLIST = "cutlist"


class KerfSide(StrEnum):
    """Where the cut width lies relative to the contours in the file.

    OUTSIDE: contours are finished part geometry; the machine offsets the cut
    outward, so the kerf band sits fully outside each part (DXF nests, cut lists).
    CENTERED: contours are tool-centre paths; half the kerf lies on each side
    (G-code).
    """

    OUTSIDE = "outside"
    CENTERED = "centered"


@dataclass
class SheetLayout:
    """One physical sheet or panel and the parts cut from it."""

    outline: Polygon
    parts: list[Polygon] = field(default_factory=list)
    sheet_detected: bool = True
    """False when the outline was assumed (bounding box or default size)."""

    @property
    def width(self) -> float:
        minx, _, maxx, _ = self.outline.bounds
        return maxx - minx

    @property
    def height(self) -> float:
        _, miny, _, maxy = self.outline.bounds
        return maxy - miny


@dataclass
class Job:
    """A cutting job normalized from any supported source file."""

    source_format: SourceFormat
    source_name: str
    sheets: list[SheetLayout]
    kerf_side: KerfSide = KerfSide.OUTSIDE
    material_code: str | None = None
    thickness_mm: float | None = None
    layout_estimated: bool = False
    """True when part positions were computed by Revalo, not read from the file."""
    warnings: list[str] = field(default_factory=list)
    metadata_text: str = ""
    """Layer names, comments and labels from the file, used to infer material and thickness."""

    @property
    def part_count(self) -> int:
        return sum(len(s.parts) for s in self.sheets)


class JobImportError(Exception):
    """Raised when a file cannot be turned into a job."""
