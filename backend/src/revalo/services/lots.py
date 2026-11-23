"""Batch lots: similar offcuts offered as one deal to buyers who take many at once.

Revalo proposes groups (same material and thickness, sizes in the same band),
the manager adjusts and lists them, and a buyer can take the whole lot or part
of it. Every piece keeps its own record and history.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import (
    BuyerKind,
    BuyerRequest,
    Listing,
    ListingStatus,
    Lot,
    LotItem,
    Piece,
    PieceEvent,
    PieceKind,
    PieceStatus,
    utcnow,
)
from revalo.engine.matching import Match, Offer, match
from revalo.engine.materials import materials
from revalo.i18n import material_name, num, tr
from revalo.services.market import (
    COMMISSION,
    _need,
    _suggested_price,
    normalize_phone,
    whatsapp_url,
)
from revalo.services.prices import EffectivePrice
from revalo.settings import get_settings

LOT_DISCOUNT = 0.15
"""Suggested price for a whole lot: the pieces' sale values, less this share."""
MIN_GROUP = 3
# Shorter side bands, in mm: pieces in one band suit the same kind of work.
BANDS = [(0, 300), (300, 600), (600, 1000), (1000, 100_000)]
ACTIVE = (ListingStatus.OPEN, ListingStatus.RESERVED)


class LotError(ValueError):
    pass


def _band(piece: Piece) -> tuple[int, int]:
    short = min(piece.width_mm or 0, piece.height_mm or 0)
    return next(b for b in BANDS if b[0] <= short < b[1])


def _band_label(band: tuple[int, int]) -> str:
    low, high = band
    if low == 0:
        return tr("under {high} mm", high=high)
    if high >= 100_000:
        return tr("{low} mm and more", low=low)
    return tr("{low} to {high} mm", low=low, high=high)


def _in_active_lot(session: Session) -> set[str]:
    rows = session.execute(
        select(LotItem.piece_id).join(Lot).where(Lot.status.in_(ACTIVE))
    ).scalars()
    return set(rows)


def _listed(session: Session) -> set[str]:
    rows = session.scalars(select(Listing.piece_id).where(Listing.status.in_(ACTIVE)))
    return set(rows)


def _sizes(pieces: list[Piece]) -> list[dict[str, Any]]:
    """Identical sizes counted together: "12 × 300 × 200"."""
    counts = Counter(
        (
            round(max(p.width_mm or 0, p.height_mm or 0)),
            round(min(p.width_mm or 0, p.height_mm or 0)),
        )
        for p in pieces
    )
    return [
        {"length_mm": length, "width_mm": width, "count": n}
        for (length, width), n in counts.most_common()
    ]


def _value(pieces: list[Piece], book: dict[str, EffectivePrice]) -> float:
    return round(sum(_suggested_price(p, book) or 0 for p in pieces), 1)


def suggestions(session: Session, book: dict[str, EffectivePrice]) -> list[dict[str, Any]]:
    """Groups of similar free offcuts that would sell better together."""
    busy = _in_active_lot(session) | _listed(session)
    free = [
        p
        for p in session.scalars(
            select(Piece).where(
                Piece.status == PieceStatus.IN_STOCK, Piece.kind == PieceKind.REMNANT
            )
        )
        if p.id not in busy and p.material_code and p.thickness_mm and p.width_mm and p.height_mm
    ]
    groups: dict[tuple[str, float, tuple[int, int]], list[Piece]] = {}
    for p in free:
        groups.setdefault((p.material_code, round(p.thickness_mm, 2), _band(p)), []).append(p)
    out = []
    for (code, thickness, band), pieces in groups.items():
        if len(pieces) < MIN_GROUP:
            continue
        value = _value(pieces, book)
        mat = materials().get(code)
        out.append(
            {
                "material_code": code,
                "thickness_mm": thickness,
                "band": _band_label(band),
                "title": tr(
                    "{count} offcuts, {material} {thickness} mm, {band}",
                    count=len(pieces),
                    material=material_name(mat) if mat else code,
                    thickness=num(thickness, 1).rstrip("0").rstrip(".,"),
                    band=_band_label(band),
                ),
                "count": len(pieces),
                "weight_kg": round(sum(p.weight_kg or 0 for p in pieces), 1),
                "area_m2": round(sum(p.area_m2 for p in pieces), 2),
                "value_tnd": value,
                "suggested_price_tnd": round(value * (1 - LOT_DISCOUNT), 1),
                "sizes": _sizes(pieces),
                "piece_ids": [p.id for p in pieces],
            }
        )
    out.sort(key=lambda g: (-g["count"], -g["weight_kg"]))
    return out


