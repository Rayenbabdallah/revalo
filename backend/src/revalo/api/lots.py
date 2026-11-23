"""Batch lots: similar offcuts sold as one deal."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.api.deps import ManagerUser, manager_only
from revalo.db.models import Lot
from revalo.db.session import get_session
from revalo.services.jobs import default_workshop
from revalo.services.lots import LotError, create_lot, lot_to_dict, suggestions, update_lot
from revalo.services.prices import price_book

router = APIRouter(prefix="/v1/lots", tags=["market"], dependencies=[manager_only])
DbSession = Annotated[Session, Depends(get_session)]


class LotCreate(BaseModel):
    piece_ids: list[str] = Field(min_length=2, max_length=500)
    title: str | None = Field(None, max_length=200)
    price_tnd: float | None = Field(None, gt=0, le=1_000_000)


class LotAction(BaseModel):
    action: Literal["reserve", "reopen", "sell", "withdraw"]
    buyer_request_id: str | None = None
    price_tnd: float | None = Field(None, gt=0, le=1_000_000)
    piece_ids: list[str] | None = Field(None, max_length=500)


def _lot(session: Session, lot_id: str) -> Lot:
    lot = session.get(Lot, lot_id)
    if lot is None:
        raise HTTPException(404, "No such lot.")
    return lot


@router.get("/suggestions")
def suggested(session: DbSession) -> dict[str, Any]:
    return {"groups": suggestions(session, price_book(session, default_workshop(session).id))}


@router.get("")
def list_lots(session: DbSession) -> dict[str, Any]:
    lots = session.scalars(select(Lot).order_by(Lot.created_at.desc()).limit(200))
    return {"lots": [lot_to_dict(session, lot, with_matches=True) for lot in lots]}


@router.post("", status_code=201)
def make_lot(body: LotCreate, user: ManagerUser, session: DbSession) -> dict[str, Any]:
    book = price_book(session, default_workshop(session).id)
    try:
        lot = create_lot(session, body.piece_ids, user.name, book, body.title, body.price_tnd)
    except LotError as exc:
        raise HTTPException(422, str(exc)) from exc
    return lot_to_dict(session, lot, with_matches=True)


@router.get("/{lot_id}")
def get_lot(lot_id: str, session: DbSession) -> dict[str, Any]:
    return lot_to_dict(session, _lot(session, lot_id), with_matches=True)


@router.patch("/{lot_id}")
def act_on_lot(
    lot_id: str, body: LotAction, user: ManagerUser, session: DbSession
) -> dict[str, Any]:
    lot = _lot(session, lot_id)
    try:
        result = update_lot(
            session,
            lot,
            body.action,
            user.name,
            body.buyer_request_id,
            body.price_tnd,
            body.piece_ids,
        )
    except LotError as exc:
        raise HTTPException(409, str(exc)) from exc
    return lot_to_dict(session, result, with_matches=True)
