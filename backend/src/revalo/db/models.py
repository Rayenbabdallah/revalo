"""Database models: workshops, jobs, leftover pieces and their history."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


# Crockford base32 without I, L, O, U: easy to read off a label and type back.
_CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_piece_code() -> str:
    return "RV-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON}


class JobStatus(StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"


class PieceKind(StrEnum):
    REMNANT = "remnant"
    """A clean rectangle that can be reused or sold."""
    SCRAP = "scrap"
    """The skeleton and offcuts of one sheet, sold by weight as one lot."""


class PieceStatus(StrEnum):
    DRAFT = "draft"
    REJECTED = "rejected"
    IN_STOCK = "in_stock"
    RESERVED = "reserved"
    REUSED = "reused"
    SOLD = "sold"
    RECYCLED = "recycled"


class Workshop(Base):
    __tablename__ = "workshops"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    governorate: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"), index=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_format: Mapped[str] = mapped_column(String(20))
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    file_key: Mapped[str] = mapped_column(String(255))
    material_code: Mapped[str | None] = mapped_column(String(40))
    thickness_mm: Mapped[float | None] = mapped_column(Float)
    process: Mapped[str | None] = mapped_column(String(40))
    kerf_mm: Mapped[float] = mapped_column(Float)
    sheet_count: Mapped[int] = mapped_column(Integer)
    part_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default=JobStatus.DRAFT)
    analysis: Mapped[dict[str, Any]] = mapped_column(JSON)
    """The full engine result, geometry included, as returned by the analysis API."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(120))

    pieces: Mapped[list[Piece]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Piece.position"
    )


class Piece(Base):
    __tablename__ = "pieces"
    __table_args__ = (Index("ix_pieces_workshop_status", "workshop_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(12), unique=True, default=new_piece_code)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"), index=True)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"))
    position: Mapped[int] = mapped_column(Integer)
    """Order within the job, so lists stay stable."""
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=PieceStatus.DRAFT)
    sheet_index: Mapped[int] = mapped_column(Integer)
    label: Mapped[str] = mapped_column(String(20))
    """Engine reference within the job, e.g. S1-R2 or S1-SCRAP."""
    material_code: Mapped[str | None] = mapped_column(String(40))
    thickness_mm: Mapped[float | None] = mapped_column(Float)
    x_mm: Mapped[float | None] = mapped_column(Float)
    y_mm: Mapped[float | None] = mapped_column(Float)
    width_mm: Mapped[float | None] = mapped_column(Float)
    height_mm: Mapped[float | None] = mapped_column(Float)
    area_m2: Mapped[float] = mapped_column(Float)
    weight_est_kg: Mapped[float | None] = mapped_column(Float)
    weight_actual_kg: Mapped[float | None] = mapped_column(Float)
    """Set by the manager after weighing; overrides the estimate."""
    condition_note: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(80))
    review_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    job: Mapped[Job] = relationship(back_populates="pieces")
    events: Mapped[list[PieceEvent]] = relationship(
        back_populates="piece", cascade="all, delete-orphan", order_by="PieceEvent.at"
    )

    @property
    def weight_kg(self) -> float | None:
        return self.weight_actual_kg if self.weight_actual_kg is not None else self.weight_est_kg


class PieceEvent(Base):
    """Append-only history: who changed what, and when."""

    __tablename__ = "piece_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    piece_id: Mapped[str] = mapped_column(ForeignKey("pieces.id"), index=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor: Mapped[str] = mapped_column(String(120))
    action: Mapped[str] = mapped_column(String(40))
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    piece: Mapped[Piece] = relationship(back_populates="events")
