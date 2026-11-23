"""Database models: workshops, jobs, leftover pieces and their history."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
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
    type_annotation_map = {dict[str, Any]: JSON, list[dict[str, Any]]: JSON}


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


class Machine(Base):
    """A cutting machine and its usual settings, so an upload needs no typing."""

    __tablename__ = "machines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    process: Mapped[str] = mapped_column(String(40))
    material_code: Mapped[str | None] = mapped_column(String(40))
    thickness_mm: Mapped[float | None] = mapped_column(Float)
    kerf_mm: Mapped[float | None] = mapped_column(Float)
    sheet_width_mm: Mapped[float | None] = mapped_column(Float)
    sheet_height_mm: Mapped[float | None] = mapped_column(Float)
    min_side_mm: Mapped[float | None] = mapped_column(Float)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"), index=True)
    machine_id: Mapped[str | None] = mapped_column(ForeignKey("machines.id"))
    """The machine the job was cut on, when the operator picked one."""
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
    created_by: Mapped[str | None] = mapped_column(String(120))
    runs: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    """How many sheets were cut with this program: each run leaves its own offcuts."""
    repeat_of_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id", name="fk_jobs_repeat_of_id_jobs")
    )
    """The earlier job with the same file, when this is the program cut again."""

    pieces: Mapped[list[Piece]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Piece.position"
    )
    workshop: Mapped[Workshop] = relationship()

    @property
    def workshop_governorate(self) -> str | None:
        return self.workshop.governorate if self.workshop else None


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
    run_index: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    """Which run of the program the piece came from (0 for the first sheet cut)."""
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
    weight_raw_kg: Mapped[float | None] = mapped_column(Float)
    """Area x thickness x density before calibration; the base for learning factors."""
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
    listing: Mapped[Listing | None] = relationship(back_populates="piece", uselist=False)

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


class PriceEntry(Base):
    """A workshop's own price for a material, overriding the library default."""

    __tablename__ = "price_entries"
    __table_args__ = (UniqueConstraint("workshop_id", "material_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"), index=True)
    material_code: Mapped[str] = mapped_column(String(40))
    new_tnd_per_kg: Mapped[float] = mapped_column(Float)
    scrap_tnd_per_kg: Mapped[float] = mapped_column(Float)
    resale_factor: Mapped[float] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(Text)
    """Where the numbers come from: a supplier quote, a scrap dealer, the owner."""
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    updated_by: Mapped[str] = mapped_column(String(120))


class ListingStatus(StrEnum):
    OPEN = "open"
    RESERVED = "reserved"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"


class BuyerKind(StrEnum):
    REUSE = "reuse"
    """Artisans, joineries and small shops that buy offcuts to use them."""
    RECYCLER = "recycler"
    """Scrap dealers and recyclers that buy by weight."""


class BuyerRequest(Base):
    """A standing need posted by a buyer: what they want, where, and at what price."""

    __tablename__ = "buyer_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(20), default=BuyerKind.REUSE)
    name: Mapped[str] = mapped_column(String(120))
    organization: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str] = mapped_column(String(32))
    """WhatsApp number, stored in international form (+216...)."""
    governorate: Mapped[str] = mapped_column(String(40))
    materials: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    """{"codes": [...]}; an empty list means any material."""
    thickness_min_mm: Mapped[float | None] = mapped_column(Float)
    thickness_max_mm: Mapped[float | None] = mapped_column(Float)
    min_length_mm: Mapped[float | None] = mapped_column(Float)
    min_width_mm: Mapped[float | None] = mapped_column(Float)
    max_price_tnd_per_kg: Mapped[float | None] = mapped_column(Float)
    offered_tnd_per_kg: Mapped[float | None] = mapped_column(Float)
    """Recyclers: what they pay per kg for sorted material."""
    min_lot_kg: Mapped[float | None] = mapped_column(Float)
    """Recyclers: the smallest lot worth a trip."""
    pickup_note: Mapped[str | None] = mapped_column(Text)
    """Recyclers: pickup terms, such as days and truck size."""
    note: Mapped[str | None] = mapped_column(Text)
    buys_lots: Mapped[bool] = mapped_column(default=False, server_default="0")
    """Takes a whole group of similar offcuts in one deal."""
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Listing(Base):
    """A piece offered on the marketplace, and the deal that follows."""

    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    piece_id: Mapped[str] = mapped_column(ForeignKey("pieces.id"), unique=True)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default=ListingStatus.OPEN, index=True)
    price_tnd: Mapped[float] = mapped_column(Float)
    buyer_request_id: Mapped[str | None] = mapped_column(ForeignKey("buyer_requests.id"))
    """The buyer the piece is reserved for or sold to."""
    sold_price_tnd: Mapped[float | None] = mapped_column(Float)
    fee_tnd: Mapped[float | None] = mapped_column(Float)
    """Revalo's commission on the completed sale."""
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    piece: Mapped[Piece] = relationship(back_populates="listing")
    buyer: Mapped[BuyerRequest | None] = relationship()


