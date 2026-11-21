"""Machine presets API."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from revalo.api.deps import manager_only, signed_in
from revalo.db.models import Machine
from revalo.db.session import get_session
from revalo.services.jobs import default_workshop
from revalo.services.machines import (
    MachineError,
    MachineInput,
    list_machines,
    machine_to_dict,
    save_machine,
)

router = APIRouter(prefix="/v1/machines", tags=["machines"], dependencies=[signed_in])
DbSession = Annotated[Session, Depends(get_session)]


class MachineBody(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    process: str
    material_code: str | None = None
    thickness_mm: float | None = Field(None, gt=0, le=200)
    kerf_mm: float | None = Field(None, ge=0, le=20)
    sheet_width_mm: float | None = Field(None, gt=0, le=20_000)
    sheet_height_mm: float | None = Field(None, gt=0, le=20_000)
    min_side_mm: float | None = Field(None, gt=0, le=5_000)


class MachinePatch(MachineBody):
    active: bool = True


@router.get("")
def get_machines(session: DbSession, include_inactive: bool = False) -> dict[str, Any]:
    shop = default_workshop(session)
    machines = list_machines(session, shop.id, include_inactive)
    return {"machines": [machine_to_dict(m) for m in machines]}


@router.post("", status_code=201, dependencies=[manager_only])
def create_machine(body: MachineBody, session: DbSession) -> dict[str, Any]:
    shop = default_workshop(session)
    try:
        machine = save_machine(session, shop.id, MachineInput(**body.model_dump()))
    except MachineError as exc:
        raise HTTPException(422, str(exc)) from exc
    return machine_to_dict(machine)


@router.put("/{machine_id}", dependencies=[manager_only])
def update_machine(machine_id: str, body: MachinePatch, session: DbSession) -> dict[str, Any]:
    machine = session.get(Machine, machine_id)
    if machine is None:
        raise HTTPException(404, "Machine not found.")
    machine.active = body.active
    try:
        save_machine(
            session,
            machine.workshop_id,
            MachineInput(**body.model_dump(exclude={"active"})),
            machine,
        )
    except MachineError as exc:
        raise HTTPException(422, str(exc)) from exc
    return machine_to_dict(machine)
