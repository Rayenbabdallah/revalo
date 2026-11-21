def prices(client):
    return {p["material_code"]: p for p in client.get("/v1/prices").json()["prices"]}


def test_defaults_come_from_the_library_with_their_sources(client):
    book = prices(client)
    steel = book["steel_mild"]
    assert steel["new_tnd_per_kg"] == 3.0 and not steel["custom"]
    assert "El Fouladh" in steel["source"]
    assert steel["co2_primary_kg_per_kg"] == 1.92
    # No invented numbers: materials without a sourced price stay empty.
    assert book["stainless_304"]["new_tnd_per_kg"] is None


def test_workshop_sets_and_resets_its_own_price(client):
    body = {
        "new_tnd_per_kg": 14.5,
        "scrap_tnd_per_kg": 3.2,
        "resale_factor": 0.45,
        "source": "Quote from supplier, Nov 2026",
        "actor": "Leila",
    }
    saved = client.put("/v1/prices/stainless_304", json=body).json()
    assert saved["custom"] and saved["new_tnd_per_kg"] == 14.5 and saved["updated_by"] == "Leila"
    assert prices(client)["stainless_304"]["source"] == "Quote from supplier, Nov 2026"

    reset = client.delete("/v1/prices/stainless_304").json()
    assert not reset["custom"] and reset["new_tnd_per_kg"] is None


def test_impossible_prices_are_rejected(client):
    bad = {"new_tnd_per_kg": 2.0, "scrap_tnd_per_kg": 3.0, "resale_factor": 0.4}
    assert client.put("/v1/prices/steel_mild", json=bad).status_code == 422
    assert (
        client.put("/v1/prices/unobtainium", json={**bad, "scrap_tnd_per_kg": 1}).status_code == 422
    )
    over = {"new_tnd_per_kg": 2.0, "scrap_tnd_per_kg": 0.1, "resale_factor": 1.5}
    assert client.put("/v1/prices/steel_mild", json=over).status_code == 422
