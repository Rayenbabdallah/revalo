"""Runtime settings read from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_url: str
    storage_dir: Path
    public_url: str
    review_days: int
    """Days a piece stays in stock before it is scored again."""
    workshop_phone: str | None
    """WhatsApp number buyers reach from the public marketplace (+216...)."""


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    var_dir = BACKEND_DIR / "var"
    return Settings(
        database_url=os.getenv(
            "REVALO_DATABASE_URL", f"sqlite:///{(var_dir / 'revalo.db').as_posix()}"
        ),
        storage_dir=Path(os.getenv("REVALO_STORAGE_DIR", str(var_dir / "files"))),
        public_url=os.getenv("REVALO_PUBLIC_URL", "http://localhost:5173").rstrip("/"),
        review_days=int(os.getenv("REVALO_REVIEW_DAYS", "30")),
        workshop_phone=os.getenv("REVALO_WORKSHOP_PHONE") or None,
    )
