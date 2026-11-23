"""Reuse, sell or recycle: value each option in TND and CO2 and recommend one.

The engine is rule-based on purpose. A workshop owner must be able to read why
a piece should be sold rather than scrapped, and the pilot has no sales history
to learn from yet. Every recommendation comes with the numbers behind it.

Values
  reuse    the purchase of new material the workshop avoids, scaled by how easy
           the piece is to fit into a future job (smaller pieces fit fewer parts)
  sell     resale at a share of the new price, minus the marketplace commission
  recycle  scrap price by weight

CO2
  reuse and sale both replace new material: the primary production footprint
  recycling saves only the difference between primary and recycled production

Timing
  A remnant in stock is first kept for reuse. When its review date passes
  without use it should be sold, and when a second review period passes it
  should be recycled, so the racks never fill up with pieces nobody takes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from revalo.i18n import num, tr

COMMISSION = 0.05
REVIEW_DAYS = 30

# Below this shorter side, buyers are rare: a remnant is reused in house or recycled.
MIN_RESALE_SIDE_MM = {"metal": 150.0, "wood": 200.0, "plastic": 150.0}


class Action(StrEnum):
    REUSE = "reuse"
    SELL = "sell"
    RECYCLE = "recycle"


@dataclass(frozen=True)
class Prices:
    new_tnd_per_kg: float
    scrap_tnd_per_kg: float
    resale_factor: float


@dataclass(frozen=True)
class Co2Factors:
    primary_kg_per_kg: float | None
    recycling_saves_kg_per_kg: float | None


@dataclass(frozen=True)
class PieceFacts:
    kind: str
    """remnant or scrap"""
    family: str | None
    material_name: str
    weight_kg: float | None
    short_side_mm: float | None = None
    days_in_stock: int = 0
    in_stock: bool = False


@dataclass
class Option:
    action: Action
    available: bool
    value_tnd: float | None = None
    co2_kg: float | None = None
    note: str = ""


@dataclass
class Decision:
    recommended: Action | None
    options: list[Option]
    reasons: list[str] = field(default_factory=list)
    stage: str = "new"
    """new: just recorded; review: past one review period; overdue: past two."""

    def option(self, action: Action) -> Option:
        return next(o for o in self.options if o.action == action)

    def to_dict(self) -> dict:
        return {
            "recommended": self.recommended.value if self.recommended else None,
            "stage": self.stage,
            "reasons": self.reasons,
            "options": [
                {
                    "action": o.action.value,
                    "available": o.available,
                    "value_tnd": o.value_tnd,
                    "co2_kg": o.co2_kg,
                    "note": o.note,
                }
                for o in self.options
            ],
        }


def usability(short_side_mm: float | None) -> float:
    """Share of a remnant's value that a future job can realistically use."""
    if short_side_mm is None:
        return 1.0
    if short_side_mm >= 600:
        return 1.0
    if short_side_mm >= 300:
        return 0.85
    return 0.65


def _tnd(value: float) -> str:
    return f"{num(value, 1)} TND"


def _pct(share: float) -> str:
    return f"{num(share * 100, 0)}%"


def _round(value: float | None, digits: int = 2) -> float | None:
    return None if value is None else round(value, digits)


