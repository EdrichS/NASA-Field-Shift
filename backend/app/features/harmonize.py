"""Harmonize every source into one 12-month feature table per field (CLAUDE.md section 8).

For each variable and calendar month (January first):
  normal   long-term average for that month (POWER: 1996-2025; satellites: their full record)
  recent   that month's value within the 12 months ending at the data's latest month
  anomaly  recent - normal
Every feature keeps its unit, dataset, native resolution, periods and a spatial-detail label
(field / local / regional). These feed confidence labels, information gaps and Tier 2 sources.

harmonize() is pure and tested on fixtures. build_field_features() fetches POWER and Earth Engine
in parallel. store_features() persists daily climate (TimescaleDB hypertable) and the table.
"""

from __future__ import annotations

import logging
import statistics
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from typing import Any

from app.data import earthengine as ee_data
from app.data import power
from app.data.cache import Cache
from app.data.earthengine import FieldSatelliteData, MonthlySeries, add_months
from app.data.geometry import centroid, geom_hash

log = logging.getLogger(__name__)

MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
MIN_VALUES_FOR_NORMAL = 3  # a monthly normal needs at least 3 years of that month
MIN_DAYS_FOR_MONTH = 20  # a recent POWER month needs at least 20 days with data

FROST_C = 0.0  # an hour at or below this is frost
HEAT_C = 35.0  # an hour at or above this is heat stress for many crops (e.g. rice at flowering)

# POWER parameter -> (feature key, label, how daily values become one monthly value).
# For t_hottest / t_coldest the normal is the *typical* yearly extreme (mean of 30 years' monthly
# extremes), never POWER's climatology value, which is the 30-year record.
POWER_FEATURES = (
    ("T2M", "t_mean", "Air temperature, monthly average", "mean"),
    ("T2M_MAX", "t_hottest", "Hottest hour of the month (air)", "max"),
    ("T2M_MIN", "t_coldest", "Coldest hour of the month (air)", "min"),
    ("PRECTOTCORR", "rain", "Rainfall", "mean"),
    ("RH2M", "humidity", "Relative humidity", "mean"),
    ("T2MDEW", "dew_point", "Dew point", "mean"),
    ("ALLSKY_SFC_SW_DWN", "solar", "Sunlight (solar radiation)", "mean"),
    ("WS2M", "wind", "Wind speed at 2 m", "mean"),
)

@dataclass(frozen=True)
class SatelliteFeatureSpec:
    label: str
    spatial_detail: str
    normal_last_year: int | None = None  # ignore later years when computing the normal
    use_anomaly: bool = True
    caveat: str = ""


# Earth Engine series key -> how it becomes a feature. GRACE becomes a static trend instead.
SATELLITE_FEATURES = {
    "ndvi": SatelliteFeatureSpec("Greenness (NDVI)", "field"),
    "et": SatelliteFeatureSpec("Water use (evapotranspiration)", "field"),
    "lst_day": SatelliteFeatureSpec(
        "Daytime ground temperature",
        "field",
        normal_last_year=2022,
        use_anomaly=False,
        caveat=(
            "Normal uses 2001-2022 only and no anomaly is reported: readings drift cooler from "
            "2023 (-0.8, -1.6, -2.3 °C in 2024-26 at the test point while air temperature was "
            "warmer than normal), consistent with Terra's drifting overpass time."
        ),
    ),
    "soil_moisture_root": SatelliteFeatureSpec("Root-zone soil moisture", "local"),
    "soil_moisture_surface": SatelliteFeatureSpec("Surface soil moisture", "local"),
    "precip_imerg": SatelliteFeatureSpec("Rainfall (satellite + rain gauges)", "local"),
}


@dataclass(frozen=True)
class Feature:
    key: str
    label: str
    unit: str
    source: str
    native_resolution: str
    spatial_detail: str  # "field" (<= 1 km), "local" (<= ~12 km), "regional" (coarser)
    normal: list[float | None]  # 12 values, January first
    normal_period: str
    recent: list[float | None]  # 12 values, January first
    recent_months: list[str]  # the "YYYY-MM" behind each recent value
    anomaly: list[float | None]
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)  # e.g. 30-year records, frost-year counts


