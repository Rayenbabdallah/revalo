"""Jobs API: upload a job, list jobs, open one with its draft records."""

from __future__ import annotations

import hashlib
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.api.deps import ManagerUser, SignedIn, signed_in
from revalo.api.forms import analysis_options
from revalo.db.models import Job, Machine
from revalo.db.session import get_session
from revalo.engine.model import JobImportError
from revalo.engine.pipeline import MAX_FILE_BYTES, AnalysisOptions
from revalo.i18n import tr
from revalo.services.jobs import (
    MAX_RUNS,
    create_job,
    default_workshop,
    earlier_runs,
    job_detail,
    job_summary,
    likely_answer,
)
from revalo.services.machines import apply_machine
from revalo.services.opportunities import opportunities_for_job
from revalo.services.pieces import ReviewError, copy_corrections
from revalo.services.prices import price_book
from revalo.storage import FileStorage, get_storage

router = APIRouter(prefix="/v1/jobs", tags=["jobs"], dependencies=[signed_in])

DbSession = Annotated[Session, Depends(get_session)]
Storage = Annotated[FileStorage, Depends(get_storage)]


@router.post("", status_code=201)
def upload_job(
    user: SignedIn,
    session: DbSession,
    storage: Storage,
    file: Annotated[UploadFile, File()],
    options: Annotated[AnalysisOptions, Depends(analysis_options)],
    machine_id: Annotated[str | None, Form()] = None,
    runs: Annotated[int, Form(ge=1, le=MAX_RUNS)] = 1,
    repeat: Annotated[str | None, Form(pattern="^new$")] = None,
) -> dict[str, Any]:
    # Sync endpoint: FastAPI runs it in a worker thread, so the engine never blocks the loop.
    data = file.file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File is larger than 25 MB.")
    machine = None
    if machine_id:
        machine = session.get(Machine, machine_id)
        if machine is None or not machine.active:
            raise HTTPException(422, "Unknown machine.")
        options = apply_machine(options, machine)
    # The same program sent again: a mistake, or the nest cut again? Ask, never guess.
    earlier = earlier_runs(session, hashlib.sha256(data).hexdigest())
    if earlier and repeat != "new":
        raise HTTPException(
            409,
            {
                "code": "repeat_run",
                "message": tr("This program was already recorded. Did you cut it again?"),
                "suggest": likely_answer(earlier[0]),
                "jobs": [
                    {
                        "id": j.id,
                        "file_name": j.file_name,
                        "status": j.status,
                        "created_at": j.created_at.isoformat(),
                        "created_by": j.created_by,
                        "runs": j.runs,
                    }
                    for j in earlier[:5]
                ],
            },
        )
    try:
        job = create_job(
            session,
            storage,
            data,
            file.filename or "upload",
            options,
            user.name,
            machine,
            runs=runs,
            repeat_of=earlier[0] if earlier else None,
        )
    except JobImportError as exc:
        raise HTTPException(422, str(exc)) from exc
    return job_detail(job, price_book(session, job.workshop_id))


@router.get("")
def list_jobs(session: DbSession, limit: int = 50) -> dict[str, Any]:
    jobs = session.scalars(select(Job).order_by(Job.created_at.desc()).limit(min(limit, 200)))
    book = price_book(session, default_workshop(session).id)
    return {"jobs": [job_summary(j, book) for j in jobs]}


@router.get("/{job_id}")
def get_job(job_id: str, session: DbSession) -> dict[str, Any]:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    return job_detail(job, price_book(session, job.workshop_id))


@router.post("/{job_id}/copy-corrections")
def copy_last_run(job_id: str, user: ManagerUser, session: DbSession) -> dict[str, Any]:
    """A repeat run takes the earlier run's corrections in one step."""
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    try:
        changed = copy_corrections(session, job, user.name)
    except ReviewError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {**job_detail(job, price_book(session, job.workshop_id)), "copied": changed}


@router.get("/{job_id}/opportunities")
def opportunities(job_id: str, user: ManagerUser, session: DbSession) -> dict[str, Any]:
    """Planned jobs and waiting buyers that the job's new offcuts already match."""
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Job not found.")
    return opportunities_for_job(session, job, price_book(session, job.workshop_id))
