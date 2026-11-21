from dxf_helpers import new_doc, rect, to_bytes
from fastapi.testclient import TestClient

from revalo.api.main import app

client = TestClient(app)


def nest_bytes():
    doc = new_doc()
    msp = doc.modelspace()
    rect(msp, 0, 0, 3000, 1500, layer="SHEET")
    rect(msp, 0, 0, 1000, 1500)
    return to_bytes(doc)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_materials():
    data = client.get("/v1/materials").json()
    assert any(m["code"] == "mdf" for m in data["materials"])
    assert any(p["code"] == "plasma" for p in data["processes"])


def test_analyze_dxf_with_form_options_and_svg():
    response = client.post(
        "/v1/analyze?include_svg=true",
        files={"file": ("nest.dxf", nest_bytes(), "application/dxf")},
        data={"material": "stainless_304", "thickness_mm": "2", "process": "fiber_laser"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["material"]["code"] == "stainless_304"
    assert body["kerf_mm"] == 0.2
    assert body["sheets"][0]["remnants"][0]["weight_kg"] > 0
    assert body["svg"].startswith("<svg")


def test_analyze_rejects_bad_input():
    bad = client.post("/v1/analyze", files={"file": ("x.dxf", b"garbage", "application/dxf")})
    assert bad.status_code == 422
    unknown = client.post(
        "/v1/analyze",
        files={"file": ("nest.dxf", nest_bytes(), "application/dxf")},
        data={"material": "gold"},
    )
    assert unknown.status_code == 422
    negative = client.post(
        "/v1/analyze",
        files={"file": ("nest.dxf", nest_bytes(), "application/dxf")},
        data={"thickness_mm": "-1"},
    )
    assert negative.status_code == 422


def test_sample_catalogue_and_download():
    samples = client.get("/v1/samples").json()["samples"]
    assert any(s["name"] == "laser_S235_3mm_3000x1500.dxf" for s in samples)
    public = [s for s in samples if s["collection"] == "public"]
    assert public and all(s["licence"] for s in public)

    first = samples[0]
    response = client.get(f"/v1/samples/{first['id']}")
    assert response.status_code == 200
    assert len(response.content) == first["size"]


def test_sample_ids_cannot_escape_the_catalogue():
    assert client.get("/v1/samples/..__..__pyproject.toml").status_code == 404
    assert client.get("/v1/samples/catalog.json").status_code == 404
