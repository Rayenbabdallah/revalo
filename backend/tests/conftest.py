"""Shared fixtures: an API client backed by a fresh database and file store."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from revalo.db import session as db_session
from revalo.settings import get_settings

OWNER = {"name": "Slim", "email": "slim@atelier.test", "password": "steel-sheet-42"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("REVALO_DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setenv("REVALO_STORAGE_DIR", str(tmp_path / "files"))
    monkeypatch.setenv("REVALO_PUBLIC_URL", "https://app.example.test")
    for cached in (get_settings, db_session.get_engine, db_session._session_factory):
        cached.cache_clear()
    from revalo.api.main import app

    with TestClient(app) as test_client:  # runs startup, which applies migrations
        # Tests act as the workshop owner unless they sign out or switch user.
        response = test_client.post("/v1/auth/setup", json=OWNER)
        assert response.status_code == 201, response.text
        yield test_client
    for cached in (get_settings, db_session.get_engine, db_session._session_factory):
        cached.cache_clear()
