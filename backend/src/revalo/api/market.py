"""Marketplace API.

Public routes (`/v1/market`, posting a buyer request) need no account: buyers are
artisans and recyclers who should be able to answer from a link in a WhatsApp
group. Workshop routes manage listings, matches and deals.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import BuyerRequest, Listing, ListingStatus, Piece
from revalo.db.session import get_session
from revalo.engine.geo import GOVERNORATES
from revalo.services.jobs import default_workshop
from revalo.services.market import (
    MarketError,
    RequestInput,
    create_request,
    list_piece,
    listing_to_dict,
    market_summary,
    match_to_dict,
    matches_for_listing,
    matches_for_request,
    request_to_dict,
    update_listing,
)
from revalo.services.prices import price_book

router = APIRouter(tags=["market"])
DbSession = Annotated[Session, Depends(get_session)]


class ListingCreate(BaseModel):
    price_tnd: float | None = Field(None, gt=0, le=1_000_000)
    actor: str = Field("manager", max_length=120)


class ListingAction(BaseModel):
    action: Literal["reprice", "reserve", "reopen", "sell", "withdraw"]
    price_tnd: float | None = Field(None, gt=0, le=1_000_000)
    buyer_request_id: str | None = None
    actor: str = Field("manager", max_length=120)


class BuyerRequestCreate(BaseModel):
    kind: Literal["reuse", "recycler"] = "reuse"
    name: str = Field(min_length=2, max_length=120)
    organization: str | None = Field(None, max_length=160)
    phone: str = Field(min_length=6, max_length=32)
    governorate: str = Field(max_length=40)
    materials: list[str] = Field(default_factory=list, max_length=20)
    thickness_min_mm: float | None = Field(None, gt=0, le=200)
    thickness_max_mm: float | None = Field(None, gt=0, le=200)
    min_length_mm: float | None = Field(None, gt=0, le=20_000)
    min_width_mm: float | None = Field(None, gt=0, le=20_000)
    max_price_tnd_per_kg: float | None = Field(None, gt=0, le=10_000)
    offered_tnd_per_kg: float | None = Field(None, gt=0, le=10_000)
    min_lot_kg: float | None = Field(None, gt=0, le=1_000_000)
    pickup_note: str | None = Field(None, max_length=300)
    note: str | None = Field(None, max_length=500)


class RequestToggle(BaseModel):
    active: bool


def _listing(session: Session, listing_id: str) -> Listing:
    listing = session.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(404, "Listing not found.")
    return listing


# ---- Public --------------------------------------------------------------------------


@router.get("/v1/geo/governorates")
def governorates() -> dict[str, Any]:
    return {"governorates": list(GOVERNORATES)}


@router.get("/v1/market")
def public_market(session: DbSession) -> dict[str, Any]:
    listings = session.scalars(
        select(Listing)
        .where(Listing.status == ListingStatus.OPEN)
        .order_by(Listing.created_at.desc())
    )
    return {"listings": [listing_to_dict(lst, public=True) for lst in listings]}


@router.post("/v1/buyer-requests", status_code=201)
def post_request(body: BuyerRequestCreate, session: DbSession) -> dict[str, Any]:
    try:
        request = create_request(
            session,
            RequestInput(**{**body.model_dump(), "materials": tuple(body.materials)}),
        )
    except MarketError as exc:
        raise HTTPException(422, str(exc)) from exc
    matches = matches_for_request(session, request)
    return {
        **request_to_dict(request),
        "matching_listings": [listing_to_dict(lst, public=True) for lst, _ in matches],
    }


# ---- Workshop ------------------------------------------------------------------------


@router.post("/v1/pieces/{piece_id}/listing", status_code=201)
def create_listing(piece_id: str, body: ListingCreate, session: DbSession) -> dict[str, Any]:
    piece = session.get(Piece, piece_id)
    if piece is None:
        raise HTTPException(404, "Piece not found.")
    try:
        listing = list_piece(
            session, piece, price_book(session, piece.workshop_id), body.price_tnd, body.actor
        )
    except MarketError as exc:
        raise HTTPException(409, str(exc)) from exc
    return listing_to_dict(listing)


@router.patch("/v1/listings/{listing_id}")
def act_on_listing(listing_id: str, body: ListingAction, session: DbSession) -> dict[str, Any]:
    listing = _listing(session, listing_id)
    try:
        update_listing(
            session, listing, body.action, body.actor, body.price_tnd, body.buyer_request_id
        )
    except MarketError as exc:
        raise HTTPException(409, str(exc)) from exc
    return listing_to_dict(listing)


@router.get("/v1/listings")
def workshop_listings(session: DbSession, status: str | None = None) -> dict[str, Any]:
    query = select(Listing).order_by(Listing.updated_at.desc())
    if status:
        query = query.where(Listing.status == status)
    rows = []
    for listing in session.scalars(query):
        body = listing_to_dict(listing)
        if listing.status == ListingStatus.OPEN:
            found = matches_for_listing(session, listing, limit=3)
            body["match_count"] = len(matches_for_listing(session, listing, limit=100))
            body["top_matches"] = [match_to_dict(listing, r, m) for r, m in found]
        rows.append(body)
    default_workshop(session)
    return {"listings": rows, "summary": market_summary(session)}


@router.get("/v1/listings/{listing_id}/matches")
def listing_matches(listing_id: str, session: DbSession) -> dict[str, Any]:
    listing = _listing(session, listing_id)
    return {
        "listing": listing_to_dict(listing),
        "matches": [match_to_dict(listing, r, m) for r, m in matches_for_listing(session, listing)],
    }


@router.get("/v1/buyer-requests")
def list_requests(session: DbSession, active: bool | None = None) -> dict[str, Any]:
    query = select(BuyerRequest).order_by(BuyerRequest.created_at.desc())
    if active is not None:
        query = query.where(BuyerRequest.active.is_(active))
    rows = []
    for request in session.scalars(query):
        body = request_to_dict(request)
        body["match_count"] = len(matches_for_request(session, request)) if request.active else 0
        rows.append(body)
    return {"requests": rows}


@router.patch("/v1/buyer-requests/{request_id}")
def toggle_request(request_id: str, body: RequestToggle, session: DbSession) -> dict[str, Any]:
    request = session.get(BuyerRequest, request_id)
    if request is None:
        raise HTTPException(404, "Request not found.")
    request.active = body.active
    session.commit()
    return request_to_dict(request)
