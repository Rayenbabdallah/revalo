"""Remnants exported as DXF sheets for nesting software."""

from __future__ import annotations

import io

import ezdxf

ROWS = [
    {
        "material": "steel_mild",
        "thickness_mm": 3,
        "width_mm": 1200,
        "height_mm": 800,
        "quantity": 2,
    },
    {"material": "steel_mild", "thickness_mm": 3, "width_mm": 450, "height_mm": 300},
    {"material": "mdf", "thickness_mm": 18, "width_mm": 900, "height_mm": 600},
    {"material": "steel_mild", "thickness_mm": 3, "kind": "scrap", "weight_kg": 20},
]


def outlines(data: bytes):
    doc = ezdxf.read(io.StringIO(data.decode("utf-8")))
    assert doc.header["$INSUNITS"] == 4
    sizes = []
    for e in doc.modelspace().query('LWPOLYLINE[layer=="REMNANT"]'):
        xs = [p[0] for p in e.get_points()]
        ys = [p[1] for p in e.get_points()]
        assert e.closed
        sizes.append((round(max(xs) - min(xs)), round(max(ys) - min(ys))))
    return sorted(sizes), doc


def test_stock_remnants_of_one_material_export_at_real_size(client):
    client.post("/v1/stock/intake", json={"rows": ROWS})
    response = client.get(
        "/v1/stock/remnants.dxf", params={"material": "steel_mild", "thickness_mm": 3}
    )
    assert response.status_code == 200
    assert "remnants_steel_mild_3mm_3.dxf" in response.headers["content-disposition"]
    sizes, doc = outlines(response.content)
    assert sizes == [(450, 300), (1200, 800), (1200, 800)]
    labels = [t.dxf.text for t in doc.modelspace().query('TEXT[layer=="LABEL"]')]
    assert any(text.startswith("RV-") and "1200x800" in text for text in labels)


def test_one_remnant_exports_alone_and_scrap_has_no_outline(client):
    pieces = client.post("/v1/stock/intake", json={"rows": ROWS}).json()["pieces"]
    remnant = next(p for p in pieces if p["material_code"] == "mdf")
    scrap = next(p for p in pieces if p["kind"] == "scrap")
    one = client.get(f"/v1/pieces/{remnant['id']}/remnant.dxf")
    assert one.status_code == 200 and remnant["code"] in one.headers["content-disposition"]
    assert outlines(one.content)[0] == [(900, 600)]
    assert client.get(f"/v1/pieces/{scrap['id']}/remnant.dxf").status_code == 404
    assert client.get("/v1/stock/remnants.dxf", params={"material": "copper"}).status_code == 404
