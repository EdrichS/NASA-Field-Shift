"""NASA POWER (Agroclimatology community): daily weather and a 30-year monthly climatology
for one point.

Docs:        https://power.larc.nasa.gov/docs/services/api/
Parameters:  names and units verified against
             /api/system/manager/parameters?community=AG&temporal=daily (Nov 14, 2026)
Resolution:  1/2° lat x 5/8° lon for meteorology (MERRA-2), 1° x 1° for solar (CERES)
             https://power.larc.nasa.gov/docs/methodology/

Fetching (HTTP, retries, cache) is kept apart from parsing (pure functions), so tests run on
saved fixtures with no network.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from app.data.cache import Cache, default_cache

BASE_URL = "https://power.larc.nasa.gov/api/temporal"
COMMUNITY = "AG"

# Parameter -> what SowSmart uses it for. Units come back in the response (AG community:
# °C, mm/day, %, MJ/m^2/day, m/s).
PARAMETERS: dict[str, str] = {
    "T2M": "mean air temperature (crop suitability, heat stress)",
    "T2M_MAX": "daily maximum temperature (heat stress)",
    "T2M_MIN": "daily minimum temperature (frost risk)",
    "T2MDEW": "dew point (disease and pest-risk rules)",
    "PRECTOTCORR": "rainfall (water supply, heavy rain, dry spells)",
    "RH2M": "relative humidity (disease and pest-risk rules)",
    "ALLSKY_SFC_SW_DWN": "solar radiation (crop water demand)",
    "WS2M": "wind speed at 2 m (crop water demand)",
}

# POWER's climatology T2M_MIN / T2M_MAX are the single most extreme hour in the whole 30-year
# period (verified: 14.92 °C = the lowest of 30 January minimums at the test point). The
# year-by-year monthly endpoint gives each year's extreme, so we can compute a *typical* extreme
# and count how many years reached frost or heat stress.
EXTREME_PARAMETERS = ("T2M_MIN", "T2M_MAX")

DAILY_FIRST_DAY = date(1981, 1, 1)
# The latest 30 complete years: still a 30-year normal, but reflects today's warmer climate
# better than the WMO 1991-2020 standard would.
CLIMATOLOGY_YEARS = (1996, 2025)
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")

DATASET = "NASA POWER (Agroclimatology)"
NATIVE_RESOLUTION = "0.5° x 0.625° (meteorology, MERRA-2); 1° x 1° (solar, CERES)"

TIMEOUT = httpx.Timeout(60.0, connect=10.0)
MAX_ATTEMPTS = 3
RETRY_STATUSES = {429, 500, 502, 503, 504}
# Ranges ending this close to today include near-real-time values that POWER may still revise.
RECENT_DAYS = 30
RECENT_MAX_AGE_S = 24 * 3600

_sleep = time.sleep  # swapped out in tests


class PowerError(RuntimeError):
    """POWER could not answer: a bad request, an odd response, or still failing after retries."""


@dataclass(frozen=True)
class DailyWeather:
    lat: float
    lon: float
    elevation_m: float | None
    start: date
    end: date
    rows: list[dict[str, Any]]  # {"date": date, "T2M": 25.1, ...}; None where POWER has no value
    units: dict[str, str]
    sources: list[str]
    api_version: str
    dataset: str = DATASET
    native_resolution: str = NATIVE_RESOLUTION


@dataclass(frozen=True)
class Climatology:
    """Long-term monthly values.

    Careful: here T2M_MIN / T2M_MAX are the coldest / hottest *hour of each month* (POWER's
    climatology definition), not the average daily minimum / maximum. Good for frost and heat
    risk ("typical coldest night of the month"); for average nights use the daily data.
    """

    lat: float
    lon: float
    elevation_m: float | None
    period: str  # e.g. "1996-2025"
    monthly: dict[str, list[float | None]]  # parameter -> 12 values, January first
    annual: dict[str, float | None]
    units: dict[str, str]
    sources: list[str]
    api_version: str
    dataset: str = DATASET
    native_resolution: str = NATIVE_RESOLUTION


@dataclass(frozen=True)
class YearlyMonthly:
    """One value per year and month, e.g. each January's coldest hour 1996-2025."""

    lat: float
    lon: float
    period: str
    values: dict[str, dict[str, float | None]]  # parameter -> {"YYYY-MM": value}
    units: dict[str, str]
    sources: list[str]
    api_version: str


