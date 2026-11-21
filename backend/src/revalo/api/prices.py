"""Price book API: the numbers behind every recommendation, editable by the workshop."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from revalo.api.deps import ManagerUser, manager_only, signed_in
from revalo.db.session import get_session
from revalo.services.jobs import default_workshop
from revalo.services.prices import PriceError, price_book, reset_price, set_price

router = APIRouter(prefix="/v1/prices", tags=["prices"], dependencies=[signed_in])
DbSession = Annotated[Session, Depends(get_session)]


class PriceUpdate(BaseModel):
    new_tnd_per_kg: float = Field(gt=0, le=10_000)
    scrap_tnd_per_kg: float = Field(ge=0, le=10_000)
    resale_factor: float = Field(gt=0, le=1)
    source: str | None = Field(None, max_length=500)


@router.get("")
def list_prices(session: DbSession) -> dict[str, Any]:
    shop = default_workshop(session)
    session.commit()
    return {"prices": [p.to_dict() for p in price_book(session, shop.id).values()]}


@router.put("/{material_code}")
def update_price(
    material_code: str, body: PriceUpdate, user: ManagerUser, session: DbSession
) -> dict[str, Any]:
    shop = default_workshop(session)
    try:
        entry = set_price(
            session,
            shop.id,
            material_code,
            body.new_tnd_per_kg,
            body.scrap_tnd_per_kg,
            body.resale_factor,
            body.source,
            user.name,
        )
    except PriceError as exc:
        raise HTTPException(422, str(exc)) from exc
    return entry.to_dict()


@router.delete("/{material_code}", dependencies=[manager_only])
def reset(material_code: str, session: DbSession) -> dict[str, Any]:
    shop = default_workshop(session)
    try:
        entry = reset_price(session, shop.id, material_code)
    except PriceError as exc:
        raise HTTPException(422, str(exc)) from exc
    return entry.to_dict()
