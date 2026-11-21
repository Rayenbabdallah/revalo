"""Accounts: first-run setup, sign-in, roles, and the owner's list of people."""

from __future__ import annotations

import pytest
from conftest import OWNER
from sqlalchemy import select
from test_jobs_api import upload as upload_nest

from revalo.api.deps import COOKIE
from revalo.db.models import AuthSession
from revalo.db.session import _session_factory
from revalo.services.auth import hash_password, throttle, verify_password

PASSWORD = "cut-twice-77"


def sign_in(client, email, password=PASSWORD):
    client.post("/v1/auth/logout")
    response = client.post("/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["user"]


def add_person(client, name, role):
    email = f"{name.lower()}@atelier.test"
    body = {"email": email, "name": name, "role": role, "password": PASSWORD}
    response = client.post("/v1/users", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def upload(client):
    response = upload_nest(client)
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture(autouse=True)
def _fresh_throttle():
    throttle._failures.clear()
    yield
    throttle._failures.clear()


def test_passwords_are_salted_hashes():
    stored = hash_password(PASSWORD)
    assert PASSWORD not in stored and stored != hash_password(PASSWORD)
    assert verify_password(PASSWORD, stored)
    assert not verify_password("cut-twice-78", stored)
    assert not verify_password(PASSWORD, "not-a-hash")


def test_setup_creates_the_owner_once(client):
    me = client.get("/v1/auth/me").json()
    assert me["user"]["name"] == "Slim" and me["user"]["role"] == "owner"
    assert me["setup_required"] is False

    again = client.post("/v1/auth/setup", json={**OWNER, "email": "other@atelier.test"})
    assert again.status_code == 409


def test_the_database_keeps_only_a_hash_of_the_session_token(client):
    token = client.cookies.get(COOKIE)
    assert token
    with _session_factory()() as session:
        stored = [row.token_hash for row in session.scalars(select(AuthSession))]
    assert stored and token not in stored


def test_signed_out_visitors_reach_only_public_pages(client):
    client.post("/v1/auth/logout")
    assert client.get("/v1/auth/me").json()["user"] is None
    for path in ("/v1/jobs", "/v1/stock", "/v1/alerts", "/v1/listings", "/v1/users"):
        assert client.get(path).status_code == 401, path

    for path in ("/health", "/v1/materials", "/v1/market", "/v1/geo/governorates", "/v1/samples"):
        assert client.get(path).status_code == 200, path
    request = {
        "kind": "reuse",
        "name": "Karim",
        "phone": "+216 20 000 000",
        "governorate": "Tunis",
        "materials": ["steel_mild"],
    }
    assert client.post("/v1/buyer-requests", json=request).status_code == 201


def test_wrong_passwords_are_refused_then_slowed_down(client):
    client.post("/v1/auth/logout")
    wrong = {"email": OWNER["email"], "password": "not-the-password"}
    for _ in range(5):
        assert client.post("/v1/auth/login", json=wrong).status_code == 401
    right = {"email": OWNER["email"], "password": OWNER["password"]}
    assert client.post("/v1/auth/login", json=right).status_code == 429


def test_unknown_email_gets_the_same_answer_as_a_wrong_password(client):
    client.post("/v1/auth/logout")
    response = client.post("/v1/auth/login", json={"email": "nobody@x.test", "password": "x" * 9})
    assert response.status_code == 401
    assert response.json()["detail"] == "Wrong email or password."


def test_operator_records_but_cannot_approve_sell_or_price(client):
    add_person(client, "Sami", "operator")
    sign_in(client, "sami@atelier.test")

    job = upload(client)
    piece = job["pieces"][0]
    created = client.get(f"/v1/pieces/{piece['id']}").json()["events"][0]
    assert created["actor"] == "Sami"
    moved = client.patch(f"/v1/pieces/{piece['id']}", json={"location": "Rack B"})
    assert moved.status_code == 200 and moved.json()["events"][-1]["actor"] == "Sami"

    assert client.post(f"/v1/jobs/{job['id']}/approve").status_code == 403
    assert client.post(f"/v1/pieces/{piece['id']}/listing", json={}).status_code == 403
    price = {"new_tnd_per_kg": 3.5, "scrap_tnd_per_kg": 0.3, "resale_factor": 0.4}
    assert client.put("/v1/prices/steel_mild", json=price).status_code == 403
    assert client.get("/v1/reports/monthly").status_code == 403
    assert client.get("/v1/users").status_code == 403
    assert client.get("/v1/alerts").json() == {"alerts": []}


def test_manager_approves_in_their_own_name_but_cannot_manage_people(client):
    job = upload(client)
    add_person(client, "Leila", "manager")
    sign_in(client, "leila@atelier.test")

    approved = client.post(f"/v1/jobs/{job['id']}/approve")
    assert approved.status_code == 200 and approved.json()["approved_by"] == "Leila"
    assert client.get("/v1/users").status_code == 403
    assert client.post("/v1/users", json={}).status_code == 403


def test_owner_lists_promotes_and_removes_people(client):
    sami = add_person(client, "Sami", "operator")
    duplicate = {"email": "SAMI@atelier.test", "name": "Sami 2", "password": PASSWORD}
    assert client.post("/v1/users", json=duplicate).status_code == 422

    people = client.get("/v1/users").json()["users"]
    assert [p["name"] for p in people] == ["Slim", "Sami"]

    promoted = client.patch(f"/v1/users/{sami['id']}", json={"role": "manager"})
    assert promoted.json()["role"] == "manager"

    # Removing someone signs them out at once.
    sign_in(client, "sami@atelier.test")
    assert client.get("/v1/jobs").status_code == 200
    sami_cookie = client.cookies.get(COOKIE)
    sign_in(client, OWNER["email"], OWNER["password"])
    assert client.patch(f"/v1/users/{sami['id']}", json={"active": False}).status_code == 200
    client.cookies.set(COOKIE, sami_cookie)
    assert client.get("/v1/jobs").status_code == 401
    client.cookies.clear()
    gone = {"email": "sami@atelier.test", "password": PASSWORD}
    assert client.post("/v1/auth/login", json=gone).status_code == 401


def test_the_last_owner_cannot_be_removed_or_demoted(client):
    me = client.get("/v1/auth/me").json()["user"]
    assert client.patch(f"/v1/users/{me['id']}", json={"role": "manager"}).status_code == 422
    assert client.patch(f"/v1/users/{me['id']}", json={"active": False}).status_code == 422

    add_person(client, "Hela", "owner")
    assert client.patch(f"/v1/users/{me['id']}", json={"role": "manager"}).status_code == 200


def test_people_change_their_own_password(client):
    short = {"current": OWNER["password"], "new": "short"}
    assert client.post("/v1/auth/password", json=short).status_code == 422
    wrong = {"current": "not-it-at-all", "new": "a-new-password-1"}
    assert client.post("/v1/auth/password", json=wrong).status_code == 422
    ok = {"current": OWNER["password"], "new": "a-new-password-1"}
    assert client.post("/v1/auth/password", json=ok).status_code == 204
    sign_in(client, OWNER["email"], "a-new-password-1")
