"""Form fields shared by every endpoint that analyzes an upload."""

from __future__ import annotations

from typing import Annotated

from fastapi import Form, HTTPException

from revalo.engine.materials import materials, processes
from revalo.engine.pipeline import AnalysisOptions


def analysis_options(
    material: Annotated[str | None, Form()] = None,
    thickness_mm: Annotated[float | None, Form(gt=0, le=200)] = None,
    kerf_mm: Annotated[float | None, Form(ge=0, le=20)] = None,
    process: Annotated[str | None, Form()] = None,
    sheet_width_mm: Annotated[float | None, Form(gt=0, le=20000)] = None,
    sheet_height_mm: Annotated[float | None, Form(gt=0, le=20000)] = None,
    min_side_mm: Annotated[float | None, Form(gt=0, le=5000)] = None,
    trim_mm: Annotated[float, Form(ge=0, le=100)] = 0.0,
    allow_rotation: Annotated[bool, Form()] = True,
) -> AnalysisOptions:
    if material and material not in materials():
        raise HTTPException(422, f"Unknown material code: {material}")
    if process and process not in processes():
        raise HTTPException(422, f"Unknown process: {process}")
    return AnalysisOptions(
        material_code=material or None,
        thickness_mm=thickness_mm,
        kerf_mm=kerf_mm,
        process=process or None,
        sheet_width_mm=sheet_width_mm,
        sheet_height_mm=sheet_height_mm,
        min_side_mm=min_side_mm,
        trim_mm=trim_mm,
        allow_rotation=allow_rotation,
    )
