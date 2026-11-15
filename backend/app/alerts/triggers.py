"""Alert rules as pure functions (no network, no database), so each one is easy to test and to
explain. Thresholds are stated here with where they come from."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Any

# How close an open NASA EONET event must be to alert a field (km). Storms and droughts are
# wide; fires and landslides are local. A team choice, stated so it can be challenged.
RADIUS_KM = {
    "severeStorms": 300,
    "floods": 100,
    "wildfires": 50,
    "drought": 200,
    "landslides": 30,
    "volcanoes": 100,
    "tempExtremes": 200,
}
FIRE_RADIUS_KM = 5  # FIRMS active-fire detections this close to the field
FIRE_DAYS = 2

# Heavy rain in the last 24 h (mm), after the India Meteorological Department's terms
# ("heavy" 64.5-115.5 mm, "very heavy" 115.6-204.4 mm in 24 h;
# https://rsmcnewdelhi.imd.gov.in/images/pdf/terminology.pdf), or a wet day far above normal.
HEAVY_MM = 64.5
VERY_HEAVY_MM = 115.6
RELATIVE_MIN_MM = 30.0
RELATIVE_FACTOR = 5.0

# Drought stress: latest SMAP root-zone soil moisture as a share of the normal for that month.
DROUGHT_WATCH = 0.75
DROUGHT_WARNING = 0.60

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_km(points: list[tuple[float, float]], lat: float, lon: float) -> float:
    """points are (lon, lat)."""
    return min(haversine_km(lat, lon, p[1], p[0]) for p in points)


def approaching(track: list[tuple[float, float]], lat: float, lon: float) -> bool:
    """True when the newest point of a storm track is closer to the field than the one before."""
    if len(track) < 2:
        return False
    last = haversine_km(lat, lon, track[-1][1], track[-1][0])
    before = haversine_km(lat, lon, track[-2][1], track[-2][0])
    return last < before - 10


def heavy_rain(mm_24h: float | None, normal_mm_day: float | None) -> str | None:
    """Severity ('warning' | 'watch') or None."""
    if mm_24h is None:
        return None
    if mm_24h >= VERY_HEAVY_MM:
        return "warning"
    if mm_24h >= HEAVY_MM:
        return "watch"
    if normal_mm_day and mm_24h >= RELATIVE_MIN_MM and mm_24h >= RELATIVE_FACTOR * normal_mm_day:
        return "watch"
    return None


@dataclass
class DroughtCheck:
    severity: str
    share: float
    month: str  # "YYYY-MM"


def drought(recent: list[float | None], normal: list[float | None],
            recent_months: list[str]) -> DroughtCheck | None:
    """Uses the newest month that has both a value and a normal."""
    best = None
    for value, base, month in zip(recent, normal, recent_months, strict=False):
        if value is None or not base or not month:
            continue
        if best is None or month > best[2]:
            best = (value, base, month)
    if best is None:
        return None
    share = best[0] / best[1]
    if share < DROUGHT_WARNING:
        return DroughtCheck("warning", share, best[2])
    if share < DROUGHT_WATCH:
        return DroughtCheck("watch", share, best[2])
    return None


def month_name(month: str) -> str:
    return MONTH_NAMES[int(month[5:7]) - 1]


@dataclass
class PestHit:
    pest: str
    crop: str
    description: str
    days: int
    last_day: date
    source: str


def _num(value: Any) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _day_matches(row: dict[str, Any], rule: dict[str, Any]) -> bool:
    t, rh, rain = row.get("T2M"), row.get("RH2M"), row.get("PRECTOTCORR")
    limits = [("t_min_c", t, lambda v, x: v >= x), ("t_max_c", t, lambda v, x: v <= x),
              ("rh_min_pct", rh, lambda v, x: v >= x), ("rh_max_pct", rh, lambda v, x: v <= x),
              ("rain_min_mm_day", rain, lambda v, x: v >= x)]
    for key, value, ok in limits:
        limit = _num(rule.get(key))
        if limit is None:
            continue
        if value is None or not ok(value, limit):
            return False
    return True


def pest_hits(rules: list[dict[str, Any]], rows: list[dict[str, Any]],
              crops: set[str]) -> list[PestHit]:
    """Rules (pest_rules.csv rows) whose weather ran for enough days in a row in `rows` (POWER
    daily values, oldest first), for crops the farmer grows."""
    hits = []
    for rule in rules:
        rule_crops = {c.strip().lower() for c in str(rule.get("crops", "")).replace(";", ",")
                      .split(",") if c.strip()}
        grown = sorted(rule_crops & crops)
        if not grown:
            continue
        need = int(_num(rule.get("consecutive_days")) or 2)
        run, best, best_end = 0, 0, None
        for row in rows:
            run = run + 1 if _day_matches(row, rule) else 0
            if run >= best and run > 0:
                best, best_end = run, row["date"]
        if best >= need and best_end is not None:
            hits.append(PestHit(rule["pest"], grown[0], rule.get("description", ""), best,
                                best_end, rule.get("source", "")))
    return hits


def rule_text(rule: dict[str, Any]) -> str:
    """'25-34 °C and humidity above 70% for 2+ days'."""
    parts = []
    lo, hi = _num(rule.get("t_min_c")), _num(rule.get("t_max_c"))
    if lo is not None and hi is not None:
        parts.append(f"{lo:g}-{hi:g} °C")
    elif lo is not None:
        parts.append(f"above {lo:g} °C")
    rh = _num(rule.get("rh_min_pct"))
    if rh is not None:
        parts.append(f"humidity above {rh:g}%")
    rain = _num(rule.get("rain_min_mm_day"))
    if rain is not None:
        parts.append(f"rain above {rain:g} mm a day")
    days = int(_num(rule.get("consecutive_days")) or 2)
    return " and ".join(parts) + f" for {days}+ days in a row"
