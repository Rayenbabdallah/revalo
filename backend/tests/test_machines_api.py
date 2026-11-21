from test_jobs_api import nest_bytes

FIBRE = {
    "name": "Fibre laser 3 kW",
    "process": "fiber_laser",
    "material_code": "steel_mild",
    "thickness_mm": 3,
    "kerf_mm": 0.25,
    "sheet_width_mm": 3000,
    "sheet_height_mm": 1500,
}


def test_create_list_and_retire_a_machine(client):
    created = client.post("/v1/machines", json=FIBRE)
    assert created.status_code == 201, created.text
    machine = created.json()
    assert machine["material_name"]["fr"] == "Acier doux"
    assert [m["name"] for m in client.get("/v1/machines").json()["machines"]] == [
        "Fibre laser 3 kW"
    ]

    retired = client.put(f"/v1/machines/{machine['id']}", json={**FIBRE, "active": False})
    assert retired.json()["active"] is False
    assert client.get("/v1/machines").json()["machines"] == []
    assert len(client.get("/v1/machines?include_inactive=true").json()["machines"]) == 1


def test_bad_presets_are_rejected(client):
    assert client.post("/v1/machines", json={**FIBRE, "process": "teleport"}).status_code == 422
    assert client.post("/v1/machines", json={**FIBRE, "material_code": "gold"}).status_code == 422
    half_sheet = {**FIBRE, "sheet_height_mm": None}
    assert client.post("/v1/machines", json=half_sheet).status_code == 422


def test_upload_with_a_machine_needs_no_typing(client):
    machine = client.post("/v1/machines", json=FIBRE).json()
    # A file name that says nothing about material or thickness.
    response = client.post(
        "/v1/jobs",
        files={"file": ("job_118.dxf", nest_bytes(), "application/dxf")},
        data={"machine_id": machine["id"]},
    )
    assert response.status_code == 201, response.text
    job = response.json()
    assert job["machine_id"] == machine["id"]
    assert job["material_code"] == "steel_mild" and job["thickness_mm"] == 3
    assert job["analysis"]["kerf_mm"] == 0.25
    assert job["analysis"]["process"] == "fiber_laser"


def test_typed_values_override_the_preset(client):
    machine = client.post("/v1/machines", json=FIBRE).json()
    job = client.post(
        "/v1/jobs",
        files={"file": ("job_119.dxf", nest_bytes(), "application/dxf")},
        data={"machine_id": machine["id"], "thickness_mm": "5"},
    ).json()
    assert job["thickness_mm"] == 5


def test_unknown_machine_is_rejected(client):
    response = client.post(
        "/v1/jobs",
        files={"file": ("x.dxf", nest_bytes(), "application/dxf")},
        data={"machine_id": "nope"},
    )
    assert response.status_code == 422
