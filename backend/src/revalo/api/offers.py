"""Offcuts offered to the workshop: sellers post them, managers buy or decline.

Posting needs no account, like a buyer's request: other workshops and suppliers
answer from a link. When a signed-in manager posts, the offer is one they
received by phone or WhatsApp and typed in.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.api.deps import ManagerUser, current_user, manager_only
from revalo.db.models import OfferStatus, Role, SupplyOffer, User
from revalo.db.session import get_session
from revalo.services.jobs import default_workshop
from revalo.services.prices import price_book
from revalo.services.sourcing import (
    OfferError,
    OfferInput,
    buy_offer,
    create_offer,
    decline_offer,
    offer_to_dict,
    planned_fits,
    purchases_summary,
    reopen_offer,
)

router = APIRouter(tags=["buying"])
DbSession = Annotated[Session, Depends(get_session)]


class OfferCreate(BaseModel):
    seller_name: str = Field(min_length=2, max_length=120)
    organization: str | None = Field(None, max_length=160)
    phone: str = Field(min_length=6, max_length=32)
    governorate: str = Field(max_length=40)
    material_code: str = Field(max_length=40)
    thickness_mm: float = Field(gt=0, le=200)
    width_mm: float = Field(gt=0, le=20_000)
    height_mm: float = Field(gt=0, le=20_000)
    quantity: int = Field(1, ge=1, le=50)
    price_tnd: float = Field(gt=0, le=1_000_000)
    note: str | None = Field(None, max_length=500)


class OfferAction(BaseModel):
    action: Literal["buy", "decline", "reopen"]
    price_tnd: float | None = Field(None, gt=0, le=1_000_000)


@router.post("/v1/supply-offers", status_code=201)
def post_offer(
    body: OfferCreate,
    session: DbSession,
    user: Annotated[User | None, Depends(current_user)],
) -> dict[str, Any]:
    manager = user is not None and Role(user.role).rank >= Role.MANAGER.rank
    try:
        offer = create_offer(
            session, OfferInput(**body.model_dump()), "workshop" if manager else "public"
        )
    except OfferError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not manager:
        # The public only learns that the offer arrived, never the workshop's view of it.
        return {"id": offer.id, "status": offer.status}
    shop = default_workshop(session)
    return offer_to_dict(offer, price_book(session, shop.id), shop.governorate)


@router.get("/v1/supply-offers", dependencies=[manager_only])
def list_offers(session: DbSession) -> dict[str, Any]:
    shop = default_workshop(session)
    book = price_book(session, shop.id)
    rows = []
    for offer in session.scalars(select(SupplyOffer).order_by(SupplyOffer.created_at.desc())):
        body = offer_to_dict(offer, book, shop.governorate)
        body["planned"] = planned_fits(session, offer) if offer.status == OfferStatus.OPEN else []
        rows.append(body)
    return {"offers": rows, "summary": purchases_summary(session, book)}


@router.patch("/v1/supply-offers/{offer_id}")
def act_on_offer(
    offer_id: str, body: OfferAction, user: ManagerUser, session: DbSession
) -> dict[str, Any]:
    offer = session.get(SupplyOffer, offer_id)
    if offer is None:
        raise HTTPException(404, "No such offer.")
    try:
        if body.action == "buy":
            buy_offer(session, offer, body.price_tnd, user.name)
        elif body.action == "decline":
            decline_offer(session, offer, user.name)
        else:
            reopen_offer(session, offer)
    except OfferError as exc:
        raise HTTPException(409, str(exc)) from exc
    shop = default_workshop(session)
    return offer_to_dict(offer, price_book(session, shop.id), shop.governorate)
