"""The workshop's price book: library defaults, overridden by its own quotes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from revalo.db.models import PriceEntry
from revalo.engine.decision import Co2Factors, Prices
from revalo.engine.materials import materials


class PriceError(ValueError):
    """Prices that cannot be right (scrap worth more than new, and so on)."""


@dataclass(frozen=True)
class EffectivePrice:
    material_code: str
    prices: Prices | None
    co2: Co2Factors | None
    source: str | None
    custom: bool
    updated_at: datetime | None = None
    updated_by: str | None = None

    def to_dict(self) -> dict[str, Any]:
        mat = materials()[self.material_code]
        return {
            "material_code": self.material_code,
            "name": {"en": mat.name_en, "fr": mat.name_fr},
            "family": mat.family,
            "new_tnd_per_kg": self.prices.new_tnd_per_kg if self.prices else None,
            "scrap_tnd_per_kg": self.prices.scrap_tnd_per_kg if self.prices else None,
            "resale_factor": self.prices.resale_factor if self.prices else None,
            "source": self.source,
            "custom": self.custom,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "updated_by": self.updated_by,
            "co2_primary_kg_per_kg": self.co2.primary_kg_per_kg if self.co2 else None,
            "co2_recycling_saves_kg_per_kg": self.co2.recycling_saves_kg_per_kg
            if self.co2
            else None,
            "co2_source": mat.co2.get("source") if mat.co2 else None,
        }


def _co2(code: str) -> Co2Factors | None:
    block = materials()[code].co2
    if not block:
        return None
    return Co2Factors(block.get("primary_kg_per_kg"), block.get("recycling_saves_kg_per_kg"))


def price_book(session: Session, workshop_id: str) -> dict[str, EffectivePrice]:
    custom = {
        e.material_code: e
        for e in session.scalars(select(PriceEntry).where(PriceEntry.workshop_id == workshop_id))
    }
    book: dict[str, EffectivePrice] = {}
    for code, mat in materials().items():
        entry = custom.get(code)
        if entry is not None:
            book[code] = EffectivePrice(
                code,
                Prices(entry.new_tnd_per_kg, entry.scrap_tnd_per_kg, entry.resale_factor),
                _co2(code),
                entry.source,
                True,
                entry.updated_at,
                entry.updated_by,
            )
        elif mat.price:
            p = mat.price
            book[code] = EffectivePrice(
                code,
                Prices(p["new_tnd_per_kg"], p["scrap_tnd_per_kg"], p["resale_factor"]),
                _co2(code),
                p.get("source"),
                False,
            )
        else:
            book[code] = EffectivePrice(code, None, _co2(code), None, False)
    return book


def set_price(
    session: Session,
    workshop_id: str,
    code: str,
    new_tnd_per_kg: float,
    scrap_tnd_per_kg: float,
    resale_factor: float,
    source: str | None,
    actor: str,
) -> EffectivePrice:
    if code not in materials():
        raise PriceError(f"Unknown material code: {code}")
    if new_tnd_per_kg <= 0:
        raise PriceError("The new price must be above zero.")
    if not 0 <= scrap_tnd_per_kg < new_tnd_per_kg:
        raise PriceError("Scrap must be worth less than new material.")
    if not 0 < resale_factor <= 1:
        raise PriceError("The resale share must be between 0 and 100% of the new price.")

    entry = session.scalars(
        select(PriceEntry).where(
            PriceEntry.workshop_id == workshop_id, PriceEntry.material_code == code
        )
    ).first()
    if entry is None:
        entry = PriceEntry(workshop_id=workshop_id, material_code=code)
        session.add(entry)
    entry.new_tnd_per_kg = new_tnd_per_kg
    entry.scrap_tnd_per_kg = scrap_tnd_per_kg
    entry.resale_factor = resale_factor
    entry.source = (source or "").strip() or None
    entry.updated_by = actor
    session.commit()
    return price_book(session, workshop_id)[code]


def reset_price(session: Session, workshop_id: str, code: str) -> EffectivePrice:
    if code not in materials():
        raise PriceError(f"Unknown material code: {code}")
    entry = session.scalars(
        select(PriceEntry).where(
            PriceEntry.workshop_id == workshop_id, PriceEntry.material_code == code
        )
    ).first()
    if entry is not None:
        session.delete(entry)
        session.commit()
    return price_book(session, workshop_id)[code]
