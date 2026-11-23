"""Coming jobs kept in mind, so every new offcut is checked against them."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from revalo.api.deps import ManagerUser, manager_only
from revalo.api.fit import _typed_parts
from revalo.db.models import PlannedJob
from revalo.db.session import get_session
from revalo.engine.model import JobImportError
from revalo.engine.pipeline import MAX_FILE_BYTES
from revalo.services.fit import FitError, FitRequest, check_stock, parts_from_file, resolve
from revalo.services.jobs import default_workshop
from revalo.services.opportunities import (
    PlannedJobError,
    active_planned,
    close_planned,
    planned_parts,
    planned_to_dict,
    save_planned,
)
from revalo.services.prices import price_book
from revalo.services.sourcing import with_offers

router = APIRouter(prefix="/v1/planned-jobs", tags=["stock"], dependencies=[manager_only])
DbSession = Annotated[Session, Depends(get_session)]


def _planned(session: Session, planned_id: str) -> PlannedJob:
    planned = session.get(PlannedJob, planned_id)
    if planned is None or not planned.active:
        raise HTTPException(404, "No such planned job.")
    return planned


@router.get("")
def list_planned(session: DbSession) -> dict[str, Any]:
    return {"planned": [planned_to_dict(session, p) for p in active_planned(session)]}


@router.post("", status_code=201)
def keep_in_mind(
    user: ManagerUser,
    session: DbSession,
    name: Annotated[str, Form(min_length=1, max_length=160)],
    file: Annotated[UploadFile | None, File()] = None,
    parts: Annotated[str | None, Form()] = None,
    material: Annotated[str | None, Form()] = None,
    thickness_mm: Annotated[float | None, Form(gt=0, le=200)] = None,
    kerf_mm: Annotated[float | None, Form(ge=0, le=20)] = None,
) -> dict[str, Any]:
    """Same inputs as "Check before cutting", plus a name."""
    data = file.file.read(MAX_FILE_BYTES + 1) if file else None
    if data is not None and len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File is larger than 25 MB.")
    filename = (file.filename if file else None) or ""
    try:
        found = list(_typed_parts(parts))
        meta = ""
        if data:
            from_file, meta = parts_from_file(data, filename)
            found.extend(from_file)
        request = FitRequest(material or None, thickness_mm, kerf_mm)
        code, thickness, kerf = resolve(request, filename, meta)
        planned = save_planned(
            session, default_workshop(session).id, name, code, thickness, kerf, found, user.name
        )
    except (FitError, PlannedJobError, JobImportError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return planned_to_dict(session, planned)


@router.post("/{planned_id}/check")
def check_planned(planned_id: str, session: DbSession) -> dict[str, Any]:
    planned = _planned(session, planned_id)
    shop = default_workshop(session)
    book = price_book(session, shop.id)
    try:
        result = check_stock(
            session,
            None,
            "",
            planned_parts(planned),
            FitRequest(planned.material_code, planned.thickness_mm, planned.kerf_mm),
            book,
        )
    except FitError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {**with_offers(session, result, book), "planned": planned_to_dict(session, planned)}


@router.delete("/{planned_id}", status_code=204)
def done(planned_id: str, session: DbSession) -> None:
    close_planned(session, _planned(session, planned_id))
