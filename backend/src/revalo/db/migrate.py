"""Run database migrations from code (app startup, tests, CLI)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from revalo.settings import BACKEND_DIR, get_settings


def alembic_config(database_url: str | None = None) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.attributes["database_url"] = database_url or get_settings().database_url
    config.attributes["configure_logging"] = False
    return config


def upgrade(database_url: str | None = None) -> None:
    url = database_url or get_settings().database_url
    if url.startswith("sqlite:///"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(url), "head")
