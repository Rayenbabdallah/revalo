"""Manager review of leftover records, approval into stock, and stock queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import Job, JobStatus, Piece, PieceEvent, PieceKind, PieceStatus, utcnow
from revalo.engine.materials import materials
from revalo.settings import get_settings

EDITABLE_STATUSES = {PieceStatus.DRAFT, PieceStatus.REJECTED}
SIZE_TOLERANCE_MM = 0.5


class ReviewError(Exception):
    """A change that the piece's state or physics does not allow."""


@dataclass
class PieceChanges:
    weight_actual_kg: float | None = None
    clear_weight: bool = False
    width_mm: float | None = None
    height_mm: float | None = None
    condition_note: str | None = None
    location: str | None = None
    rejected: bool | None = None


def _estimate_weight(piece: Piece) -> float | None:
    material = materials().get(piece.material_code or "")
    if material is None or piece.thickness_mm is None:
        return None
    return round(material.weight_kg(piece.area_m2 * 1e6, piece.thickness_mm), 3)


def update_piece(session: Session, piece: Piece, changes: PieceChanges, actor: str) -> Piece:
    diff: dict[str, Any] = {}
    reviewing = (
        any(
            v is not None
            for v in (
                changes.weight_actual_kg,
                changes.width_mm,
                changes.height_mm,
                changes.rejected,
            )
        )
        or changes.clear_weight
    )
    if reviewing and piece.status not in EDITABLE_STATUSES:
        raise ReviewError("Only draft records can be corrected; this piece is already approved.")

    if changes.width_mm is not None or changes.height_mm is not None:
        if piece.kind != PieceKind.REMNANT:
            raise ReviewError("Only remnants have dimensions to correct.")
        width = changes.width_mm if changes.width_mm is not None else piece.width_mm
        height = changes.height_mm if changes.height_mm is not None else piece.height_mm
        # The file shows the most that can remain: a trimmed edge only makes it smaller.
        if (
            width > piece.width_mm + SIZE_TOLERANCE_MM
            or height > piece.height_mm + SIZE_TOLERANCE_MM
        ):
            raise ReviewError("A remnant can be trimmed, not enlarged beyond the cut file.")
        diff["size"] = {"from": [piece.width_mm, piece.height_mm], "to": [width, height]}
        piece.width_mm, piece.height_mm = width, height
        piece.area_m2 = round(width * height / 1e6, 4)
        piece.weight_est_kg = _estimate_weight(piece)

    if changes.clear_weight:
        diff["weight_actual_kg"] = {"from": piece.weight_actual_kg, "to": None}
        piece.weight_actual_kg = None
    elif changes.weight_actual_kg is not None:
        diff["weight_actual_kg"] = {"from": piece.weight_actual_kg, "to": changes.weight_actual_kg}
        piece.weight_actual_kg = changes.weight_actual_kg

    if changes.condition_note is not None:
        note = changes.condition_note.strip() or None
        diff["condition_note"] = {"from": piece.condition_note, "to": note}
        piece.condition_note = note
    if changes.location is not None:
        location = changes.location.strip() or None
        diff["location"] = {"from": piece.location, "to": location}
        piece.location = location
    if changes.rejected is not None:
        status = PieceStatus.REJECTED if changes.rejected else PieceStatus.DRAFT
        if status != piece.status:
            diff["status"] = {"from": piece.status, "to": status}
            piece.status = status

    if diff:
        piece.events.append(PieceEvent(actor=actor, action="corrected", data=diff))
    session.commit()
    return piece


def approve_job(session: Session, job: Job, actor: str) -> Job:
    if job.status == JobStatus.APPROVED:
        raise ReviewError("This job is already approved.")
    review = date.today() + timedelta(days=get_settings().review_days)
    for piece in job.pieces:
        if piece.status == PieceStatus.DRAFT:
            piece.status = PieceStatus.IN_STOCK
            piece.review_date = review
            piece.events.append(
                PieceEvent(actor=actor, action="approved", data={"review_date": review.isoformat()})
            )
    job.status = JobStatus.APPROVED
    job.approved_at = utcnow()
    job.approved_by = actor
    session.commit()
    return job


def stock_pieces(session: Session, status: str | None, kind: str | None) -> list[Piece]:
    query = select(Piece).order_by(Piece.created_at.desc(), Piece.position)
    if status:
        query = query.where(Piece.status == status)
    if kind:
        query = query.where(Piece.kind == kind)
    return list(session.scalars(query.limit(500)))


def stock_summary(session: Session) -> dict[str, Any]:
    pieces = session.scalars(select(Piece).where(Piece.status == PieceStatus.IN_STOCK))
    by_material: dict[str, dict[str, Any]] = {}
    for piece in pieces:
        key = piece.material_code or "unknown"
        row = by_material.setdefault(
            key,
            {
                "material_code": piece.material_code,
                "remnant_count": 0,
                "remnant_area_m2": 0.0,
                "remnant_weight_kg": 0.0,
                "scrap_lots": 0,
                "scrap_weight_kg": 0.0,
                "unweighed": 0,
                "due_for_review": 0,
            },
        )
        weight = piece.weight_kg
        if weight is None:
            row["unweighed"] += 1
        if piece.kind == PieceKind.REMNANT:
            row["remnant_count"] += 1
            row["remnant_area_m2"] += piece.area_m2
            row["remnant_weight_kg"] += weight or 0.0
        else:
            row["scrap_lots"] += 1
            row["scrap_weight_kg"] += weight or 0.0
        if piece.review_date and piece.review_date <= date.today():
            row["due_for_review"] += 1

    rows = sorted(
        by_material.values(), key=lambda r: -(r["remnant_weight_kg"] + r["scrap_weight_kg"])
    )
    for row in rows:
        for field in ("remnant_area_m2", "remnant_weight_kg", "scrap_weight_kg"):
            row[field] = round(row[field], 3)
    totals = {
        field: round(sum(r[field] for r in rows), 3)
        for field in (
            "remnant_count",
            "remnant_area_m2",
            "remnant_weight_kg",
            "scrap_lots",
            "scrap_weight_kg",
            "due_for_review",
        )
    }
    return {"materials": rows, "totals": totals}
