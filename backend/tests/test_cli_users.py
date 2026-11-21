"""Accounts can be created from the command line, for the first setup on a server."""

from __future__ import annotations

from revalo import cli
from revalo.db import session as db_session
from revalo.settings import get_settings


def test_add_and_list_users(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("REVALO_DATABASE_URL", f"sqlite:///{(tmp_path / 'cli.db').as_posix()}")
    for cached in (get_settings, db_session.get_engine, db_session._session_factory):
        cached.cache_clear()
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: "rack-and-roll-9")
    try:
        args = ["users", "add", "--email", "Hela@Atelier.test", "--name", "Hela", "--role", "owner"]
        assert cli.main(args) == 0
        assert cli.main(["users", "add", "--email", "hela@atelier.test", "--name", "H"]) == 1
        assert cli.main(["users", "list"]) == 0
    finally:
        for cached in (get_settings, db_session.get_engine, db_session._session_factory):
            cached.cache_clear()
    out = capsys.readouterr()
    assert "Added Hela <hela@atelier.test> as owner." in out.out
    assert "owner     hela@atelier.test" in out.out
    assert "already has an account" in out.err
