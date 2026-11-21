"""Jobs API: upload a job, list jobs, open one with its draft records."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.api.deps import SignedIn, signed_in
from revalo.api.forms import analysis_options
from revalo.db.models import Job, Machine
from revalo.db.session import get_session
from revalo.engine.model import JobImportError
from revalo.engine.pipeline import MAX_FILE_BYTES, AnalysisOptions
from revalo.services.jobs import create_job, default_workshop, job_detail, job_summary
from revalo.services.machines import apply_machine
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
    try:
        job = create_job(
            session, storage, data, file.filename or "upload", options, user.name, machine
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
