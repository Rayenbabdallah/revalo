"""Machine presets: the settings an operator would otherwise type for every job."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import Machine
from revalo.engine.materials import materials, processes
from revalo.engine.pipeline import AnalysisOptions


class MachineError(ValueError):
    pass


@dataclass
class MachineInput:
    name: str
    process: str
    material_code: str | None = None
    thickness_mm: float | None = None
    kerf_mm: float | None = None
    sheet_width_mm: float | None = None
    sheet_height_mm: float | None = None
    min_side_mm: float | None = None


def _validate(data: MachineInput) -> None:
    if not data.name.strip():
        raise MachineError("Give the machine a name.")
    if data.process not in processes():
        raise MachineError(f"Unknown process: {data.process}")
    if data.material_code and data.material_code not in materials():
        raise MachineError(f"Unknown material code: {data.material_code}")
    if (data.sheet_width_mm is None) != (data.sheet_height_mm is None):
        raise MachineError("Give both the sheet width and height, or neither.")


def save_machine(
    session: Session, workshop_id: str, data: MachineInput, machine: Machine | None = None
) -> Machine:
    _validate(data)
    machine = machine or Machine(workshop_id=workshop_id)
    machine.name = data.name.strip()
    machine.process = data.process
    machine.material_code = data.material_code or None
    machine.thickness_mm = data.thickness_mm
    machine.kerf_mm = data.kerf_mm
    machine.sheet_width_mm = data.sheet_width_mm
    machine.sheet_height_mm = data.sheet_height_mm
    machine.min_side_mm = data.min_side_mm
    session.add(machine)
    session.commit()
    return machine


def list_machines(session: Session, workshop_id: str, include_inactive: bool = False):
    query = select(Machine).where(Machine.workshop_id == workshop_id).order_by(Machine.created_at)
    if not include_inactive:
        query = query.where(Machine.active.is_(True))
    return list(session.scalars(query))


def apply_machine(options: AnalysisOptions, machine: Machine) -> AnalysisOptions:
    """Fill what the operator left blank from the machine's preset; typed values win."""

    def pick(given, preset):
        return given if given is not None else preset

    width, height = options.sheet_width_mm, options.sheet_height_mm
    if width is None and height is None:
        width, height = machine.sheet_width_mm, machine.sheet_height_mm
    return replace(
        options,
        process=options.process or machine.process,
        material_code=options.material_code or machine.material_code,
        thickness_mm=pick(options.thickness_mm, machine.thickness_mm),
        kerf_mm=pick(options.kerf_mm, machine.kerf_mm),
        sheet_width_mm=width,
        sheet_height_mm=height,
        min_side_mm=pick(options.min_side_mm, machine.min_side_mm),
    )


def machine_to_dict(machine: Machine) -> dict[str, Any]:
    mat = materials().get(machine.material_code or "")
    return {
        "id": machine.id,
        "name": machine.name,
        "process": machine.process,
        "material_code": machine.material_code,
        "material_name": {"en": mat.name_en, "fr": mat.name_fr} if mat else None,
        "thickness_mm": machine.thickness_mm,
        "kerf_mm": machine.kerf_mm,
        "sheet_width_mm": machine.sheet_width_mm,
        "sheet_height_mm": machine.sheet_height_mm,
        "min_side_mm": machine.min_side_mm,
        "active": machine.active,
    }
