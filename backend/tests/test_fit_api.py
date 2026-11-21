import json

import pytest
from dxf_helpers import new_doc, rect, to_bytes
from test_market_api import stock  # noqa: F401  (fixture: an approved job in stock)


def parts_dxf():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 0, 0, 400, 300)
    rect(msp, 500, 0, 400, 300)
    rect(msp, 1000, 0, 2600, 1300)  # too big for any remnant
    return to_bytes(doc)


def test_parts_are_placed_on_matching_remnants(client, stock):  # noqa: F811
    response = client.post(
        "/v1/stock/fit",
        files={"file": ("next_job_S235_3mm.dxf", parts_dxf(), "application/dxf")},
    )
    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["material_code"] == "steel_mild" and plan["thickness_mm"] == 3
    assert plan["part_count"] == 3 and plan["placed_count"] == 2
    assert [p["length"] for p in plan["unplaced"]] == [2600]
    assert plan["saved_kg"] == pytest.approx(2 * 400 * 300 * 3 * 7850 / 1e9, rel=1e-3)
    assert plan["saved_tnd"] == pytest.approx(plan["saved_kg"] * 3.0, rel=1e-3)
    used = plan["uses"][0]
    assert used["piece"]["code"].startswith("RV-") and len(used["placements"]) == 2


def test_typed_parts_and_other_materials(client, stock):  # noqa: F811
    parts = json.dumps([{"label": "Bracket", "length": 200, "width": 100, "qty": 3}])
    plan = client.post(
        "/v1/stock/fit", data={"parts": parts, "material": "steel_mild", "thickness_mm": "3"}
    ).json()
    assert plan["placed_count"] == 3
    other = client.post(
        "/v1/stock/fit", data={"parts": parts, "material": "aluminium", "thickness_mm": "3"}
    ).json()
    assert other["candidates"] == 0 and other["placed_count"] == 0


def test_missing_material_or_parts_is_explained(client):
    assert client.post("/v1/stock/fit", data={}).status_code == 422
    parts = json.dumps([{"length": 200, "width": 100}])
    no_material = client.post("/v1/stock/fit", data={"parts": parts})
    assert no_material.status_code == 422 and "material" in no_material.json()["detail"]
    bad = client.post("/v1/stock/fit", data={"parts": json.dumps([{"length": -1, "width": 2}])})
    assert bad.status_code == 422


def test_using_remnants_takes_them_out_of_stock_and_off_sale(client, stock):  # noqa: F811
    remnant, _ = stock
    client.post(f"/v1/pieces/{remnant['id']}/listing", json={"price_tnd": 80})
    body = {"piece_ids": [remnant["id"]], "job_name": "Order 2026-131", "actor": "Slim"}
    response = client.post("/v1/stock/fit/reuse", json=body)
    assert response.status_code == 200
    piece = client.get(f"/v1/pieces/{remnant['id']}").json()
    assert piece["status"] == "reused"
    assert piece["events"][-1]["data"] == {"for": "Order 2026-131"}
    assert piece["listing"]["status"] == "withdrawn"
    assert client.post("/v1/stock/fit/reuse", json=body).status_code == 409
