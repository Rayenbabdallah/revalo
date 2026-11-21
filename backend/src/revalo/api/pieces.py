"""Pieces API: correct and approve leftover records, look them up, list stock."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import Job, Piece, PieceStatus
from revalo.db.session import get_session
from revalo.services.jobs import job_detail, piece_to_dict
from revalo.services.pieces import (
    PieceChanges,
    ReviewError,
    approve_job,
    stock_pieces,
    stock_summary,
    update_piece,
)

router = APIRouter(tags=["pieces"])
DbSession = Annotated[Session, Depends(get_session)]


class PiecePatch(BaseModel):
    actor: str = Field("manager", max_length=120)
    weight_actual_kg: float | None = Field(None, gt=0, le=100_000)
    clear_weight: bool = False
    width_mm: float | None = Field(None, gt=0, le=20_000)
    height_mm: float | None = Field(None, gt=0, le=20_000)
    condition_note: str | None = Field(None, max_length=500)
    location: str | None = Field(None, max_length=80)
    rejected: bool | None = None


class Approval(BaseModel):
    actor: str = Field("manager", max_length=120)


def _piece_with_history(piece: Piece) -> dict[str, Any]:
    return {
        **piece_to_dict(piece),
        "events": [
            {"at": e.at.isoformat(), "actor": e.actor, "action": e.action, "data": e.data}
            for e in piece.events
        ],
    }


@router.patch("/v1/pieces/{piece_id}")
def patch_piece(piece_id: str, body: PiecePatch, session: DbSession) -> dict[str, Any]:
    piece = session.get(Piece, piece_id)
    if piece is None:
        raise HTTPException(404, "Piece not found.")
    changes = PieceChanges(**body.model_dump(exclude={"actor"}))
    try:
        update_piece(session, piece, changes, body.actor)
    except ReviewError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _piece_with_history(piece)


@router.post("/v1/jobs/{job_id}/approve")
def approve(job_id: str, body: Approval, session: DbSession) -> dict[str, Any]:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    try:
        approve_job(session, job, body.actor)
    except ReviewError as exc:
        raise HTTPException(409, str(exc)) from exc
    return job_detail(job)


@router.get("/v1/pieces/{piece_id}")
def get_piece(piece_id: str, session: DbSession) -> dict[str, Any]:
    piece = session.get(Piece, piece_id)
    if piece is None:
        raise HTTPException(404, "Piece not found.")
    return _piece_with_history(piece)


@router.get("/v1/codes/{code}")
def get_piece_by_code(code: str, session: DbSession) -> dict[str, Any]:
    """What a QR label opens: the piece and the job it came from."""
    piece = session.scalars(select(Piece).where(Piece.code == code.upper())).first()
    if piece is None:
        raise HTTPException(404, "No piece with this code.")
    return {
        **_piece_with_history(piece),
        "job": {"id": piece.job.id, "file_name": piece.job.file_name, "status": piece.job.status},
    }


@router.get("/v1/stock")
def list_stock(
    session: DbSession,
    status: str | None = PieceStatus.IN_STOCK,
    kind: str | None = None,
) -> dict[str, Any]:
    if status and status not in {s.value for s in PieceStatus}:
        raise HTTPException(422, f"Unknown status: {status}")
    return {"pieces": [piece_to_dict(p) for p in stock_pieces(session, status or None, kind)]}


@router.get("/v1/stock/summary")
def get_stock_summary(session: DbSession) -> dict[str, Any]:
    return stock_summary(session)
