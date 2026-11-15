"""Fetching what the alert rules need. Network only; the rules themselves are in triggers.py.

- NASA EONET v3 open events (region-wide natural events). Category IDs checked against
  https://eonet.gsfc.nasa.gov/api/v3/categories on Nov 15, 2026.
- NASA FIRMS area API, VIIRS NOAA-20 and NOAA-21 near-real-time (VIIRS S-NPP NRT stopped at
  2026-11-02 per the FIRMS data_availability endpoint on Nov 15, 2026).
- JAXA GSMaP v8 operational hourly rain in Earth Engine (JAXA/GPM_L3/GSMaP/v8/operational,
  band hourlyPrecipRate, mm/h; newest image ~half a day old when checked).
- NASA POWER daily weather for the last ~3 weeks (pest-risk rules).
"""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from app.alerts.triggers import RADIUS_KM
from app.config import get_settings
from app.data import power
from app.data.crops import PEST_RULES_CSV

log = logging.getLogger(__name__)

EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
FIRMS_URL = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/{key}/{source}/{bbox}/{days}"
FIRMS_SOURCES = ("VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT")
GSMAP = "JAXA/GPM_L3/GSMaP/v8/operational"


@dataclass
class NaturalEvent:
    id: str
    title: str
    category: str
    track: list[tuple[float, float]]  # (lon, lat), oldest first; polygon events use their ring
    geometry: dict[str, Any]
    event_date: str | None
    url: str | None
    simulated: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def parse_eonet(payload: dict[str, Any]) -> list[NaturalEvent]:
    events = []
    for e in payload.get("events", []):
        category = next((c["id"] for c in e.get("categories", []) if c["id"] in RADIUS_KM), None)
        if category is None:
            continue
        points: list[tuple[float, float]] = []
        for g in sorted(e.get("geometry", []), key=lambda g: g.get("date") or ""):
            if g.get("type") == "Point":
                points.append((float(g["coordinates"][0]), float(g["coordinates"][1])))
            elif g.get("type") == "Polygon":
                points.extend((float(x), float(y)) for x, y in g["coordinates"][0])
        if not points:
            continue
        dates = [g.get("date") for g in e.get("geometry", []) if g.get("date")]
        geometry = ({"type": "Point", "coordinates": list(points[0])} if len(points) == 1
                    else {"type": "MultiPoint", "coordinates": [list(p) for p in points]})
        events.append(NaturalEvent(e["id"], e["title"], category, points, geometry,
                                   max(dates) if dates else None, e.get("link")))
    return events


def fetch_eonet(days: int = 20) -> list[NaturalEvent]:
    params = {"status": "open", "days": days, "category": ",".join(RADIUS_KM)}
    r = httpx.get(EONET_URL, params=params, timeout=30)
    r.raise_for_status()
    return parse_eonet(r.json())


@dataclass
class Fire:
    lat: float
    lon: float
    acq_date: str
    satellite: str
    confidence: str


def parse_firms(text: str) -> list[Fire]:
    rows = list(csv.DictReader(io.StringIO(text)))
    return [Fire(float(r["latitude"]), float(r["longitude"]), r.get("acq_date", ""),
                 r.get("satellite", ""), r.get("confidence", "")) for r in rows
            if r.get("latitude") and r.get("longitude")]


def fetch_fires(lat: float, lon: float, km: float, days: int) -> list[Fire]:
    key = get_settings().firms_map_key.get_secret_value()
    if not key:
        raise RuntimeError("FIRMS_MAP_KEY is not set")
    d = km / 111.0 + 0.01
    bbox = f"{lon - d:.4f},{lat - d:.4f},{lon + d:.4f},{lat + d:.4f}"
    fires: list[Fire] = []
    for source in FIRMS_SOURCES:
        r = httpx.get(FIRMS_URL.format(key=key, source=source, bbox=bbox, days=days), timeout=30)
        if r.status_code != 200 or r.text.startswith("Invalid"):
            log.info("FIRMS %s answered %s", source, r.status_code)
            continue
        fires.extend(parse_firms(r.text))
    return fires


def rain_last_24h(lat: float, lon: float) -> tuple[float | None, str | None]:
    """(mm in the 24 hours before the newest GSMaP image, that image's time UTC)."""
    from app.data.earthengine import _ee

    ee = _ee()
    now = datetime.now(UTC)
    start = (now - timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
    col = (ee.ImageCollection(GSMAP).filterDate(start, now.strftime("%Y-%m-%dT%H:%M"))
           .select("hourlyPrecipRate"))
    newest = col.aggregate_max("system:time_start")
    window = col.filter(ee.Filter.gt("system:time_start",
                                     ee.Number(newest).subtract(24 * 3600 * 1000)))
    point = ee.Geometry.Point([lon, lat])
    info = ee.Dictionary({
        "mm": window.sum().reduceRegion(ee.Reducer.first(), point, 1000).get("hourlyPrecipRate"),
        "newest": ee.Date(newest).format("YYYY-MM-dd'T'HH:mm"),
    }).getInfo()
    mm = info.get("mm")
    return (round(float(mm), 1) if mm is not None else None), info.get("newest")


def recent_weather(lat: float, lon: float, days: int = 21) -> list[dict[str, Any]]:
    """POWER daily rows for the last `days` days (newest days may be missing: POWER lags)."""
    end = date.today() - timedelta(days=1)
    weather = power.fetch_daily(lat, lon, end - timedelta(days=days), end)
    return [r for r in weather.rows if r.get("T2M") is not None]


def pest_rules() -> list[dict[str, Any]]:
    with PEST_RULES_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))
