"""Earth Engine data tests. No network: the fixture holds real Earth Engine responses for the
Philippines test point (lat 15.6, lon 120.9), saved on Nov 14, 2026."""

import json
from datetime import date
from pathlib import Path

import pytest

from app.data import earthengine as E

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "ee_15.6_120.9.json").read_text())
POINT = {"type": "Point", "coordinates": [120.9, 15.6]}


def series(key):
    return E.parse_series(E.SERIES_BY_KEY[key], FIXTURE["series"][key])


def year(s, y):
    return [s.values.get(f"{y}-{m:02d}") for m in range(1, 13)]


# --- parsed values are physically sensible ----------------------------------------------------


def test_every_series_parses_with_a_long_record():
    for spec in E.SERIES:
        s = series(spec.key)
        assert len(s.months_with_data) > 100, spec.key  # each record spans 9+ years
        assert s.unit and s.native_resolution and s.dataset


def test_ndvi_is_scaled_to_index_range_and_shows_dry_season_dip():
    s = series("ndvi")
    assert all(-0.2 <= v <= 1 for v in s.values.values() if v is not None)
    ndvi_2025 = year(s, 2025)
    assert min(ndvi_2025[2:5]) < 0.45 < max(ndvi_2025[6:8])  # bare-ish Mar-May, green Jul-Aug


def test_temperatures_are_celsius_not_kelvin():
    assert all(10 < v < 60 for v in series("lst_day").values.values() if v is not None)


def test_et_and_rain_are_mm_per_day():
    assert all(0 <= v < 15 for v in series("et").values.values() if v is not None)
    rain = series("precip_imerg")
    assert all(0 <= v < 60 for v in rain.values.values() if v is not None)
    wet, dry = year(rain, 2024)[6:9], year(rain, 2024)[0:3]
    assert min(wet) > 3 * max(dry)


def test_soil_moisture_is_a_volume_fraction():
    for key in ("soil_moisture_root", "soil_moisture_surface"):
        assert all(0 < v < 0.7 for v in series(key).values.values() if v is not None)


def test_et_newest_months_come_from_the_8_day_product():
    s = series("et")
    assert s.values["2026-06"] is not None  # gap-filled product ends 2025-12
    assert s.values["2001-06"] is not None  # 8-day product starts 2021


def test_static_layers():
    terrain = E.parse_terrain(FIXTURE["terrain"])
    assert 0 < terrain.elevation_m < 200 and 0 <= terrain.slope_deg < 10
    soil = E.parse_soil(FIXTURE["soil"])
    assert abs(soil.clay_pct + soil.sand_pct + soil.silt_pct - 100) < 3  # g/kg -> % done right
    assert 4 < soil.ph < 9 and 0.8 < soil.bulk_density_g_cm3 < 2
    assert soil.texture == "silty clay loam"


# --- parsing rules ---------------------------------------------------------------------------


def test_missing_and_empty_months_become_none():
    spec = E.SERIES_BY_KEY["ndvi"]
    raw = {spec.collections[0]: [
        {"m": "2024-01", "v": 5000, "n": 2},
        {"m": "2024-02", "v": E.MISSING, "n": 2},
        {"m": "2024-03", "v": None, "n": 2},
        {"m": "2024-04", "v": 5000, "n": 0},
    ]}
    s = E.parse_series(spec, raw)
    assert s.values == {"2024-01": 0.5, "2024-02": None, "2024-03": None, "2024-04": None}


def test_earlier_collection_wins_and_later_fills_gaps():
    spec = E.SERIES_BY_KEY["et"]
    gap_filled, eight_day = spec.collections
    raw = {
        gap_filled: [{"m": "2025-12", "v": 160, "n": 4}, {"m": "2026-01", "v": None, "n": 0}],
        eight_day: [{"m": "2025-12", "v": 999, "n": 4}, {"m": "2026-01", "v": 240, "n": 4}],
    }
    s = E.parse_series(spec, raw)
    assert s.values["2025-12"] == 2.0  # 160 * 0.1 / 8 from the gap-filled product
    assert s.values["2026-01"] == 3.0  # filled from the 8-day product


@pytest.mark.parametrize(
    "sand,silt,clay,expected",
    [
        (90, 5, 5, "sand"),
        (80, 12, 8, "loamy sand"),
        (65, 20, 15, "sandy loam"),
        (40, 40, 20, "loam"),
        (20, 65, 15, "silt loam"),
        (5, 88, 7, "silt"),
        (60, 15, 25, "sandy clay loam"),
        (30, 35, 35, "clay loam"),
        (10, 55, 35, "silty clay loam"),
        (50, 14, 36, "sandy clay"),
        (5, 45, 50, "silty clay"),
        (20, 20, 60, "clay"),
    ],
)
def test_usda_texture_classes(sand, silt, clay, expected):
    assert E.texture_class(sand, silt, clay) == expected


# --- months and request chunks ----------------------------------------------------------------


def test_month_helpers():
    assert E.last_complete_month(date(2026, 11, 14)) == "2026-10"
    assert E.last_complete_month(date(2027, 1, 3)) == "2026-12"
    assert E.months_between("2015-04", "2026-10") == 139
    assert E.add_months("2025-11", 3) == "2026-02"
    pieces = E.chunks("2015-04", "2016-06", 12)
    assert pieces == [("2015-04", 12), ("2016-04", 3)]
    assert E.chunks("2001-01", "2001-12", None) == [("2001-01", 12)]


# --- caching: no Earth Engine call when cached ----------------------------------------------------


def test_fetch_field_uses_cache_without_touching_earth_engine(monkeypatch):
    class FixtureCache:
        def get(self, key, max_age_s=None):
            kind = key.split(":")[1]
            if kind == "terrain":
                return FIXTURE["terrain"]
            if kind == "soilgrids":
                return FIXTURE["soil"]
            if kind == "landcover":
                return FIXTURE["land_cover"]
            return FIXTURE["series"][kind]

        def set(self, key, value):
            raise AssertionError("nothing should be written when everything is cached")

    def no_earth_engine():
        raise AssertionError("Earth Engine must not be called")

    monkeypatch.setattr(E, "_ee", no_earth_engine)
    data = E.fetch_field(POINT, end_month=FIXTURE["end_month"], cache=FixtureCache())
    assert data.errors == {}
    assert set(data.series) == {s.key for s in E.SERIES}
    assert data.soil.texture == "silty clay loam"
    assert data.land_cover.main_class == "cropland"


def test_one_failing_dataset_is_reported_not_raised(monkeypatch):
    class EmptyCache:
        def get(self, key, max_age_s=None):
            return None

        def set(self, key, value):
            pass

    def broken():
        raise RuntimeError("Earth Engine is down")

    monkeypatch.setattr(E, "_ee", broken)
    data = E.fetch_field(POINT, end_month="2026-10", cache=EmptyCache())
    assert set(data.errors) == {s.key for s in E.SERIES} | {"terrain", "soil", "land_cover"}
    assert data.series == {} and data.soil is None