def create_lot(
    session: Session,
    piece_ids: list[str],
    actor: str,
    book: dict[str, EffectivePrice],
    title: str | None = None,
    price_tnd: float | None = None,
) -> Lot:
    pieces = [session.get(Piece, pid) for pid in dict.fromkeys(piece_ids)]
    if len(pieces) < 2 or any(p is None for p in pieces):
        raise LotError(tr("A lot needs at least two pieces."))
    busy = _in_active_lot(session)
    for p in pieces:
        if p.status != PieceStatus.IN_STOCK or p.kind != PieceKind.REMNANT or p.id in busy:
            raise LotError(tr("{code} is not a free remnant in stock.", code=p.code))
    if len({(p.material_code, round(p.thickness_mm or 0, 2)) for p in pieces}) != 1:
        raise LotError(tr("A lot holds one material and one thickness."))
    first = pieces[0]
    value = _value(pieces, book)
    price = price_tnd if price_tnd is not None else round(value * (1 - LOT_DISCOUNT), 1)
    if price <= 0:
        raise LotError(tr("Set a price for the lot."))
    code = first.material_code or ""
    mat = materials().get(code)
    lot = Lot(
        workshop_id=first.workshop_id,
        title=(title or "").strip()[:200]
        or f"{len(pieces)} × {mat.name_en if mat else code} {first.thickness_mm:g} mm",
        material_code=first.material_code,
        thickness_mm=first.thickness_mm,
        price_tnd=round(price, 2),
        created_by=actor,
    )
    for p in pieces:
        # A piece is offered once: alone or in a lot, not both.
        if p.listing is not None and p.listing.status == ListingStatus.OPEN:
            p.listing.status = ListingStatus.WITHDRAWN
            p.listing.closed_at = utcnow()
        lot.items.append(LotItem(piece=p))
        p.events.append(PieceEvent(actor=actor, action="lotted", data={"lot": lot.code}))
    session.add(lot)
    session.commit()
    return lot


def _close(lot: Lot, status: str, actor: str, action: str, data: dict[str, Any]) -> None:
    lot.status = status
    lot.closed_at = utcnow()
    for p in lot.pieces:
        p.events.append(PieceEvent(actor=actor, action=action, data={"lot": lot.code, **data}))


def update_lot(
    session: Session,
    lot: Lot,
    action: str,
    actor: str,
    buyer_request_id: str | None = None,
    price_tnd: float | None = None,
    piece_ids: list[str] | None = None,
) -> Lot:
    """Reserve, reopen, sell (all or part), or withdraw. Returns the lot that was sold."""
    if lot.status not in ACTIVE:
        raise LotError(tr("This lot is closed."))
    buyer = session.get(BuyerRequest, buyer_request_id) if buyer_request_id else None
    if buyer_request_id and buyer is None:
        raise LotError(tr("Unknown buyer."))

    if action == "reserve":
        if buyer is None:
            raise LotError(tr("Choose the buyer the lot is reserved for."))
        lot.status = ListingStatus.RESERVED
        lot.buyer_request_id = buyer.id
        for p in lot.pieces:
            p.status = PieceStatus.RESERVED
            p.events.append(
                PieceEvent(
                    actor=actor, action="lot_reserved", data={"lot": lot.code, "buyer": buyer.name}
                )
            )
    elif action == "reopen":
        lot.status = ListingStatus.OPEN
        lot.buyer_request_id = None
        for p in lot.pieces:
            p.status = PieceStatus.IN_STOCK
    elif action == "withdraw":
        for p in lot.pieces:
            p.status = PieceStatus.IN_STOCK
        _close(lot, ListingStatus.WITHDRAWN, actor, "lot_withdrawn", {})
    elif action == "sell":
        chosen = set(piece_ids or [])
        everything = not chosen or chosen == {p.id for p in lot.pieces}
        if not everything:
            if not chosen <= {p.id for p in lot.pieces}:
                raise LotError(tr("Those pieces are not in this lot."))
            lot = _split(session, lot, chosen, actor)
        final = price_tnd if price_tnd is not None else lot.price_tnd
        if final <= 0:
            raise LotError(tr("The sale price must be above zero."))
        lot.sold_price_tnd = round(final, 2)
        lot.fee_tnd = round(final * COMMISSION, 2)
        if buyer is not None:
            lot.buyer_request_id = buyer.id
        for p in lot.pieces:
            p.status = PieceStatus.SOLD
        data: dict[str, Any] = {"price_tnd": lot.sold_price_tnd}
        if lot.buyer is not None or buyer is not None:
            data["buyer"] = (buyer or lot.buyer).name
        _close(lot, ListingStatus.SOLD, actor, "lot_sold", data)
    else:
        raise LotError(tr("Unknown action: {action}", action=action))
    session.commit()
    return lot


