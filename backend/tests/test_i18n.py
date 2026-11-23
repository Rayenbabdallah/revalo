"""Server-written text follows the reader's language."""

from __future__ import annotations

from test_jobs_api import upload

from revalo.i18n import num, parse_accept_language, reset_lang, set_lang, tr, trn


def test_accept_language_picks_a_supported_language():
    assert parse_accept_language("fr-TN,fr;q=0.9,en;q=0.8") == "fr"
    assert parse_accept_language("ar") == "ar"
    assert parse_accept_language("de-DE,de") == "en"
    assert parse_accept_language(None) == "en"


def test_numbers_and_plurals_per_language():
    token = set_lang("fr")
    try:
        assert num(1234.5, 1) == "1 234,5"
        two = trn("{count} new buyer request|{count} new buyer requests", 2)
        assert two.startswith("2 nouvelles")
    finally:
        reset_lang(token)
    token = set_lang("ar")
    try:
        assert trn("{count} new buyer request|{count} new buyer requests", 2) == "طلبا شراء جديدان"
        assert trn("{count} new buyer request|{count} new buyer requests", 5).startswith("5 ")
    finally:
        reset_lang(token)
    assert tr("Sign in to continue.") == "Sign in to continue."


def test_errors_and_decisions_come_back_in_french(client):
    job = upload(client).json()
    piece = job["pieces"][0]["id"]
    fr = {"Accept-Language": "fr"}

    reasons = client.get(f"/v1/pieces/{piece}", headers=fr).json()["decision"]["reasons"]
    assert reasons and all("kg" in r or "TND" in r or "ferraille" in r for r in reasons)
    english = client.get(f"/v1/pieces/{piece}").json()["decision"]["reasons"]
    assert reasons != english

    client.post("/v1/auth/logout")
    denied = client.get("/v1/jobs", headers=fr)
    assert denied.status_code == 401
    assert denied.json()["detail"] == "Connectez-vous pour continuer."
    assert client.get("/v1/jobs", headers={"Accept-Language": "ar"}).json()["detail"] == (
        "سجّل الدخول للمتابعة."
    )
