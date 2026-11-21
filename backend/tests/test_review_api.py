from datetime import date, timedelta

import pytest
from test_jobs_api import upload


@pytest.fixture
def job(client):
    return upload(client).json()


def remnant(job):
    return next(p for p in job["pieces"] if p["kind"] == "remnant")


def scrap(job):
    return next(p for p in job["pieces"] if p["kind"] == "scrap")


def test_manager_corrects_weight_and_trims_a_damaged_edge(client, job):
    piece = remnant(job)
    response = client.patch(
        f"/v1/pieces/{piece['id']}",
        json={
            "actor": "Sami",
            "weight_actual_kg": 69.4,
            "width_mm": 1950,
            "condition_note": "Edge dented",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["weight_kg"] == 69.4
    assert body["width_mm"] == 1950
    assert body["area_m2"] == pytest.approx(1950 * 1500 / 1e6, rel=1e-4)
    assert body["weight_est_kg"] < piece["weight_est_kg"]
    corrected = body["events"][-1]
    assert corrected["actor"] == "Sami" and corrected["action"] == "corrected"
    assert corrected["data"]["size"]["from"] == [1999, 1500]


def test_remnant_cannot_grow_beyond_the_file(client, job):
    piece = remnant(job)
    response = client.patch(f"/v1/pieces/{piece['id']}", json={"width_mm": piece["width_mm"] + 50})
    assert response.status_code == 409


def test_scrap_lot_takes_a_weighed_value_but_no_dimensions(client, job):
    lot = scrap(job)
    assert (
        client.patch(f"/v1/pieces/{lot['id']}", json={"weight_actual_kg": 12.5}).status_code == 200
    )
    assert client.patch(f"/v1/pieces/{lot['id']}", json={"width_mm": 10}).status_code == 409


def test_approval_moves_drafts_to_stock_and_skips_rejected(client, job):
    first, *_ = [p for p in job["pieces"] if p["kind"] == "remnant"]
    client.patch(f"/v1/pieces/{first['id']}", json={"rejected": True})

    response = client.post(f"/v1/jobs/{job['id']}/approve", json={"actor": "Leila"})
    assert response.status_code == 200
    approved = response.json()
    assert approved["status"] == "approved" and approved["approved_by"] == "Leila"
    statuses = {p["id"]: p["status"] for p in approved["pieces"]}
    assert statuses[first["id"]] == "rejected"
    others = [p for p in approved["pieces"] if p["id"] != first["id"]]
    assert all(p["status"] == "in_stock" for p in others)
    review = date.fromisoformat(others[0]["review_date"])
    assert review == date.today() + timedelta(days=30)

    # Approved records are locked, and a job is approved only once.
    assert (
        client.patch(f"/v1/pieces/{others[0]['id']}", json={"weight_actual_kg": 1}).status_code
        == 409
    )
    assert client.post(f"/v1/jobs/{job['id']}/approve", json={}).status_code == 409
    # Location and notes can still change once in stock.
    moved = client.patch(f"/v1/pieces/{others[0]['id']}", json={"location": "Rack B3"})
    assert moved.status_code == 200 and moved.json()["location"] == "Rack B3"


def test_qr_code_lookup_is_case_insensitive(client, job):
    piece = remnant(job)
    found = client.get(f"/v1/codes/{piece['code'].lower()}")
    assert found.status_code == 200
    assert found.json()["job"]["file_name"] == job["file_name"]
    assert client.get("/v1/codes/RV-NOPE00").status_code == 404


def test_stock_lists_and_summarises_approved_pieces(client, job):
    assert client.get("/v1/stock").json()["pieces"] == []
    client.post(f"/v1/jobs/{job['id']}/approve", json={})
    stock = client.get("/v1/stock").json()["pieces"]
    assert len(stock) == len(job["pieces"])
    remnants_only = client.get("/v1/stock?kind=remnant").json()["pieces"]
    assert all(p["kind"] == "remnant" for p in remnants_only)

    summary = client.get("/v1/stock/summary").json()
    steel = summary["materials"][0]
    assert steel["material_code"] == "steel_mild"
    assert steel["remnant_count"] == job["remnant_count"]
    assert steel["scrap_lots"] == 1
    assert summary["totals"]["remnant_weight_kg"] == pytest.approx(
        job["remnant_weight_kg"], rel=1e-6
    )
    assert client.get("/v1/stock?status=bogus").status_code == 422
