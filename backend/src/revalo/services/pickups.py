"""Recycler pickups: batch what should be recycled, pick a recycler, track the trip."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import (
    BuyerKind,
    BuyerRequest,
    Listing,
    ListingStatus,
    Pickup,
    PickupItem,
    PickupStatus,
    Piece,
    PieceEvent,
    PieceKind,
    PieceStatus,
    utcnow,
)
from revalo.engine.decision import Action
from revalo.engine.geo import distance_km
from revalo.engine.matching import MAX_DISTANCE_KM
from revalo.engine.materials import materials
from revalo.services.decisions import decide_piece
from revalo.services.market import request_to_dict, whatsapp_url
from revalo.services.prices import EffectivePrice

OPEN_PICKUP = {PickupStatus.REQUESTED, PickupStatus.SCHEDULED}


class PickupError(ValueError):
    pass


def recycle_queue(session: Session, book: dict[str, EffectivePrice]) -> list[Piece]:
    """Pieces in stock that the decision engine says to recycle."""
    pieces = session.scalars(
        select(Piece).where(Piece.status == PieceStatus.IN_STOCK).order_by(Piece.created_at)
    )
    return [p for p in pieces if decide_piece(p, book).recommended == Action.RECYCLE]


def recyclers_for(
    session: Session, material_code: str | None, total_kg: float, governorate: str | None
) -> list[dict[str, Any]]:
    """Recyclers who take this material, from this far, in this quantity: best offer first."""
    rows = []
    for r in session.scalars(
        select(BuyerRequest).where(
            BuyerRequest.kind == BuyerKind.RECYCLER, BuyerRequest.active.is_(True)
        )
    ):
        codes = r.materials.get("codes", [])
        if codes and material_code not in codes:
            continue
        km = distance_km(governorate, r.governorate)
        if km is not None and km > MAX_DISTANCE_KM:
            continue
        too_small = r.min_lot_kg is not None and total_kg < r.min_lot_kg
        rows.append(
            {
                "recycler": request_to_dict(r),
                "distance_km": None if km is None else round(km, 1),
                "lot_ok": not too_small,
                "estimated_tnd": round(total_kg * r.offered_tnd_per_kg, 2)
                if r.offered_tnd_per_kg
                else None,
            }
        )
    rows.sort(
        key=lambda row: (
            not row["lot_ok"],
            -(row["recycler"]["offered_tnd_per_kg"] or 0),
            row["distance_km"] if row["distance_km"] is not None else 9999,
        )
    )
    return rows


def _message(pickup: Pickup) -> str:
    lines = []
    by_material: dict[str, float] = {}
    for item in pickup.items:
        mat = materials().get(item.piece.material_code or "")
        name = mat.name_fr if mat else "matière"
        thickness = f" {item.piece.thickness_mm:g} mm" if item.piece.thickness_mm else ""
        key = f"{name}{thickness}"
        by_material[key] = by_material.get(key, 0) + (item.piece.weight_kg or 0)
    for key, kg in by_material.items():
        lines.append(f"- {key} : {kg:.0f} kg")
    shop = pickup.items[0].piece.job.workshop_governorate if pickup.items else None
    where = f" à {shop}" if shop else ""
    return (
        f"Bonjour {pickup.recycler.name}, nous avons un lot trié à enlever{where} "
        f"({pickup.estimated_kg:.0f} kg) :\n" + "\n".join(lines) + "\nQuand pouvez-vous passer ?"
    )


def request_pickup(
    session: Session, recycler_id: str, piece_ids: list[str], actor: str, workshop_id: str
) -> Pickup:
    recycler = session.get(BuyerRequest, recycler_id)
    if recycler is None or recycler.kind != BuyerKind.RECYCLER or not recycler.active:
        raise PickupError("Choose an active recycler.")
    pieces = [session.get(Piece, pid) for pid in dict.fromkeys(piece_ids)]
    if not pieces or any(p is None for p in pieces):
        raise PickupError("Unknown piece.")
    for piece in pieces:
        if piece.status != PieceStatus.IN_STOCK:
            raise PickupError(f"{piece.code} is not in stock.")
    pickup = Pickup(
        workshop_id=workshop_id,
        recycler_id=recycler.id,
        estimated_kg=round(sum(p.weight_kg or 0 for p in pieces), 2),
        created_by=actor,
    )
    for piece in pieces:
        pickup.items.append(PickupItem(piece=piece))
        listing = session.scalars(select(Listing).where(Listing.piece_id == piece.id)).first()
        if listing is not None and listing.status in (ListingStatus.OPEN, ListingStatus.RESERVED):
            listing.status = ListingStatus.WITHDRAWN
            listing.closed_at = utcnow()
        piece.status = PieceStatus.RESERVED
        piece.events.append(
            PieceEvent(actor=actor, action="pickup_requested", data={"recycler": recycler.name})
        )
    session.add(pickup)
    session.commit()
    return pickup


def update_pickup(
    session: Session,
    pickup: Pickup,
    action: str,
    actor: str,
    scheduled_for: date | None = None,
    weighed_kg: float | None = None,
    paid_tnd: float | None = None,
) -> Pickup:
    if pickup.status not in OPEN_PICKUP:
        raise PickupError("This pickup is closed.")
    if action == "schedule":
        if scheduled_for is None:
            raise PickupError("Choose the pickup date.")
        pickup.status = PickupStatus.SCHEDULED
        pickup.scheduled_for = scheduled_for
    elif action == "collect":
        if weighed_kg is None or weighed_kg <= 0:
            raise PickupError("Enter the weight on the recycler's ticket.")
        offered = pickup.recycler.offered_tnd_per_kg
        pickup.status = PickupStatus.COLLECTED
        pickup.weighed_kg = weighed_kg
        pickup.paid_tnd = (
            paid_tnd
            if paid_tnd is not None
            else (round(weighed_kg * offered, 2) if offered else None)
        )
        pickup.closed_at = utcnow()
        for item in pickup.items:
            item.piece.status = PieceStatus.RECYCLED
            item.piece.events.append(
                PieceEvent(actor=actor, action="recycled", data={"recycler": pickup.recycler.name})
            )
    elif action == "cancel":
        pickup.status = PickupStatus.CANCELLED
        pickup.closed_at = utcnow()
        for item in pickup.items:
            item.piece.status = PieceStatus.IN_STOCK
            item.piece.events.append(PieceEvent(actor=actor, action="pickup_cancelled", data={}))
    else:
        raise PickupError(f"Unknown action: {action}")
    session.commit()
    return pickup


def pickup_to_dict(pickup: Pickup) -> dict[str, Any]:
    return {
        "id": pickup.id,
        "status": pickup.status,
        "recycler": request_to_dict(pickup.recycler),
        "scheduled_for": pickup.scheduled_for.isoformat() if pickup.scheduled_for else None,
        "estimated_kg": pickup.estimated_kg,
        "weighed_kg": pickup.weighed_kg,
        "paid_tnd": pickup.paid_tnd,
        "created_by": pickup.created_by,
        "created_at": pickup.created_at.isoformat(),
        "closed_at": pickup.closed_at.isoformat() if pickup.closed_at else None,
        "pieces": [
            {
                "id": i.piece.id,
                "code": i.piece.code,
                "kind": i.piece.kind,
                "material_code": i.piece.material_code,
                "thickness_mm": i.piece.thickness_mm,
                "weight_kg": i.piece.weight_kg,
            }
            for i in pickup.items
        ],
        "whatsapp_url": whatsapp_url(pickup.recycler.phone, _message(pickup)),
    }


def queue_to_dict(session: Session, pieces: list[Piece], governorate: str | None) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for piece in pieces:
        key = piece.material_code or "unknown"
        mat = materials().get(key)
        group = groups.setdefault(
            key,
            {
                "material_code": piece.material_code,
                "material_name": {"en": mat.name_en, "fr": mat.name_fr} if mat else None,
                "total_kg": 0.0,
                "pieces": [],
            },
        )
        group["total_kg"] += piece.weight_kg or 0
        group["pieces"].append(
            {
                "id": piece.id,
                "code": piece.code,
                "kind": piece.kind,
                "label": "Scrap lot" if piece.kind == PieceKind.SCRAP else "Remnant",
                "width_mm": piece.width_mm,
                "height_mm": piece.height_mm,
                "thickness_mm": piece.thickness_mm,
                "weight_kg": piece.weight_kg,
            }
        )
    out = []
    for group in groups.values():
        group["total_kg"] = round(group["total_kg"], 2)
        group["recyclers"] = recyclers_for(
            session, group["material_code"], group["total_kg"], governorate
        )
        out.append(group)
    out.sort(key=lambda g: -g["total_kg"])
    return {"groups": out}
