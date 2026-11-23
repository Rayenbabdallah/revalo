"""The same program sent twice: a mistake to catch, or a real repeat run to record."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from test_jobs_api import nest_bytes
from test_jobs_api import upload as upload_file

from revalo.db.models import Job, JobStatus
from revalo.services.jobs import likely_answer

NEST = nest_bytes()  # one file, sent several times: same bytes, same fingerprint


def upload(client, **fields):
    return upload_file(client, data=NEST, **fields)


def remnants(job):
    return [p for p in job["pieces"] if p["kind"] == "remnant"]


def test_a_known_file_asks_instead_of_duplicating(client):
    first = upload(client).json()
    again = upload(client)
    assert again.status_code == 409
    detail = again.json()["detail"]
    assert detail["code"] == "repeat_run"
    assert detail["suggest"] == "same"  # minutes old and still in review: a double send
    assert detail["jobs"][0]["id"] == first["id"]
    assert detail["jobs"][0]["created_by"] == "Slim"
    assert len(client.get("/v1/jobs").json()["jobs"]) == 1


def test_a_confirmed_repeat_run_is_recorded_and_linked(client):
    first = upload(client).json()
    client.post(f"/v1/jobs/{first['id']}/approve")
    asked = upload(client).json()["detail"]
    assert asked["suggest"] == "new"  # approved earlier: most likely cut again

    second = upload(client, repeat="new")
    assert second.status_code == 201, second.text
    run2 = second.json()
    assert run2["repeat_of_id"] == first["id"]
    assert len(remnants(run2)) == len(remnants(first))
    codes = {p["code"] for p in run2["pieces"]} | {p["code"] for p in first["pieces"]}
    assert len(codes) == len(run2["pieces"]) + len(first["pieces"])


def test_several_sheets_cut_with_one_program(client):
    one = upload(client, name="a.dxf").json()
    three = upload(client, name="b.dxf", runs="3", repeat="new").json()
    assert three["runs"] == 3
    assert three["sheet_count"] == one["sheet_count"] * 3
    assert len(three["pieces"]) == len(one["pieces"]) * 3
    assert sorted({p["run_index"] for p in three["pieces"]}) == [0, 1, 2]
    assert upload(client, name="c.dxf", runs="0", repeat="new").status_code == 422


def test_last_runs_corrections_apply_in_one_step(client):
    first = upload(client).json()
    remnant = remnants(first)[0]
    scrap = next(p for p in first["pieces"] if p["kind"] == "scrap")
    client.patch(f"/v1/pieces/{scrap['id']}", json={"rejected": True})
    trimmed = {
        "width_mm": remnant["width_mm"] - 20,
        "weight_actual_kg": 5.5,
        "condition_note": "Bent corner",
    }
    assert client.patch(f"/v1/pieces/{remnant['id']}", json=trimmed).status_code == 200
    client.post(f"/v1/jobs/{first['id']}/approve")

    run2 = upload(client, repeat="new").json()
    copied = client.post(f"/v1/jobs/{run2['id']}/copy-corrections")
    assert copied.status_code == 200, copied.text
    body = copied.json()
    assert body["copied"] == 2
    by_label = {p["label"]: p for p in body["pieces"]}
    assert by_label[scrap["label"]]["status"] == "rejected"
    fixed = by_label[remnant["label"]]
    assert fixed["width_mm"] == trimmed["width_mm"]
    assert fixed["weight_actual_kg"] == 5.5 and fixed["condition_note"] == "Bent corner"


def test_copy_needs_a_repeat_run(client):
    job = upload(client).json()
    assert client.post(f"/v1/jobs/{job['id']}/copy-corrections").status_code == 409


def test_old_drafts_count_as_repeats():
    now = datetime.now(UTC)
    fresh = Job(status=JobStatus.DRAFT, created_at=now - timedelta(minutes=10))
    stale = Job(status=JobStatus.DRAFT, created_at=now - timedelta(days=2))
    assert likely_answer(fresh, now) == "same"
    assert likely_answer(stale, now) == "new"
