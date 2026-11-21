import pytest

from revalo.engine.decision import Action, Co2Factors, PieceFacts, Prices, decide, usability

STEEL = Prices(new_tnd_per_kg=3.0, scrap_tnd_per_kg=0.27, resale_factor=0.4)
STEEL_CO2 = Co2Factors(primary_kg_per_kg=1.92, recycling_saves_kg_per_kg=1.5)
MDF = Prices(new_tnd_per_kg=2.67, scrap_tnd_per_kg=0.0, resale_factor=0.3)


def steel_remnant(weight=70.0, short=1500.0, days=0, in_stock=True):
    return PieceFacts(
        kind="remnant",
        family="metal",
        material_name="Mild steel",
        weight_kg=weight,
        short_side_mm=short,
        days_in_stock=days,
        in_stock=in_stock,
    )


def test_usability_steps_with_the_short_side():
    assert usability(1500) == 1.0
    assert usability(400) == 0.85
    assert usability(150) == 0.65
    assert usability(None) == 1.0


def test_new_remnant_is_kept_for_reuse_with_values_and_co2():
    d = decide(steel_remnant(), STEEL, STEEL_CO2)
    assert d.recommended is Action.REUSE and d.stage == "new"
    assert d.option(Action.REUSE).value_tnd == pytest.approx(210.0)
    assert d.option(Action.SELL).value_tnd == pytest.approx(70 * 3 * 0.4 * 0.95)
    assert d.option(Action.RECYCLE).value_tnd == pytest.approx(70 * 0.27)
    assert d.option(Action.REUSE).co2_kg == pytest.approx(134.4)
    assert d.option(Action.RECYCLE).co2_kg == pytest.approx(105.0)
    assert "210.0 TND" in d.reasons[0]
    assert any("CO₂" in r for r in d.reasons)


def test_after_one_review_period_an_unused_remnant_should_be_sold():
    d = decide(steel_remnant(days=31), STEEL, STEEL_CO2)
    assert d.stage == "review" and d.recommended is Action.SELL
    assert "Not reused in 30 days" in d.reasons[0]


def test_after_two_review_periods_metal_goes_to_the_recycler():
    d = decide(steel_remnant(days=61), STEEL, STEEL_CO2)
    assert d.stage == "overdue" and d.recommended is Action.RECYCLE


def test_narrow_metal_strip_is_not_offered_for_sale():
    d = decide(steel_remnant(weight=4, short=109, days=31), STEEL, STEEL_CO2)
    sell = d.option(Action.SELL)
    assert not sell.available and sell.value_tnd is None
    assert d.recommended is Action.RECYCLE


def test_small_pieces_are_valued_lower():
    big = decide(steel_remnant(weight=10, short=800), STEEL, STEEL_CO2)
    small = decide(steel_remnant(weight=10, short=200), STEEL, STEEL_CO2)
    assert small.option(Action.REUSE).value_tnd < big.option(Action.REUSE).value_tnd
    assert any("fewer parts fit" in r for r in small.reasons)


def test_wood_has_no_scrap_market_so_old_offcuts_are_sold():
    piece = PieceFacts(
        "remnant", "wood", "MDF", 9.2, short_side_mm=479, days_in_stock=70, in_stock=True
    )
    d = decide(piece, MDF, Co2Factors(0.39, None))
    assert d.recommended is Action.SELL
    assert d.option(Action.RECYCLE).value_tnd == 0
    assert d.option(Action.RECYCLE).co2_kg is None
    assert "no scrap value" in d.reasons[0]


def test_scrap_lot_always_goes_to_recycling():
    lot = PieceFacts("scrap", "metal", "Mild steel", 12.3)
    d = decide(lot, STEEL, STEEL_CO2)
    assert d.recommended is Action.RECYCLE
    assert not d.option(Action.REUSE).available and not d.option(Action.SELL).available
    assert d.option(Action.RECYCLE).value_tnd == pytest.approx(12.3 * 0.27, abs=0.01)


def test_missing_price_or_weight_says_what_to_add():
    no_price = decide(steel_remnant(), None, None)
    assert no_price.recommended is Action.REUSE
    assert "price for Mild steel" in no_price.reasons[0]
    no_weight = decide(steel_remnant(weight=None), STEEL, STEEL_CO2)
    assert "thickness or weight" in no_weight.reasons[0]
    assert no_weight.option(Action.REUSE).value_tnd is None


def test_draft_records_are_never_past_review():
    d = decide(steel_remnant(days=90, in_stock=False), STEEL, STEEL_CO2)
    assert d.stage == "new"


def test_decision_serializes():
    data = decide(steel_remnant(), STEEL, STEEL_CO2).to_dict()
    assert data["recommended"] == "reuse"
    assert [o["action"] for o in data["options"]] == ["reuse", "sell", "recycle"]
