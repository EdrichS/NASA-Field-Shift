"""Crops that are actually grown in the field's country (FAOSTAT harvested area, latest 3 years;
built by scripts/build_regional_crops.py into data/regional_crops.csv).

Why: a suggestion is only useful if the farmer can get seed, knows how to grow it and can sell or
eat it. A crop the country harvests on at least MIN_AREA_HA is treated as locally known; the
engine offers only those (when the country is known) and favors the more widely grown ones.

The same table carries the national yield and farm-gate price (FAOSTAT producer prices, USD), so
the income score can use a typical gross value per hectare before costs.
"""

from __future__ import annotations

import csv
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

CSV = Path(__file__).resolve().parents[3] / "data" / "regional_crops.csv"
MIN_AREA_HA = 1000.0

# GAUL country names that differ from FAOSTAT's (both are FAO lists; most match exactly).
ALIASES = {
    "united states": "united states of america",
    "usa": "united states of america",
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


@dataclass(frozen=True)
class MarketValue:
    """A crop's typical gross value per hectare in one country, before costs."""
    yield_t_ha: float
    price_usd_t: float
    value_usd_ha: float
    price_years: str


@lru_cache(maxsize=1)
def _table() -> dict[str, dict[str, dict[str, str]]]:
    out: dict[str, dict[str, dict[str, str]]] = {}
    if not CSV.exists():
        return out
    with CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.setdefault(_key(row["country"]), {})[row["crop"]] = row
    return out


def _rows(country: str | None) -> dict[str, dict[str, str]] | None:
    if not country:
        return None
    table = _table()
    key = _key(country)
    return table.get(key) or table.get(ALIASES.get(key, ""))


def local_crops(country: str | None) -> dict[str, float] | None:
    """{crop: hectares} grown on at least MIN_AREA_HA in the country, or None when the country
    is unknown or not in FAOSTAT (then no filter applies)."""
    rows = _rows(country)
    if rows is None:
        return None
    return {c: float(r["area_ha"]) for c, r in rows.items() if float(r["area_ha"]) >= MIN_AREA_HA}


@lru_cache(maxsize=1)
def tracked_crops() -> frozenset[str]:
    """Crops FAOSTAT records anywhere. Cover crops outside this set (sunn hemp, sesbania) are
    never harvested for sale, so their absence from a country's statistics says nothing."""
    return frozenset(crop for rows in _table().values() for crop in rows)


def crop_values(country: str | None) -> dict[str, MarketValue] | None:
    """{crop: MarketValue} where FAOSTAT has both a yield and a recent producer price."""
    rows = _rows(country)
    if rows is None:
        return None
    return {c: MarketValue(float(r["yield_t_ha"]), float(r["price_usd_t"]),
                           float(r["value_usd_ha"]), r.get("price_years") or "")
            for c, r in rows.items() if r.get("value_usd_ha")}


def reference_value(local: dict[str, float] | None,
                    values: dict[str, MarketValue] | None, crops: set[str]) -> str | None:
    """The country's most widely grown crop (among `crops`) that has a value per hectare."""
    if not local or not values:
        return None
    priced = [c for c in local if c in values and c in crops]
    return max(priced, key=lambda c: local[c], default=None)


def familiarity(crop: str, local: dict[str, float] | None) -> float:
    """1.0-1.2: more widely grown in the country = easier seed, advice and buyers."""
    if not local or crop not in local:
        return 1.0
    return 1.0 + 0.2 * min(1.0, math.log10(max(local[crop], 1.0)) / 7)
