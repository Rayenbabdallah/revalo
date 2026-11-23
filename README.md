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
5. **Decide.** Every record is valued three ways in TND and CO2: reuse it
   (new material you do not buy), sell it (at a share of the new price, minus
   commission), or recycle it (scrap price by weight). Revalo recommends one and
   says why. A remnant is first kept for reuse; once its review date passes it
   should be sold, and after a second period recycled, so racks do not fill up.
6. **Stock.** See what is on the racks by material, its recoverable value, the
   next step for each piece, and what is due for review.
7. **Sell.** List a piece at its suggested price. Buyers (artisans, small
   shops, recyclers) post what they need on the public page at `/buy`; each
   listing is matched with them by material, thickness, size, price and
   distance between governorates, with the reasons shown. One tap opens
   WhatsApp with a ready message; reserve, mark sold, or withdraw, and the 5%
   commission is recorded on each sale. Recyclers are offered scrap lots, and
   reusable remnants only as a fallback.
8. **Recycle.** Scrap lots and pieces past their time are grouped by material
   for the recycler who pays the most nearby. Book a pickup on WhatsApp, set
   the date, and record the weighed ticket when the truck leaves.
9. **Check before cutting.** Give Revalo the next job (a drawing or part
   sizes): it places the parts on remnants already in stock, so a new sheet is
   opened only for what does not fit.
10. **Report.** One printable page for the owner each month: what leftovers
    brought back in TND against the Revalo plan, kg kept out of the bin and CO2
    avoided. Stock exports to Excel (CSV).

Operators work at the machine: they pick a machine preset and the file it just
cut, nothing to type. The alerts bell lists what needs a manager now: jobs to
review, pieces past their date, buyer matches, scrap ready for a recycler.

## Accounts and roles

Each person signs in with their own email and password; every record keeps
the name of who made or changed it.

| Role | Can |
|---|---|
| Operator | upload jobs, measure and move pieces, take remnants for a new job |
| Manager | also approve records, sell, book pickups, set prices and machines, see the report |
| Owner | also add people, change roles, reset passwords, remove access |

On a fresh install the first screen creates the workshop and its owner. From a
terminal: `uv run revalo users add --email you@example.tn --name You --role owner`.
Passwords are hashed with scrypt; a sign-in is an HttpOnly cookie whose token is
stored only as a hash, and repeated wrong passwords are slowed down. The public
buyer page (`/buy`) needs no account.

## Languages

The interface is in English, French and Arabic (right to left), switched from
the account menu, the sign-in page or the buyer page. Text the server writes
(decision reasons, alerts, errors) follows the same choice. Translations live in
`frontend/src/lib/locales` and `backend/src/revalo/i18n.py`;
`pnpm check:i18n` fails when a text has no French or Arabic version.

Prices live in a per-workshop price book. Defaults ship only where a source
exists (mild steel and MDF, from the financial model); every other material
waits for the workshop's own quotes rather than an invented number.

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
frontend/                web app (React, TypeScript, Three.js), brand assets in public/brand
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

A demo workshop (three accounts, machines, four jobs, buyers, a sale and a
recycler pickup) for presentations, on an empty database only:

```bash
REVALO_DEMO_PASSWORD=revalo-demo-2026 uv run revalo demo
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
| `REVALO_WORKSHOP_GOVERNORATE` | `Ben Arous` | Workshop location, used for distances to buyers |
| `REVALO_WORKSHOP_PHONE` | none | WhatsApp number buyers reach from the public page |
| `REVALO_PLAN_TND` | `120` | Monthly plan price in the owner report |
| `REVALO_SECURE_COOKIES` | auto | `1` forces Secure cookies (set automatically behind HTTPS) |
| `REVALO_DEMO_PASSWORD` | none | Password of the demo accounts created by `revalo demo` |

## Deployment

`compose.yaml` runs the whole product on one server: PostgreSQL, the API, and
the web app behind Caddy, which serves HTTPS for your domain automatically and
sends `/api` to the API.

```bash
cp .env.example .env    # set POSTGRES_PASSWORD, SITE_ADDRESS (your domain) and REVALO_PUBLIC_URL
docker compose up -d --build
```

Point the domain's DNS at the server first. Job files are kept in the `files`
volume and the database in `db`; back both up. CI builds both images and starts
the stack on every change, and runs the migrations and the demo on PostgreSQL.
