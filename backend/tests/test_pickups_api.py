import pytest
from test_market_api import stock  # noqa: F401

RECYCLER = {
    "kind": "recycler",
    "name": "Récupération Ben Arous",
    "phone": "98 765 432",
    "governorate": "Ben Arous",
    "materials": ["steel_mild"],
    "offered_tnd_per_kg": 0.3,
    "min_lot_kg": 1,  # the test sheet leaves a 1.1 kg scrap lot
    "pickup_note": "Tuesdays, light truck",
}


def test_queue_holds_what_should_be_recycled_with_suitable_recyclers(client, stock):  # noqa: F811
    _, lot = stock
    client.post("/v1/buyer-requests", json=RECYCLER)
    inox_only = {**RECYCLER, "name": "Inox only", "materials": ["stainless_304"]}
    client.post("/v1/buyer-requests", json=inox_only)
    client.post("/v1/buyer-requests", json={**RECYCLER, "name": "Big lots", "min_lot_kg": 500})

    groups = client.get("/v1/pickups/queue").json()["groups"]
    assert len(groups) == 1
    steel = groups[0]
    assert [p["code"] for p in steel["pieces"]] == [lot["code"]]
    names = [r["recycler"]["name"] for r in steel["recyclers"]]
    assert names == ["Récupération Ben Arous", "Big lots"]  # lot too small for the second
    assert steel["recyclers"][0]["lot_ok"] and not steel["recyclers"][1]["lot_ok"]
    assert steel["recyclers"][0]["recycler"]["pickup_note"] == "Tuesdays, light truck"


def test_pickup_lifecycle(client, stock):  # noqa: F811
    _, lot = stock
    recycler = client.post("/v1/buyer-requests", json=RECYCLER).json()
    created = client.post(
        "/v1/pickups",
        json={"recycler_id": recycler["id"], "piece_ids": [lot["id"]]},
    )
    assert created.status_code == 201, created.text
    pickup = created.json()
    assert pickup["status"] == "requested"
    assert pickup["estimated_kg"] == pytest.approx(lot["weight_kg"], abs=0.01)
    assert pickup["whatsapp_url"].startswith("https://wa.me/21698765432?text=Bonjour")
    assert client.get(f"/v1/pieces/{lot['id']}").json()["status"] == "reserved"
    assert client.get("/v1/pickups/queue").json()["groups"] == []

    url = f"/v1/pickups/{pickup['id']}"
    assert client.patch(url, json={"action": "schedule"}).status_code == 409
    scheduled = client.patch(url, json={"action": "schedule", "scheduled_for": "2026-11-24"})
    assert scheduled.json()["scheduled_for"] == "2026-11-24"
    collected = client.patch(url, json={"action": "collect", "weighed_kg": 12.0}).json()
    assert collected["status"] == "collected" and collected["paid_tnd"] == 3.6
    piece = client.get(f"/v1/pieces/{lot['id']}").json()
    assert piece["status"] == "recycled" and piece["events"][-1]["action"] == "recycled"
    assert client.patch(url, json={"action": "cancel"}).status_code == 409


def test_cancelled_pickup_returns_pieces_to_stock(client, stock):  # noqa: F811
    _, lot = stock
    recycler = client.post("/v1/buyer-requests", json=RECYCLER).json()
    pickup = client.post(
        "/v1/pickups", json={"recycler_id": recycler["id"], "piece_ids": [lot["id"]]}
    ).json()
    client.patch(f"/v1/pickups/{pickup['id']}", json={"action": "cancel"})
    assert client.get(f"/v1/pieces/{lot['id']}").json()["status"] == "in_stock"


def test_only_recyclers_and_stock_pieces(client, stock):  # noqa: F811
    _, lot = stock
    buyer = client.post(
        "/v1/buyer-requests",
        json={"name": "Karim", "phone": "22 123 456", "governorate": "Tunis"},
    ).json()
    bad = client.post("/v1/pickups", json={"recycler_id": buyer["id"], "piece_ids": [lot["id"]]})
    assert bad.status_code == 409
