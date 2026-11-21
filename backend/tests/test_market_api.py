import pytest
from test_jobs_api import upload

from revalo.settings import get_settings

BUYER = {
    "kind": "reuse",
    "name": "Atelier Karim",
    "organization": "Menuiserie métallique",
    "phone": "22 123 456",
    "governorate": "tunis",
    "materials": ["steel_mild"],
    "thickness_min_mm": 2,
    "thickness_max_mm": 4,
    "min_length_mm": 600,
    "min_width_mm": 400,
    "max_price_tnd_per_kg": 2.0,
}


@pytest.fixture
def stock(client):
    job = upload(client).json()
    client.post(f"/v1/jobs/{job['id']}/approve", json={})
    pieces = client.get(f"/v1/jobs/{job['id']}").json()["pieces"]
    remnant = next(p for p in pieces if p["kind"] == "remnant")
    lot = next(p for p in pieces if p["kind"] == "scrap")
    return remnant, lot


def test_listing_uses_the_sale_value_as_asking_price(client, stock):
    remnant, _ = stock
    response = client.post(f"/v1/pieces/{remnant['id']}/listing", json={"actor": "Slim"})
    assert response.status_code == 201, response.text
    listing = response.json()
    sell = next(o for o in remnant["decision"]["options"] if o["action"] == "sell")
    # Asking price is the net sale value grossed up for the 5% commission.
    assert listing["price_tnd"] == pytest.approx(sell["value_tnd"] / 0.95, abs=0.1)
    assert listing["status"] == "open"
    assert client.post(f"/v1/pieces/{remnant['id']}/listing", json={}).status_code == 409

    piece = client.get(f"/v1/pieces/{remnant['id']}").json()
    assert piece["listing"]["status"] == "open"
    assert piece["events"][-1]["action"] == "listed"


def test_draft_pieces_cannot_be_listed(client):
    job = upload(client).json()
    draft = job["pieces"][0]
    assert client.post(f"/v1/pieces/{draft['id']}/listing", json={}).status_code == 409


def test_buyer_posts_a_need_and_sees_matching_listings(client, stock):
    remnant, _ = stock
    client.post(f"/v1/pieces/{remnant['id']}/listing", json={"price_tnd": 80})
    response = client.post("/v1/buyer-requests", json=BUYER)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["phone"] == "+21622123456"
    assert body["governorate"] == "Tunis"
    assert [lst["piece"]["code"] for lst in body["matching_listings"]] == [remnant["code"]]
    assert "buyer" not in body["matching_listings"][0]


@pytest.mark.parametrize(
    ("field", "value"),
    [("governorate", "Atlantis"), ("phone", "123"), ("materials", ["unobtainium"])],
)
def test_bad_buyer_requests_are_rejected(client, field, value):
    assert client.post("/v1/buyer-requests", json={**BUYER, field: value}).status_code == 422


def test_workshop_sees_ranked_matches_with_whatsapp_links(client, stock):
    remnant, _ = stock
    client.post(f"/v1/pieces/{remnant['id']}/listing", json={"price_tnd": 80})
    client.post("/v1/buyer-requests", json=BUYER)
    client.post("/v1/buyer-requests", json={**BUYER, "name": "Sfax Metal", "governorate": "Sfax"})
    client.post(
        "/v1/buyer-requests", json={**BUYER, "name": "Inox only", "materials": ["stainless_304"]}
    )

    data = client.get("/v1/listings").json()
    listing = data["listings"][0]
    assert listing["match_count"] == 2
    top = listing["top_matches"][0]
    assert top["request"]["name"] == "Atelier Karim"  # closer than Sfax
    assert top["whatsapp_url"].startswith("https://wa.me/21622123456?text=Bonjour")
    assert remnant["code"] in top["whatsapp_url"]
    assert data["summary"]["open"] == 1 and data["summary"]["active_requests"] == 3


