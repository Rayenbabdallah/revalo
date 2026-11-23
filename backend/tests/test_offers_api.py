"""Buying offcuts that other workshops and suppliers offer to us."""

from __future__ import annotations

from datetime import UTC, datetime

from test_auth_api import add_person, sign_in
from test_opportunities import keep_in_mind

MONTH = datetime.now(UTC).strftime("%Y-%m")

OFFER = {
    "seller_name": "Nabil",
    "organization": "Atelier Nabil",
    "phone": "55 111 222",
    "governorate": "Sousse",
    "material_code": "steel_mild",
    "thickness_mm": 3,
    "width_mm": 300,
    "height_mm": 500,
    "quantity": 2,
    "price_tnd": 20,
}


def post_offer(client, **changes):
    response = client.post("/v1/supply-offers", json={**OFFER, **changes})
    assert response.status_code == 201, response.text
    return response.json()


def offers(client):
    return client.get("/v1/supply-offers").json()


def test_a_seller_posts_without_an_account_and_sees_nothing_of_ours(client):
    client.post("/v1/auth/logout")
    posted = post_offer(client)
    assert set(posted) == {"id", "status"} and posted["status"] == "open"
    assert client.get("/v1/supply-offers").status_code == 401

    sign_in(client, "slim@atelier.test", "steel-sheet-42")
    row = offers(client)["offers"][0]
    assert row["source"] == "public" and row["phone"] == "+21655111222"
    # Stored long side first, like remnants.
    assert (row["width_mm"], row["height_mm"]) == (500, 300)


def test_an_offer_is_valued_against_new_material(client):
    row = post_offer(client)  # a manager typing an offer received on WhatsApp
    assert row["source"] == "workshop"
    # Two 500 x 300 x 3 mm steel pieces: about 7 kg.
    assert 6.9 < row["weight_kg"] < 7.2
    assert row["new_tnd"] > row["price_tnd"] and row["saving_tnd"] > 0
    assert row["price_tnd_per_kg"] < 3
    assert row["distance_km"] and row["distance_km"] > 100  # Sousse from Ben Arous
    assert row["whatsapp_url"].startswith("https://wa.me/21655111222?text=")


def test_buying_puts_the_pieces_in_stock_with_seller_and_price(client):
    offer = post_offer(client)
    bought = client.patch(
        f"/v1/supply-offers/{offer['id']}", json={"action": "buy", "price_tnd": 18}
    ).json()
    assert bought["status"] == "bought" and bought["bought_price_tnd"] == 18

    stock = client.get("/v1/stock").json()["pieces"]
    mine = [p for p in stock if p["job_id"] == bought["intake_job_id"]]
    assert len(mine) == 2 and all(p["width_mm"] == 500 for p in mine)
    piece = client.get(f"/v1/pieces/{mine[0]['id']}").json()
    events = {e["action"]: e["data"] for e in piece["events"]}
    assert events["bought"] == {"seller": "Atelier Nabil", "price_tnd": 9, "material": "Mild steel"}

    summary = offers(client)["summary"]
    assert summary["bought"] == 1 and summary["spent_tnd"] == 18 and summary["saved_tnd"] > 0
    again = client.patch(f"/v1/supply-offers/{offer['id']}", json={"action": "buy"})
    assert again.status_code == 409


def test_an_offer_that_holds_a_coming_job_is_flagged(client):
    keep_in_mind(client)  # four 120 x 80 parts in 3 mm mild steel, nothing in stock
    post_offer(client, quantity=1, width_mm=400, height_mm=200)
    row = offers(client)["offers"][0]
    assert row["planned"][0]["name"] == "Order 2026-140"
    assert row["planned"][0]["extra_parts"] == 4

    alerts = client.get("/v1/alerts").json()["alerts"]
    flagged = [a for a in alerts if a["kind"] == "offer"]
    assert flagged and flagged[0]["link"] == "/market?tab=buying"
    assert "Atelier Nabil" in flagged[0]["title"]

    # Check before cutting: the racks are empty, so the offer is suggested instead.
    check = client.post(
        "/v1/stock/fit",
        data={
            "parts": '[{"length": 120, "width": 80, "qty": 4}]',
            "material": "steel_mild",
            "thickness_mm": "3",
        },
    ).json()
    assert check["placed_count"] == 0
    assert check["offers"][0]["placed_count"] == 4


def test_offers_of_another_material_are_not_suggested(client):
    keep_in_mind(client)
    post_offer(client, material_code="aluminium")
    assert offers(client)["offers"][0]["planned"] == []


def test_decline_and_reopen(client):
    offer = post_offer(client)
    url = f"/v1/supply-offers/{offer['id']}"
    assert client.patch(url, json={"action": "reopen"}).status_code == 409
    assert client.patch(url, json={"action": "decline"}).json()["status"] == "declined"
    assert client.patch(url, json={"action": "buy"}).status_code == 409
    assert client.patch(url, json={"action": "reopen"}).json()["status"] == "open"


def test_only_managers_buy(client):
    offer = post_offer(client)
    add_person(client, "Sami", "operator")
    sign_in(client, "sami@atelier.test")
    response = client.patch(f"/v1/supply-offers/{offer['id']}", json={"action": "buy"})
    assert response.status_code == 403
    # An operator posting is treated like the public.
    assert set(post_offer(client)) == {"id", "status"}


def test_bad_offers_are_refused_in_the_readers_language(client):
    response = client.post(
        "/v1/supply-offers",
        json={**OFFER, "governorate": "Atlantis"},
        headers={"Accept-Language": "fr"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "Gouvernorat inconnu : Atlantis"
    unknown = client.post("/v1/supply-offers", json={**OFFER, "material_code": "unobtainium"})
    assert unknown.status_code == 422


def test_the_report_counts_a_purchase_saving_once(client):
    offer = post_offer(client)
    bought = client.patch(
        f"/v1/supply-offers/{offer['id']}", json={"action": "buy", "price_tnd": 20}
    ).json()
    before = client.get(f"/v1/reports/monthly?month={MONTH}").json()
    saved = before["outcomes"]["bought"]["tnd"]
    assert before["outcomes"]["bought"]["offers"] == 1 and saved == offer["saving_tnd"]
    assert before["production"]["jobs"] == 0  # a purchase is not production

    pieces = [p["id"] for p in client.get("/v1/stock").json()["pieces"]]
    client.post("/v1/stock/fit/reuse", json={"piece_ids": pieces, "job_name": "Order 9"})
    after = client.get(f"/v1/reports/monthly?month={MONTH}").json()
    assert after["outcomes"]["reused"]["tnd"] == 0
    assert after["recovered_tnd"] == before["recovered_tnd"]

    job = client.get(f"/v1/jobs/{bought['intake_job_id']}").json()
    assert job["file_format"] == "purchase"
