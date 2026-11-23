"""Similar offcuts sold together as one lot, whole or in part."""

from __future__ import annotations

ROW = {"material": "mdf", "thickness_mm": 18, "width_mm": 500, "height_mm": 300, "quantity": 6}


def stock(client):
    return client.post("/v1/stock/intake", json={"rows": [ROW]}).json()["pieces"]


def test_similar_offcuts_are_suggested_and_sold_in_part(client):
    pieces = stock(client)
    groups = client.get("/v1/lots/suggestions").json()["groups"]
    assert groups[0]["count"] == 6 and groups[0]["sizes"][0]["count"] == 6

    lot = client.post("/v1/lots", json={"piece_ids": groups[0]["piece_ids"], "price_tnd": 60})
    assert lot.status_code == 201, lot.text
    lot = lot.json()
    assert lot["count"] == 6 and lot["code"].startswith("LT-")
    assert client.get("/v1/market").json()["lots"][0]["code"] == lot["code"]

    part = [p["id"] for p in pieces[:2]]
    sold = client.patch(f"/v1/lots/{lot['id']}", json={"action": "sell", "piece_ids": part})
    assert sold.status_code == 200, sold.text
    assert sold.json()["count"] == 2 and sold.json()["status"] == "sold"
    rest = client.get(f"/v1/lots/{lot['id']}").json()
    assert rest["count"] == 4 and rest["status"] == "open" and rest["price_tnd"] == 40
    assert client.get("/v1/reports/monthly").json()["outcomes"]["sold"]["pieces"] == 2


def test_a_lot_needs_one_material_and_free_pieces(client):
    pieces = stock(client)
    steel = client.post(
        "/v1/stock/intake",
        json={"rows": [{**ROW, "material": "steel_mild", "thickness_mm": 3, "quantity": 1}]},
    ).json()["pieces"]
    mixed = client.post("/v1/lots", json={"piece_ids": [pieces[0]["id"], steel[0]["id"]]})
    assert mixed.status_code == 422
    ids = [p["id"] for p in pieces[:3]]
    assert client.post("/v1/lots", json={"piece_ids": ids}).status_code == 201
    assert client.post("/v1/lots", json={"piece_ids": ids}).status_code == 422


def test_buyers_who_take_whole_lots_come_first(client):
    pieces = stock(client)
    base = {
        "kind": "reuse",
        "phone": "+216 20 000 000",
        "governorate": "Tunis",
        "materials": ["mdf"],
    }
    client.post("/v1/buyer-requests", json={**base, "name": "Karim"})
    client.post("/v1/buyer-requests", json={**base, "name": "Samia", "buys_lots": True})
    lot = client.post("/v1/lots", json={"piece_ids": [p["id"] for p in pieces]}).json()
    names = [m["name"] for m in lot["matches"]]
    assert names[0] == "Samia" and "Karim" in names
    assert lot["matches"][0]["buys_lots"] is True
    assert "wa.me" in lot["matches"][0]["whatsapp_url"]