class PickupStatus(StrEnum):
    REQUESTED = "requested"
    SCHEDULED = "scheduled"
    COLLECTED = "collected"
    CANCELLED = "cancelled"


class Pickup(Base):
    """A recycler collecting a batch of scrap lots and old remnants."""

    __tablename__ = "pickups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"), index=True)
    recycler_id: Mapped[str] = mapped_column(ForeignKey("buyer_requests.id"))
    status: Mapped[str] = mapped_column(String(20), default=PickupStatus.REQUESTED)
    scheduled_for: Mapped[date | None] = mapped_column(Date)
    estimated_kg: Mapped[float] = mapped_column(Float)
    weighed_kg: Mapped[float | None] = mapped_column(Float)
    paid_tnd: Mapped[float | None] = mapped_column(Float)
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    recycler: Mapped[BuyerRequest] = relationship()
    items: Mapped[list[PickupItem]] = relationship(
        back_populates="pickup", cascade="all, delete-orphan"
    )


class PickupItem(Base):
    __tablename__ = "pickup_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    pickup_id: Mapped[str] = mapped_column(ForeignKey("pickups.id"), index=True)
    piece_id: Mapped[str] = mapped_column(ForeignKey("pieces.id"))

    pickup: Mapped[Pickup] = relationship(back_populates="items")
    piece: Mapped[Piece] = relationship()


class Role(StrEnum):
    """What a person may do. Each role includes everything the ones below it can."""

    OPERATOR = "operator"
    """Uploads jobs, measures and moves pieces, takes remnants for new jobs."""
    MANAGER = "manager"
    """Approves records, sells, books pickups, sets prices and machines."""
    OWNER = "owner"
    """Everything, plus who has an account."""

    @property
    def rank(self) -> int:
        return {"operator": 1, "manager": 2, "owner": 3}[self.value]


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"), index=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(20), default=Role.OPERATOR)
    password_hash: Mapped[str] = mapped_column(String(300))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    workshop: Mapped[Workshop] = relationship()


class AuthSession(Base):
    """A signed-in browser. Only a hash of the cookie token is stored."""

    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship()


class PlannedJob(Base):
    """A coming job kept in mind, so new offcuts are checked against its parts."""

    __tablename__ = "planned_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    material_code: Mapped[str] = mapped_column(String(40))
    thickness_mm: Mapped[float] = mapped_column(Float)
    kerf_mm: Mapped[float] = mapped_column(Float)
    parts: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    """[{label, length, width, rotatable}] as the fit engine reads them."""
    active: Mapped[bool] = mapped_column(default=True)
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def new_lot_code() -> str:
    return "LT-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(6))


class Lot(Base):
    """Similar offcuts sold together: one price, one buyer, one pickup."""

    __tablename__ = "lots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(12), unique=True, default=new_lot_code)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    material_code: Mapped[str] = mapped_column(String(40))
    thickness_mm: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default=ListingStatus.OPEN, index=True)
    price_tnd: Mapped[float] = mapped_column(Float)
    buyer_request_id: Mapped[str | None] = mapped_column(ForeignKey("buyer_requests.id"))
    sold_price_tnd: Mapped[float | None] = mapped_column(Float)
    fee_tnd: Mapped[float | None] = mapped_column(Float)
    split_from_id: Mapped[str | None] = mapped_column(
        ForeignKey("lots.id", name="fk_lots_split_from_id_lots")
    )
    """The lot this one was taken from, when a buyer took only part of it."""
    created_by: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list[LotItem]] = relationship(back_populates="lot", cascade="all, delete-orphan")
    buyer: Mapped[BuyerRequest | None] = relationship()

    @property
    def pieces(self) -> list[Piece]:
        return [item.piece for item in self.items]


class LotItem(Base):
    __tablename__ = "lot_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lot_id: Mapped[str] = mapped_column(ForeignKey("lots.id"), index=True)
    piece_id: Mapped[str] = mapped_column(ForeignKey("pieces.id"), index=True)

    lot: Mapped[Lot] = relationship(back_populates="items")
    piece: Mapped[Piece] = relationship()
