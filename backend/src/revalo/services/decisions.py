"""Apply the decision engine to stored pieces, with the workshop's own prices.

Recommendations are computed when asked for, never stored: the price book and
the time a piece has spent in stock both change, so a stored answer would go
stale. That is also what makes pieces "scored again" on their review date.
"""

from __future__ import annotations

from datetime import UTC, datetime

from revalo.db.models import Piece, PieceKind, PieceStatus
from revalo.engine.decision import Decision, PieceFacts, decide
from revalo.engine.materials import materials
from revalo.services.prices import EffectivePrice
from revalo.settings import get_settings


def decide_piece(
    piece: Piece, book: dict[str, EffectivePrice], now: datetime | None = None
) -> Decision:
    mat = materials().get(piece.material_code or "")
    entry = book.get(piece.material_code or "")
    in_stock = piece.status == PieceStatus.IN_STOCK
    days = 0
    approved_at = piece.job.approved_at if piece.job else None
    if in_stock and approved_at is not None:
        if approved_at.tzinfo is None:  # SQLite returns naive datetimes
            approved_at = approved_at.replace(tzinfo=UTC)
        days = max(((now or datetime.now(UTC)) - approved_at).days, 0)
    short = None
    if piece.kind == PieceKind.REMNANT and piece.width_mm and piece.height_mm:
        short = min(piece.width_mm, piece.height_mm)
    facts = PieceFacts(
        kind=piece.kind,
        family=mat.family if mat else None,
        material_name=mat.name_en if mat else "this material",
        weight_kg=piece.weight_kg,
        short_side_mm=short,
        days_in_stock=days,
        in_stock=in_stock,
    )
    return decide(
        facts,
        entry.prices if entry else None,
        entry.co2 if entry else None,
        review_days=get_settings().review_days,
    )
