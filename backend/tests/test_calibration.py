"""Estimated weights learn from the pieces people weigh."""

from __future__ import annotations

import pytest
from test_jobs_api import upload

ROW = {
    "material": "steel_mild",
    "thickness_mm": 3,
    "width_mm": 600,
    "height_mm": 400,
    "quantity": 5,
}


def intake(client, row=ROW):
    return client.post("/v1/stock/intake", json={"rows": [row]}).json()["pieces"]


def weigh(client, piece, factor):
    body = {"weight_actual_kg": round(piece["weight_raw_kg"] * factor, 3)}
    assert client.patch(f"/v1/pieces/{piece['id']}", json=body).status_code == 200


def table(client):
    return {m["material_code"]: m for m in client.get("/v1/prices/calibration").json()["materials"]}


def test_three_weighings_teach_a_correction_used_for_new_estimates(client):
    pieces = intake(client)
    weigh(client, pieces[0], 1.04)
    weigh(client, pieces[1], 1.05)
    assert table(client) == {}  # two weighings are not enough
    weigh(client, pieces[2], 1.06)
    weigh(client, pieces[3], 2.5)  # a typing mistake: ignored

    steel = table(client)["steel_mild"]
    assert steel["factor"] == pytest.approx(1.05, abs=0.001)
    assert steel["weighings"] == 3 and steel["adjust_pct"] == pytest.approx(5.0, abs=0.1)

    fresh = intake(client, {**ROW, "quantity": 1})[0]
    assert fresh["weight_est_kg"] == round(fresh["weight_raw_kg"] * steel["factor"], 3)

    job = upload(client).json()
    remnant = next(p for p in job["pieces"] if p["kind"] == "remnant")
    assert remnant["weight_est_kg"] == pytest.approx(
        remnant["weight_raw_kg"] * steel["factor"], abs=0.002
    )


def test_other_materials_and_typed_weights_are_left_alone(client):
    pieces = intake(client)
    for piece in pieces[:3]:
        weigh(client, piece, 1.1)
    mdf = intake(client, {**ROW, "material": "mdf", "thickness_mm": 18, "quantity": 1})[0]
    assert mdf["weight_est_kg"] == mdf["weight_raw_kg"]
    scrap = intake(
        client, {"material": "steel_mild", "thickness_mm": 3, "kind": "scrap", "weight_kg": 40}
    )[0]
    assert scrap["weight_est_kg"] == 40
