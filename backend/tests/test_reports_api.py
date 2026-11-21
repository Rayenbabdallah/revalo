from datetime import UTC, datetime

import pytest
from test_jobs_api import upload
from test_market_api import stock  # noqa: F401

MONTH = datetime.now(UTC).strftime("%Y-%m")


def test_monthly_report_adds_up_reuse_sales_and_recycling(client, stock):  # noqa: F811
    remnant, lot = stock
    second = upload(client, "b_S235_3mm.dxf").json()
    client.post(f"/v1/jobs/{second['id']}/approve", json={})
    other = next(p for p in second["pieces"] if p["kind"] == "remnant")

    # Sell one remnant for 80 TND.
    listing = client.post(f"/v1/pieces/{remnant['id']}/listing", json={"price_tnd": 80}).json()
    client.patch(f"/v1/listings/{listing['id']}", json={"action": "sell"})
    # Reuse another for an order.
    client.post("/v1/stock/fit/reuse", json={"piece_ids": [other["id"]], "job_name": "Order 7"})
    # Recycle the scrap lot.
    recycler = client.post(
        "/v1/buyer-requests",
        json={
            "kind": "recycler",
            "name": "Recycler",
            "phone": "98765432",
            "governorate": "Ben Arous",
            "offered_tnd_per_kg": 0.3,
        },
    ).json()
    pickup = client.post(
        "/v1/pickups", json={"recycler_id": recycler["id"], "piece_ids": [lot["id"]]}
    ).json()
    client.patch(f"/v1/pickups/{pickup['id']}", json={"action": "collect", "weighed_kg": 10})

    report = client.get(f"/v1/reports/monthly?month={MONTH}").json()
    assert report["production"]["jobs"] == 2 and report["production"]["parts"] == 10
    out = report["outcomes"]
    assert out["sold"]["tnd"] == 80 and out["sold"]["fees_tnd"] == 4
    assert out["reused"]["pieces"] == 1
    assert out["reused"]["tnd"] == pytest.approx(other["weight_kg"] * 3.0, rel=1e-3)
    assert out["recycled"] == {"pickups": 1, "kg": 10, "tnd": 3}
    expected = out["reused"]["tnd"] + 80 - 4 + 3
    assert report["recovered_tnd"] == pytest.approx(expected, abs=0.01)
    assert report["co2_avoided_kg"] > 0
    assert report["plan_tnd"] == 120
    assert report["return_on_plan"] == pytest.approx(expected / 120, abs=0.01)


def test_other_months_are_empty_and_bad_months_rejected(client, stock):  # noqa: F811
    report = client.get("/v1/reports/monthly?month=2020-01").json()
    assert report["production"]["jobs"] == 0 and report["recovered_tnd"] == 0
    assert client.get("/v1/reports/monthly?month=nope").status_code == 422


def test_stock_exports_as_an_excel_friendly_csv(client, stock):  # noqa: F811
    response = client.get("/v1/stock/export.csv")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    text = response.content.decode("utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0].startswith("code;kind;material")
    assert len(lines) == 1 + 2  # one remnant and one scrap lot in stock
    assert "Acier doux" in text
