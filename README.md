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

## The workflow

1. **Analyze.** Drop a job file, or pick a sample. The sheet appears in 3D with
   every remnant lifted out of it, its size and weight attached.
2. **Save and review.** The manager checks each draft record against the real
   sheet: enter a weighed value, trim a damaged edge, note the condition, or
   reject a piece. A remnant can shrink but never grow beyond the cut file.
3. **Approve.** Records go into stock with a review date, and every change is
   kept in the piece's history.
4. **Label.** Print QR labels (50 x 30 mm thermal or A4 sticker sheets). A
   scan opens the piece's page on any phone.
5. **Stock.** See what is on the racks by material, what is reusable, what is
   scrap for recyclers, and what is due for review.

## Repository layout

```
backend/
  src/revalo/engine/     importers, leftover geometry, material library
  src/revalo/api/        HTTP API (FastAPI)
  src/revalo/services/   jobs, record review, stock
  src/revalo/db/         models and session (SQLAlchemy)
  migrations/            database migrations (Alembic)
  src/revalo/cli.py      command line tool
  scripts/               sample generator
  tests/                 automated tests
frontend/                web app (React, TypeScript, Three.js)
samples/                 sample jobs and their expected results
```

## Development

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 22+ and pnpm.

Backend:

```bash
cd backend
uv sync
uv run pytest
uv run uvicorn revalo.api.main:app --reload   # http://localhost:8000/docs
```

The API creates a SQLite database in `backend/var/` and applies migrations on
start. Set `REVALO_DATABASE_URL` for PostgreSQL in production, and
`REVALO_AUTO_MIGRATE=0` to run `alembic upgrade head` as a deploy step instead.

Frontend:

```bash
cd frontend
pnpm install
pnpm dev   # http://localhost:5173, proxies /api to the backend
```

Analyze a file from the command line:

```bash
uv run revalo analyze ../samples/synthetic/laser_S235_3mm_3000x1500.dxf --svg preview.svg
```

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `REVALO_DATABASE_URL` | SQLite in `backend/var/` | Database connection |
| `REVALO_STORAGE_DIR` | `backend/var/files` | Where original job files are kept |
| `REVALO_PUBLIC_URL` | `http://localhost:5173` | Base URL printed in QR labels |
| `REVALO_REVIEW_DAYS` | `30` | Days in stock before a piece is reviewed |
| `REVALO_WORKSHOP_NAME` | `Pilot workshop` | Name of the workshop this deployment serves |
| `REVALO_CORS_ORIGINS` | `http://localhost:5173` | Allowed web origins |
| `REVALO_AUTO_MIGRATE` | `1` | Apply migrations when the API starts |
