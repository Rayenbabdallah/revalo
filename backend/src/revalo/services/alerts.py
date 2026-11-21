"""What needs the manager's attention now, worked out from the current state.

Alerts are not stored: they are the open to-dos the data implies, so they can
never be stale or out of sync. Each one links to where it is handled.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import (
    BuyerRequest,
    Job,
    JobStatus,
    Listing,
    ListingStatus,
    Pickup,
    PickupStatus,
    Piece,
    PieceStatus,
)
from revalo.services.market import matches_for_listing
from revalo.services.pickups import recycle_queue
from revalo.services.prices import EffectivePrice

NEW_REQUEST_DAYS = 7


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'s' if n != 1 else ''}"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def current_alerts(session: Session, book: dict[str, EffectivePrice]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []

    drafts = list(session.scalars(select(Job).where(Job.status == JobStatus.DRAFT)))
    for job in drafts:
        alerts.append(
            {
                "kind": "review",
                "title": "Job waiting for review",
                "detail": f"{job.file_name}: check and approve its leftover records.",
                "link": f"/jobs/{job.id}",
            }
        )

    due = [
        p
        for p in session.scalars(select(Piece).where(Piece.status == PieceStatus.IN_STOCK))
        if p.review_date is not None and p.review_date <= datetime.now(UTC).date()
    ]
    if due:
        alerts.append(
            {
                "kind": "due",
                "title": f"{_plural(len(due), 'piece')} past review date",
                "detail": "Not reused in time: now recommended for sale or recycling.",
                "link": "/stock",
            }
        )

    for listing in session.scalars(select(Listing).where(Listing.status == ListingStatus.OPEN)):
        found = matches_for_listing(session, listing, limit=50)
        if found:
            alerts.append(
                {
                    "kind": "match",
                    "title": f"{_plural(len(found), 'buyer')} for {listing.piece.code}",
                    "detail": f"Best match: {found[0][0].name}, score {found[0][1].score}.",
                    "link": "/market",
                }
            )

    queue = recycle_queue(session, book)
    if queue:
        kg = sum(p.weight_kg or 0 for p in queue)
        alerts.append(
            {
                "kind": "recycle",
                "title": f"{kg:,.0f} kg ready for a recycler",
                "detail": f"{_plural(len(queue), 'piece')} to send as a sorted lot.",
                "link": "/market?tab=recycling",
            }
        )

    for pickup in session.scalars(select(Pickup).where(Pickup.status == PickupStatus.REQUESTED)):
        alerts.append(
            {
                "kind": "pickup",
                "title": f"Pickup to schedule with {pickup.recycler.name}",
                "detail": f"{pickup.estimated_kg:,.0f} kg requested; set the date when they reply.",
                "link": "/market?tab=recycling",
            }
        )

    since = datetime.now(UTC) - timedelta(days=NEW_REQUEST_DAYS)
    fresh = [
        r
        for r in session.scalars(select(BuyerRequest).where(BuyerRequest.active.is_(True)))
        if _aware(r.created_at) >= since
    ]
    if fresh:
        alerts.append(
            {
                "kind": "buyer",
                "title": _plural(len(fresh), "new buyer request"),
                "detail": ", ".join(r.name for r in fresh[:3]) + ("…" if len(fresh) > 3 else ""),
                "link": "/market?tab=buyers",
            }
        )
    return alerts
