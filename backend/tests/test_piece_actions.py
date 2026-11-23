"""What can be done from a scanned label, on the rack."""

from __future__ import annotations

from test_jobs_api import upload


def approved_remnant(client):
    job = upload(client).json()
    client.post(f"/v1/jobs/{job['id']}/approve")
    piece = next(p for p in job["pieces"] if p["kind"] == "remnant")
    return client.get(f"/v1/codes/{piece['code']}").json()


def test_moving_a_piece_is_recorded_as_a_move(client):
    piece = approved_remnant(client)
    moved = client.patch(f"/v1/pieces/{piece['id']}", json={"location": "Rack C2"}).json()
    assert moved["location"] == "Rack C2"
    assert moved["events"][-1]["action"] == "moved"
    assert moved["events"][-1]["actor"] == "Slim"


def test_a_damaged_remnant_goes_to_scrap(client):
    piece = approved_remnant(client)
    client.post(f"/v1/pieces/{piece['id']}/listing", json={})
    scrapped = client.post(
        f"/v1/pieces/{piece['id']}/scrap", json={"reason": "Bent by the forklift"}
    )
    assert scrapped.status_code == 200, scrapped.text
    body = scrapped.json()
    assert body["kind"] == "scrap" and body["condition_note"] == "Bent by the forklift"
    assert body["events"][-1]["action"] == "scrapped"
    assert body["decision"]["recommended"] == "recycle"
    listing = client.get(f"/v1/codes/{piece['code']}").json()["listing"]
    assert listing is None or listing["status"] == "withdrawn"
    again = client.post(f"/v1/pieces/{piece['id']}/scrap", json={"reason": "again"})
    assert again.status_code == 409


def test_taking_a_piece_for_a_job_from_the_rack(client):
    piece = approved_remnant(client)
    body = {"piece_ids": [piece["id"]], "job_name": "Order 2026-140"}
    assert client.post("/v1/stock/fit/reuse", json=body).status_code == 200
    taken = client.get(f"/v1/codes/{piece['code']}").json()
    assert taken["status"] == "reused" and taken["events"][-1]["data"]["for"] == "Order 2026-140"
