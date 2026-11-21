"""Sample jobs for demos: a catalogue and the files themselves."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/v1/samples", tags=["samples"])


def samples_dir() -> Path:
    configured = os.getenv("REVALO_SAMPLES_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[4] / "samples"


@lru_cache(maxsize=1)
def _catalog() -> list[dict[str, Any]]:
    root = samples_dir()
    path = root / "catalog.json"
    if not path.is_file():
        return []
    entries = json.loads(path.read_text(encoding="utf-8"))["samples"]
    out = []
    for entry in entries:
        file = root / entry["file"]
        if file.is_file():
            out.append(
                {**entry, "id": entry["file"].replace("/", "__"), "size": file.stat().st_size}
            )
    return out


@router.get("")
def list_samples() -> dict[str, Any]:
    return {
        "samples": [
            {
                "id": s["id"],
                "name": Path(s["file"]).name,
                "collection": s["file"].split("/", 1)[0],
                "title": s["title"],
                "process": s["process"],
                "licence": s["licence"],
                "source": s["source"],
                "size": s["size"],
            }
            for s in _catalog()
        ]
    }


@router.get("/{sample_id}")
def get_sample(sample_id: str) -> FileResponse:
    # Only files listed in the catalogue can be served, so ids cannot reach other paths.
    entry = next((s for s in _catalog() if s["id"] == sample_id), None)
    if entry is None:
        raise HTTPException(404, "Unknown sample.")
    path = samples_dir() / entry["file"]
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")
