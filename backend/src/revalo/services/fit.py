"""Before cutting a new sheet, find which stored remnants can hold the job's parts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import (
    Listing,
    ListingStatus,
    Piece,
    PieceEvent,
    PieceKind,
    PieceStatus,
    utcnow,
)
from revalo.engine.fit import (
    FitPlan,
    PartSize,
    StockRemnant,
    part_size,
    parts_from_cutlist,
    plan_fit,
)
from revalo.engine.importers.common import ImportOptions
from revalo.engine.importers.cutlist import parse_cutlist
from revalo.engine.importers.dxf import import_dxf
from revalo.engine.importers.gcode import import_gcode
from revalo.engine.materials import default_kerf, infer_material, infer_thickness, materials
from revalo.engine.model import JobImportError, SourceFormat
from revalo.engine.pipeline import detect_format
from revalo.services.prices import EffectivePrice

THICKNESS_TOLERANCE_MM = 0.05


class FitError(ValueError):
    pass


@dataclass
class FitRequest:
    material_code: str | None
    thickness_mm: float | None
    kerf_mm: float | None


def parts_from_file(data: bytes, filename: str) -> tuple[list[PartSize], str]:
    """Parts of the coming job, and any text that may name its material."""
    fmt = detect_format(data, filename)
    if fmt is SourceFormat.CUTLIST:
        cut, _sheet, meta, _skipped = parse_cutlist(data)
        return parts_from_cutlist(cut), meta
    importer = import_dxf if fmt is SourceFormat.DXF else import_gcode
    # A parts drawing has no sheet; give a generous one so every part is kept.
    job = importer(data, filename, ImportOptions(sheet_width_mm=20000, sheet_height_mm=20000))
    polygons = [poly for sheet in job.sheets for poly in sheet.parts]
    parts = [part_size(f"P{i + 1}", poly) for i, poly in enumerate(polygons)]
    return parts, job.metadata_text


def resolve(request: FitRequest, filename: str, meta: str) -> tuple[str, float, float]:
    code = request.material_code or infer_material(filename) or infer_material(meta)
    if code is None or code not in materials():
        raise FitError("Choose the material of the coming job.")
    thickness = request.thickness_mm or infer_thickness(filename) or infer_thickness(meta)
    if thickness is None:
        raise FitError("Enter the thickness of the coming job.")
    kerf = request.kerf_mm if request.kerf_mm is not None else default_kerf(None, code)
    return code, thickness, kerf


def candidate_remnants(session: Session, code: str, thickness: float) -> list[Piece]:
    pieces = session.scalars(
        select(Piece).where(
            Piece.status == PieceStatus.IN_STOCK,
            Piece.kind == PieceKind.REMNANT,
            Piece.material_code == code,
        )
    )
    return [
        p
        for p in pieces
        if p.thickness_mm is not None
        and abs(p.thickness_mm - thickness) <= THICKNESS_TOLERANCE_MM
        and p.width_mm
        and p.height_mm
    ]


def check_stock(
    session: Session,
    data: bytes | None,
    filename: str,
    extra_parts: list[PartSize],
    request: FitRequest,
    book: dict[str, EffectivePrice],
) -> dict[str, Any]:
    parts = list(extra_parts)
    meta = ""
    if data:
        try:
            from_file, meta = parts_from_file(data, filename)
        except JobImportError as exc:
            raise FitError(str(exc)) from exc
        parts.extend(from_file)
    if not parts:
        raise FitError("Add the coming job's file or its part sizes.")
    code, thickness, kerf = resolve(request, filename, meta)

    stock = candidate_remnants(session, code, thickness)
    by_id = {p.id: p for p in stock}
    plan: FitPlan = plan_fit(
        parts,
        [StockRemnant(p.id, p.code, p.width_mm, p.height_mm) for p in stock],
        kerf,
    )
    mat = materials()[code]
    saved_kg = mat.weight_kg(plan.placed_area, thickness)
    entry = book.get(code)
    new_price = entry.prices.new_tnd_per_kg if entry and entry.prices else None

    return {
        "material_code": code,
        "material_name": {"en": mat.name_en, "fr": mat.name_fr},
        "thickness_mm": thickness,
        "kerf_mm": kerf,
        "part_count": len(parts),
        "placed_count": plan.placed_count,
        "candidates": len(stock),
        "saved_kg": round(saved_kg, 2),
        "saved_tnd": round(saved_kg * new_price, 2) if new_price else None,
        "uses": [
            {
                "piece": {
                    "id": use.remnant.id,
                    "code": use.remnant.code,
                    "width_mm": use.remnant.width,
                    "height_mm": use.remnant.height,
                    "location": by_id[use.remnant.id].location,
                },
                "fill": round(use.fill, 3),
                "placements": [
                    {
                        "label": p.part.label,
                        "x": p.x,
                        "y": p.y,
                        "width": p.width,
                        "height": p.height,
                    }
                    for p in use.placements
                ],
            }
            for use in plan.uses
        ],
        "unplaced": [
            {"label": p.label, "length": p.length, "width": p.width} for p in plan.unplaced
        ],
    }


def mark_reused(session: Session, piece_ids: list[str], job_name: str, actor: str) -> list[Piece]:
    pieces = [session.get(Piece, pid) for pid in piece_ids]
    if any(p is None for p in pieces):
        raise FitError("Unknown piece.")
    for piece in pieces:
        if piece.status != PieceStatus.IN_STOCK:
            raise FitError(f"{piece.code} is no longer in stock.")
    for piece in pieces:
        listing = session.scalars(select(Listing).where(Listing.piece_id == piece.id)).first()
        if listing is not None and listing.status in (ListingStatus.OPEN, ListingStatus.RESERVED):
            listing.status = ListingStatus.WITHDRAWN
            listing.closed_at = utcnow()
        piece.status = PieceStatus.REUSED
        piece.events.append(PieceEvent(actor=actor, action="reused", data={"for": job_name}))
    session.commit()
    return pieces
