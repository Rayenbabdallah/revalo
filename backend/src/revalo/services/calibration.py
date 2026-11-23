"""Weights that learn from the scale.

The engine computes a piece's weight from area x thickness x nominal density.
Real sheets are often a few percent off their nominal thickness, so every time
someone weighs a piece, Revalo compares the scale with the calculation. Once a
material has enough weighings, new estimates are corrected by the median ratio.

The raw calculated weight is always kept, so factors are learned from raw
values only and never feed on themselves.
"""

from __future__ import annotations

from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import Piece
from revalo.engine.materials import materials

MIN_WEIGHINGS = 3
RECENT = 50
"""Only the latest weighings count: suppliers and sheet batches change."""
FACTOR_RANGE = (0.8, 1.25)
"""A ratio outside this is a typing or scale mistake, not a thickness tolerance."""


def factors(session: Session) -> dict[str, tuple[float, int]]:
    """Material code -> (correction factor, weighings it rests on)."""
    rows = session.execute(
        select(Piece.material_code, Piece.weight_actual_kg, Piece.weight_raw_kg)
        .where(
            Piece.weight_actual_kg.is_not(None),
            Piece.weight_raw_kg.is_not(None),
            Piece.weight_raw_kg > 0,
            Piece.material_code.is_not(None),
        )
        .order_by(Piece.updated_at.desc())
    )
    ratios: dict[str, list[float]] = {}
    low, high = FACTOR_RANGE
    for code, actual, raw in rows:
        ratio = actual / raw
        bucket = ratios.setdefault(code, [])
        if low <= ratio <= high and len(bucket) < RECENT:
            bucket.append(ratio)
    return {
        code: (round(median(values), 4), len(values))
        for code, values in ratios.items()
        if len(values) >= MIN_WEIGHINGS
    }


def calibrate(
    raw: float | None, code: str | None, table: dict[str, tuple[float, int]]
) -> float | None:
    """The estimate to show for a raw calculated weight."""
    if raw is None:
        return None
    factor = table.get(code or "", (1.0, 0))[0]
    return round(raw * factor, 3)


def calibration_table(session: Session) -> list[dict[str, Any]]:
    out = []
    for code, (factor, n) in sorted(factors(session).items()):
        mat = materials().get(code)
        out.append(
            {
                "material_code": code,
                "material_name": {"en": mat.name_en, "fr": mat.name_fr} if mat else None,
                "factor": factor,
                "adjust_pct": round((factor - 1) * 100, 1),
                "weighings": n,
            }
        )
    return out
