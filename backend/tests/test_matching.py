from datetime import UTC, datetime, timedelta

import pytest

from revalo.engine.geo import canonical, distance_km
from revalo.engine.matching import Need, Offer, match

NOW = datetime(2026, 11, 21, tzinfo=UTC)


def offer(**kw):
    base = dict(
        kind="remnant",
        material_code="steel_mild",
        material_name="Mild steel",
        thickness_mm=3.0,
        width_mm=1469.0,
        height_mm=1500.0,
        weight_kg=51.9,
        price_tnd=59.0,
        governorate="Ben Arous",
    )
    return Offer(**{**base, **kw})


def need(**kw):
    base = dict(
        kind="reuse",
        materials=("steel_mild",),
        thickness_min_mm=2.0,
        thickness_max_mm=4.0,
        min_length_mm=600.0,
        min_width_mm=400.0,
        max_price_tnd_per_kg=1.5,
        governorate="Tunis",
        created_at=NOW - timedelta(days=3),
    )
    return Need(**{**base, **kw})


def test_governorate_names_are_forgiving():
    assert canonical("ben arous") == canonical("BEN-AROUS") == "Ben Arous"
    assert canonical("Gabes") == "Gabès"
    assert canonical("Atlantis") is None
    assert distance_km("Tunis", "Tunis") == pytest.approx(0)
    assert distance_km("Ben Arous", "Sfax") == pytest.approx(225, abs=15)


def test_a_good_match_scores_high_with_reasons():
    m = match(offer(), need(), NOW)
    assert m is not None and m.score >= 70
    assert m.distance_km == pytest.approx(distance_km("Ben Arous", "Tunis"), abs=0.1)
    assert any("km away" in r for r in m.reasons)
    assert any("Fits their 600 × 400 mm minimum" in r for r in m.reasons)
    assert any("within their 1.50 TND/kg budget" in r for r in m.reasons)


@pytest.mark.parametrize(
    "changes",
    [
        {"materials": ("stainless_304",)},
        {"thickness_min_mm": 4.0},
        {"thickness_max_mm": 2.0},
        {"min_length_mm": 2000.0},
        {"max_price_tnd_per_kg": 0.5},
        {"governorate": "Tataouine"},
    ],
)
def test_hard_rules_exclude(changes):
    assert match(offer(), need(**changes), NOW) is None


def test_reuse_buyers_never_get_scrap_lots_but_recyclers_do():
    lot = offer(kind="scrap", width_mm=None, height_mm=None, weight_kg=12.3, price_tnd=3.3)
    assert match(lot, need(), NOW) is None
    recycler = need(
        kind="recycler", min_length_mm=None, min_width_mm=None, max_price_tnd_per_kg=None
    )
    m = match(lot, recycler, NOW)
    assert m is not None
    assert any("Recycler buying mild steel" in r for r in m.reasons)


def test_rotation_is_allowed_when_checking_size():
    tall = offer(width_mm=300.0, height_mm=900.0)
    assert match(tall, need(min_length_mm=800.0, min_width_mm=250.0), NOW) is not None


def test_closer_and_fresher_buyers_rank_higher():
    near = match(offer(), need(governorate="Ben Arous"), NOW)
    far = match(offer(), need(governorate="Sfax"), NOW)
    old = match(offer(), need(governorate="Ben Arous", created_at=NOW - timedelta(days=80)), NOW)
    assert near.score > far.score
    assert near.score > old.score
    assert any("check it is still open" in r for r in old.reasons)


def test_empty_material_list_means_any_material():
    assert match(offer(material_code="aluminium"), need(materials=()), NOW) is not None
