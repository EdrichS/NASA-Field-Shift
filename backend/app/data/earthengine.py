"""NASA satellite data (plus ISRIC SoilGrids) for one field, through Google Earth Engine.

Every dataset ID, band, scale factor and unit here was checked on Nov 14, 2026 against the
Earth Engine catalog (STAC metadata) and against Earth Engine itself; catalog URLs are in
REFERENCES.md. Each dataset is one small request, reduced on Earth Engine's side, cached, and
fetched in parallel with the others.

Time series come back as monthly means over each dataset's whole record, so step 1.4 can build
the long-term monthly normal and recent anomalies from a single fetch.

Fetching (Earth Engine + cache) is kept apart from parsing (pure functions), so tests run on
saved fixtures with no network.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.data.cache import Cache, default_cache
from app.data.geometry import geom_hash, to_ee_geometry

MISSING = -9999
# Coarse pixels are resampled to 100 m before averaging, so even a small field always gets the
# value of the pixel it sits in. bestEffort lets Earth Engine coarsen this for very large fields.
REDUCE_SCALE_M = 100


@dataclass(frozen=True)
class SeriesSpec:
    key: str
    dataset: str
    collections: tuple[str, ...]  # priority order: later ones only fill months earlier ones lack
    band: str
    unit: str
    native_resolution: str
    start: str  # first month requested, "YYYY-MM"
    scale: float = 1.0  # value = raw * scale + offset
    offset: float = 0.0
    valid_raw: tuple[float, float] | None = None  # raw values outside are fill codes: masked
    hour_utc: int | None = None  # keep one image per day at this UTC hour (3-hourly products)
    chunk_months: int | None = None  # split into requests of this many months (memory limits)
    note: str = ""


SERIES: tuple[SeriesSpec, ...] = (
    SeriesSpec(
        key="soil_moisture_root",
        dataset="NASA SMAP L4 v8 (SPL4SMGP.008)",
        collections=("NASA/SMAP/SPL4SMGP/008",),
        band="sm_rootzone",
        unit="m³/m³",
        native_resolution="9 km",
        start="2015-04",
        hour_utc=13,
        chunk_months=12,
        note="Root zone (0-100 cm). SMAP satellite data assimilated into a land model.",
    ),
    SeriesSpec(
        key="soil_moisture_surface",
        dataset="NASA SMAP L4 v8 (SPL4SMGP.008)",
        collections=("NASA/SMAP/SPL4SMGP/008",),
        band="sm_surface",
        unit="m³/m³",
        native_resolution="9 km",
        start="2015-04",
        hour_utc=13,
        chunk_months=12,
        note="Top layer (0-5 cm).",
    ),
    SeriesSpec(
        key="ndvi",
        dataset="NASA MODIS Terra MOD13Q1 v6.1",
        collections=("MODIS/061/MOD13Q1",),
        band="NDVI",
        unit="index (-1 to 1)",
        native_resolution="250 m",
        start="2001-01",
        scale=0.0001,
        valid_raw=(-2000, 10000),
        note="Greenness. Low values mean bare soil or stressed plants.",
    ),
    SeriesSpec(
        key="et",
        dataset="NASA MODIS Terra MOD16A2 v6.1 (gap-filled, newest months from 8-day)",
        collections=("MODIS/061/MOD16A2GF", "MODIS/061/MOD16A2"),
        band="ET",
        unit="mm/day",
        native_resolution="500 m",
        start="2001-01",
        scale=0.1 / 8,
        valid_raw=(0, 32700),
        note="Water used by plants and soil. 8-day totals shown per day; codes 32761+ masked.",
    ),
    SeriesSpec(
        key="lst_day",
        dataset="NASA MODIS Terra MOD11A2 v6.1",
        collections=("MODIS/061/MOD11A2",),
        band="LST_Day_1km",
        unit="°C",
        native_resolution="1 km",
        start="2001-01",
        scale=0.02,
        offset=-273.15,
        valid_raw=(7500, 65535),
        note="Daytime land surface temperature (the ground, not the air).",
    ),
    SeriesSpec(
        key="precip_imerg",
        dataset="NASA GPM IMERG V07 Final Run, monthly",
        collections=("NASA/GPM_L3/IMERG_MONTHLY_V07",),
        band="precipitation",
        unit="mm/day",
        native_resolution="0.1° (~11 km)",
        start="2001-01",
        scale=24.0,
        note="Satellite rainfall merged with rain gauges. Final Run lags a few months.",
    ),
    SeriesSpec(
        key="water_storage",
        dataset="NASA/GFZ GRACE & GRACE-FO, JPL mascons RL06.3 v4 (CRI filtered)",
        collections=("NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI",),
        band="lwe_thickness",
        unit="cm of water",
        native_resolution="0.5° grid (3° mascons)",
        start="2002-04",
        note="Change in total water stored in the region. Regional trend context only.",
    ),
)
SERIES_BY_KEY = {s.key: s for s in SERIES}

SRTM_ID = "USGS/SRTMGL1_003"
WORLDCOVER_ID = "ESA/WorldCover/v200"  # 10 m, 2021; ESA is a 2026 Space Agency Partner
WORLDCOVER_CLASSES = {"10": "trees", "20": "shrubs", "30": "grass", "40": "cropland",
                      "50": "built_up", "60": "bare", "70": "snow_ice", "80": "water",
                      "90": "wetland", "95": "mangroves", "100": "moss"}
SOILGRIDS = {  # property -> (unit, divide raw by) per the SoilGrids 2.0 conversion table
    "clay": ("%", 10),
    "sand": ("%", 10),
    "silt": ("%", 10),
    "soc": ("g/kg", 10),
    "phh2o": ("pH", 10),
    "bdod": ("g/cm³", 100),
}
SOIL_DEPTHS = (("0-5cm", 5), ("5-15cm", 10), ("15-30cm", 15))  # weighted to a 0-30 cm average


@dataclass(frozen=True)
class MonthlySeries:
    key: str
    dataset: str
    collections: tuple[str, ...]
    unit: str
    native_resolution: str
    note: str
    values: dict[str, float | None]  # "YYYY-MM" -> monthly mean; None = no valid data
    images: dict[str, int]  # how many images went into each month

    @property
    def months_with_data(self) -> list[str]:
        return [m for m, v in self.values.items() if v is not None]

    @property
    def period(self) -> str:
        months = self.months_with_data
        return f"{months[0]} to {months[-1]}" if months else "no data"


@dataclass(frozen=True)
class Terrain:
    elevation_m: float | None
    slope_deg: float | None
    dataset: str = "NASA SRTM v3 (SRTMGL1_003)"
    native_resolution: str = "30 m"


@dataclass(frozen=True)
class Soil:
    clay_pct: float | None
    sand_pct: float | None
    silt_pct: float | None
    soc_g_kg: float | None
    ph: float | None
    bulk_density_g_cm3: float | None
    texture: str | None  # USDA texture class from clay/sand/silt
    depth: str = "0-30 cm"
    dataset: str = "ISRIC SoilGrids 2.0 (not NASA)"
    native_resolution: str = "250 m"


@dataclass(frozen=True)
class LandCover:
    shares: dict[str, float]  # class -> share of the field area
    dataset: str = "ESA WorldCover 10 m v200 (2021)"
    native_resolution: str = "10 m"

    @property
    def main_class(self) -> str:
        return max(self.shares, key=self.shares.get) if self.shares else "unknown"


@dataclass(frozen=True)
class FieldSatelliteData:
    geom_hash: str
    end_month: str
    series: dict[str, MonthlySeries]
    terrain: Terrain | None
    soil: Soil | None
    errors: dict[str, str]  # dataset key -> what went wrong (becomes an information gap)
    land_cover: LandCover | None = None


# --- months ------------------------------------------------------------------------------


def last_complete_month(today: date | None = None) -> str:
    today = today or date.today()
    year, month = (today.year, today.month - 1) if today.month > 1 else (today.year - 1, 12)
    return f"{year:04d}-{month:02d}"


def add_months(month: str, k: int) -> str:
    year, mon = map(int, month.split("-"))
    total = year * 12 + (mon - 1) + k
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def chunks(start: str, end: str, size: int | None) -> list[tuple[str, int]]:
    """(first month, month count) pieces covering start..end; one piece if size is None."""
    total = months_between(start, end)
    size = size or total
    return [(add_months(start, i), min(size, total - i)) for i in range(0, total, size)]


def months_between(start: str, end: str) -> int:
    """Number of months from start to end inclusive ("YYYY-MM")."""
    sy, sm = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    count = (ey - sy) * 12 + (em - sm) + 1
    if count < 1:
        raise ValueError(f"end {end} is before start {start}")
    return count


# --- Earth Engine (network) ----------------------------------------------------------------

_init_lock = threading.Lock()
_initialized = False


def _ee() -> Any:
    """The initialized `ee` module (initialized once, with EE_PROJECT)."""
    global _initialized
    import ee

    from app.config import get_settings

    with _init_lock:
        if not _initialized:
            project = get_settings().ee_project
            if not project:
                raise RuntimeError("EE_PROJECT is empty; set it in .env")
            ee.Initialize(project=project)
            _initialized = True
    return ee


def _monthly_collection(
    ee: Any, region: Any, collection_id: str, spec: SeriesSpec, first: str, n: int
) -> Any:
    # All these collections hold global images, so no filterBounds. SMAP is requested in
    # 12-month chunks: 60+ months of its 3-hourly images in one request exceeds EE memory.
    start = ee.Date(f"{first}-01")
    coll = ee.ImageCollection(collection_id).select(spec.band)

    def one_month(i: Any) -> Any:
        month_start = start.advance(i, "month")
        images = coll.filterDate(month_start, month_start.advance(1, "month"))
        if spec.hour_utc is not None:
            images = images.filter(ee.Filter.calendarRange(spec.hour_utc, spec.hour_utc, "hour"))
        if spec.valid_raw is not None:
            low, high = spec.valid_raw
            images = images.map(lambda img: img.updateMask(img.gte(low).And(img.lte(high))))
        stats = images.mean().reduceRegion(
            ee.Reducer.mean(), region, REDUCE_SCALE_M, bestEffort=True, maxPixels=1e8
        )
        props = {
            "m": month_start.format("YYYY-MM"),
            "v": stats.get(spec.band, MISSING),
            "n": images.size(),
        }
        return ee.Feature(None, props)

    return ee.FeatureCollection(ee.List.sequence(0, n - 1).map(one_month))


def _series_raw(spec: SeriesSpec, geometry: dict, end: str, cache: Cache) -> dict[str, list]:
    key = f"earthengine:{spec.key}:{geom_hash(geometry)}:{spec.start}:{end}"
    raw = cache.get(key)
    if raw is None:
        ee = _ee()
        region = to_ee_geometry(ee, geometry)
        pieces = chunks(spec.start, end, spec.chunk_months)

        def fetch(collection_id: str, first: str, n: int) -> list[dict[str, Any]]:
            info = _monthly_collection(ee, region, collection_id, spec, first, n).getInfo()
            return [f["properties"] for f in info["features"]]

        raw = {}
        with ThreadPoolExecutor(max_workers=min(6, len(pieces))) as pool:
            for collection_id in spec.collections:
                parts = pool.map(lambda p, c=collection_id: fetch(c, *p), pieces)
                raw[collection_id] = [row for part in parts for row in part]
        cache.set(key, raw)
    return raw


def _terrain_raw(geometry: dict, cache: Cache) -> dict[str, Any]:
    key = f"earthengine:terrain:{geom_hash(geometry)}"
    raw = cache.get(key)
    if raw is None:
        ee = _ee()
        dem = ee.Image(SRTM_ID).select("elevation")
        image = dem.addBands(ee.Terrain.slope(dem))
        raw = image.reduceRegion(
            ee.Reducer.mean(), to_ee_geometry(ee, geometry), 30, bestEffort=True, maxPixels=1e8
        ).getInfo()
        cache.set(key, raw)
    return raw


def _soil_raw(geometry: dict, cache: Cache) -> dict[str, Any]:
    key = f"earthengine:soilgrids:{geom_hash(geometry)}"
    raw = cache.get(key)
    if raw is None:
        ee = _ee()
        layers = []
        for prop in SOILGRIDS:
            image = ee.Image(f"projects/soilgrids-isric/{prop}_mean")
            weighted = None
            for depth, weight in SOIL_DEPTHS:
                part = image.select(f"{prop}_{depth}_mean").multiply(weight)
                weighted = part if weighted is None else weighted.add(part)
            layers.append(weighted.divide(sum(w for _, w in SOIL_DEPTHS)).rename(prop))
        stack = ee.Image.cat(layers)
        raw = stack.reduceRegion(
            ee.Reducer.mean(), to_ee_geometry(ee, geometry), REDUCE_SCALE_M,
            bestEffort=True, maxPixels=1e8,
        ).getInfo()
        cache.set(key, raw)
    return raw


def _land_cover_raw(geometry: dict, cache: Cache) -> dict[str, Any]:
    key = f"earthengine:landcover:{geom_hash(geometry)}"
    raw = cache.get(key)
    if raw is None:
        ee = _ee()
        image = ee.ImageCollection(WORLDCOVER_ID).first().select("Map")
        raw = image.reduceRegion(
            ee.Reducer.frequencyHistogram(), to_ee_geometry(ee, geometry), 10,
            bestEffort=True, maxPixels=1e8,
        ).getInfo()
        cache.set(key, raw)
    return raw


def parse_land_cover(raw: dict[str, Any]) -> LandCover:
    histogram = raw.get("Map") or {}
    total = sum(histogram.values()) or 1
    shares: dict[str, float] = {}
    for code, count in histogram.items():
        name = WORLDCOVER_CLASSES.get(str(int(float(code))), "other")
        shares[name] = round(shares.get(name, 0) + count / total, 3)
    return LandCover(shares)


def fetch_land_cover(geometry: dict, *, cache: Cache | None = None) -> LandCover:
    return parse_land_cover(_land_cover_raw(geometry, cache or default_cache()))


def fetch_series(
    key: str, geometry: dict, *, end_month: str | None = None, cache: Cache | None = None
) -> MonthlySeries:
    spec = SERIES_BY_KEY[key]
    raw = _series_raw(spec, geometry, end_month or last_complete_month(), cache or default_cache())
    return parse_series(spec, raw)


def fetch_terrain(geometry: dict, *, cache: Cache | None = None) -> Terrain:
    return parse_terrain(_terrain_raw(geometry, cache or default_cache()))


def fetch_soil(geometry: dict, *, cache: Cache | None = None) -> Soil:
    return parse_soil(_soil_raw(geometry, cache or default_cache()))


def fetch_field(
    geometry: dict, *, end_month: str | None = None, cache: Cache | None = None
) -> FieldSatelliteData:
    """Every dataset for one field, in parallel. A failing dataset is reported, not raised."""
    cache = cache or default_cache()
    end = end_month or last_complete_month()
    jobs: dict[str, Callable[[], Any]] = {
        spec.key: (lambda k=spec.key: fetch_series(k, geometry, end_month=end, cache=cache))
        for spec in SERIES
    }
    jobs["terrain"] = lambda: fetch_terrain(geometry, cache=cache)
    jobs["soil"] = lambda: fetch_soil(geometry, cache=cache)
    jobs["land_cover"] = lambda: fetch_land_cover(geometry, cache=cache)

    results: dict[str, Any] = {}
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
        futures = {name: pool.submit(job) for name, job in jobs.items()}
        for name, future in futures.items():
            try:
                results[name] = future.result()
            except Exception as exc:  # one dataset failing must not sink the whole analysis
                errors[name] = f"{type(exc).__name__}: {str(exc)[:200]}"
    return FieldSatelliteData(
        geom_hash=geom_hash(geometry),
        end_month=end,
        series={k: v for k, v in results.items() if isinstance(v, MonthlySeries)},
        terrain=results.get("terrain"),
        soil=results.get("soil"),
        errors=errors,
        land_cover=results.get("land_cover"),
    )


# --- parsing (pure) ------------------------------------------------------------------------


def parse_series(spec: SeriesSpec, raw: dict[str, list[dict[str, Any]]]) -> MonthlySeries:
    values: dict[str, float | None] = {}
    images: dict[str, int] = {}
    for collection_id in spec.collections:  # earlier collections win; later ones fill gaps
        for row in raw.get(collection_id, []):
            month, value, count = row["m"], row.get("v"), int(row.get("n") or 0)
            if values.get(month) is not None:
                continue
            if value is None or value == MISSING or count == 0:
                values.setdefault(month, None)
                images.setdefault(month, 0)
                continue
            values[month] = round(value * spec.scale + spec.offset, 4)
            images[month] = count
    order = sorted(values)
    return MonthlySeries(
        key=spec.key,
        dataset=spec.dataset,
        collections=spec.collections,
        unit=spec.unit,
        native_resolution=spec.native_resolution,
        note=spec.note,
        values={m: values[m] for m in order},
        images={m: images[m] for m in order},
    )


def _num(raw: dict[str, Any], key: str, divide: float = 1.0, digits: int = 2) -> float | None:
    value = raw.get(key)
    return None if value is None else round(float(value) / divide, digits)


def parse_terrain(raw: dict[str, Any]) -> Terrain:
    return Terrain(elevation_m=_num(raw, "elevation", digits=1), slope_deg=_num(raw, "slope"))


def parse_soil(raw: dict[str, Any]) -> Soil:
    v = {prop: _num(raw, prop, divide) for prop, (_, divide) in SOILGRIDS.items()}
    texture = None
    if None not in (v["sand"], v["silt"], v["clay"]):
        texture = texture_class(v["sand"], v["silt"], v["clay"])
    return Soil(
        clay_pct=v["clay"],
        sand_pct=v["sand"],
        silt_pct=v["silt"],
        soc_g_kg=v["soc"],
        ph=v["phh2o"],
        bulk_density_g_cm3=v["bdod"],
        texture=texture,
    )


def texture_class(sand: float, silt: float, clay: float) -> str:
    """USDA soil texture class (the standard texture-triangle rules, NRCS)."""
    total = sand + silt + clay
    if total <= 0:
        raise ValueError("sand + silt + clay must be positive")
    sand, silt, clay = (100 * x / total for x in (sand, silt, clay))
    if silt + 1.5 * clay < 15:
        return "sand"
    if silt + 2 * clay < 30:
        return "loamy sand"
    if (7 <= clay < 20 and sand > 52) or (clay < 7 and silt < 50):
        return "sandy loam"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52:
        return "loam"
    if silt >= 80 and clay < 12:
        return "silt"
    if silt >= 50 and clay < 27:
        return "silt loam"
    if 20 <= clay < 35 and silt < 28 and sand > 45:
        return "sandy clay loam"
    if 27 <= clay < 40 and sand <= 20:
        return "silty clay loam"
    if 27 <= clay < 40 and sand <= 45:
        return "clay loam"
    if clay >= 35 and sand > 45:
        return "sandy clay"
    if clay >= 40 and silt >= 40:
        return "silty clay"
    return "clay"
