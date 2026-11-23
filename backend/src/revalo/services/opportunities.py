"""Who already wants a new offcut: a planned job that fits on it, or a buyer waiting.

Matching runs the other way round from "Check before cutting": instead of a
job looking for remnants, each newly approved remnant looks for a job or a
buyer, so a good piece never sits on the rack while someone needs it.
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import (
    BuyerKind,
    BuyerRequest,
    Job,
    Piece,
    PieceKind,
    PieceStatus,
    PlannedJob,
    utcnow,
)
from revalo.engine.fit import PartSize, StockRemnant, plan_fit
from revalo.engine.matching import Offer, match
from revalo.engine.materials import materials
from revalo.services.fit import THICKNESS_TOLERANCE_MM, candidate_remnants
from revalo.services.market import _need, _suggested_price
from revalo.services.prices import EffectivePrice


class PlannedJobError(ValueError):
    pass


# ---- Planned jobs ------------------------------------------------------------------


def save_planned(
    session: Session,
    workshop_id: str,
    name: str,
    material_code: str,
    thickness_mm: float,
    kerf_mm: float,
    parts: list[PartSize],
    actor: str,
) -> PlannedJob:
    if not name.strip():
        raise PlannedJobError("Give the coming job a name.")
    if not parts:
        raise PlannedJobError("Add the coming job's file or its part sizes.")
    planned = PlannedJob(
        workshop_id=workshop_id,
        name=name.strip()[:160],
        material_code=material_code,
        thickness_mm=thickness_mm,
        kerf_mm=kerf_mm,
        parts=[
            {"label": p.label, "length": p.length, "width": p.width, "rotatable": p.rotatable}
            for p in parts
        ],
        created_by=actor,
    )
    session.add(planned)
    session.commit()
    return planned


def planned_parts(planned: PlannedJob) -> list[PartSize]:
    return [PartSize(**p) for p in planned.parts]


def close_planned(session: Session, planned: PlannedJob) -> None:
    planned.active = False
    planned.closed_at = utcnow()
    session.commit()


def active_planned(session: Session) -> list[PlannedJob]:
    return list(
        session.scalars(
            select(PlannedJob).where(PlannedJob.active.is_(True)).order_by(PlannedJob.created_at)
        )
    )


def _fits(planned: PlannedJob, pieces: list[Piece]) -> dict[str, Any] | None:
    usable = [
        p
        for p in pieces
        if p.kind == PieceKind.REMNANT
        and p.status == PieceStatus.IN_STOCK
        and p.material_code == planned.material_code
        and p.thickness_mm is not None
        and abs(p.thickness_mm - planned.thickness_mm) <= THICKNESS_TOLERANCE_MM
        and p.width_mm
        and p.height_mm
    ]
    if not usable:
        return None
    parts = planned_parts(planned)
    plan = plan_fit(
        parts,
        [StockRemnant(p.id, p.code, p.width_mm, p.height_mm) for p in usable],
        planned.kerf_mm,
    )
    if plan.placed_count == 0:
        return None
    return {
        "id": planned.id,
        "name": planned.name,
        "placed": plan.placed_count,
        "total": len(parts),
        "codes": [u.remnant.code for u in plan.uses],
    }


def planned_to_dict(session: Session, planned: PlannedJob) -> dict[str, Any]:
    stock = candidate_remnants(session, planned.material_code, planned.thickness_mm)
    fit = _fits(planned, stock)
    mat = materials().get(planned.material_code)
    return {
        "id": planned.id,
        "name": planned.name,
        "material_code": planned.material_code,
        "material_name": {"en": mat.name_en, "fr": mat.name_fr} if mat else None,
        "thickness_mm": planned.thickness_mm,
        "part_count": len(planned.parts),
        "parts": planned.parts,
        "created_by": planned.created_by,
        "created_at": planned.created_at.astimezone(UTC).isoformat()
        if planned.created_at.tzinfo
        else planned.created_at.isoformat(),
        "fits_in_stock": fit["placed"] if fit else 0,
    }


# ---- New offcuts looking for a use --------------------------------------------------


def _offer(piece: Piece, book: dict[str, EffectivePrice]) -> Offer:
    mat = materials().get(piece.material_code or "")
    return Offer(
        kind=piece.kind,
        material_code=piece.material_code,
        material_name=mat.name_en if mat else "material",
        thickness_mm=piece.thickness_mm,
        width_mm=piece.width_mm,
        height_mm=piece.height_mm,
        weight_kg=piece.weight_kg,
        price_tnd=_suggested_price(piece, book) or 0.0,
        governorate=piece.job.workshop_governorate if piece.job else None,
    )


def opportunities_for_job(
    session: Session, job: Job, book: dict[str, EffectivePrice]
) -> dict[str, Any]:
    """For an approved job's remnants: planned jobs they fit, buyers who want them."""
    remnants = [
        p for p in job.pieces if p.kind == PieceKind.REMNANT and p.status == PieceStatus.IN_STOCK
    ]
    planned = [fit for pj in active_planned(session) if (fit := _fits(pj, remnants))]

    buyers = list(
        session.scalars(
            select(BuyerRequest).where(
                BuyerRequest.active.is_(True), BuyerRequest.kind == BuyerKind.REUSE
            )
        )
    )
    wanted = []
    for piece in remnants:
        offer = _offer(piece, book)
        found = []
        for buyer in buyers:
            m = match(offer, _need(buyer))
            if m is not None:
                found.append({"id": buyer.id, "name": buyer.name, "score": m.score})
        if found:
            found.sort(key=lambda b: -b["score"])
            wanted.append({"piece_id": piece.id, "code": piece.code, "buyers": found[:3]})
    return {"planned": planned, "buyers": wanted}


def planned_alerts(session: Session) -> list[dict[str, Any]]:
    """Planned jobs whose parts fit remnants already in stock."""
    out = []
    for pj in active_planned(session):
        fit = _fits(pj, candidate_remnants(session, pj.material_code, pj.thickness_mm))
        if fit:
            out.append(fit)
    return out
