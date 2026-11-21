from dxf_helpers import new_doc, rect, to_bytes


def nest_bytes():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 0, 0, 3000, 1500, layer="SHEET")
    for i in range(5):
        rect(msp, 0, i * 300, 1000, 290)
    return to_bytes(doc)


def upload(client, name="Tole_S235_3mm.dxf", data=None, **fields):
    return client.post(
        "/v1/jobs",
        files={"file": (name, data or nest_bytes(), "application/dxf")},
        data=fields,
    )


def test_upload_creates_job_with_draft_records(client):
    response = upload(client)
    assert response.status_code == 201, response.text
    job = response.json()
    assert job["status"] == "draft"
    assert job["material_code"] == "steel_mild"
    assert job["part_count"] == 5

    kinds = [p["kind"] for p in job["pieces"]]
    assert kinds.count("remnant") == job["remnant_count"] >= 1
    assert kinds.count("scrap") == 1
    remnant = job["pieces"][0]
    assert remnant["status"] == "draft"
    assert remnant["code"].startswith("RV-")
    assert remnant["label_url"] == f"https://app.example.test/p/{remnant['code']}"
    assert remnant["width_mm"] == 1999 and remnant["weight_kg"] > 70
    assert job["analysis"]["sheets"][0]["geometry"]["parts"]


def test_jobs_are_listed_newest_first_and_can_be_opened(client):
    first = upload(client, "a_S235_3mm.dxf").json()
    second = upload(client, "b_S235_3mm.dxf").json()
    listed = client.get("/v1/jobs").json()["jobs"]
    assert [j["id"] for j in listed][:2] == [second["id"], first["id"]]
    opened = client.get(f"/v1/jobs/{first['id']}").json()
    assert opened["file_name"] == "a_S235_3mm.dxf"
    assert client.get("/v1/jobs/missing").status_code == 404


def test_same_file_is_stored_once(client, tmp_path):
    data = nest_bytes()  # generated once: DXF headers carry a timestamp
    upload(client, data=data)
    upload(client, data=data)
    stored = [p for p in (tmp_path / "files").rglob("*") if p.is_file()]
    assert len(stored) == 1


def test_bad_upload_is_rejected_without_saving(client):
    response = upload(client, "bad.dxf", data=b"not a dxf")
    assert response.status_code == 422
    assert client.get("/v1/jobs").json()["jobs"] == []
