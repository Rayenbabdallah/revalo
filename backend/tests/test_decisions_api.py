from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session
from test_jobs_api import upload

from revalo.db.models import Piece
from revalo.db.session import get_engine
from revalo.services.decisions import decide_piece
from revalo.services.prices import price_book


def test_every_record_carries_a_recommendation(client):
    job = upload(client).json()
    remnant = next(p for p in job["pieces"] if p["kind"] == "remnant")
    lot = next(p for p in job["pieces"] if p["kind"] == "scrap")

    decision = remnant["decision"]
    assert decision["recommended"] == "reuse" and decision["stage"] == "new"
    reuse = next(o for o in decision["options"] if o["action"] == "reuse")
    # 1999 x 1500 x 3 mm of mild steel (~70.6 kg) at 3 TND/kg
    assert reuse["value_tnd"] == pytest.approx(remnant["weight_kg"] * 3.0, rel=1e-3)
    assert reuse["co2_kg"] == pytest.approx(remnant["weight_kg"] * 1.92, abs=0.1)
    assert decision["reasons"]

    assert lot["decision"]["recommended"] == "recycle"
    assert job["recovered"]["value_tnd"] > 200
    assert job["recovered"]["priced_pieces"] == job["recovered"]["pieces"]


def test_a_workshop_price_changes_the_numbers(client):
    job = upload(client).json()
    remnant = next(p for p in job["pieces"] if p["kind"] == "remnant")
    before = remnant["decision"]["options"][0]["value_tnd"]
    client.put(
        "/v1/prices/steel_mild",
        json={"new_tnd_per_kg": 4.5, "scrap_tnd_per_kg": 0.3, "resale_factor": 0.4},
    )
    after = client.get(f"/v1/pieces/{remnant['id']}").json()["decision"]["options"][0]["value_tnd"]
    assert after == pytest.approx(before * 1.5, rel=1e-3)


def test_unpriced_material_asks_for_a_price(client):
    job = upload(client, name="inox_304_2mm.dxf").json()
    remnant = next(p for p in job["pieces"] if p["kind"] == "remnant")
    assert "price for Stainless steel 304" in remnant["decision"]["reasons"][0]
    assert job["recovered"]["priced_pieces"] == 0


def test_stock_is_scored_again_as_it_ages(client):
    job = upload(client).json()
    client.post(f"/v1/jobs/{job['id']}/approve", json={})
    summary = client.get("/v1/stock/summary").json()
    assert summary["actions"]["reuse"]["count"] >= 1
    assert summary["actions"]["recycle"]["count"] == 1
    assert summary["totals"]["value_tnd"] > 0 and summary["totals"]["co2_kg"] > 0

    with Session(get_engine()) as session:
        piece = session.get(Piece, job["pieces"][0]["id"])
        book = price_book(session, piece.workshop_id)
        approved = piece.job.approved_at
        if approved.tzinfo is None:
            approved = approved.replace(tzinfo=UTC)
        assert decide_piece(piece, book, approved + timedelta(days=31)).recommended.value == "sell"
        assert (
            decide_piece(piece, book, approved + timedelta(days=61)).recommended.value == "recycle"
        )
        assert decide_piece(piece, book, datetime.now(UTC)).stage == "new"
