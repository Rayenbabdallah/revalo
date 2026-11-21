"""The owner's monthly report: what leftovers were worth, against what Revalo costs."""

from __future__ import annotations

import csv
import io
import os
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import Job, Listing, ListingStatus, Pickup, PickupStatus, Piece, PieceEvent
from revalo.engine.materials import materials
from revalo.services.decisions import decide_piece
from revalo.services.pieces import stock_summary
from revalo.services.prices import EffectivePrice

# Standard plan of the Market Playbook (section 5); the pilot can override it.
DEFAULT_PLAN_TND = 120.0


def month_bounds(month: str) -> tuple[datetime, datetime]:
    try:
        year, mon = (int(x) for x in month.split("-"))
        start = datetime(year, mon, 1, tzinfo=UTC)
    except ValueError as exc:
        raise ValueError("Use a month like 2026-11.") from exc
    end = datetime(year + (mon == 12), mon % 12 + 1, 1, tzinfo=UTC)
    return start, end


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _co2(code: str | None, kg: float, recycled: bool) -> float:
    block = materials()[code].co2 if code in materials() else None
    if not block:
        return 0.0
    factor = block.get("recycling_saves_kg_per_kg") if recycled else block.get("primary_kg_per_kg")
    return kg * (factor or 0.0)


def monthly_report(
    session: Session, month: str, book: dict[str, EffectivePrice], workshop_name: str
) -> dict[str, Any]:
    start, end = month_bounds(month)

    def in_month(moment: datetime | None) -> bool:
        return moment is not None and start <= _aware(moment) < end

    jobs = [j for j in session.scalars(select(Job)) if in_month(j.created_at)]
    pieces_from_jobs = [p for j in jobs for p in j.pieces if p.status != "rejected"]
    remnant_kg = sum(p.weight_kg or 0 for p in pieces_from_jobs if p.kind == "remnant")
    scrap_kg = sum(p.weight_kg or 0 for p in pieces_from_jobs if p.kind == "scrap")

    # Reused: new material the workshop did not have to buy.
    reused = []
    for event in session.scalars(select(PieceEvent).where(PieceEvent.action == "reused")):
        if in_month(event.at):
            reused.append(event.piece)
    reused_kg = sum(p.weight_kg or 0 for p in reused)
    reused_tnd = 0.0
    for p in reused:
        entry = book.get(p.material_code or "")
        if entry and entry.prices and p.weight_kg:
            reused_tnd += p.weight_kg * entry.prices.new_tnd_per_kg

    sold = [
        lst
        for lst in session.scalars(select(Listing).where(Listing.status == ListingStatus.SOLD))
        if in_month(lst.closed_at)
    ]
    sales_tnd = sum(lst.sold_price_tnd or 0 for lst in sold)
    fees_tnd = sum(lst.fee_tnd or 0 for lst in sold)
    sold_kg = sum(lst.piece.weight_kg or 0 for lst in sold)

    pickups = [
        pk
        for pk in session.scalars(select(Pickup).where(Pickup.status == PickupStatus.COLLECTED))
        if in_month(pk.closed_at)
    ]
    recycled_kg = sum(pk.weighed_kg or 0 for pk in pickups)
    recycled_tnd = sum(pk.paid_tnd or 0 for pk in pickups)

    co2 = sum(_co2(p.material_code, p.weight_kg or 0, False) for p in reused)
    co2 += sum(_co2(lst.piece.material_code, lst.piece.weight_kg or 0, False) for lst in sold)
    for pk in pickups:
        share = (pk.weighed_kg or 0) / pk.estimated_kg if pk.estimated_kg else 1.0
        co2 += sum(
            _co2(i.piece.material_code, (i.piece.weight_kg or 0) * share, True) for i in pk.items
        )

    recovered = reused_tnd + (sales_tnd - fees_tnd) + recycled_tnd
    plan = float(os.getenv("REVALO_PLAN_TND", DEFAULT_PLAN_TND))
    stock = stock_summary(session, book)

    return {
        "month": month,
        "workshop": workshop_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "production": {
            "jobs": len(jobs),
            "sheets": sum(j.sheet_count for j in jobs),
            "parts": sum(j.part_count for j in jobs),
            "remnant_kg": round(remnant_kg, 1),
            "scrap_kg": round(scrap_kg, 1),
        },
        "outcomes": {
            "reused": {
                "pieces": len(reused),
                "kg": round(reused_kg, 1),
                "tnd": round(reused_tnd, 2),
            },
            "sold": {
                "pieces": len(sold),
                "kg": round(sold_kg, 1),
                "tnd": round(sales_tnd, 2),
                "fees_tnd": round(fees_tnd, 2),
            },
            "recycled": {
                "pickups": len(pickups),
                "kg": round(recycled_kg, 1),
                "tnd": round(recycled_tnd, 2),
            },
        },
        "recovered_tnd": round(recovered, 2),
        "diverted_kg": round(reused_kg + sold_kg + recycled_kg, 1),
        "co2_avoided_kg": round(co2, 1),
        "plan_tnd": plan,
        "return_on_plan": round(recovered / plan, 2) if plan else None,
        "stock": {
            "value_tnd": stock["totals"]["value_tnd"],
            "remnant_count": stock["totals"]["remnant_count"],
            "remnant_kg": stock["totals"]["remnant_weight_kg"],
            "scrap_kg": stock["totals"]["scrap_weight_kg"],
            "due_for_review": stock["totals"]["due_for_review"],
        },
    }


STOCK_COLUMNS = [
    "code",
    "kind",
    "material",
    "thickness_mm",
    "width_mm",
    "height_mm",
    "area_m2",
    "weight_kg",
    "status",
    "location",
    "review_date",
    "next_step",
    "value_tnd",
]


def stock_csv(pieces: list[Piece], book: dict[str, EffectivePrice]) -> str:
    """Stock as a spreadsheet the owner can open in Excel (semicolons, decimal commas)."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";")
    writer.writerow(STOCK_COLUMNS)

    def num(value: float | None) -> str:
        return "" if value is None else f"{value:g}".replace(".", ",")

    for p in pieces:
        decision = decide_piece(p, book)
        option = decision.option(decision.recommended) if decision.recommended else None
        mat = materials().get(p.material_code or "")
        writer.writerow(
            [
                p.code,
                p.kind,
                mat.name_fr if mat else "",
                num(p.thickness_mm),
                num(p.width_mm),
                num(p.height_mm),
                num(p.area_m2),
                num(p.weight_kg),
                p.status,
                p.location or "",
                p.review_date.isoformat() if isinstance(p.review_date, date) else "",
                decision.recommended.value if decision.recommended else "",
                num(option.value_tnd if option else None),
            ]
        )
    # A BOM so Excel opens accented French text correctly.
    return "﻿" + out.getvalue()
