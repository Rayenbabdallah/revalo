"""Manager review of leftover records, approval into stock, and stock queries."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import Job, JobStatus, Piece, PieceEvent, PieceKind, PieceStatus, utcnow
from revalo.engine.decision import Action
from revalo.engine.materials import materials
from revalo.services.decisions import decide_piece
from revalo.services.prices import EffectivePrice
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
    if reviewing and (
        piece.status not in EDITABLE_STATUSES or piece.job.status == JobStatus.APPROVED
    ):
        raise ReviewError("Only draft records can be corrected; this job is already approved.")

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


def stock_summary(session: Session, book: dict[str, EffectivePrice]) -> dict[str, Any]:
    pieces = session.scalars(select(Piece).where(Piece.status == PieceStatus.IN_STOCK))
    by_material: dict[str, dict[str, Any]] = {}
    actions = {a.value: {"count": 0, "value_tnd": 0.0} for a in Action}
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
                "value_tnd": 0.0,
                "co2_kg": 0.0,
            },
        )
        decision = decide_piece(piece, book)
        if decision.recommended is not None:
            option = decision.option(decision.recommended)
            row["value_tnd"] += option.value_tnd or 0.0
            row["co2_kg"] += option.co2_kg or 0.0
            slot = actions[decision.recommended.value]
            slot["count"] += 1
            slot["value_tnd"] += option.value_tnd or 0.0
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
        row["value_tnd"] = round(row["value_tnd"], 2)
        row["co2_kg"] = round(row["co2_kg"], 1)
    totals = {
        field: round(sum(r[field] for r in rows), 3)
        for field in (
            "remnant_count",
            "remnant_area_m2",
            "remnant_weight_kg",
            "scrap_lots",
            "scrap_weight_kg",
            "due_for_review",
            "value_tnd",
            "co2_kg",
        )
    }
    for slot in actions.values():
        slot["value_tnd"] = round(slot["value_tnd"], 2)
    return {"materials": rows, "totals": totals, "actions": actions}


def _same_spot(a: Piece, b: Piece) -> bool:
    """Same place on the same sheet: the same offcut of the same program."""
    if a.kind != b.kind:
        return False
    if a.x_mm is None or b.x_mm is None:  # scrap lots have no position
        return True
    return abs(a.x_mm - b.x_mm) <= 1 and abs((a.y_mm or 0) - (b.y_mm or 0)) <= 1


def copy_corrections(session: Session, job: Job, actor: str) -> int:
    """Apply the first run's review to a repeat run: same program, same offcuts.

    Copies rejections, trimmed sizes, weighed values and condition notes from
    the piece of the earlier job at the same place on the same sheet. Pieces
    that do not line up, or that the review rules refuse, are left as they are.
    Returns how many pieces were changed.
    """
    source = session.get(Job, job.repeat_of_id) if job.repeat_of_id else None
    if source is None:
        raise ReviewError("This job is not a repeat run of an earlier job.")
    reviewed = {(p.sheet_index, p.label): p for p in source.pieces if p.run_index == 0}
    changed = 0
    for piece in job.pieces:
        src = reviewed.get((piece.sheet_index, piece.label))
        if src is None or piece.status not in EDITABLE_STATUSES or not _same_spot(src, piece):
            continue
        changes = PieceChanges(
            rejected=True if src.status == PieceStatus.REJECTED else None,
            weight_actual_kg=src.weight_actual_kg,
            condition_note=src.condition_note,
        )
        if piece.kind == PieceKind.REMNANT and src.width_mm and src.height_mm:
            fits = (
                src.width_mm <= piece.width_mm + SIZE_TOLERANCE_MM
                and src.height_mm <= piece.height_mm + SIZE_TOLERANCE_MM
            )
            smaller = (
                src.width_mm < piece.width_mm - SIZE_TOLERANCE_MM
                or src.height_mm < piece.height_mm - SIZE_TOLERANCE_MM
            )
            if fits and smaller:
                changes.width_mm, changes.height_mm = src.width_mm, src.height_mm
        if changes == PieceChanges():
            continue
        try:
            update_piece(session, piece, changes, actor)
        except ReviewError:
            session.rollback()
            continue
        changed += 1
    return changed
