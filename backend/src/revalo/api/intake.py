"""Enter the pieces already on the racks: by hand, or from a CSV list."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from revalo.api.deps import ManagerUser
from revalo.db.session import get_session
from revalo.services.intake import MAX_ROWS, IntakeError, IntakeRow, add_existing, check_rows
from revalo.services.jobs import job_detail
from revalo.services.prices import price_book

router = APIRouter(prefix="/v1/stock/intake", tags=["stock"])
DbSession = Annotated[Session, Depends(get_session)]


class RowBody(BaseModel):
    material: str = Field(min_length=1, max_length=80)
    thickness_mm: float = Field(gt=0, le=300)
    width_mm: float | None = Field(None, gt=0, le=20_000)
    height_mm: float | None = Field(None, gt=0, le=20_000)
    quantity: int = Field(1, ge=1, le=200)
    location: str | None = Field(None, max_length=80)
    kind: str = Field("remnant", pattern="^(remnant|scrap)$")
    weight_kg: float | None = Field(None, gt=0, le=100_000)


class IntakeBody(BaseModel):
    name: str | None = Field(None, max_length=200)
    rows: list[RowBody] = Field(min_length=1, max_length=MAX_ROWS)


def _rows(body: IntakeBody) -> list[IntakeRow]:
    return [IntakeRow(**row.model_dump()) for row in body.rows]


@router.post("/check")
def check(body: IntakeBody, user: ManagerUser, session: DbSession) -> dict[str, Any]:
    """What would be added, and which rows look like pieces already in stock."""
    try:
        return {"rows": check_rows(session, _rows(body))}
    except IntakeError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("", status_code=201)
def add(body: IntakeBody, user: ManagerUser, session: DbSession) -> dict[str, Any]:
    try:
        job = add_existing(session, _rows(body), body.name, user.name)
    except IntakeError as exc:
        raise HTTPException(422, str(exc)) from exc
    return job_detail(job, price_book(session, job.workshop_id))