def test_deal_lifecycle_reserve_reopen_sell(client, stock):
    remnant, _ = stock
    listing = client.post(f"/v1/pieces/{remnant['id']}/listing", json={"price_tnd": 80}).json()
    buyer = client.post("/v1/buyer-requests", json=BUYER).json()
    url = f"/v1/listings/{listing['id']}"

    reserved = client.patch(url, json={"action": "reserve", "buyer_request_id": buyer["id"]}).json()
    assert reserved["status"] == "reserved" and reserved["buyer"]["name"] == "Atelier Karim"
    assert client.get(f"/v1/pieces/{remnant['id']}").json()["status"] == "reserved"

    assert client.patch(url, json={"action": "reopen"}).json()["status"] == "open"
    sold = client.patch(
        url, json={"action": "sell", "price_tnd": 75, "buyer_request_id": buyer["id"]}
    ).json()
    assert sold["status"] == "sold" and sold["sold_price_tnd"] == 75 and sold["fee_tnd"] == 3.75
    piece = client.get(f"/v1/pieces/{remnant['id']}").json()
    assert piece["status"] == "sold"
    assert [e["action"] for e in piece["events"]][-4:] == [
        "listed",
        "listing_reserve",
        "listing_reopen",
        "listing_sell",
    ]
    assert client.patch(url, json={"action": "withdraw"}).status_code == 409
    summary = client.get("/v1/listings").json()["summary"]
    assert summary["sold"] == 1 and summary["sales_tnd"] == 75 and summary["fees_tnd"] == 3.75


def test_withdrawn_piece_returns_to_stock_and_can_be_relisted(client, stock):
    remnant, _ = stock
    listing = client.post(f"/v1/pieces/{remnant['id']}/listing", json={"price_tnd": 80}).json()
    client.patch(f"/v1/listings/{listing['id']}", json={"action": "withdraw"})
    assert client.get(f"/v1/pieces/{remnant['id']}").json()["status"] == "in_stock"
    again = client.post(f"/v1/pieces/{remnant['id']}/listing", json={"price_tnd": 70})
    assert again.status_code == 201 and again.json()["price_tnd"] == 70


def test_scrap_lot_goes_to_a_recycler(client, stock):
    _, lot = stock
    listing = client.post(f"/v1/pieces/{lot['id']}/listing", json={}).json()
    recycler = {
        "kind": "recycler",
        "name": "Récupération Ben Arous",
        "phone": "+216 98 765 432",
        "governorate": "Ben Arous",
        "materials": ["steel_mild"],
    }
    client.post("/v1/buyer-requests", json=recycler)
    client.post("/v1/buyer-requests", json=BUYER)  # a reuse buyer never gets a scrap lot
    matches = client.get(f"/v1/listings/{listing['id']}/matches").json()["matches"]
    assert [m["request"]["kind"] for m in matches] == ["recycler"]
    assert "Same governorate." in matches[0]["reasons"]

    client.patch(f"/v1/listings/{listing['id']}", json={"action": "sell"})
    assert client.get(f"/v1/pieces/{lot['id']}").json()["status"] == "recycled"


def test_public_market_shows_open_listings_and_workshop_contact(client, stock, monkeypatch):
    remnant, _ = stock
    client.post(f"/v1/pieces/{remnant['id']}/listing", json={"price_tnd": 80})
    public = client.get("/v1/market").json()["listings"]
    assert len(public) == 1 and public[0]["contact_url"] is None
    assert "buyer" not in public[0] and "piece_id" not in public[0]

    monkeypatch.setenv("REVALO_WORKSHOP_PHONE", "+21671000000")
    get_settings.cache_clear()
    public = client.get("/v1/market").json()["listings"]
    assert public[0]["contact_url"].startswith("https://wa.me/21671000000?text=Bonjour")
    assert client.get("/v1/geo/governorates").json()["governorates"][0] == "Tunis"
