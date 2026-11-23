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
from revalo.i18n import num, tr, trn
from revalo.services.market import matches_for_listing
from revalo.services.opportunities import planned_alerts
from revalo.services.pickups import recycle_queue
from revalo.services.prices import EffectivePrice
from revalo.services.sourcing import open_offers, planned_fits

NEW_REQUEST_DAYS = 7


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def current_alerts(session: Session, book: dict[str, EffectivePrice]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []

    drafts = list(session.scalars(select(Job).where(Job.status == JobStatus.DRAFT)))
    for job in drafts:
        alerts.append(
            {
                "kind": "review",
                "title": tr("Job waiting for review"),
                "detail": tr("{file}: check and approve its leftover records.", file=job.file_name),
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
                "title": trn(
                    "{count} piece past review date|{count} pieces past review date", len(due)
                ),
                "detail": tr("Not reused in time: now recommended for sale or recycling."),
                "link": "/stock",
            }
        )

    for listing in session.scalars(select(Listing).where(Listing.status == ListingStatus.OPEN)):
        found = matches_for_listing(session, listing, limit=50)
        if found:
            alerts.append(
                {
                    "kind": "match",
                    "title": trn(
                        "{count} buyer for {code}|{count} buyers for {code}",
                        len(found),
                        code=listing.piece.code,
                    ),
                    "detail": tr(
                        "Best match: {name}, score {score}.",
                        name=found[0][0].name,
                        score=found[0][1].score,
                    ),
                    "link": "/market",
                }
            )

    queue = recycle_queue(session, book)
    if queue:
        kg = sum(p.weight_kg or 0 for p in queue)
        alerts.append(
            {
                "kind": "recycle",
                "title": tr("{kg} kg ready for a recycler", kg=num(kg, 0)),
                "detail": trn(
                    "{count} piece to send as a sorted lot."
                    "|{count} pieces to send as a sorted lot.",
                    len(queue),
                ),
                "link": "/market?tab=recycling",
            }
        )

    for pickup in session.scalars(select(Pickup).where(Pickup.status == PickupStatus.REQUESTED)):
        alerts.append(
            {
                "kind": "pickup",
                "title": tr("Pickup to schedule with {name}", name=pickup.recycler.name),
                "detail": tr(
                    "{kg} kg requested; set the date when they reply.",
                    kg=num(pickup.estimated_kg, 0),
                ),
                "link": "/market?tab=recycling",
            }
        )

    for fit in planned_alerts(session):
        alerts.append(
            {
                "kind": "planned",
                "title": tr(
                    "{placed} of {total} parts of {name} fit the racks",
                    placed=fit["placed"],
                    total=fit["total"],
                    name=fit["name"],
                ),
                "detail": trn(
                    "Cut them from {count} remnant before opening a new sheet."
                    "|Cut them from {count} remnants before opening a new sheet.",
                    len(fit["codes"]),
                ),
                "link": f"/stock/fit?planned={fit['id']}",
            }
        )

    for offer in open_offers(session):
        fits = planned_fits(session, offer)
        if fits:
            alerts.append(
                {
                    "kind": "offer",
                    "title": tr(
                        "{seller} offers offcuts for {name}",
                        seller=offer.organization or offer.seller_name,
                        name=fits[0]["name"],
                    ),
                    "detail": trn(
                        "They would hold {count} more part than your racks."
                        "|They would hold {count} more parts than your racks.",
                        fits[0]["extra_parts"],
                    ),
                    "link": "/market?tab=buying",
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
                "title": trn("{count} new buyer request|{count} new buyer requests", len(fresh)),
                "detail": ", ".join(r.name for r in fresh[:3]) + ("…" if len(fresh) > 3 else ""),
                "link": "/market?tab=buyers",
            }
        )
    return alerts
