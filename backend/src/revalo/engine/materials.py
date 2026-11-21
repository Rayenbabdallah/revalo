"""Material library and metadata inference from file names and layer names."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Any


@dataclass(frozen=True)
class Material:
    code: str
    name_en: str
    name_fr: str
    family: str
    density_kg_m3: float
    aliases: tuple[str, ...]
    price: dict[str, Any] | None

    def weight_kg(self, area_mm2: float, thickness_mm: float) -> float:
        """Mass of a flat piece: area x thickness x density."""
        return area_mm2 * thickness_mm * 1e-9 * self.density_kg_m3


@dataclass(frozen=True)
class Process:
    code: str
    kerf_mm: float
    families: tuple[str, ...]


@lru_cache(maxsize=1)
def _library() -> dict[str, Any]:
    raw = resources.files("revalo.engine.data").joinpath("materials.json").read_text("utf-8")
    return json.loads(raw)


@lru_cache(maxsize=1)
def materials() -> dict[str, Material]:
    out: dict[str, Material] = {}
    for m in _library()["materials"]:
        out[m["code"]] = Material(
            code=m["code"],
            name_en=m["name"]["en"],
            name_fr=m["name"]["fr"],
            family=m["family"],
            density_kg_m3=float(m["density_kg_m3"]),
            aliases=tuple(_normalize(a) for a in m["aliases"]),
            price=m.get("price"),
        )
    return out


@lru_cache(maxsize=1)
def processes() -> dict[str, Process]:
    return {
        code: Process(code=code, kerf_mm=float(p["kerf_mm"]), families=tuple(p["families"]))
        for code, p in _library()["processes"].items()
    }


def get_material(code: str) -> Material:
    try:
        return materials()[code]
    except KeyError as exc:
        raise KeyError(f"unknown material code: {code}") from exc


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text.lower()


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9.]+", _normalize(text)) if t]


def infer_material(text: str) -> str | None:
    """Guess a material code from free text such as a file or layer name.

    Longer aliases win, so "inox316" resolves to 316 rather than generic inox.
    Short aliases (3 characters or fewer, or purely numeric) must match a whole token.
    """
    norm = _normalize(text)
    tokens = set(_tokens(text))
    joined = " ".join(_tokens(text))
    best: tuple[int, str] | None = None
    for mat in materials().values():
        for alias in mat.aliases:
            whole_token_only = len(alias) <= 3 or alias.replace(".", "").isdigit()
            if whole_token_only:
                hit = alias in tokens
            else:
                hit = alias in norm or alias in joined
            if hit and (best is None or len(alias) > best[0]):
                best = (len(alias), mat.code)
    return best[1] if best else None


_THICKNESS_PATTERNS = [
    re.compile(r"(?<![\dx])(\d{1,2}(?:[.,]\d{1,2})?)\s*mm\b"),
    re.compile(r"\b(?:t|e|ep|epaisseur|thk|th)\s*[=_-]?\s*(\d{1,2}(?:[.,]\d{1,2})?)\b"),
]
_SHEET_PATTERN = re.compile(r"(?<!\d)(\d{3,4})\s*[x*]\s*(\d{3,4})(?!\d)")


def infer_thickness(text: str) -> float | None:
    """Find a plausible sheet thickness (0.3 to 80 mm) in free text."""
    norm = _normalize(text).replace("_", " ")
    for pattern in _THICKNESS_PATTERNS:
        for match in pattern.finditer(norm):
            value = float(match.group(1).replace(",", "."))
            if 0.3 <= value <= 80:
                return value
    return None


def infer_sheet_size(text: str) -> tuple[float, float] | None:
    """Find a sheet size such as 3000x1500 in free text. Returns (width, height)."""
    match = _SHEET_PATTERN.search(_normalize(text).replace("×", "x"))
    if not match:
        return None
    a, b = float(match.group(1)), float(match.group(2))
    return (max(a, b), min(a, b))


def default_kerf(process: str | None, material_code: str | None) -> float:
    """Kerf for a known process, otherwise a conservative guess from the material family."""
    if process and process in processes():
        return processes()[process].kerf_mm
    if material_code and material_code in materials():
        family = materials()[material_code].family
        return {"metal": 0.3, "wood": 3.2, "plastic": 0.2}.get(family, 1.0)
    return 1.0
