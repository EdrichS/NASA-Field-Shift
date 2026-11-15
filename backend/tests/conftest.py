"""Shared offline fixtures: the Philippines showcase field built from recorded API responses."""

import json
from pathlib import Path

import pytest

from app.data import earthengine as E
from app.data import power
from app.data.crops import TRAITS_CSV
from app.data.earthengine import FieldSatelliteData
from app.engine import catalog as C
from app.features import harmonize as H

FX = Path(__file__).parent / "fixtures"
RAW = json.loads((FX / "ee_15.6_120.9.json").read_text())
POINT = {"type": "Point", "coordinates": [120.9, 15.6]}
SHOWCASE = json.loads((FX.parents[2] / "data" / "showcase_farms.json").read_text())["farms"]


def build_ph_features(land_cover=RAW["land_cover"], with_power=True):
    sat = FieldSatelliteData(
        "test", "2024-12",
        {s.key: E.parse_series(s, RAW["series"][s.key]) for s in E.SERIES},
        E.parse_terrain(RAW["terrain"]), E.parse_soil(RAW["soil"]), {},
        E.parse_land_cover(land_cover),
    )
    daily = clim = yearly = None
    if with_power:
        daily = power.parse_daily(
            json.loads((FX / "power_daily_15.6_120.9_2024.json").read_text()))
        clim = power.parse_climatology(
            json.loads((FX / "power_climatology_15.6_120.9_1996-2025.json").read_text()))
        yearly = power.parse_monthly(
            json.loads((FX / "power_monthly_15.6_120.9_1996-2025.json").read_text()))
    return H.harmonize(POINT, "2024-12", daily, clim, sat, yearly=yearly)


@pytest.fixture(scope="session")
def ph_ff():
    return build_ph_features()


@pytest.fixture(scope="session")
def make_ph():
    return build_ph_features


@pytest.fixture(scope="session")
def catalog():
    return C.load_from_files(TRAITS_CSV, FX / "ecocrop_sample.csv")
