"""Pieces that were on the racks before Revalo: entered by hand or from a CSV list.

They go straight into stock (the manager is the one checking them), grouped
under one "existing stock" intake so labels can be printed for all of them.
Every row is first compared with what is already in stock, so the same rack
is not entered twice.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import Job, JobStatus, Piece, PieceEvent, PieceKind, PieceStatus, utcnow
from revalo.engine.materials import infer_material, materials
from revalo.i18n import tr
from revalo.services.jobs import default_workshop
from revalo.settings import get_settings

INTAKE_FORMAT = "manual"
MAX_ROWS = 500
MAX_QUANTITY = 200
SAME_SIZE_MM = 2.0


class IntakeError(Exception):
    pass


@dataclass(frozen=True)
class IntakeRow:
    material: str
    thickness_mm: float
    width_mm: float | None = None
    height_mm: float | None = None
    quantity: int = 1
    location: str | None = None
    kind: str = PieceKind.REMNANT
    weight_kg: float | None = None
    """Needed for scrap lots, which have no rectangle; optional for remnants."""


def resolve_material(text: str) -> str | None:
    """A code, a name in English or French, or a workshop alias ("inox", "S235")."""
    text = text.strip()
    if text.lower() in materials():
        return text.lower()
    for mat in materials().values():
        if text.lower() in (mat.name_en.lower(), mat.name_fr.lower()):
            return mat.code
    return infer_material(text)


def _check(row: IntakeRow, index: int) -> str:
    code = resolve_material(row.material)
    n = index + 1
    if code is None:
        raise IntakeError(tr("Row {n}: unknown material {name}.", n=n, name=row.material))
    if not 0 < row.thickness_mm <= 300:
        raise IntakeError(tr("Row {n}: thickness must be between 0 and 300 mm.", n=n))
    if not 1 <= row.quantity <= MAX_QUANTITY:
        raise IntakeError(
            tr("Row {n}: quantity must be between 1 and {max}.", n=n, max=MAX_QUANTITY)
        )
    if row.kind == PieceKind.REMNANT:
        sides = (row.width_mm or 0, row.height_mm or 0)
        if not all(0 < side <= 20_000 for side in sides):
            raise IntakeError(tr("Row {n}: a remnant needs a width and a height in mm.", n=n))
    elif row.kind == PieceKind.SCRAP:
        if not row.weight_kg or row.weight_kg <= 0:
            raise IntakeError(tr("Row {n}: a scrap lot needs its weight in kg.", n=n))
    else:
        raise IntakeError(tr("Row {n}: kind must be remnant or scrap.", n=n))
    return code


def _similar_in_stock(session: Session, code: str, row: IntakeRow) -> list[Piece]:
    """Pieces already recorded with the same material, thickness and size (either way round)."""
    candidates = session.scalars(
        select(Piece).where(
            Piece.status == PieceStatus.IN_STOCK,
            Piece.material_code == code,
            Piece.kind == row.kind,
        )
    )
    found = []
    for p in candidates:
        if p.thickness_mm is None or abs(p.thickness_mm - row.thickness_mm) > 0.05:
            continue
        if row.kind == PieceKind.REMNANT:
            w, h = row.width_mm or 0, row.height_mm or 0
            pw, ph = p.width_mm or 0, p.height_mm or 0
            same = (abs(pw - w) <= SAME_SIZE_MM and abs(ph - h) <= SAME_SIZE_MM) or (
                abs(pw - h) <= SAME_SIZE_MM and abs(ph - w) <= SAME_SIZE_MM
            )
            if not same:
                continue
        found.append(p)
    return found


def check_rows(session: Session, rows: list[IntakeRow]) -> list[dict[str, Any]]:
    """What each row would add, and what similar pieces are already in stock."""
    if not rows:
        raise IntakeError(tr("Add at least one piece."))
    if len(rows) > MAX_ROWS:
        raise IntakeError(tr("At most {max} rows at a time.", max=MAX_ROWS))
    out = []
    for i, row in enumerate(rows):
        code = _check(row, i)
        similar = _similar_in_stock(session, code, row)
        out.append(
            {
                "row": i,
                "material_code": code,
                "similar_in_stock": len(similar),
                "similar": [{"code": p.code, "location": p.location} for p in similar[:5]],
            }
        )
    return out


def _weight(code: str, row: IntakeRow) -> float | None:
    if row.weight_kg:
        return row.weight_kg
    mat = materials()[code]
    return round(mat.weight_kg((row.width_mm or 0) * (row.height_mm or 0), row.thickness_mm), 3)


def add_existing(session: Session, rows: list[IntakeRow], name: str | None, actor: str) -> Job:
    """Record pieces already on the racks, straight into stock."""
    checks = check_rows(session, rows)
    shop = default_workshop(session)
    today = date.today()
    stamp = secrets.token_hex(16)
    job = Job(
        workshop_id=shop.id,
        file_name=(name or "").strip()[:200] or f"Existing stock {today.isoformat()}",
        file_format=INTAKE_FORMAT,
        # No file: a unique fingerprint so an intake is never taken for a repeat run.
        file_sha256=hashlib.sha256(stamp.encode()).hexdigest(),
        file_key="",
        material_code=None,
        thickness_mm=None,
        process=None,
        kerf_mm=0,
        sheet_count=0,
        part_count=0,
        analysis={"sheets": [], "source": {"format": INTAKE_FORMAT}},
        status=JobStatus.APPROVED,
        approved_at=utcnow(),
        approved_by=actor,
        created_by=actor,
    )
    review = today + timedelta(days=get_settings().review_days)
    position = 0
    for row, check in zip(rows, checks, strict=True):
        code = check["material_code"]
        for _ in range(row.quantity):
            remnant = row.kind == PieceKind.REMNANT
            area = (row.width_mm or 0) * (row.height_mm or 0) / 1e6 if remnant else 0.0
            piece = Piece(
                workshop_id=shop.id,
                position=position,
                kind=row.kind,
                status=PieceStatus.IN_STOCK,
                sheet_index=0,
                label=f"E{position + 1}",
                material_code=code,
                thickness_mm=row.thickness_mm,
                width_mm=row.width_mm if remnant else None,
                height_mm=row.height_mm if remnant else None,
                area_m2=round(area, 4),
                weight_est_kg=_weight(code, row),
                location=(row.location or "").strip()[:80] or None,
                review_date=review,
            )
            piece.events.append(
                PieceEvent(actor=actor, action="created", data={"source": "existing stock"})
            )
            piece.events.append(
                PieceEvent(actor=actor, action="approved", data={"review_date": review.isoformat()})
            )
            job.pieces.append(piece)
            position += 1
    session.add(job)
    session.commit()
    return job
