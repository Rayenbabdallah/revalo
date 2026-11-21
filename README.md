# Revalo

Revalo turns the job files that CNC and nesting software already produce into
leftover records: every reusable remnant with its size and weight, plus the
skeleton scrap that can only go to a recycler. Managers verify the records,
then reuse, sell or recycle each piece.

## Repository layout

```
backend/    Python engine and API
  src/revalo/engine/   file importers and leftover geometry
  tests/               automated tests
```

## Development

Requirements: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
cd backend
uv sync
uv run pytest
```
