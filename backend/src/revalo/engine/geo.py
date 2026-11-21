"""Tunisia's governorates and straight-line distances between them.

Buyers and workshops give their governorate rather than an address: it is what
people say ("Ben Arous", "Sfax") and it is enough to rank who is close. The
coordinates are those of each governorate's capital city.
"""

from __future__ import annotations

import math
import unicodedata

GOVERNORATES: dict[str, tuple[float, float]] = {
    "Tunis": (36.806, 10.181),
    "Ariana": (36.862, 10.193),
    "Ben Arous": (36.753, 10.219),
    "Manouba": (36.808, 10.097),
    "Nabeul": (36.451, 10.735),
    "Zaghouan": (36.402, 10.142),
    "Bizerte": (37.274, 9.873),
    "Béja": (36.725, 9.182),
    "Jendouba": (36.501, 8.780),
    "Le Kef": (36.174, 8.704),
    "Siliana": (36.084, 9.370),
    "Sousse": (35.825, 10.636),
    "Monastir": (35.778, 10.826),
    "Mahdia": (35.504, 11.062),
    "Sfax": (34.740, 10.760),
    "Kairouan": (35.678, 10.096),
    "Kasserine": (35.168, 8.836),
    "Sidi Bouzid": (35.038, 9.485),
    "Gabès": (33.881, 10.098),
    "Médenine": (33.354, 10.505),
    "Tataouine": (32.929, 10.452),
    "Gafsa": (34.425, 8.784),
    "Tozeur": (33.920, 8.134),
    "Kébili": (33.705, 8.969),
}


def _key(name: str) -> str:
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in plain.lower() if ch.isalnum())


_BY_KEY = {_key(name): name for name in GOVERNORATES}
_BY_KEY.update({"kef": "Le Kef", "elkef": "Le Kef", "medenine": "Médenine", "gabes": "Gabès"})


def canonical(name: str | None) -> str | None:
    """'ben arous', 'BEN-AROUS' and 'Ben Arous' all become 'Ben Arous'."""
    if not name:
        return None
    return _BY_KEY.get(_key(name))


def distance_km(a: str | None, b: str | None) -> float | None:
    ca, cb = canonical(a), canonical(b)
    if ca is None or cb is None:
        return None
    (lat1, lon1), (lat2, lon2) = GOVERNORATES[ca], GOVERNORATES[cb]
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))
