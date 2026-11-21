"""Marketplace: list pieces, record buyers' needs, match them, and track deals."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import (
    BuyerKind,
    BuyerRequest,
    Listing,
    ListingStatus,
    Piece,
    PieceEvent,
    PieceKind,
    PieceStatus,
    utcnow,
)
from revalo.engine.decision import COMMISSION, Action
from revalo.engine.geo import canonical
from revalo.engine.matching import Match, Need, Offer, match
from revalo.engine.materials import materials
from revalo.services.decisions import decide_piece
from revalo.services.prices import EffectivePrice
from revalo.settings import get_settings

ACTIVE_LISTING = {ListingStatus.OPEN, ListingStatus.RESERVED}


class MarketError(ValueError):
    """A marketplace action the current state does not allow."""


def normalize_phone(raw: str) -> str:
    """WhatsApp needs international numbers. Eight digits alone are Tunisian (+216)."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 8:
        digits = "216" + digits
    if not 10 <= len(digits) <= 15:
        raise MarketError("Enter a WhatsApp number, for example 22 123 456 or +216 22 123 456.")
    return "+" + digits


def whatsapp_url(phone: str, text: str) -> str:
    return f"https://wa.me/{phone.lstrip('+')}?text={quote(text)}"


# ---- Buyer requests -------------------------------------------------------------------


@dataclass
class RequestInput:
    kind: str
    name: str
    phone: str
    governorate: str
    organization: str | None = None
    materials: tuple[str, ...] = ()
    thickness_min_mm: float | None = None
    thickness_max_mm: float | None = None
    min_length_mm: float | None = None
    min_width_mm: float | None = None
    max_price_tnd_per_kg: float | None = None
    note: str | None = None


def create_request(session: Session, data: RequestInput) -> BuyerRequest:
    if data.kind not in {k.value for k in BuyerKind}:
        raise MarketError(f"Unknown buyer kind: {data.kind}")
    governorate = canonical(data.governorate)
    if governorate is None:
        raise MarketError(f"Unknown governorate: {data.governorate}")
    unknown = [m for m in data.materials if m not in materials()]
    if unknown:
        raise MarketError(f"Unknown material code: {unknown[0]}")
    if (
        data.thickness_min_mm is not None
        and data.thickness_max_mm is not None
        and data.thickness_min_mm > data.thickness_max_mm
    ):
        raise MarketError("The minimum thickness is above the maximum.")
    request = BuyerRequest(
        kind=data.kind,
        name=data.name.strip(),
        organization=(data.organization or "").strip() or None,
        phone=normalize_phone(data.phone),
        governorate=governorate,
        materials={"codes": list(dict.fromkeys(data.materials))},
        thickness_min_mm=data.thickness_min_mm,
        thickness_max_mm=data.thickness_max_mm,
        min_length_mm=data.min_length_mm,
        min_width_mm=data.min_width_mm,
        max_price_tnd_per_kg=data.max_price_tnd_per_kg,
        note=(data.note or "").strip() or None,
    )
    session.add(request)
    session.commit()
    return request


def request_to_dict(request: BuyerRequest) -> dict[str, Any]:
    return {
        "id": request.id,
        "kind": request.kind,
        "name": request.name,
        "organization": request.organization,
        "phone": request.phone,
        "governorate": request.governorate,
        "materials": request.materials.get("codes", []),
        "thickness_min_mm": request.thickness_min_mm,
        "thickness_max_mm": request.thickness_max_mm,
        "min_length_mm": request.min_length_mm,
        "min_width_mm": request.min_width_mm,
        "max_price_tnd_per_kg": request.max_price_tnd_per_kg,
        "note": request.note,
        "active": request.active,
        "created_at": request.created_at.isoformat(),
    }


# ---- Listings -------------------------------------------------------------------------


def _suggested_price(piece: Piece, book: dict[str, EffectivePrice]) -> float | None:
    decision = decide_piece(piece, book)
    action = Action.RECYCLE if piece.kind == PieceKind.SCRAP else Action.SELL
    value = decision.option(action).value_tnd
    if value is None or value <= 0:
        return None
    # Asking price before commission: the seller receives the sale value net of fees.
    return round(value / (1 - COMMISSION), 1) if action == Action.SELL else round(value, 1)


