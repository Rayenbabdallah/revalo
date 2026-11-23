"""Storage for original job files.

Files are addressed by content hash, so uploading the same file twice stores it
once. Files are kept on local disk; an object store can implement the same
two methods.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Protocol

from revalo.settings import get_settings


class FileStorage(Protocol):
    def put(self, data: bytes, filename: str) -> tuple[str, str]: ...
    def get(self, key: str) -> bytes: ...


def _safe_name(filename: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename).strip("._") or "file"
    return name[-120:]


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def put(self, data: bytes, filename: str) -> tuple[str, str]:
        """Store bytes; returns (key, sha256)."""
        digest = hashlib.sha256(data).hexdigest()
        key = f"{digest[:2]}/{digest}-{_safe_name(filename)}"
        path = self.root / key
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return key, digest

    def get(self, key: str) -> bytes:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise KeyError(key)
        return path.read_bytes()


def get_storage() -> FileStorage:
    return LocalStorage(get_settings().storage_dir)
