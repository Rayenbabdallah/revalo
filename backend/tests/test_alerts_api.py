from test_jobs_api import upload
from test_market_api import BUYER


def kinds(client):
    return [a["kind"] for a in client.get("/v1/alerts").json()["alerts"]]


def test_alerts_follow_the_work(client):
    assert kinds(client) == []
    job = upload(client).json()
    assert kinds(client) == ["review"]
    assert client.get("/v1/alerts").json()["alerts"][0]["link"] == f"/jobs/{job['id']}"

    client.post(f"/v1/jobs/{job['id']}/approve", json={})
    # The scrap lot is ready for a recycler; nothing to review any more.
    assert kinds(client) == ["recycle"]

    remnant = next(p for p in job["pieces"] if p["kind"] == "remnant")
    client.post(f"/v1/pieces/{remnant['id']}/listing", json={"price_tnd": 80})
    client.post("/v1/buyer-requests", json=BUYER)
    assert set(kinds(client)) == {"recycle", "match", "buyer"}
