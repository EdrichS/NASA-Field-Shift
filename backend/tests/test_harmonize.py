"""Harmonizer tests. No network: real POWER and Earth Engine responses saved as fixtures for the
Philippines test point (lat 15.6, lon 120.9)."""

import json
import statistics
from pathlib import Path

from app.data import earthengine as E
from app.data import power
from app.data.earthengine import FieldSatelliteData
from app.data.geometry import centroid
from app.features import harmonize as H

FX = Path(__file__).parent / "fixtures"
DAILY = power.parse_daily(json.loads((FX / "power_daily_15.6_120.9_2024.json").read_text()))
CLIM = power.parse_climatology(
    json.loads((FX / "power_climatology_15.6_120.9_1996-2025.json").read_text())
)
YEARLY = power.parse_monthly(
    json.loads((FX / "power_monthly_15.6_120.9_1996-2025.json").read_text())
)
EE_RAW = json.loads((FX / "ee_15.6_120.9.json").read_text())
POINT = {"type": "Point", "coordinates": [120.9, 15.6]}


def satellite(errors=None, end="2024-12"):
    return FieldSatelliteData(
        geom_hash="test",
        end_month=end,
        series={s.key: E.parse_series(s, EE_RAW["series"][s.key]) for s in E.SERIES},
        terrain=E.parse_terrain(EE_RAW["terrain"]),
        soil=E.parse_soil(EE_RAW["soil"]),
        errors=errors or {},
    )


def build(end="2024-12", **kw):
    args = {"daily": DAILY, "clim": CLIM, "satellite": satellite(end=end), "yearly": YEARLY}
    args.update(kw)
    return H.harmonize(POINT, end, args["daily"], args["clim"], args["satellite"],
                       kw.get("gaps"), yearly=args["yearly"])


def jan_2024(param):
    return [r[param] for r in DAILY.rows if r["date"].strftime("%Y-%m") == "2024-01"]


def test_every_feature_has_twelve_months():
    ff = build()
    expected = {k for _, k, _, _ in H.POWER_FEATURES} | set(H.SATELLITE_FEATURES)
    assert set(ff.features) == expected
    for f in ff.features.values():
        assert len(f.normal) == len(f.recent) == len(f.anomaly) == len(f.recent_months) == 12


def test_power_recent_window_and_monthly_values():
    rain = build().features["rain"]
    assert rain.recent_months == [f"2024-{m:02d}" for m in range(1, 13)]
    assert rain.normal == CLIM.monthly["PRECTOTCORR"]
    assert rain.recent[0] == round(statistics.fmean(jan_2024("PRECTOTCORR")), 4)
    assert rain.anomaly[0] == round(rain.recent[0] - rain.normal[0], 4)
    assert rain.spatial_detail == "regional" and rain.normal_period == "1996-2025"


def test_extremes_use_typical_year_not_the_30_year_record():
    cold = build().features["t_coldest"]
    jan_years = [v for m, v in YEARLY.values["T2M_MIN"].items() if m.endswith("-01")]
    assert cold.normal[0] == round(statistics.fmean(jan_years), 4)  # ~17.4 °C typical
    assert cold.extra["record_30y"][0] == min(jan_years) == 14.92  # the 30-year record
    assert cold.extra["frost_years"] == [0] * 12  # no frost in 30 years in Central Luzon
    assert cold.recent[0] == min(jan_2024("T2M_MIN"))
    hot = build().features["t_hottest"]
    assert hot.recent[0] == max(jan_2024("T2M_MAX"))
    assert hot.extra["heat_years"][3] > 15  # April passes 35 °C in most years


def test_without_yearly_data_extremes_report_no_anomaly():
    cold = build(yearly=None).features["t_coldest"]
    assert cold.extra == {"normal_is_30y_record": True}
    assert cold.anomaly == [None] * 12


def test_satellite_normals_windows_and_detail():
    ff = build()
    ndvi = ff.features["ndvi"]
    assert ndvi.spatial_detail == "field"
    assert ndvi.recent_months == [f"2024-{m:02d}" for m in range(1, 13)]
    assert min(ndvi.normal[3:6]) < 0.5 < max(ndvi.normal[7:9])  # Apr-Jun low, Aug-Sep green
    assert ff.features["soil_moisture_root"].spatial_detail == "local"


def test_lagging_dataset_uses_its_own_latest_months():
    ff = build(end="2026-10")
    assert ff.features["ndvi"].recent_months[9] == "2026-10"
    assert ff.features["ndvi"].recent_months[10] == "2025-11"
    imerg = ff.features["precip_imerg"]
    assert imerg.recent_months[8] == "2025-09"  # IMERG monthly ends 2025-09
    assert imerg.recent_months[9] == "2024-10"


def test_ground_temperature_normal_stops_in_2022_and_has_no_anomaly():
    lst = build().features["lst_day"]
    assert lst.normal_period == "2001-2022"
    assert lst.anomaly == [None] * 12
    assert "drift" in lst.note


def test_static_layers_and_regional_water_trend():
    ff = build()
    assert ff.static["soil"]["texture"] == "silty clay loam"
    assert ff.static["terrain"]["slope_deg"] < 10
    assert isinstance(ff.static["water_storage"]["trend_cm_per_year"], float)
    assert (ff.lon, ff.lat) == (120.9, 15.6)


def test_missing_sources_become_information_gaps():
    ff = H.harmonize(
        POINT, "2024-12", None, None, satellite(errors={"ndvi": "EEException: boom"}),
        ["NASA POWER recent weather unavailable (ConnectError)"],
    )
    assert "rain" not in ff.features
    assert any("POWER" in g for g in ff.gaps)
    assert any("'ndvi'" in g for g in ff.gaps)


def test_to_dict_is_json_ready():
    json.dumps(build().to_dict())


def test_window_and_trend_helpers():
    assert H.window("2026-10")[0] == "2026-01" and H.window("2026-10")[11] == "2025-12"
    rising = {f"{2000 + i // 12}-{i % 12 + 1:02d}": i / 12 for i in range(60)}
    assert abs(H.linear_trend(rising) - 1.0) < 0.01  # 1 cm per year
    assert H.linear_trend({"2020-01": 1.0}) is None


def test_polygon_centroid():
    square = {"type": "Polygon",
              "coordinates": [[[0, 0], [0.02, 0], [0.02, 0.02], [0, 0.02], [0, 0]]]}
    assert centroid(square) == (0.01, 0.01)
