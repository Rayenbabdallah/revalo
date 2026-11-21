import pytest

from revalo.engine.units import insunits_to_mm, parse_number


@pytest.mark.parametrize(
    ("code", "factor"),
    [(None, 1.0), (0, 1.0), (1, 25.4), (4, 1.0), (5, 10.0), (6, 1000.0), (999, 1.0)],
)
def test_insunits_to_mm(code, factor):
    assert insunits_to_mm(code) == pytest.approx(factor)


@pytest.mark.parametrize(
    ("text", "value"),
    [("12", 12.0), ("12.5", 12.5), ("12,5", 12.5), (" 1 220 ", 1220.0), ("1.234,5", 1234.5)],
)
def test_parse_number_handles_locales(text, value):
    assert parse_number(text) == pytest.approx(value)
