"""Recycler pickups API."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.api.deps import ManagerUser, manager_only
from revalo.db.models import Pickup
from revalo.db.session import get_session
from revalo.services.jobs import default_workshop
from revalo.services.pickups import (
    PickupError,
    pickup_to_dict,
    queue_to_dict,
    recycle_queue,
    request_pickup,
    update_pickup,
)
from revalo.services.prices import price_book

router = APIRouter(prefix="/v1/pickups", tags=["pickups"], dependencies=[manager_only])
DbSession = Annotated[Session, Depends(get_session)]


class PickupCreate(BaseModel):
    recycler_id: str
    piece_ids: list[str] = Field(min_length=1, max_length=500)


class PickupAction(BaseModel):
    action: Literal["schedule", "collect", "cancel"]
    scheduled_for: date | None = None
    weighed_kg: float | None = Field(None, gt=0, le=1_000_000)
    paid_tnd: float | None = Field(None, ge=0, le=10_000_000)


@router.get("/queue")
def queue(session: DbSession) -> dict[str, Any]:
    shop = default_workshop(session)
    pieces = recycle_queue(session, price_book(session, shop.id))
    return queue_to_dict(session, pieces, shop.governorate)


@router.get("")
def list_pickups(session: DbSession) -> dict[str, Any]:
    pickups = session.scalars(select(Pickup).order_by(Pickup.created_at.desc()))
    return {"pickups": [pickup_to_dict(p) for p in pickups]}


@router.post("", status_code=201)
def create(body: PickupCreate, user: ManagerUser, session: DbSession) -> dict[str, Any]:
    shop = default_workshop(session)
    try:
        pickup = request_pickup(session, body.recycler_id, body.piece_ids, user.name, shop.id)
    except PickupError as exc:
        raise HTTPException(409, str(exc)) from exc
    return pickup_to_dict(pickup)


@router.patch("/{pickup_id}")
def act(
    pickup_id: str, body: PickupAction, user: ManagerUser, session: DbSession
) -> dict[str, Any]:
    pickup = session.get(Pickup, pickup_id)
    if pickup is None:
        raise HTTPException(404, "Pickup not found.")
    try:
        update_pickup(
            session,
            pickup,
            body.action,
            user.name,
            body.scheduled_for,
            body.weighed_kg,
            body.paid_tnd,
        )
    except PickupError as exc:
        raise HTTPException(409, str(exc)) from exc
    return pickup_to_dict(pickup)
