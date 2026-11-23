"""Pieces already on the racks before Revalo, entered by hand or from a list."""

from __future__ import annotations

from test_auth_api import add_person, sign_in

ROWS = [
    {
        "material": "steel_mild",
        "thickness_mm": 3,
        "width_mm": 600,
        "height_mm": 400,
        "quantity": 3,
        "location": "Rack A1",
    },
    {"material": "Inox 304", "thickness_mm": 1.5, "width_mm": 300, "height_mm": 200},
    {"material": "Acier doux", "thickness_mm": 3, "kind": "scrap", "weight_kg": 42},
]


def test_existing_pieces_go_straight_into_stock(client):
    added = client.post("/v1/stock/intake", json={"name": "Racks A and B", "rows": ROWS})
    assert added.status_code == 201, added.text
    job = added.json()
    assert job["file_name"] == "Racks A and B" and job["status"] == "approved"
    pieces = job["pieces"]
    assert len(pieces) == 5 and all(p["status"] == "in_stock" for p in pieces)
    assert len({p["code"] for p in pieces}) == 5
    steel = [p for p in pieces if p["material_code"] == "steel_mild" and p["kind"] == "remnant"]
    assert len(steel) == 3 and steel[0]["location"] == "Rack A1"
    assert abs(steel[0]["weight_kg"] - 0.6 * 0.4 * 0.003 * 7850) < 0.2
    assert next(p for p in pieces if p["kind"] == "scrap")["weight_kg"] == 42
    assert {p["material_code"] for p in pieces} == {"steel_mild", "stainless_304"}


def test_rows_already_in_stock_are_flagged_before_adding(client):
    client.post("/v1/stock/intake", json={"rows": ROWS[:1]})
    rotated = {**ROWS[0], "width_mm": 401, "height_mm": 599, "quantity": 1}
    checked = client.post("/v1/stock/intake/check", json={"rows": [rotated, ROWS[1]]}).json()[
        "rows"
    ]
    assert checked[0]["similar_in_stock"] == 3
    assert checked[0]["similar"][0]["location"] == "Rack A1"
    assert checked[1]["similar_in_stock"] == 0


def test_bad_rows_say_which_row(client):
    bad = client.post(
        "/v1/stock/intake/check", json={"rows": [ROWS[0], {**ROWS[1], "material": "unobtainium"}]}
    )
    assert bad.status_code == 422 and "Row 2" in bad.json()["detail"]
    no_size = client.post(
        "/v1/stock/intake", json={"rows": [{"material": "mdf", "thickness_mm": 18}]}
    )
    assert no_size.status_code == 422


def test_only_managers_add_stock_and_it_is_not_production(client):
    client.post("/v1/stock/intake", json={"rows": ROWS})
    report = client.get("/v1/reports/monthly").json()
    assert report["production"]["jobs"] == 0
    assert report["stock"]["remnant_count"] == 4

    add_person(client, "Sami", "operator")
    sign_in(client, "sami@atelier.test")
    assert client.post("/v1/stock/intake", json={"rows": ROWS}).status_code == 403
