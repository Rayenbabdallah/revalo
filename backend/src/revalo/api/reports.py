"""Reports and exports for the owner."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from revalo.api.deps import SignedIn, manager_only
from revalo.db.models import Role
from revalo.db.session import get_session
from revalo.services.alerts import current_alerts
from revalo.services.jobs import default_workshop
from revalo.services.pieces import stock_pieces
from revalo.services.prices import price_book
from revalo.services.reports import monthly_report, stock_csv

router = APIRouter(tags=["reports"])
DbSession = Annotated[Session, Depends(get_session)]


@router.get("/v1/reports/monthly", dependencies=[manager_only])
def monthly(session: DbSession, month: str | None = None) -> dict[str, Any]:
    shop = default_workshop(session)
    month = month or datetime.now(UTC).strftime("%Y-%m")
    try:
        return monthly_report(session, month, price_book(session, shop.id), shop.name)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.get("/v1/stock/export.csv", dependencies=[manager_only])
def export_stock(session: DbSession) -> Response:
    shop = default_workshop(session)
    body = stock_csv(stock_pieces(session, "in_stock", None), price_book(session, shop.id))
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    return Response(
        content=body,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="revalo-stock-{stamp}.csv"'},
    )


@router.get("/v1/alerts")
def alerts(user: SignedIn, session: DbSession) -> dict[str, Any]:
    # Every alert today is a manager's task; operators would only see what they cannot do.
    if Role(user.role).rank < Role.MANAGER.rank:
        return {"alerts": []}
    shop = default_workshop(session)
    return {"alerts": current_alerts(session, price_book(session, shop.id))}