def list_piece(
    session: Session,
    piece: Piece,
    book: dict[str, EffectivePrice],
    price_tnd: float | None,
    actor: str,
) -> Listing:
    if piece.status != PieceStatus.IN_STOCK:
        raise MarketError("Only approved pieces in stock can be listed.")
    existing = session.scalars(select(Listing).where(Listing.piece_id == piece.id)).first()
    if existing is not None and existing.status in ACTIVE_LISTING:
        raise MarketError("This piece is already on the marketplace.")
    price = price_tnd if price_tnd is not None else _suggested_price(piece, book)
    if price is None or price <= 0:
        raise MarketError("Set an asking price: this material has no price in the price book yet.")

    listing = existing or Listing(piece_id=piece.id, workshop_id=piece.workshop_id)
    listing.status = ListingStatus.OPEN
    listing.price_tnd = round(price, 2)
    listing.buyer_request_id = None
    listing.sold_price_tnd = None
    listing.fee_tnd = None
    listing.closed_at = None
    if existing is None:
        session.add(listing)
    piece.events.append(
        PieceEvent(actor=actor, action="listed", data={"price_tnd": listing.price_tnd})
    )
    session.commit()
    return listing


def update_listing(
    session: Session,
    listing: Listing,
    action: str,
    actor: str,
    price_tnd: float | None = None,
    buyer_request_id: str | None = None,
) -> Listing:
    piece = listing.piece
    data: dict[str, Any] = {}
    if action == "reprice":
        if listing.status != ListingStatus.OPEN or price_tnd is None or price_tnd <= 0:
            raise MarketError("Only an open listing can be repriced, with a price above zero.")
        data = {"from": listing.price_tnd, "to": price_tnd}
        listing.price_tnd = round(price_tnd, 2)
    elif action == "reserve":
        if listing.status != ListingStatus.OPEN:
            raise MarketError("Only an open listing can be reserved.")
        buyer = session.get(BuyerRequest, buyer_request_id) if buyer_request_id else None
        if buyer is None:
            raise MarketError("Choose the buyer the piece is reserved for.")
        listing.status = ListingStatus.RESERVED
        listing.buyer_request_id = buyer.id
        piece.status = PieceStatus.RESERVED
        data = {"buyer": buyer.name}
    elif action == "reopen":
        if listing.status != ListingStatus.RESERVED:
            raise MarketError("Only a reserved listing can be reopened.")
        listing.status = ListingStatus.OPEN
        listing.buyer_request_id = None
        piece.status = PieceStatus.IN_STOCK
    elif action == "sell":
        if listing.status not in ACTIVE_LISTING:
            raise MarketError("This listing is closed.")
        if buyer_request_id:
            if session.get(BuyerRequest, buyer_request_id) is None:
                raise MarketError("Unknown buyer.")
            listing.buyer_request_id = buyer_request_id
        final = price_tnd if price_tnd is not None else listing.price_tnd
        if final <= 0:
            raise MarketError("The sale price must be above zero.")
        listing.status = ListingStatus.SOLD
        listing.sold_price_tnd = round(final, 2)
        listing.fee_tnd = round(final * COMMISSION, 2)
        listing.closed_at = utcnow()
        piece.status = PieceStatus.RECYCLED if piece.kind == PieceKind.SCRAP else PieceStatus.SOLD
        data = {"price_tnd": listing.sold_price_tnd, "fee_tnd": listing.fee_tnd}
        if listing.buyer is not None:
            data["buyer"] = listing.buyer.name
    elif action == "withdraw":
        if listing.status not in ACTIVE_LISTING:
            raise MarketError("This listing is already closed.")
        listing.status = ListingStatus.WITHDRAWN
        listing.closed_at = utcnow()
        piece.status = PieceStatus.IN_STOCK
    else:
        raise MarketError(f"Unknown action: {action}")
    piece.events.append(PieceEvent(actor=actor, action=f"listing_{action}", data=data))
    session.commit()
    return listing


def _offer(listing: Listing) -> Offer:
    piece = listing.piece
    mat = materials().get(piece.material_code or "")
    shop_governorate = piece.job.workshop_governorate if piece.job else None
    return Offer(
        kind=piece.kind,
        material_code=piece.material_code,
        material_name=mat.name_en if mat else "material",
        thickness_mm=piece.thickness_mm,
        width_mm=piece.width_mm,
        height_mm=piece.height_mm,
        weight_kg=piece.weight_kg,
        price_tnd=listing.price_tnd,
        governorate=shop_governorate,
    )


def _need(request: BuyerRequest) -> Need:
    return Need(
        kind=request.kind,
        materials=tuple(request.materials.get("codes", [])),
        thickness_min_mm=request.thickness_min_mm,
        thickness_max_mm=request.thickness_max_mm,
        min_length_mm=request.min_length_mm,
        min_width_mm=request.min_width_mm,
        max_price_tnd_per_kg=request.max_price_tnd_per_kg,
        governorate=request.governorate,
        created_at=request.created_at,
    )