@dataclass(frozen=True)
class FieldFeatures:
    geom_hash: str
    lon: float
    lat: float
    end_month: str
    features: dict[str, Feature]
    static: dict[str, Any]
    gaps: list[str]  # data we could not get: becomes "information gaps" in reports

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_analysis(cls, analysis: dict[str, Any]) -> FieldFeatures:
        """Rebuild the features stored in an analysis response (a showcase file), so the engine
        can run again without calling NASA POWER or Earth Engine."""
        field_ = analysis["field"]
        return cls(field_["geom_hash"], field_["lon"], field_["lat"], field_["end_month"],
                   {k: Feature(**v) for k, v in analysis["features"].items()},
                   analysis["static"], list(analysis.get("feature_gaps") or []))


# --- helpers (pure) --------------------------------------------------------------------------


def window(end_month: str) -> list[str]:
    """The 12 months ending at end_month, placed by calendar month (index 0 = January)."""
    slots = [""] * 12
    for k in range(12):
        month = add_months(end_month, -k)
        slots[int(month[5:7]) - 1] = month
    return slots


def _r(x: float | None, digits: int = 4) -> float | None:
    return None if x is None else round(x, digits)


def _anomaly(recent: list[float | None], normal: list[float | None]) -> list[float | None]:
    return [
        _r(r - n) if r is not None and n is not None else None
        for r, n in zip(recent, normal, strict=True)
    ]


def linear_trend(values: dict[str, float | None]) -> float | None:
    """Least-squares slope per year of a monthly series {"YYYY-MM": value}."""
    points = [
        (int(m[:4]) + (int(m[5:7]) - 0.5) / 12, v) for m, v in values.items() if v is not None
    ]
    if len(points) < 24:
        return None
    xs, ys = zip(*points, strict=True)
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    denom = sum((x - mx) ** 2 for x in xs)
    return _r(sum((x - mx) * (y - my) for x, y in points) / denom, 3) if denom else None


def _unit(u: str) -> str:
    return "°C" if u == "C" else u


# --- building features (pure) ------------------------------------------------------------------


def extremes(
    yearly: power.YearlyMonthly, param: str, how: str
) -> tuple[list[float | None], dict[str, Any]]:
    """Typical yearly extreme per calendar month, plus the 30-year record and how many years
    reached frost (coldest hour <= 0 °C) or heat stress (hottest hour >= 35 °C)."""
    by_month: dict[int, list[float]] = {}
    for month, value in yearly.values.get(param, {}).items():
        if value is not None:
            by_month.setdefault(int(month[5:7]), []).append(value)
    typical, record, reached = [], [], []
    for m in range(1, 13):
        vals = by_month.get(m, [])
        typical.append(_r(statistics.fmean(vals)) if len(vals) >= MIN_VALUES_FOR_NORMAL else None)
        if how == "min":
            record.append(min(vals) if vals else None)
            reached.append(sum(v <= FROST_C for v in vals))
        else:
            record.append(max(vals) if vals else None)
            reached.append(sum(v >= HEAT_C for v in vals))
    threshold = (
        {"frost_years": reached, "frost_threshold_c": FROST_C}
        if how == "min"
        else {"heat_years": reached, "heat_threshold_c": HEAT_C}
    )
    return typical, {"record_30y": record, "years": yearly.period, **threshold}