# --- requests ------------------------------------------------------------------------------


def _check_point(lat: float, lon: float) -> None:
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"latitude/longitude out of range: {lat}, {lon}")


def daily_request(lat: float, lon: float, start: date, end: date) -> tuple[str, dict[str, str]]:
    _check_point(lat, lon)
    if start > end:
        raise ValueError(f"start {start} is after end {end}")
    if start < DAILY_FIRST_DAY:
        raise ValueError(f"POWER daily data starts on {DAILY_FIRST_DAY}")
    return f"{BASE_URL}/daily/point", {
        "parameters": ",".join(PARAMETERS),
        "community": COMMUNITY,
        "latitude": str(round(lat, 4)),
        "longitude": str(round(lon, 4)),
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
    }


def climatology_request(
    lat: float, lon: float, years: tuple[int, int] = CLIMATOLOGY_YEARS
) -> tuple[str, dict[str, str]]:
    _check_point(lat, lon)
    return f"{BASE_URL}/climatology/point", {
        "parameters": ",".join(PARAMETERS),
        "community": COMMUNITY,
        "latitude": str(round(lat, 4)),
        "longitude": str(round(lon, 4)),
        "start": str(years[0]),
        "end": str(years[1]),
        "format": "JSON",
    }


def monthly_request(
    lat: float,
    lon: float,
    years: tuple[int, int] = CLIMATOLOGY_YEARS,
    parameters: tuple[str, ...] = EXTREME_PARAMETERS,
) -> tuple[str, dict[str, str]]:
    _check_point(lat, lon)
    return f"{BASE_URL}/monthly/point", {
        "parameters": ",".join(parameters),
        "community": COMMUNITY,
        "latitude": str(round(lat, 4)),
        "longitude": str(round(lon, 4)),
        "start": str(years[0]),
        "end": str(years[1]),
        "format": "JSON",
    }


# --- fetching (network + cache) ------------------------------------------------------------


def fetch_daily_payload(
    lat: float,
    lon: float,
    start: date,
    end: date,
    *,
    client: httpx.Client | None = None,
    cache: Cache | None = None,
) -> dict[str, Any]:
    url, params = daily_request(lat, lon, start, end)
    recent = end >= date.today() - timedelta(days=RECENT_DAYS)
    max_age = RECENT_MAX_AGE_S if recent else None
    return _get_json(url, params, client=client, cache=cache, max_age_s=max_age)


def fetch_daily(lat: float, lon: float, start: date, end: date, **kwargs: Any) -> DailyWeather:
    return parse_daily(fetch_daily_payload(lat, lon, start, end, **kwargs))


def fetch_climatology_payload(
    lat: float,
    lon: float,
    years: tuple[int, int] = CLIMATOLOGY_YEARS,
    *,
    client: httpx.Client | None = None,
    cache: Cache | None = None,
) -> dict[str, Any]:
    url, params = climatology_request(lat, lon, years)
    return _get_json(url, params, client=client, cache=cache, max_age_s=None)


def fetch_climatology(lat: float, lon: float, **kwargs: Any) -> Climatology:
    return parse_climatology(fetch_climatology_payload(lat, lon, **kwargs))


def fetch_monthly_payload(
    lat: float,
    lon: float,
    years: tuple[int, int] = CLIMATOLOGY_YEARS,
    *,
    client: httpx.Client | None = None,
    cache: Cache | None = None,
) -> dict[str, Any]:
    url, params = monthly_request(lat, lon, years)
    return _get_json(url, params, client=client, cache=cache, max_age_s=None)


def fetch_monthly(lat: float, lon: float, **kwargs: Any) -> YearlyMonthly:
    return parse_monthly(fetch_monthly_payload(lat, lon, **kwargs))


def _get_json(
    url: str,
    params: dict[str, str],
    *,
    client: httpx.Client | None,
    cache: Cache | None,
    max_age_s: float | None,
) -> dict[str, Any]:
    cache = cache if cache is not None else default_cache()
    key = "power:" + url + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
    cached = cache.get(key, max_age_s=max_age_s)
    if cached is not None:
        return cached

    http = client or httpx.Client(timeout=TIMEOUT)
    try:
        payload = _request_with_retries(http, url, params)
    finally:
        if client is None:
            http.close()
    cache.set(key, payload)
    return payload