def decide(
    piece: PieceFacts,
    prices: Prices | None,
    co2: Co2Factors | None,
    review_days: int = REVIEW_DAYS,
) -> Decision:
    w = piece.weight_kg
    stage = "new"
    if piece.in_stock and piece.days_in_stock >= 2 * review_days:
        stage = "overdue"
    elif piece.in_stock and piece.days_in_stock >= review_days:
        stage = "review"

    primary = co2.primary_kg_per_kg if co2 else None
    saves = co2.recycling_saves_kg_per_kg if co2 else None
    co2_reuse = _round(w * primary, 1) if w is not None and primary is not None else None
    co2_recycle = _round(w * saves, 1) if w is not None and saves is not None else None

    # Scrap lots have one route: a recycler, paid by weight.
    if piece.kind == "scrap":
        value = _round(w * prices.scrap_tnd_per_kg) if w is not None and prices else None
        options = [
            Option(Action.REUSE, False, note=tr("Skeleton and slugs cannot be reused.")),
            Option(Action.SELL, False, note=tr("Sold by weight only.")),
            Option(Action.RECYCLE, True, value, co2_recycle, tr("Sorted lot for a recycler.")),
        ]
        reasons = [tr("The skeleton between parts only sells by weight, as one sorted lot.")]
        if value is not None:
            reasons.append(
                tr(
                    "{kg} kg at {price} TND/kg: {value}.",
                    kg=num(w, 1),
                    price=num(prices.scrap_tnd_per_kg, 2),
                    value=_tnd(value),
                )
            )
        return Decision(Action.RECYCLE, options, reasons, stage)

    fit = usability(piece.short_side_mm)
    min_resale = MIN_RESALE_SIDE_MM.get(piece.family or "", 150.0)
    sellable = piece.short_side_mm is None or piece.short_side_mm >= min_resale

    if w is None or prices is None:
        options = [
            Option(Action.REUSE, True, None, co2_reuse),
            Option(Action.SELL, sellable, None, co2_reuse),
            Option(Action.RECYCLE, True, None, co2_recycle),
        ]
        reason = (
            tr(
                "Add the thickness or weight to compare the options in dinars. "
                "Until then, keep it for reuse."
            )
            if w is None
            else tr(
                "Add a price for {material} to compare the options in dinars. "
                "Until then, keep it for reuse.",
                material=piece.material_name,
            )
        )
        return Decision(Action.REUSE, options, [reason], stage)

    new_value = w * prices.new_tnd_per_kg
    reuse_value = new_value * fit
    sell_value = new_value * prices.resale_factor * fit * (1 - COMMISSION)
    recycle_value = w * prices.scrap_tnd_per_kg

    options = [
        Option(
            Action.REUSE,
            True,
            _round(reuse_value),
            co2_reuse,
            tr("New material you do not have to buy."),
        ),
        Option(
            Action.SELL,
            sellable,
            _round(sell_value) if sellable else None,
            co2_reuse if sellable else None,
            tr(
                "At {share} of the new price, after {fee} commission.",
                share=_pct(prices.resale_factor),
                fee=_pct(COMMISSION),
            )
            if sellable
            else tr("Too narrow to sell (under {size} mm).", size=num(min_resale, 0)),
        ),
        Option(
            Action.RECYCLE, True, _round(recycle_value), co2_recycle, tr("Scrap price by weight.")
        ),
    ]

    reasons: list[str] = []
    if stage == "new":
        recommended = Action.REUSE
        reasons.append(
            tr(
                "Reusing it saves buying {kg} kg of new {material}: about {value}.",
                kg=num(w, 1),
                material=piece.material_name.lower(),
                value=_tnd(reuse_value),
            )
        )
        if fit < 1:
            reasons.append(
                tr(
                    "Its shorter side is {size} mm, so fewer parts fit: value counted at {share}.",
                    size=num(piece.short_side_mm or 0, 0),
                    share=_pct(fit),
                )
            )
    elif stage == "review" and sellable and sell_value > recycle_value:
        recommended = Action.SELL
        reasons.append(
            tr(
                "Not reused in {days} days. Selling brings about {sell}, against {scrap} as scrap.",
                days=review_days,
                sell=_tnd(sell_value),
                scrap=_tnd(recycle_value),
            )
        )
    elif prices.scrap_tnd_per_kg > 0:
        recommended = Action.RECYCLE
        reasons.append(
            tr(
                "Not reused or sold in time: send it to a recycler before it blocks rack space "
                "({value}).",
                value=_tnd(recycle_value),
            )
            if stage == "overdue"
            else tr(
                "Too small to find a buyer; as scrap it brings {value}.",
                value=_tnd(recycle_value),
            )
        )
    else:
        # No scrap market (most wood): selling cheaply still beats the bin.
        recommended = Action.SELL if sellable else Action.REUSE
        reasons.append(
            tr(
                "{material} offcuts have no scrap value: offer it to artisans or makers, "
                "even at a discount.",
                material=piece.material_name,
            )
            if sellable
            else tr(
                "{material} offcuts have no scrap value and this piece is small: "
                "keep it for small parts.",
                material=piece.material_name,
            )
        )

    if co2_reuse is not None and recommended in (Action.REUSE, Action.SELL):
        reasons.append(
            tr("Avoids about {kg} kg CO₂ of new material production.", kg=num(co2_reuse, 1))
        )
    elif co2_recycle is not None and recommended == Action.RECYCLE:
        reasons.append(tr("Recycling avoids about {kg} kg CO₂.", kg=num(co2_recycle, 1)))

    return Decision(recommended, options, reasons, stage)