def power_features(
    daily: power.DailyWeather,
    clim: power.Climatology,
    end_month: str,
    yearly: power.YearlyMonthly | None = None,
) -> dict[str, Feature]:
    months = window(end_month)
    by_month: dict[str, list[dict[str, Any]]] = {}
    for row in daily.rows:
        by_month.setdefault(row["date"].strftime("%Y-%m"), []).append(row)

    features = {}
    for param, key, label, how in POWER_FEATURES:
        recent: list[float | None] = []
        for month in months:
            values = [r[param] for r in by_month.get(month, []) if r[param] is not None]
            if len(values) < MIN_DAYS_FOR_MONTH:
                recent.append(None)
            elif how == "max":
                recent.append(_r(max(values)))
            elif how == "min":
                recent.append(_r(min(values)))
            else:
                recent.append(_r(statistics.fmean(values)))
        extra: dict[str, Any] = {}
        anomaly_ok = True
        if how in ("min", "max"):
            if yearly is not None and param in yearly.values:
                normal, extra = extremes(yearly, param, how)
            else:  # only the 30-year record is available: not comparable with one year
                normal = list(clim.monthly.get(param, [None] * 12))
                extra = {"normal_is_30y_record": True}
                anomaly_ok = False
        else:
            normal = list(clim.monthly.get(param, [None] * 12))
        features[key] = Feature(
            key=key,
            label=label,
            unit=_unit(clim.units.get(param) or daily.units.get(param, "")),
            source=f"{power.DATASET}, API {daily.api_version or clim.api_version}",
            native_resolution=power.NATIVE_RESOLUTION,
            spatial_detail="regional",
            normal=normal,
            normal_period=clim.period,
            recent=recent,
            recent_months=months,
            anomaly=_anomaly(recent, normal) if anomaly_ok else [None] * 12,
            note=power.PARAMETERS[param],
            extra=extra,
        )
    return features


def satellite_feature(series: MonthlySeries, end_month: str, spec: SatelliteFeatureSpec) -> Feature:
    groups: dict[int, list[float]] = {}
    normal_years: set[str] = set()
    for month, value in series.values.items():
        if value is None:
            continue
        if spec.normal_last_year is not None and int(month[:4]) > spec.normal_last_year:
            continue
        groups.setdefault(int(month[5:7]), []).append(value)
        normal_years.add(month[:4])
    normal = [
        _r(statistics.fmean(groups[m])) if len(groups.get(m, [])) >= MIN_VALUES_FOR_NORMAL else None
        for m in range(1, 13)
    ]
    with_data = [m for m in series.months_with_data if m <= end_month]
    last = with_data[-1] if with_data else end_month
    months = window(last)
    recent = [series.values.get(m) for m in months]
    years = sorted(normal_years)
    return Feature(
        key=series.key,
        label=spec.label,
        unit=series.unit,
        source=series.dataset,
        native_resolution=series.native_resolution,
        spatial_detail=spec.spatial_detail,
        normal=normal,
        normal_period=f"{years[0]}-{years[-1]}" if years else "",
        recent=recent,
        recent_months=months,
        anomaly=_anomaly(recent, normal) if spec.use_anomaly else [None] * 12,
        note=" ".join(x for x in (series.note, spec.caveat) if x),
    )


def harmonize(
    geometry: dict[str, Any],
    end_month: str,
    daily: power.DailyWeather | None,
    clim: power.Climatology | None,
    satellite: FieldSatelliteData | None,
    gaps: list[str] | None = None,
    yearly: power.YearlyMonthly | None = None,
) -> FieldFeatures:
    gaps = list(gaps or [])
    features: dict[str, Feature] = {}
    if daily is not None and clim is not None:
        features.update(power_features(daily, clim, end_month, yearly))

    static: dict[str, Any] = {}
    if satellite is not None:
        for key, spec in SATELLITE_FEATURES.items():
            if key in satellite.series:
                features[key] = satellite_feature(satellite.series[key], end_month, spec)
        grace = satellite.series.get("water_storage")
        if grace is not None:
            static["water_storage"] = {
                "trend_cm_per_year": linear_trend(grace.values),
                "period": grace.period,
                "source": grace.dataset,
                "native_resolution": grace.native_resolution,
                "spatial_detail": "regional",
            }
        if satellite.terrain is not None:
            static["terrain"] = asdict(satellite.terrain)
        if satellite.soil is not None:
            static["soil"] = asdict(satellite.soil)
        if satellite.land_cover is not None:
            static["land_cover"] = {**asdict(satellite.land_cover),
                                    "main_class": satellite.land_cover.main_class}
        for name, problem in satellite.errors.items():
            gaps.append(f"Satellite dataset '{name}' unavailable ({problem.split(':')[0]})")

    lon, lat = centroid(geometry)
    return FieldFeatures(
        geom_hash=geom_hash(geometry),
        lon=lon,
        lat=lat,
        end_month=end_month,
        features=features,
        static=static,
        gaps=gaps,
    )


