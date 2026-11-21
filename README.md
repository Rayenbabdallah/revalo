# Revalo

Revalo turns the job files that CNC and nesting software already produce into
leftover records: every reusable remnant with its size and weight, plus the
skeleton scrap that can only go to a recycler. Managers verify the records,
then reuse, sell or recycle each piece.

## What the engine reads

| Input | Typical source | Notes |
|---|---|---|
| DXF nest (`.dxf`) | CypNest, SigmaNEST, Lantek, Deepnest, AutoCAD | Blocks, arcs, splines, units, loose segments with small gaps, several sheets per file |
| G-code (`.nc`, `.gcode`, `.tap`, ...) | Routers (NcStudio, Mach3), plasma tables, lasers | Rebuilds cut paths; ignores rapids, shallow passes and torch-off moves |
| Cut list (`.csv`) | Panel saws, OptiCut exports, spreadsheets | Lays parts out with guillotine cuts; French or English headers |

For each sheet it returns the parts, the largest clean rectangular remnants
(shorter side at least 100 mm for metal, 150 mm for wood by default), the
scrap left between parts, and weights from the material library. Material,
thickness, process and sheet size are read from the file name or file content
when the user does not give them.

## Repository layout

```
backend/
  src/revalo/engine/   importers, leftover geometry, material library
  src/revalo/api/      HTTP API (FastAPI)
  src/revalo/cli.py    command line tool
  scripts/             sample generator
  tests/               automated tests
samples/               sample jobs and their expected results
```

## Development

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync
uv run pytest
```

Analyze a file from the command line:

```bash
uv run revalo analyze ../samples/synthetic/laser_S235_3mm_3000x1500.dxf --svg preview.svg
```

Run the API (docs at http://localhost:8000/docs):

```bash
uv run uvicorn revalo.api.main:app --reload
```

`POST /v1/analyze` takes the file as multipart form data, plus optional
`material`, `thickness_mm`, `kerf_mm`, `process`, `sheet_width_mm`,
`sheet_height_mm`, `min_side_mm`, `trim_mm` and `allow_rotation` fields.
