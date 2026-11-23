"""Jobs: run the engine on an upload and keep the result as draft leftover records."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import Job, JobStatus, Machine, Piece, PieceEvent, PieceKind, Workshop
from revalo.engine.geo import canonical
from revalo.engine.pipeline import AnalysisOptions, analyze
from revalo.services.decisions import decide_piece
from revalo.services.prices import EffectivePrice
from revalo.settings import get_settings
from revalo.storage import FileStorage

MAX_RUNS = 50
# A copy of a program still in review and this recent is most likely sent twice by mistake.
MISTAKE_WINDOW = timedelta(hours=2)


def earlier_runs(session: Session, digest: str) -> list[Job]:
    """Jobs recorded from exactly the same file, newest first."""
    return list(
        session.scalars(
            select(Job).where(Job.file_sha256 == digest).order_by(Job.created_at.desc())
        )
    )


def likely_answer(job: Job, now: datetime | None = None) -> str:
    """'same' when the earlier copy looks like a double send, 'new' for a real repeat run."""
    created = job.created_at if job.created_at.tzinfo else job.created_at.replace(tzinfo=UTC)
    recent = (now or datetime.now(UTC)) - created < MISTAKE_WINDOW
    return "same" if job.status == JobStatus.DRAFT and recent else "new"


def default_workshop(session: Session) -> Workshop:
    """The pilot runs one workshop per deployment; accounts come later."""
    # The pilot starts in Ben Arous (Market Playbook, section 4).
    governorate = canonical(os.getenv("REVALO_WORKSHOP_GOVERNORATE", "Ben Arous"))
    shop = session.scalars(select(Workshop).order_by(Workshop.created_at)).first()
    if shop is None:
        shop = Workshop(
            name=os.getenv("REVALO_WORKSHOP_NAME", "Pilot workshop"), governorate=governorate
        )
        session.add(shop)
        session.flush()
    elif shop.governorate is None and governorate:
        # Distances to buyers need a location; fill it in for workshops created without one.
        shop.governorate = governorate
        session.commit()
    return shop


def create_job(
    session: Session,
    storage: FileStorage,
    data: bytes,
    filename: str,
    options: AnalysisOptions,
    actor: str,
    machine: Machine | None = None,
    runs: int = 1,
    repeat_of: Job | None = None,
) -> Job:
    if not 1 <= runs <= MAX_RUNS:
        raise ValueError(f"Between 1 and {MAX_RUNS} sheets per upload.")
    result = analyze(data, filename, options)
    body = result.to_dict(include_geometry=True)
    key, digest = storage.put(data, filename)
    shop = default_workshop(session)

    job = Job(
        workshop_id=shop.id,
        machine_id=machine.id if machine else None,
        file_name=filename,
        file_format=body["source"]["format"],
        file_sha256=digest,
        file_key=key,
        material_code=body["material"]["code"] if body["material"] else None,
        thickness_mm=body["thickness_mm"],
        process=body["process"],
        kerf_mm=body["kerf_mm"],
        sheet_count=len(body["sheets"]) * runs,
        part_count=sum(s["part_count"] for s in body["sheets"]) * runs,
        analysis=body,
        created_by=actor,
        runs=runs,
        repeat_of_id=repeat_of.id if repeat_of else None,
    )

    position = 0
    # Every run of the program is a real sheet that leaves its own offcuts.
    for run, sheet in ((r, s) for r in range(runs) for s in body["sheets"]):
        for remnant in sheet["remnants"]:
            job.pieces.append(
                Piece(
                    workshop_id=shop.id,
                    position=position,
                    kind=PieceKind.REMNANT,
                    sheet_index=sheet["index"],
                    run_index=run,
                    label=remnant["id"],
                    material_code=job.material_code,
                    thickness_mm=job.thickness_mm,
                    x_mm=remnant["x"],
                    y_mm=remnant["y"],
                    width_mm=remnant["width"],
                    height_mm=remnant["height"],
                    area_m2=remnant["area_m2"],
                    weight_est_kg=remnant["weight_kg"],
                )
            )
            position += 1
        if sheet["scrap_area_m2"] > 0:
            # The skeleton of one sheet goes to a recycler as one lot, sold by weight.
            job.pieces.append(
                Piece(
                    workshop_id=shop.id,
                    position=position,
                    kind=PieceKind.SCRAP,
                    sheet_index=sheet["index"],
                    run_index=run,
                    label=f"S{sheet['index'] + 1}-SCRAP",
                    material_code=job.material_code,
                    thickness_mm=job.thickness_mm,
                    area_m2=sheet["scrap_area_m2"],
                    weight_est_kg=sheet["scrap_weight_kg"],
                )
            )
            position += 1

    for piece in job.pieces:
        piece.events.append(PieceEvent(actor=actor, action="created", data={"source": filename}))

    session.add(job)
    session.commit()
    return job


def piece_to_dict(piece: Piece, book: dict[str, EffectivePrice]) -> dict[str, Any]:
    return {
        "id": piece.id,
        "code": piece.code,
        "job_id": piece.job_id,
        "kind": piece.kind,
        "status": piece.status,
        "label": piece.label,
        "sheet_index": piece.sheet_index,
        "run_index": piece.run_index,
        "material_code": piece.material_code,
        "thickness_mm": piece.thickness_mm,
        "x_mm": piece.x_mm,
        "y_mm": piece.y_mm,
        "width_mm": piece.width_mm,
        "height_mm": piece.height_mm,
        "area_m2": piece.area_m2,
        "weight_est_kg": piece.weight_est_kg,
        "weight_actual_kg": piece.weight_actual_kg,
        "weight_kg": piece.weight_kg,
        "condition_note": piece.condition_note,
        "location": piece.location,
        "review_date": piece.review_date.isoformat() if piece.review_date else None,
        "due_for_review": (
            piece.status == "in_stock"
            and piece.review_date is not None
            and piece.review_date <= date.today()
        ),
        "label_url": f"{get_settings().public_url}/p/{piece.code}",
        "updated_at": piece.updated_at.isoformat(),
        "decision": decide_piece(piece, book).to_dict(),
        "listing": None
        if piece.listing is None
        else {
            "id": piece.listing.id,
            "status": piece.listing.status,
            "price_tnd": piece.listing.price_tnd,
        },
    }


def recommended_value(pieces: list[Piece], book: dict[str, EffectivePrice]) -> dict[str, Any]:
    """What the pieces are worth if each follows its recommendation."""
    value = 0.0
    co2 = 0.0
    priced = 0
    for piece in pieces:
        decision = decide_piece(piece, book)
        if decision.recommended is None:
            continue
        option = decision.option(decision.recommended)
        if option.value_tnd is not None:
            value += option.value_tnd
            priced += 1
        co2 += option.co2_kg or 0.0
    return {
        "value_tnd": round(value, 2),
        "co2_kg": round(co2, 1),
        "priced_pieces": priced,
        "pieces": len(pieces),
    }


def job_summary(job: Job, book: dict[str, EffectivePrice]) -> dict[str, Any]:
    kept = [p for p in job.pieces if p.status != "rejected"]
    remnants = [p for p in kept if p.kind == PieceKind.REMNANT]
    scrap = [p for p in kept if p.kind == PieceKind.SCRAP]

    def total(pieces: list[Piece]) -> float | None:
        weights = [p.weight_kg for p in pieces]
        return None if any(w is None for w in weights) else round(sum(weights), 3)

    return {
        "id": job.id,
        "file_name": job.file_name,
        "file_format": job.file_format,
        "material_code": job.material_code,
        "thickness_mm": job.thickness_mm,
        "process": job.process,
        "machine_id": job.machine_id,
        "status": job.status,
        "sheet_count": job.sheet_count,
        "part_count": job.part_count,
        "remnant_count": len(remnants),
        "remnant_weight_kg": total(remnants),
        "scrap_weight_kg": total(scrap),
        "recovered": recommended_value(kept, book),
        "created_at": job.created_at.isoformat(),
        "approved_at": job.approved_at.isoformat() if job.approved_at else None,
        "approved_by": job.approved_by,
        "created_by": job.created_by,
        "runs": job.runs,
        "repeat_of_id": job.repeat_of_id,
    }


def job_detail(job: Job, book: dict[str, EffectivePrice]) -> dict[str, Any]:
    return {
        **job_summary(job, book),
        "analysis": job.analysis,
        "pieces": [piece_to_dict(p, book) for p in job.pieces],
    }