def _request_with_retries(http: httpx.Client, url: str, params: dict[str, str]) -> dict[str, Any]:
    last_problem = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = http.get(url, params=params)
        except httpx.TransportError as exc:  # timeouts, refused or dropped connections
            last_problem = f"{type(exc).__name__}: {exc}"
        else:
            if response.status_code == 200:
                return response.json()
            if response.status_code not in RETRY_STATUSES:
                raise PowerError(
                    f"POWER returned HTTP {response.status_code}: {response.text[:300]}"
                )
            last_problem = f"HTTP {response.status_code}"
        if attempt < MAX_ATTEMPTS:
            _sleep(2 ** (attempt - 1))  # 1 s, then 2 s
    raise PowerError(f"POWER still failing after {MAX_ATTEMPTS} attempts ({last_problem})")


# --- parsing (pure) ------------------------------------------------------------------------


def _clean(value: Any, fill: float) -> float | None:
    if value is None or value == fill:
        return None
    return float(value)


def _common(payload: dict[str, Any]) -> tuple[dict[str, dict], float, float, float | None]:
    try:
        series = payload["properties"]["parameter"]
        coords = payload["geometry"]["coordinates"]
        lon, lat = float(coords[0]), float(coords[1])
    except (KeyError, TypeError, IndexError, ValueError) as exc:
        messages = payload.get("messages") if isinstance(payload, dict) else None
        raise PowerError(f"unexpected POWER response: {messages or str(payload)[:200]}") from exc
    elevation = float(coords[2]) if len(coords) > 2 else None
    return series, lat, lon, elevation


def _meta(payload: dict[str, Any]) -> tuple[float, dict[str, str], list[str], str]:
    header = payload.get("header", {})
    units = {p: m.get("units", "") for p, m in payload.get("parameters", {}).items()}
    version = header.get("api", {}).get("version", "")
    return header.get("fill_value", -999.0), units, header.get("sources", []), version


def parse_daily(payload: dict[str, Any]) -> DailyWeather:
    series, lat, lon, elevation = _common(payload)
    fill, units, sources, version = _meta(payload)
    days = sorted(set().union(*(values.keys() for values in series.values())))
    if not days:
        raise PowerError("POWER returned no daily values")
    rows = []
    for day in days:
        row: dict[str, Any] = {"date": datetime.strptime(day, "%Y%m%d").date()}
        for name, values in series.items():
            row[name] = _clean(values.get(day), fill)
        rows.append(row)
    return DailyWeather(
        lat=lat,
        lon=lon,
        elevation_m=elevation,
        start=rows[0]["date"],
        end=rows[-1]["date"],
        rows=rows,
        units=units,
        sources=sources,
        api_version=version,
    )


def parse_monthly(payload: dict[str, Any]) -> YearlyMonthly:
    series, lat, lon, _ = _common(payload)
    fill, units, sources, version = _meta(payload)
    values: dict[str, dict[str, float | None]] = {}
    for name, by_key in series.items():
        # Keys are YYYYMM; month "13" is POWER's annual value, which we skip.
        values[name] = {
            f"{k[:4]}-{k[4:]}": _clean(v, fill) for k, v in sorted(by_key.items()) if k[4:] != "13"
        }
    years = sorted({m[:4] for v in values.values() for m in v})
    return YearlyMonthly(
        lat=lat,
        lon=lon,
        period=f"{years[0]}-{years[-1]}" if years else "",
        values=values,
        units=units,
        sources=sources,
        api_version=version,
    )


def parse_climatology(payload: dict[str, Any]) -> Climatology:
    series, lat, lon, elevation = _common(payload)
    fill, units, sources, version = _meta(payload)
    years = re.findall(r"\b(\d{4})\b", payload.get("header", {}).get("range", ""))
    period = f"{years[0]}-{years[-1]}" if len(years) >= 2 else ""
    return Climatology(
        lat=lat,
        lon=lon,
        elevation_m=elevation,
        period=period,
        monthly={p: [_clean(v.get(m), fill) for m in MONTHS] for p, v in series.items()},
        annual={p: _clean(v.get("ANN"), fill) for p, v in series.items()},
        units=units,
        sources=sources,
        api_version=version,
    )
