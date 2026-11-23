"""The demo seed builds a believable workshop, and only on an empty database."""

from __future__ import annotations

from revalo import cli
from revalo.db import session as db_session
from revalo.settings import get_settings


def _fresh(tmp_path, monkeypatch):
    monkeypatch.setenv("REVALO_DATABASE_URL", f"sqlite:///{(tmp_path / 'demo.db').as_posix()}")
    monkeypatch.setenv("REVALO_STORAGE_DIR", str(tmp_path / "files"))
    monkeypatch.setenv("REVALO_DEMO_PASSWORD", "demo-password-1")
    for cached in (get_settings, db_session.get_engine, db_session._session_factory):
        cached.cache_clear()


def test_demo_seeds_once_and_signs_in(tmp_path, monkeypatch, capsys):
    _fresh(tmp_path, monkeypatch)
    try:
        assert cli.main(["demo"]) == 0
        assert cli.main(["demo"]) == 1  # never on a database that has accounts
        out = capsys.readouterr()
        assert "Demo workshop ready: 4 jobs" in out.out
        assert "owner     slim@atelier-demo.test" in out.out
        assert "already has accounts" in out.err

        from fastapi.testclient import TestClient

        from revalo.api.main import app

        with TestClient(app) as client:
            login = {"email": "leila@atelier-demo.test", "password": "demo-password-1"}
            assert client.post("/v1/auth/login", json=login).status_code == 200
            jobs = client.get("/v1/jobs").json()["jobs"]
            assert sorted(j["status"] for j in jobs) == [
                "approved",
                "approved",
                "approved",
                "draft",
            ]
            market = client.get("/v1/listings").json()["summary"]
            assert market["sold"] == 1 and market["open"] >= 1
            kinds = {a["kind"] for a in client.get("/v1/alerts").json()["alerts"]}
            assert {"review", "pickup"} <= kinds
            report = client.get("/v1/reports/monthly").json()
            assert report["recovered_tnd"] > 0 and report["outcomes"]["recycled"]["pickups"] == 1
    finally:
        for cached in (get_settings, db_session.get_engine, db_session._session_factory):
            cached.cache_clear()