def _split(session: Session, lot: Lot, chosen: set[str], actor: str) -> Lot:
    """Part of a lot leaves: it becomes its own lot; the rest stays on sale at a lower price."""
    taken = [item for item in lot.items if item.piece_id in chosen]
    share = len(taken) / len(lot.items)
    part = Lot(
        workshop_id=lot.workshop_id,
        title=f"{lot.title} ({len(taken)}/{len(lot.items)})",
        material_code=lot.material_code,
        thickness_mm=lot.thickness_mm,
        price_tnd=round(lot.price_tnd * share, 2),
        buyer_request_id=lot.buyer_request_id,
        split_from_id=lot.id,
        created_by=actor,
    )
    for item in taken:
        lot.items.remove(item)
        part.items.append(LotItem(piece=item.piece))
    lot.price_tnd = round(lot.price_tnd * (1 - share), 2)
    if lot.status == ListingStatus.RESERVED:
        # The buyer took what they wanted: the rest goes back on sale.
        lot.status = ListingStatus.OPEN
        lot.buyer_request_id = None
        for p in lot.pieces:
            p.status = PieceStatus.IN_STOCK
    session.add(part)
    session.flush()
    return part


# ---- Matching and presenting ---------------------------------------------------------


def _offer(lot: Lot) -> Offer:
    pieces = lot.pieces
    mat = materials().get(lot.material_code)
    return Offer(
        kind=PieceKind.REMNANT,
        material_code=lot.material_code,
        material_name=mat.name_en if mat else "material",
        thickness_mm=lot.thickness_mm,
        # Every piece must meet a buyer's minimum size: offer the smallest one.
        width_mm=min(max(p.width_mm or 0, p.height_mm or 0) for p in pieces),
        height_mm=min(min(p.width_mm or 0, p.height_mm or 0) for p in pieces),
        weight_kg=sum(p.weight_kg or 0 for p in pieces) or None,
        price_tnd=lot.price_tnd,
        governorate=pieces[0].job.workshop_governorate if pieces and pieces[0].job else None,
    )


def matches_for_lot(
    session: Session, lot: Lot, limit: int = 10
) -> list[tuple[BuyerRequest, Match]]:
    offer = _offer(lot)
    found = []
    for request in session.scalars(
        select(BuyerRequest).where(
            BuyerRequest.active.is_(True), BuyerRequest.kind == BuyerKind.REUSE
        )
    ):
        m = match(offer, _need(request))
        if m is not None:
            found.append((request, m))
    # Buyers who take whole lots first, then the best match.
    found.sort(key=lambda pair: (not pair[0].buys_lots, -pair[1].score))
    return found[:limit]


def lot_message(lot: Lot, buyer_name: str) -> str:
    mat = materials().get(lot.material_code)
    material = mat.name_fr if mat else "matière"
    kg = sum(p.weight_kg or 0 for p in lot.pieces)
    url = f"{get_settings().public_url}/buy"
    return (
        f"Bonjour {buyer_name}, nous avons un lot de {len(lot.items)} chutes de {material} "
        f"{lot.thickness_mm:g} mm ({kg:.0f} kg) à {lot.price_tnd:.0f} TND. Réf. {lot.code} : {url}"
    )


def lot_to_dict(
    session: Session, lot: Lot, public: bool = False, with_matches: bool = False
) -> dict[str, Any]:
    pieces = sorted(lot.pieces, key=lambda p: ((p.location or "~"), p.code))
    mat = materials().get(lot.material_code)
    body: dict[str, Any] = {
        "id": lot.id,
        "code": lot.code,
        "title": lot.title,
        "material_code": lot.material_code,
        "material_name": {"en": mat.name_en, "fr": mat.name_fr} if mat else None,
        "thickness_mm": lot.thickness_mm,
        "status": lot.status,
        "price_tnd": lot.price_tnd,
        "count": len(pieces),
        "weight_kg": round(sum(p.weight_kg or 0 for p in pieces), 1),
        "area_m2": round(sum(p.area_m2 for p in pieces), 2),
        "sizes": _sizes(pieces),
    }
    if public:
        phone = get_settings().workshop_phone
        if phone:
            body["contact_url"] = whatsapp_url(
                normalize_phone(phone), f"Bonjour, je suis intéressé par le lot {lot.code}."
            )
        return body
    body.update(
        {
            "sold_price_tnd": lot.sold_price_tnd,
            "fee_tnd": lot.fee_tnd,
            "buyer": {"id": lot.buyer.id, "name": lot.buyer.name} if lot.buyer else None,
            "created_by": lot.created_by,
            "created_at": lot.created_at.isoformat(),
            "closed_at": lot.closed_at.isoformat() if lot.closed_at else None,
            "items": [
                {
                    "id": p.id,
                    "code": p.code,
                    "width_mm": p.width_mm,
                    "height_mm": p.height_mm,
                    "weight_kg": p.weight_kg,
                    "location": p.location,
                    "status": p.status,
                }
                for p in pieces
            ],
            "label_url": f"{get_settings().public_url}/lots/{lot.id}",
        }
    )
    if with_matches and lot.status in ACTIVE:
        body["matches"] = [
            {
                "id": r.id,
                "name": r.name,
                "buys_lots": r.buys_lots,
                "score": m.score,
                "distance_km": m.distance_km,
                "whatsapp_url": whatsapp_url(r.phone, lot_message(lot, r.name)),
            }
            for r, m in matches_for_lot(session, lot)
        ]
    return body