def offer_message(listing: Listing, buyer_name: str) -> str:
    """The WhatsApp message a manager sends, in French as the trade writes it."""
    piece = listing.piece
    mat = materials().get(piece.material_code or "")
    material = mat.name_fr if mat else "matière"
    thickness = f" {piece.thickness_mm:g} mm" if piece.thickness_mm else ""
    size = (
        f"{piece.width_mm:.0f} × {piece.height_mm:.0f} mm"
        if piece.kind == PieceKind.REMNANT
        else "lot de chutes et squelettes"
    )
    weight = f", {piece.weight_kg:.1f} kg" if piece.weight_kg else ""
    url = f"{get_settings().public_url}/p/{piece.code}"
    return (
        f"Bonjour {buyer_name}, nous avons {material}{thickness} disponible : {size}{weight}, "
        f"à {listing.price_tnd:.0f} TND. Réf. {piece.code} : {url}"
    )


def matches_for_listing(session: Session, listing: Listing, limit: int = 10):
    offer = _offer(listing)
    found: list[tuple[BuyerRequest, Match]] = []
    for request in session.scalars(select(BuyerRequest).where(BuyerRequest.active.is_(True))):
        m = match(offer, _need(request))
        if m is not None:
            found.append((request, m))
    found.sort(key=lambda pair: (-pair[1].score, pair[1].distance_km or 0))
    return found[:limit]


def matches_for_request(session: Session, request: BuyerRequest, limit: int = 20):
    need = _need(request)
    found: list[tuple[Listing, Match]] = []
    for listing in session.scalars(select(Listing).where(Listing.status == ListingStatus.OPEN)):
        m = match(_offer(listing), need)
        if m is not None:
            found.append((listing, m))
    found.sort(key=lambda pair: -pair[1].score)
    return found[:limit]


def match_to_dict(listing: Listing, request: BuyerRequest, m: Match) -> dict[str, Any]:
    return {
        "request": request_to_dict(request),
        "score": m.score,
        "distance_km": m.distance_km,
        "reasons": m.reasons,
        "whatsapp_url": whatsapp_url(request.phone, offer_message(listing, request.name)),
    }


def listing_to_dict(listing: Listing, public: bool = False) -> dict[str, Any]:
    piece = listing.piece
    mat = materials().get(piece.material_code or "")
    body: dict[str, Any] = {
        "id": listing.id,
        "status": listing.status,
        "price_tnd": listing.price_tnd,
        "price_tnd_per_kg": round(listing.price_tnd / piece.weight_kg, 2)
        if piece.weight_kg
        else None,
        "piece": {
            "code": piece.code,
            "kind": piece.kind,
            "material_code": piece.material_code,
            "material_name": {"en": mat.name_en, "fr": mat.name_fr} if mat else None,
            "family": mat.family if mat else None,
            "thickness_mm": piece.thickness_mm,
            "width_mm": piece.width_mm,
            "height_mm": piece.height_mm,
            "area_m2": piece.area_m2,
            "weight_kg": piece.weight_kg,
            "condition_note": piece.condition_note,
        },
        "governorate": piece.job.workshop_governorate if piece.job else None,
        "created_at": listing.created_at.isoformat(),
    }
    if public:
        phone = get_settings().workshop_phone
        body["contact_url"] = (
            whatsapp_url(
                phone,
                f"Bonjour, je suis intéressé par la pièce {piece.code} "
                f"({listing.price_tnd:.0f} TND) vue sur Revalo.",
            )
            if phone
            else None
        )
        return body
    body.update(
        {
            "piece_id": piece.id,
            "buyer": request_to_dict(listing.buyer) if listing.buyer else None,
            "sold_price_tnd": listing.sold_price_tnd,
            "fee_tnd": listing.fee_tnd,
            "updated_at": listing.updated_at.isoformat(),
            "closed_at": listing.closed_at.isoformat() if listing.closed_at else None,
        }
    )
    return body


def market_summary(session: Session) -> dict[str, Any]:
    listings = list(session.scalars(select(Listing)))
    sold = [lst for lst in listings if lst.status == ListingStatus.SOLD]
    return {
        "open": sum(1 for lst in listings if lst.status == ListingStatus.OPEN),
        "reserved": sum(1 for lst in listings if lst.status == ListingStatus.RESERVED),
        "sold": len(sold),
        "sales_tnd": round(sum(lst.sold_price_tnd or 0 for lst in sold), 2),
        "fees_tnd": round(sum(lst.fee_tnd or 0 for lst in sold), 2),
        "open_value_tnd": round(
            sum(lst.price_tnd for lst in listings if lst.status == ListingStatus.OPEN), 2
        ),
        "active_requests": len(
            list(session.scalars(select(BuyerRequest.id).where(BuyerRequest.active.is_(True))))
        ),
    }
