"""HTTP API for the leftover engine."""

from __future__ import annotations

import asyncio
import os
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from revalo import __version__
from revalo.engine.materials import materials, processes
from revalo.engine.model import JobImportError
from revalo.engine.pipeline import MAX_FILE_BYTES, AnalysisOptions, analyze
from revalo.engine.render import render_svg

ANALYSIS_TIMEOUT_S = float(os.getenv("REVALO_ANALYSIS_TIMEOUT_S", "30"))

app = FastAPI(
    title="Revalo API",
    version=__version__,
    description="Turns CNC job files into leftover records: remnants, scrap, weights.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip()
        for o in os.getenv("REVALO_CORS_ORIGINS", "http://localhost:5173").split(",")
        if o.strip()
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/v1/materials")
def list_materials() -> dict[str, Any]:
    return {
        "materials": [
            {
                "code": m.code,
                "name": {"en": m.name_en, "fr": m.name_fr},
                "family": m.family,
                "density_kg_m3": m.density_kg_m3,
            }
            for m in materials().values()
        ],
        "processes": [
            {"code": p.code, "kerf_mm": p.kerf_mm, "families": list(p.families)}
            for p in processes().values()
        ],
    }


@app.post("/v1/analyze")
async def analyze_file(
    file: Annotated[UploadFile, File(description="DXF nest, G-code program or CSV cut list")],
    material: Annotated[str | None, Form()] = None,
    thickness_mm: Annotated[float | None, Form(gt=0, le=200)] = None,
    kerf_mm: Annotated[float | None, Form(ge=0, le=20)] = None,
    process: Annotated[str | None, Form()] = None,
    sheet_width_mm: Annotated[float | None, Form(gt=0, le=20000)] = None,
    sheet_height_mm: Annotated[float | None, Form(gt=0, le=20000)] = None,
    min_side_mm: Annotated[float | None, Form(gt=0, le=5000)] = None,
    trim_mm: Annotated[float, Form(ge=0, le=100)] = 0.0,
    allow_rotation: Annotated[bool, Form()] = True,
    include_geometry: Annotated[bool, Query()] = True,
    include_svg: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    if material and material not in materials():
        raise HTTPException(422, f"Unknown material code: {material}")
    if process and process not in processes():
        raise HTTPException(422, f"Unknown process: {process}")

    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File is larger than 25 MB.")

    options = AnalysisOptions(
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
    try:
        result = await asyncio.wait_for(
            run_in_threadpool(analyze, data, file.filename or "upload", options),
            timeout=ANALYSIS_TIMEOUT_S,
        )
    except JobImportError as exc:
        raise HTTPException(422, str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(408, "The file took too long to analyze.") from exc

    body = result.to_dict(include_geometry=include_geometry)
    if include_svg:
        body["svg"] = render_svg(result)
    return body
