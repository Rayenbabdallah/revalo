"""Buying offcuts: what other workshops and suppliers offer to sell to us.

A seller posts an offer on the public page, or a manager enters one received
on WhatsApp. Each open offer is valued against new material and checked
against the coming jobs, so the workshop buys a remnant only when it is worth
it. A bought offer goes straight into stock, with its seller and price.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import OfferStatus, PieceEvent, PieceKind, SupplyOffer, utcnow
from revalo.engine.fit import PartSize, StockRemnant, plan_fit
from revalo.engine.geo import canonical, distance_km
from revalo.engine.materials import materials
from revalo.i18n import tr
from revalo.services.fit import THICKNESS_TOLERANCE_MM, candidate_remnants
from revalo.services.intake import IntakeRow, add_existing
from revalo.services.jobs import default_workshop
from revalo.services.market import normalize_phone, whatsapp_url
from revalo.services.opportunities import active_planned, planned_parts
from revalo.services.prices import EffectivePrice

PURCHASE_FORMAT = "purchase"
MAX_QUANTITY = 50


class OfferError(ValueError):
    """An offer that cannot be recorded, or an action its state does not allow."""


@dataclass
class OfferInput:
    seller_name: str
    phone: str
    governorate: str
    material_code: str
    thickness_mm: float
    width_mm: float
    height_mm: float
    price_tnd: float
    quantity: int = 1
    organization: str | None = None
    note: str | None = None


def create_offer(session: Session, data: OfferInput, source: str = "public") -> SupplyOffer:
    governorate = canonical(data.governorate)
    if governorate is None:
        raise OfferError(tr("Unknown governorate: {name}", name=data.governorate))
    if data.material_code not in materials():
        raise OfferError(tr("Choose the material of the offcuts."))
    if not 1 <= data.quantity <= MAX_QUANTITY:
        raise OfferError(tr("Quantity must be between 1 and {max}.", max=MAX_QUANTITY))
    if data.width_mm <= 0 or data.height_mm <= 0 or data.thickness_mm <= 0:
        raise OfferError(tr("Enter the size and thickness of the offcuts in mm."))
    if data.price_tnd <= 0:
        raise OfferError(tr("Enter the asking price in TND."))
    try:
        phone = normalize_phone(data.phone)
    except ValueError as exc:
        raise OfferError(str(exc)) from exc
    offer = SupplyOffer(
        workshop_id=default_workshop(session).id,
        source=source,
        seller_name=data.seller_name.strip(),
        organization=(data.organization or "").strip() or None,
        phone=phone,
        governorate=governorate,
        material_code=data.material_code,
        thickness_mm=data.thickness_mm,
        # Stored long side first, as remnants are.
        width_mm=max(data.width_mm, data.height_mm),
        height_mm=min(data.width_mm, data.height_mm),
        quantity=data.quantity,
        price_tnd=round(data.price_tnd, 2),
        note=(data.note or "").strip() or None,
    )
    session.add(offer)
    session.commit()
    return offer


# ---- Is it worth buying? -------------------------------------------------------------


def offer_weight_kg(offer: SupplyOffer) -> float:
    mat = materials()[offer.material_code]
    return mat.weight_kg(offer.width_mm * offer.height_mm, offer.thickness_mm) * offer.quantity


def offer_value(
    offer: SupplyOffer, book: dict[str, EffectivePrice], workshop_governorate: str | None
) -> dict[str, Any]:
    """The offer against new material of the same weight, and how far away it is."""
    kg = offer_weight_kg(offer)
    entry = book.get(offer.material_code)
    new_price = entry.prices.new_tnd_per_kg if entry and entry.prices else None
    new_tnd = kg * new_price if new_price else None
    return {
        "weight_kg": round(kg, 2),
        "price_tnd_per_kg": round(offer.price_tnd / kg, 2) if kg else None,
        "new_tnd": round(new_tnd, 2) if new_tnd is not None else None,
        "saving_tnd": round(new_tnd - offer.price_tnd, 2) if new_tnd is not None else None,
        "distance_km": distance_km(workshop_governorate, offer.governorate),
    }


def _offer_remnants(offer: SupplyOffer) -> list[StockRemnant]:
    return [
        StockRemnant(f"{offer.id}:{i}", f"{offer.id}:{i}", offer.width_mm, offer.height_mm)
        for i in range(offer.quantity)
    ]


def _same_material(offer: SupplyOffer, code: str, thickness: float) -> bool:
    return (
        offer.material_code == code
        and abs(offer.thickness_mm - thickness) <= THICKNESS_TOLERANCE_MM
    )


def planned_fits(session: Session, offer: SupplyOffer) -> list[dict[str, Any]]:
    """Coming jobs whose parts the offer would hold, beyond what the racks already hold."""
    found = []
    for planned in active_planned(session):
        if not _same_material(offer, planned.material_code, planned.thickness_mm):
            continue
        parts = planned_parts(planned)
        stock = [
            StockRemnant(p.id, p.code, p.width_mm, p.height_mm)
            for p in candidate_remnants(session, planned.material_code, planned.thickness_mm)
        ]
        before = plan_fit(parts, stock, planned.kerf_mm).placed_count if stock else 0
        after = plan_fit(parts, stock + _offer_remnants(offer), planned.kerf_mm).placed_count
        if after > before:
            found.append(
                {
                    "id": planned.id,
                    "name": planned.name,
                    "extra_parts": after - before,
                    "placed": after,
                    "total": len(parts),
                }
            )
    return found


def offers_for_parts(
    session: Session,
    code: str,
    thickness: float,
    kerf: float,
    parts: list[PartSize],
    book: dict[str, EffectivePrice],
) -> list[dict[str, Any]]:
    """Open offers that would hold parts the racks cannot: buy before opening a new sheet."""
    if not parts:
        return []
    shop = default_workshop(session)
    out = []
    for offer in open_offers(session):
        if not _same_material(offer, code, thickness):
            continue
        plan = plan_fit(parts, _offer_remnants(offer), kerf)
        if plan.placed_count:
            out.append(
                {
                    **offer_to_dict(offer, book, shop.governorate),
                    "placed_count": plan.placed_count,
                }
            )
    out.sort(key=lambda o: (-o["placed_count"], o["price_tnd"]))
    return out


# ---- Deal ----------------------------------------------------------------------------


def open_offers(session: Session) -> list[SupplyOffer]:
    return list(
        session.scalars(
            select(SupplyOffer)
            .where(SupplyOffer.status == OfferStatus.OPEN)
            .order_by(SupplyOffer.created_at.desc())
        )
    )


def contact_message(offer: SupplyOffer) -> str:
    """The WhatsApp message to the seller, in French as the trade writes it."""
    mat = materials()[offer.material_code]
    return (
        f"Bonjour {offer.seller_name}, votre offre de {mat.name_fr} {offer.thickness_mm:g} mm "
        f"({offer.quantity} × {offer.width_mm:.0f} × {offer.height_mm:.0f} mm, "
        f"{offer.price_tnd:.0f} TND) nous intéresse. Est-elle toujours disponible ?"
    )


def buy_offer(
    session: Session, offer: SupplyOffer, price_tnd: float | None, actor: str
) -> SupplyOffer:
    if offer.status != OfferStatus.OPEN:
        raise OfferError(tr("This offer is closed."))
    paid = price_tnd if price_tnd is not None else offer.price_tnd
    if paid <= 0:
        raise OfferError(tr("The price paid must be above zero."))
    mat = materials()[offer.material_code]
    seller = offer.organization or offer.seller_name
    job = add_existing(
        session,
        [
            IntakeRow(
                material=offer.material_code,
                thickness_mm=offer.thickness_mm,
                width_mm=offer.width_mm,
                height_mm=offer.height_mm,
                quantity=offer.quantity,
                kind=PieceKind.REMNANT,
            )
        ],
        f"Bought from {seller}",
        actor,
        file_format=PURCHASE_FORMAT,
        source=f"bought from {seller}",
    )
    each = round(paid / offer.quantity, 2)
    for piece in job.pieces:
        piece.events.append(
            PieceEvent(
                actor=actor,
                action="bought",
                data={"seller": seller, "price_tnd": each, "material": mat.name_en},
            )
        )
    offer.status = OfferStatus.BOUGHT
    offer.bought_price_tnd = round(paid, 2)
    offer.intake_job_id = job.id
    offer.closed_by = actor
    offer.closed_at = utcnow()
    session.commit()
    return offer


def decline_offer(session: Session, offer: SupplyOffer, actor: str) -> SupplyOffer:
    if offer.status != OfferStatus.OPEN:
        raise OfferError(tr("This offer is closed."))
    offer.status = OfferStatus.DECLINED
    offer.closed_by = actor
    offer.closed_at = utcnow()
    session.commit()
    return offer


def reopen_offer(session: Session, offer: SupplyOffer) -> SupplyOffer:
    if offer.status != OfferStatus.DECLINED:
        raise OfferError(tr("Only a declined offer can be reopened."))
    offer.status = OfferStatus.OPEN
    offer.closed_by = None
    offer.closed_at = None
    session.commit()
    return offer


def offer_to_dict(
    offer: SupplyOffer, book: dict[str, EffectivePrice], workshop_governorate: str | None
) -> dict[str, Any]:
    mat = materials()[offer.material_code]
    return {
        "id": offer.id,
        "status": offer.status,
        "source": offer.source,
        "seller_name": offer.seller_name,
        "organization": offer.organization,
        "phone": offer.phone,
        "governorate": offer.governorate,
        "material_code": offer.material_code,
        "material_name": {"en": mat.name_en, "fr": mat.name_fr},
        "thickness_mm": offer.thickness_mm,
        "width_mm": offer.width_mm,
        "height_mm": offer.height_mm,
        "quantity": offer.quantity,
        "price_tnd": offer.price_tnd,
        "note": offer.note,
        "bought_price_tnd": offer.bought_price_tnd,
        "intake_job_id": offer.intake_job_id,
        "closed_by": offer.closed_by,
        "created_at": offer.created_at.isoformat(),
        "closed_at": offer.closed_at.isoformat() if offer.closed_at else None,
        "whatsapp_url": whatsapp_url(offer.phone, contact_message(offer)),
        **offer_value(offer, book, workshop_governorate),
    }


def with_offers(
    session: Session, result: dict[str, Any], book: dict[str, EffectivePrice]
) -> dict[str, Any]:
    """Add to a stock check the offers that would hold the parts the racks cannot."""
    unplaced = [PartSize(p["label"], p["length"], p["width"]) for p in result["unplaced"]]
    result["offers"] = offers_for_parts(
        session, result["material_code"], result["thickness_mm"], result["kerf_mm"], unplaced, book
    )
    return result


def purchases_summary(session: Session, book: dict[str, EffectivePrice]) -> dict[str, Any]:
    bought = list(
        session.scalars(select(SupplyOffer).where(SupplyOffer.status == OfferStatus.BOUGHT))
    )
    spent = sum(o.bought_price_tnd or 0 for o in bought)
    saved = 0.0
    for o in bought:
        value = offer_value(o, book, None)
        if value["new_tnd"] is not None:
            saved += value["new_tnd"] - (o.bought_price_tnd or 0)
    return {
        "open": len(open_offers(session)),
        "bought": len(bought),
        "spent_tnd": round(spent, 2),
        "saved_tnd": round(saved, 2),
    }
