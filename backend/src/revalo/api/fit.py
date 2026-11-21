"""Check stock before cutting: which stored remnants can hold the next job."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from revalo.api.deps import SignedIn, signed_in
from revalo.db.session import get_session
from revalo.engine.fit import PartSize
from revalo.engine.pipeline import MAX_FILE_BYTES
from revalo.services.fit import FitError, FitRequest, check_stock, mark_reused
from revalo.services.jobs import default_workshop, piece_to_dict
from revalo.services.prices import price_book

router = APIRouter(prefix="/v1/stock/fit", tags=["stock"], dependencies=[signed_in])
DbSession = Annotated[Session, Depends(get_session)]


class ReuseBody(BaseModel):
    piece_ids: list[str] = Field(min_length=1, max_length=200)
    job_name: str = Field(min_length=1, max_length=160)


def _typed_parts(raw: str | None) -> list[PartSize]:
    """Parts typed by hand: [{"label", "length", "width", "qty"}]."""
    if not raw:
        return []
    try:
        rows = json.loads(raw)
        parts = []
        for i, row in enumerate(rows):
            length, width = float(row["length"]), float(row["width"])
            qty = int(row.get("qty", 1))
            if length <= 0 or width <= 0 or not 0 < qty <= 500:
                raise ValueError
            label = str(row.get("label") or f"Part {i + 1}")
            parts.extend(PartSize(label, length, width) for _ in range(qty))
        return parts
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(422, "Part sizes must be positive lengths and widths.") from exc


@router.post("")
def fit(
    session: DbSession,
    file: Annotated[UploadFile | None, File()] = None,
    parts: Annotated[str | None, Form()] = None,
    material: Annotated[str | None, Form()] = None,
    thickness_mm: Annotated[float | None, Form(gt=0, le=200)] = None,
    kerf_mm: Annotated[float | None, Form(ge=0, le=20)] = None,
) -> dict[str, Any]:
    data = file.file.read(MAX_FILE_BYTES + 1) if file else None
    if data is not None and len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File is larger than 25 MB.")
    shop = default_workshop(session)
    try:
        return check_stock(
            session,
            data,
            (file.filename if file else None) or "",
            _typed_parts(parts),
            FitRequest(material or None, thickness_mm, kerf_mm),
            price_book(session, shop.id),
        )
    except FitError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/reuse")
def reuse(body: ReuseBody, user: SignedIn, session: DbSession) -> dict[str, Any]:
    try:
        pieces = mark_reused(session, body.piece_ids, body.job_name, user.name)
    except FitError as exc:
        raise HTTPException(409, str(exc)) from exc
    book = price_book(session, default_workshop(session).id)
    return {"pieces": [piece_to_dict(p, book) for p in pieces]}
