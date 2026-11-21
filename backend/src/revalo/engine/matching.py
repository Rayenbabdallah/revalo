"""Match a piece on offer with the buyers who could take it.

Hard rules first (a buyer who needs stainless never sees mild steel, a piece
smaller than the buyer's minimum is never suggested), then a score out of 100:

  distance  40  a light truck trip is the real cost of a small deal
  size fit  30  the closer to what they need, the less they waste
  price     20  headroom under the buyer's maximum price per kg
  freshness 10  recent requests are more likely to still be open

Every match carries the reasons behind its score, written for the manager.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from revalo.engine.geo import distance_km

MAX_DISTANCE_KM = 400.0
RECYCLER_REMNANT_PENALTY = 40


@dataclass(frozen=True)
class Offer:
    kind: str
    """remnant or scrap"""
    material_code: str | None
    material_name: str
    thickness_mm: float | None
    width_mm: float | None
    height_mm: float | None
    weight_kg: float | None
    price_tnd: float
    governorate: str | None


@dataclass(frozen=True)
class Need:
    kind: str
    """reuse or recycler"""
    materials: tuple[str, ...]
    thickness_min_mm: float | None
    thickness_max_mm: float | None
    min_length_mm: float | None
    min_width_mm: float | None
    max_price_tnd_per_kg: float | None
    governorate: str | None
    created_at: datetime


@dataclass
class Match:
    score: int
    distance_km: float | None
    reasons: list[str] = field(default_factory=list)


def _fits(offer: Offer, need: Need) -> bool:
    if need.min_length_mm is None and need.min_width_mm is None:
        return True
    if offer.width_mm is None or offer.height_mm is None:
        return False
    long_side, short_side = (
        max(offer.width_mm, offer.height_mm),
        min(offer.width_mm, offer.height_mm),
    )
    want_long = max(need.min_length_mm or 0, need.min_width_mm or 0)
    want_short = min(need.min_length_mm or 0, need.min_width_mm or 0)
    return long_side >= want_long and short_side >= want_short


def match(offer: Offer, need: Need, now: datetime | None = None) -> Match | None:
    """Score how well `need` fits `offer`, or None when it cannot fit at all."""
    # A recycler buys scrap lots and pieces by weight; reuse buyers want usable remnants.
    if need.kind == "reuse" and offer.kind != "remnant":
        return None
    if need.materials and offer.material_code not in need.materials:
        return None
    t = offer.thickness_mm
    if t is not None:
        if need.thickness_min_mm is not None and t < need.thickness_min_mm - 1e-6:
            return None
        if need.thickness_max_mm is not None and t > need.thickness_max_mm + 1e-6:
            return None
    if need.kind == "reuse" and not _fits(offer, need):
        return None
    price_per_kg = offer.price_tnd / offer.weight_kg if offer.weight_kg else None
    if (
        need.max_price_tnd_per_kg is not None
        and price_per_kg is not None
        and price_per_kg > need.max_price_tnd_per_kg + 1e-9
    ):
        return None
    km = distance_km(offer.governorate, need.governorate)
    if km is not None and km > MAX_DISTANCE_KM:
        return None

    reasons: list[str] = []
    if km is None:
        distance_points = 15.0
        reasons.append("Location unknown.")
    else:
        distance_points = 40.0 * max(0.0, 1 - km / 300.0)
        reasons.append("Same governorate." if km < 1 else f"About {km:,.0f} km away.")

    if need.kind == "reuse" and (need.min_length_mm or need.min_width_mm):
        # Waste ratio: how much bigger the piece is than the minimum they asked for.
        want = (need.min_length_mm or need.min_width_mm or 1) * (
            need.min_width_mm or need.min_length_mm or 1
        )
        have = (offer.width_mm or 0) * (offer.height_mm or 0)
        ratio = want / have if have else 0
        size_points = 30.0 * min(1.0, 0.4 + 0.6 * ratio)
        reasons.append(
            f"Fits their {need.min_length_mm or 0:,.0f} × {need.min_width_mm or 0:,.0f} mm minimum."
        )
    else:
        size_points = 20.0
        if need.kind == "recycler":
            reasons.append(f"Recycler buying {offer.material_name.lower()} by weight.")

    if need.max_price_tnd_per_kg is not None and price_per_kg is not None:
        headroom = 1 - price_per_kg / need.max_price_tnd_per_kg if need.max_price_tnd_per_kg else 0
        price_points = 20.0 * min(1.0, 0.5 + headroom)
        budget = need.max_price_tnd_per_kg
        reasons.append(f"{price_per_kg:,.2f} TND/kg, within their {budget:,.2f} TND/kg budget.")
    else:
        price_points = 10.0

    created = need.created_at if need.created_at.tzinfo else need.created_at.replace(tzinfo=UTC)
    age_days = max(((now or datetime.now(UTC)) - created).days, 0)
    fresh_points = 10.0 * max(0.0, 1 - age_days / 90)
    if age_days > 60:
        reasons.append(f"Request posted {age_days} days ago: check it is still open.")

    score = round(distance_points + size_points + price_points + fresh_points)
    if need.kind == "recycler" and offer.kind == "remnant":
        # A recycler pays scrap price by weight: for a reusable piece it is the fallback,
        # ranked below any buyer who will reuse it.
        score -= RECYCLER_REMNANT_PENALTY
        reasons.append("Pays scrap price: keep as a fallback if no one reuses it.")
    return Match(
        score=max(min(score, 100), 0),
        distance_km=None if km is None else round(km, 1),
        reasons=reasons,
    )
