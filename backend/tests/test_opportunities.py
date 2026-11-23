"""New offcuts look for a use as soon as they are approved."""

from __future__ import annotations

import json

from test_auth_api import add_person, sign_in
from test_jobs_api import upload

PARTS = json.dumps([{"length": 120, "width": 80, "qty": 4}])


def keep_in_mind(client, name="Order 2026-140", parts=PARTS):
    data = {"name": name, "parts": parts, "material": "steel_mild", "thickness_mm": "3"}
    response = client.post("/v1/planned-jobs", data=data)
    assert response.status_code == 201, response.text
    return response.json()


def approved_job(client):
    job = upload(client).json()
    client.post(f"/v1/jobs/{job['id']}/approve")
    return job


def test_a_planned_job_is_kept_and_checked_against_stock(client):
    planned = keep_in_mind(client)
    assert planned["part_count"] == 4 and planned["fits_in_stock"] == 0
    approved_job(client)

    listed = client.get("/v1/planned-jobs").json()["planned"]
    assert listed[0]["name"] == "Order 2026-140" and listed[0]["fits_in_stock"] == 4
    check = client.post(f"/v1/planned-jobs/{planned['id']}/check").json()
    assert check["placed_count"] == 4 and check["planned"]["id"] == planned["id"]


def test_approval_shows_which_planned_jobs_and_buyers_want_the_new_offcuts(client):
    keep_in_mind(client)
    buyer = {
        "kind": "reuse",
        "name": "Hela",
        "phone": "+216 22 654 321",
        "governorate": "Ben Arous",
        "materials": ["steel_mild"],
    }
    assert client.post("/v1/buyer-requests", json=buyer).status_code == 201
    job = approved_job(client)

    found = client.get(f"/v1/jobs/{job['id']}/opportunities").json()
    assert found["planned"][0]["name"] == "Order 2026-140"
    assert found["planned"][0]["placed"] == 4
    assert found["buyers"] and found["buyers"][0]["buyers"][0]["name"] == "Hela"

    alerts = client.get("/v1/alerts").json()["alerts"]
    planned = [a for a in alerts if a["kind"] == "planned"]
    assert planned and planned[0]["link"].startswith("/stock/fit?planned=")


def test_a_finished_planned_job_stops_matching(client):
    planned = keep_in_mind(client)
    approved_job(client)
    assert client.delete(f"/v1/planned-jobs/{planned['id']}").status_code == 204
    assert client.get("/v1/planned-jobs").json()["planned"] == []
    assert not [a for a in client.get("/v1/alerts").json()["alerts"] if a["kind"] == "planned"]


def test_planned_jobs_need_parts_and_a_manager(client):
    empty = client.post(
        "/v1/planned-jobs", data={"name": "X", "material": "steel_mild", "thickness_mm": "3"}
    )
    assert empty.status_code == 422
    add_person(client, "Sami", "operator")
    sign_in(client, "sami@atelier.test")
    assert client.get("/v1/planned-jobs").status_code == 403