# --- fetching and storing ------------------------------------------------------------------------


def build_field_features(
    geometry: dict[str, Any], *, end_month: str | None = None, cache: Cache | None = None
) -> tuple[FieldFeatures, power.DailyWeather | None]:
    """Fetch POWER (recent daily + normal) and every Earth Engine dataset in parallel."""
    end = end_month or ee_data.last_complete_month()
    lon, lat = centroid(geometry)
    first_day = date.fromisoformat(f"{add_months(end, -11)}-01")
    last_day = date.fromisoformat(f"{add_months(end, 1)}-01") - timedelta(days=1)

    gaps: list[str] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        f_daily = pool.submit(power.fetch_daily, lat, lon, first_day, last_day, cache=cache)
        f_clim = pool.submit(power.fetch_climatology, lat, lon, cache=cache)
        f_yearly = pool.submit(power.fetch_monthly, lat, lon, cache=cache)
        f_sat = pool.submit(ee_data.fetch_field, geometry, end_month=end, cache=cache)
        daily = clim = yearly = satellite = None
        try:
            daily = f_daily.result()
        except Exception as exc:
            gaps.append(f"NASA POWER recent weather unavailable ({type(exc).__name__})")
        try:
            clim = f_clim.result()
        except Exception as exc:
            gaps.append(f"NASA POWER 30-year normal unavailable ({type(exc).__name__})")
        try:
            yearly = f_yearly.result()
        except Exception as exc:
            gaps.append(f"NASA POWER yearly extremes unavailable ({type(exc).__name__})")
        try:
            satellite = f_sat.result()
        except Exception as exc:
            gaps.append(f"Satellite data unavailable ({type(exc).__name__})")
    return harmonize(geometry, end, daily, clim, satellite, gaps, yearly=yearly), daily


def store_features(features: FieldFeatures, daily: power.DailyWeather | None) -> dict[str, int]:
    """Persist daily climate to the climate_daily hypertable and the table to
    field_monthly_features (year 0 = normal). Best effort: logs and returns {} on failure."""
    from app.db import connect

    climate_rows = []
    if daily is not None:
        for row in daily.rows:
            for param in power.PARAMETERS:
                unit = _unit(daily.units.get(param, ""))
                climate_rows.append(
                    (features.geom_hash, param, row["date"], row[param], unit, power.DATASET)
                )
    feature_rows = []
    for f in features.features.values():
        for i in range(12):
            feature_rows.append(
                (features.geom_hash, f.key, 0, i + 1, f.normal[i], None, f.unit, f.source,
                 f.native_resolution, f.normal_period)
            )
            if f.recent_months[i]:
                feature_rows.append(
                    (features.geom_hash, f.key, int(f.recent_months[i][:4]), i + 1, f.recent[i],
                     f.anomaly[i], f.unit, f.source, f.native_resolution, f.recent_months[i])
                )
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO climate_daily (geom_hash, variable, day, value, unit, source)"
                " VALUES (%s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (geom_hash, variable, day) DO UPDATE SET value = EXCLUDED.value",
                climate_rows,
            )
            cur.executemany(
                "INSERT INTO field_monthly_features (geom_hash, variable, year, month, value,"
                " anomaly, unit, source, native_resolution, period)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (geom_hash, variable, year, month) DO UPDATE SET"
                " value = EXCLUDED.value, anomaly = EXCLUDED.anomaly, period = EXCLUDED.period,"
                " computed_at = now()",
                feature_rows,
            )
    except Exception as exc:
        log.warning("storing features failed (%s)", type(exc).__name__)
        return {}
    return {"climate_daily": len(climate_rows), "field_monthly_features": len(feature_rows)}
