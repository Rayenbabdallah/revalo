"""HTTP API for the leftover engine."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware

from revalo import __version__
from revalo.api.forms import analysis_options
from revalo.api.jobs import router as jobs_router
from revalo.api.machines import router as machines_router
from revalo.api.market import router as market_router
from revalo.api.pieces import router as pieces_router
from revalo.api.prices import router as prices_router
from revalo.api.samples import router as samples_router
from revalo.db.migrate import upgrade
from revalo.engine.materials import materials, processes
from revalo.engine.model import JobImportError
from revalo.engine.pipeline import MAX_FILE_BYTES, AnalysisOptions, analyze
from revalo.engine.render import render_svg

ANALYSIS_TIMEOUT_S = float(os.getenv("REVALO_ANALYSIS_TIMEOUT_S", "30"))


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Keep the schema current on start. Production can set REVALO_AUTO_MIGRATE=0
    # and run migrations as a separate deploy step instead.
    if os.getenv("REVALO_AUTO_MIGRATE", "1") != "0":
        await run_in_threadpool(upgrade)
    yield


app = FastAPI(
    title="Revalo API",
    version=__version__,
    description="Turns CNC job files into leftover records: remnants, scrap, weights.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        o.strip()
        for o in os.getenv("REVALO_CORS_ORIGINS", "http://localhost:5173").split(",")
        if o.strip()
    ],
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["*"],
)
app.include_router(samples_router)
app.include_router(jobs_router)
app.include_router(pieces_router)
app.include_router(prices_router)
app.include_router(market_router)
app.include_router(machines_router)


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
    options: Annotated[AnalysisOptions, Depends(analysis_options)],
    include_geometry: Annotated[bool, Query()] = True,
    include_svg: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    """Analyze a file without saving anything: the try-before-you-sign-up path."""
    data = await file.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(413, "File is larger than 25 MB.")
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
