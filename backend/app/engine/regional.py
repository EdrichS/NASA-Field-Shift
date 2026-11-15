"""Crops that are actually grown in the field's country (FAOSTAT harvested area, latest 3 years;
built by scripts/build_regional_crops.py into data/regional_crops.csv).

Why: a suggestion is only useful if the farmer can get seed, knows how to grow it and can sell or
eat it. A crop the country harvests on at least MIN_AREA_HA is treated as locally known; the
engine offers only those (when the country is known) and favors the more widely grown ones.
"""

from __future__ import annotations

import csv
import math
import re
from functools import lru_cache
from pathlib import Path

CSV = Path(__file__).resolve().parents[3] / "data" / "regional_crops.csv"
MIN_AREA_HA = 1000.0

# GAUL country names that differ from FAOSTAT's (both are FAO lists; most match exactly).
ALIASES = {
    "china": "china, mainland",
    "united kingdom": "united kingdom of great britain and northern ireland",
    "netherlands": "netherlands (kingdom of the)",
    "turkey": "türkiye",
    "vietnam": "viet nam",
    "south korea": "republic of korea",
    "north korea": "democratic people's republic of korea",
    "laos": "lao people's democratic republic",
    "russia": "russian federation",
    "iran": "iran (islamic republic of)",
    "bolivia": "bolivia (plurinational state of)",
    "venezuela": "venezuela (bolivarian republic of)",
    "tanzania": "united republic of tanzania",
    "syria": "syrian arab republic",
    "moldova": "republic of moldova",
    "ivory coast": "côte d'ivoire",
    "cote d'ivoire": "côte d'ivoire",
}


def _key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


@lru_cache(maxsize=1)
def _table() -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    if not CSV.exists():
        return out
    with CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.setdefault(_key(row["country"]), {})[row["crop"]] = float(row["area_ha"])
    return out


def local_crops(country: str | None) -> dict[str, float] | None:
    """{crop: hectares} grown on at least MIN_AREA_HA in the country, or None when the country
    is unknown or not in FAOSTAT (then no filter applies)."""
    if not country:
        return None
    table = _table()
    key = _key(country)
    crops = table.get(key) or table.get(ALIASES.get(key, ""))
    if crops is None:
        return None
    return {c: ha for c, ha in crops.items() if ha >= MIN_AREA_HA}


def familiarity(crop: str, local: dict[str, float] | None) -> float:
    """1.0-1.2: more widely grown in the country = easier seed, advice and buyers."""
    if not local or crop not in local:
        return 1.0
    return 1.0 + 0.2 * min(1.0, math.log10(max(local[crop], 1.0)) / 7)
