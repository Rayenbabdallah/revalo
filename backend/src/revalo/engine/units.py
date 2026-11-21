"""Length unit conversion to millimetres."""

from __future__ import annotations

# DXF $INSUNITS codes that matter for sheet work.
_INSUNITS_TO_MM: dict[int, float] = {
    0: 1.0,  # unitless: nesting exports are almost always millimetres
    1: 25.4,  # inches
    2: 304.8,  # feet
    4: 1.0,  # millimetres
    5: 10.0,  # centimetres
    6: 1000.0,  # metres
    8: 0.0000254,  # microinches
    9: 0.0254,  # mils
    13: 0.001,  # microns
    14: 100.0,  # decimetres
}


def insunits_to_mm(code: int | None) -> float:
    """Scale factor from a DXF $INSUNITS code to millimetres.

    Unknown or missing codes fall back to 1.0 (millimetres).
    """
    if code is None:
        return 1.0
    return _INSUNITS_TO_MM.get(int(code), 1.0)


def parse_number(text: str) -> float:
    """Parse a number that may use a decimal comma (French locale exports)."""
    cleaned = text.strip().replace(" ", "").replace(" ", "")
    if "," in cleaned and "." in cleaned:
        # "1.234,5" -> thousands dot, decimal comma
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", ".")
    return float(cleaned)
