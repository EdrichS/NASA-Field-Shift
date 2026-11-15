"""Engine tests: real Philippines fixtures plus synthetic fields where the right answer is known.
Offline: crop data from the CSV + an EcoCrop fixture."""

import json
from pathlib import Path

import pytest

from app.data import earthengine as E
from app.data import power
from app.data.crops import TRAITS_CSV
from app.data.earthengine import FieldSatelliteData
from app.engine import catalog as C
from app.engine.answers import parse_answers
from app.engine.candidates import suitability
from app.engine.engine import DISCLAIMER, run_engine
from app.engine.rotation import Slot, bare_by_month, gap_months, gaps, group_years
from app.engine.scoring import FieldContext, cold_night_c, survives_frost, weights_for
from app.features import harmonize as H
from app.features.prefill import prefill_cards
from app.features.stress import stress_calendar

FX = Path(__file__).parent / "fixtures"
CATALOG = C.load_from_files(TRAITS_CSV, FX / "ecocrop_sample.csv")
SHOWCASE = json.loads((FX.parents[2] / "data" / "showcase_farms.json").read_text())["farms"]
PH_ANSWERS = SHOWCASE[0]["answers"]
EVIDENCE_FIELDS = {"claim", "value", "unit", "dataset", "native_resolution", "period",
                   "confidence"}


def ph_features():
    raw = json.loads((FX / "ee_15.6_120.9.json").read_text())
    sat = FieldSatelliteData(
        "test", "2024-12",
        {s.key: E.parse_series(s, raw["series"][s.key]) for s in E.SERIES},
        E.parse_terrain(raw["terrain"]), E.parse_soil(raw["soil"]), {},
    )
    daily = power.parse_daily(json.loads((FX / "power_daily_15.6_120.9_2024.json").read_text()))
    clim = power.parse_climatology(
        json.loads((FX / "power_climatology_15.6_120.9_1996-2025.json").read_text()))
    yearly = power.parse_monthly(
        json.loads((FX / "power_monthly_15.6_120.9_1996-2025.json").read_text()))
    return H.harmonize({"type": "Point", "coordinates": [120.9, 15.6]}, "2024-12", daily,
                       clim, sat, yearly=yearly)


PH = ph_features()


def feature(key, normal, unit="", extra=None, detail="regional"):
    return H.Feature(key, key, unit, "test data", "test", detail, list(normal), "1996-2025",
                     list(normal), [f"2024-{m:02d}" for m in range(1, 13)], [0.0] * 12,
                     extra=extra or {})


def fake_field(t_mean, rain, heat_years=None, frost_years=None, t_cold=None, ndvi=None,
               slope=2.0, texture="loam", ph=6.5):
    features = {
        "t_mean": feature("t_mean", t_mean, "°C"),
        "rain": feature("rain", rain, "mm/day"),
        "solar": feature("solar", [18.0] * 12, "MJ/m^2/day"),
        "t_hottest": feature("t_hottest", [t + 8 for t in t_mean], "°C",
                             {"heat_years": heat_years or [0] * 12, "years": "1996-2025"}),
        "t_coldest": feature("t_coldest", t_cold or [t - 10 for t in t_mean], "°C",
                             {"frost_years": frost_years or [0] * 12, "years": "1996-2025"}),
    }
    if ndvi:
        features["ndvi"] = feature("ndvi", ndvi, "NDVI", detail="field")
    static = {"terrain": {"elevation_m": 50, "slope_deg": slope, "dataset": "SRTM",
                          "native_resolution": "30 m"},
              "soil": {"texture": texture, "ph": ph, "clay_pct": 20, "dataset": "SoilGrids",
                       "native_resolution": "250 m"}}
    return H.FieldFeatures("fake", 0.0, 0.0, "2024-12", features, static, [])


WARM = [26.0] * 12
WET = [5.0] * 12


# --- the Philippines showcase, end to end --------------------------------------------------------


def test_showcase_gives_current_plus_four_alternatives():
    result = run_engine(PH, PH_ANSWERS, CATALOG)
    keys = [s.key for s in result.strategies]
    assert sorted(keys) == ["add_income", "break_pest", "current", "fill_bare", "save_water"]
    assert [s.rank for s in result.strategies] == [1, 2, 3, 4, 5]
    assert result.disclaimer == DISCLAIMER


def test_showcase_fill_bare_adds_a_legume_or_cover_crop_into_a_real_gap():
    result = run_engine(PH, PH_ANSWERS, CATALOG)
    fill = next(s for s in result.strategies if s.key == "fill_bare")
    new = [slot for year in fill.rotation for slot in year if slot["new"]]
    assert new, "fill_bare must add a crop"
    crop = CATALOG[new[0]["crop"]]
    assert crop.is_legume or crop.is_cover
    current = next(s for s in result.strategies if s.key == "current")
    assert sum(m["bare"] for m in fill.calendar) < sum(m["bare"] for m in current.calendar)


def test_every_component_and_month_carries_complete_evidence():
    data = run_engine(PH, PH_ANSWERS, CATALOG).to_dict()
    for strategy in data["strategies"]:
        for comp in strategy["components"].values():
            assert comp["evidence"], comp["summary"]
            for ev in comp["evidence"]:
                assert set(ev) == EVIDENCE_FIELDS
    json.dumps(data)  # API-ready


def test_engine_is_deterministic():
    assert run_engine(PH, PH_ANSWERS, CATALOG).to_dict() == \
        run_engine(PH, PH_ANSWERS, CATALOG).to_dict()


def test_wont_grow_crops_never_appear():
    answers = {**PH_ANSWERS, "wont_grow": ["mungbean", "sorghum", "cowpea"]}
    for strategy in run_engine(PH, answers, CATALOG).strategies:
        crops = {slot["crop"] for year in strategy.rotation for slot in year}
        assert not crops & {"mungbean", "sorghum", "cowpea"}, strategy.key


def test_alternatives_are_all_different_rotations():
    titles = [s.title for s in run_engine(PH, PH_ANSWERS, CATALOG).strategies]
    assert len(set(titles)) == len(titles)


def test_alternatives_explain_themselves():
    for s in run_engine(PH, PH_ANSWERS, CATALOG).strategies:
        if s.key == "current":
            continue
        assert s.why and s.changes and s.expert_questions
        assert s.confidence in ("high", "medium", "low")


# --- synthetic fields with known answers ----------------------------------------------------------


def test_bare_window_gets_filled():
    ff = fake_field(WARM, WET)
    answers = {"current_crops": [{"crop": "maize", "plant_month": 6, "harvest_month": 10}],
               "water": "rainfed", "equipment": "hand_tools", "top_goal": "build_soil"}
    fill = next(s for s in run_engine(ff, answers, CATALOG).strategies if s.key == "fill_bare")
    new = [slot for year in fill.rotation for slot in year if slot["new"]][0]
    assert new["plant_month"] == 10 and new["harvest_month"] == 6  # the Oct-Jun gap


def test_monoculture_gets_a_new_plant_family():
    ff = fake_field(WARM, WET)
    answers = {"current_crops": [{"crop": "rice", "plant_month": 12, "harvest_month": 4},
                                 {"crop": "rice", "plant_month": 6, "harvest_month": 10}],
               "water": "irrigated", "equipment": "small_tractor", "top_goal": "earn_more"}
    pest = next(s for s in run_engine(ff, answers, CATALOG).strategies if s.key == "break_pest")
    families = {CATALOG[slot["crop"]].family for year in pest.rotation for slot in year}
    assert len(families) >= 2


def test_save_water_needs_less_water_than_the_current_rotation():
    ff = fake_field(WARM, [1.0] * 12)
    answers = {"current_crops": [{"crop": "rice", "plant_month": 12, "harvest_month": 4}],
               "water": "irrigated", "equipment": "hand_tools", "top_goal": "save_water"}
    result = run_engine(ff, answers, CATALOG)
    by_key = {s.key: s for s in result.strategies}
    assert by_key["save_water"].components["water"]["metrics"]["deficit_mm"] < \
        by_key["current"].components["water"]["metrics"]["deficit_mm"]


def test_frost_sensitive_crops_are_never_placed_in_frost_months():
    cold = [-8, -6, 2, 9, 16, 21, 24, 23, 18, 11, 3, -4]
    frost = [30, 30, 25, 10, 3, 0, 0, 0, 0, 5, 20, 30]
    ff = fake_field(cold, [2.5] * 12, frost_years=frost, t_cold=[t - 16 for t in cold])
    answers = {"current_crops": [{"crop": "maize", "plant_month": 5, "harvest_month": 10}],
               "water": "rainfed", "equipment": "full_machinery", "top_goal": "build_soil"}
    for s in run_engine(ff, answers, CATALOG).strategies:
        for year in s.rotation:
            for slot in year:
                if slot["new"]:
                    crop = CATALOG[slot["crop"]]
                    for m in Slot(**slot).months():
                        if frost[m - 1] >= 3:
                            assert survives_frost(crop, cold[m - 1], cold[m - 1] - 16), \
                                (crop.name, m)


def test_winter_rye_survives_an_iowa_january_but_oats_do_not():
    night = cold_night_c(-6.6, -23.2)
    assert -17 < night < -16
    assert survives_frost(CATALOG["cereal rye"], -6.6, -23.2)
    assert not survives_frost(CATALOG["oats"], -6.6, -23.2)


def test_goals_change_weights_and_rank():
    assert weights_for(["save_water"])["water"] > weights_for(["earn_more"])["water"]
    assert abs(sum(weights_for(["build_soil", "earn_more"]).values()) - 1) < 1e-3
    assert len(set(weights_for([]).values())) == 1  # no goal: equal weights


def test_unknown_answers_become_information_gaps():
    profile = parse_answers({"current_crops": [{"crop": "corn", "plant_month": 5,
                                                "harvest_month": 10}]}, CATALOG)
    assert profile.slots[0].crop == "maize"  # alias
    assert profile.water == "rainfed" and profile.equipment == "hand_tools"
    assert any("Irrigation unknown" in a for a in profile.assumptions)
    assert any("No goal" in a for a in profile.assumptions)


def test_just_exploring_estimates_crops_from_satellite_greenness():
    ndvi = [0.3, 0.3, 0.3, 0.3, 0.7, 0.8, 0.8, 0.8, 0.7, 0.3, 0.3, 0.3]
    ff = fake_field(WARM, WET, ndvi=ndvi)
    result = run_engine(ff, {"mode": "exploring"}, CATALOG)
    assert result.profile["rotation_source"] == "satellite"
    assert result.strategies  # still produces a comparison


# --- building blocks ---------------------------------------------------------------


def test_stress_calendar_on_the_philippines_fixture():
    flags = {m["name"]: set(m["flags"]) for m in stress_calendar(PH)}
    assert "heat" in flags["Apr"] and "very_wet" in flags["Aug"] and "dry" in flags["Jan"]
    assert not any("frost" in f for f in flags.values())


def test_dry_months_only_count_when_crops_can_grow():
    ff = fake_field([-5.0] * 3 + [15.0] * 9, [1.0] * 12)
    flags = [set(m["flags"]) for m in stress_calendar(ff)]
    assert "dry" not in flags[0] and "dry" in flags[5]


def test_prefill_cards_for_the_philippines():
    ids = {card["id"] for card in prefill_cards(PH)}
    assert {"bare_months", "driest_soil", "rain", "heat", "frost", "slope", "soil"} <= ids
    for card in prefill_cards(PH):
        assert card["statement"] and card["confidence"] in ("high", "medium", "low")


def test_rotation_arithmetic():
    dry, wet = Slot("rice", 12, 4), Slot("rice", 6, 10)
    assert dry.occupancy() == {12: 0.5, 1: 1.0, 2: 1.0, 3: 1.0, 4: 0.5}
    found = gaps([[dry, wet]])
    assert sorted((g.start_month, g.end_month, g.days) for g in found) == \
        [(4, 6, 60), (10, 12, 60)]
    assert gap_months(found[0]) in ([4, 5, 6], [10, 11, 12])
    corn, soy = Slot("maize", 5, 10), Slot("soybean", 5, 10)
    assert group_years([corn, soy]) == [[corn], [soy]]  # alternate years
    assert bare_by_month([[corn]])[0] == 1.0


@pytest.mark.parametrize("name,expected", [("corn", "maize"), ("Mung bean", "mungbean"),
                                           ("palay", "rice"), ("nothing", None)])
def test_crop_aliases(name, expected):
    crop = C.resolve(name, CATALOG)
    assert (crop.name if crop else None) == expected


@pytest.mark.parametrize("name,expected", [
    ("Sweet potatoes", "sweet potato"), ("Mung beans", "mungbean"), ("Tomatoes", "tomato"),
    ("Groundnuts", "peanut"), ("Cowpeas", "cowpea"), ("soya  beans", "soybean"),
    ("Cabbages", "cabbage"), ("Oats", "oats"), ("Chilli", "chili pepper")])
def test_crop_names_as_farmers_type_them(name, expected):
    crop = C.resolve(name, CATALOG)
    assert (crop.name if crop else None) == expected


def test_wont_grow_accepts_plurals_and_is_never_suggested():
    answers = {**PH_ANSWERS, "wont_grow": ["Mung beans", "String beans", "Okras"]}
    assert parse_answers(answers, CATALOG).wont_grow == {"mungbean", "string bean", "okra"}
    for s in run_engine(PH, answers, CATALOG).strategies:
        new = {slot["crop"] for year in s.rotation for slot in year if slot["new"]}
        assert not new & {"mungbean", "string bean", "okra"}, s.key


def test_wont_grow_also_applies_to_crops_guessed_from_satellite():
    guessed = run_engine(PH, {}, CATALOG, country="Philippines").strategies
    first = next(s for s in guessed if s.key == "current").rotation[0][0]["crop"]
    current = next(s for s in run_engine(PH, {"wont_grow": [first]}, CATALOG,
                                         country="Philippines").strategies if s.key == "current")
    assert first not in {slot["crop"] for year in current.rotation for slot in year}


def test_rainfed_crop_with_less_rain_than_its_absolute_minimum_is_unsuitable():
    ff = fake_field(WARM, [0.5] * 12)  # ~180 mm a year
    ctx = FieldContext.build(ff, stress_calendar(ff))
    rice = CATALOG["rice"]  # EcoCrop: at least 1000 mm
    assert suitability(rice, [6, 7, 8, 9], ctx, "rainfed").score == 0
    assert suitability(rice, [6, 7, 8, 9], ctx, "irrigated").score >= 0.6


def test_rainfed_crop_is_not_placed_in_the_dry_season():
    sahel = [0.0, 0.0, 0.0, 0.0, 0.5, 2.5, 5.0, 6.0, 3.0, 0.5, 0.0, 0.0]  # ~550 mm, Jun-Sep
    ff = fake_field(WARM, sahel)
    ctx = FieldContext.build(ff, stress_calendar(ff))
    mungbean = CATALOG["mungbean"]  # EcoCrop: at least 500 mm
    assert suitability(mungbean, [7, 8, 9], ctx, "rainfed").score > 0
    assert suitability(mungbean, [12, 1, 2, 3], ctx, "rainfed").score == 0
    assert suitability(mungbean, [12, 1, 2, 3], ctx, "irrigated").score > 0


def test_crops_without_a_killing_temperature_are_frost_tender_not_always_dead():
    maize = CATALOG["maize"]
    assert maize.eco.get("killing_temp_c") is None
    assert survives_frost(maize, 16.2, 2.2)  # Iowa May: cold night ~7.8 C
    assert not survives_frost(maize, -6.6, -23.2)  # Iowa January


@pytest.mark.parametrize("crops", [
    [{"crop": "cassava", "plant_month": 5, "harvest_month": 4}],
    [{"crop": "maize", "plant_month": 6, "harvest_month": 9}],
    PH_ANSWERS["current_crops"]])
def test_new_crops_are_never_placed_much_longer_than_they_grow(crops):
    for s in run_engine(PH, {**PH_ANSWERS, "current_crops": crops}, CATALOG).strategies:
        for year in s.rotation:
            for slot in year:
                crop = CATALOG[slot["crop"]]
                if slot["new"] and not crop.is_cover:
                    days = Slot(slot["crop"], slot["plant_month"], slot["harvest_month"]).days
                    assert days <= crop.cycle_max_days + 45, (s.key, slot)


def test_break_pest_needs_a_repeated_family_and_alternates_a_single_crop():
    two_families = [{"crop": "maize", "plant_month": 6, "harvest_month": 9},
                    {"crop": "soybean", "plant_month": 6, "harvest_month": 9}]
    keys = {s.key for s in run_engine(PH, {**PH_ANSWERS, "current_crops": two_families},
                                      CATALOG).strategies}
    assert "break_pest" not in keys
    one = [{"crop": "cassava", "plant_month": 5, "harvest_month": 4}]
    pest = next(s for s in run_engine(PH, {**PH_ANSWERS, "current_crops": one},
                                      CATALOG).strategies if s.key == "break_pest")
    assert len(pest.rotation) == 2 and pest.rotation[0][0]["crop"] == "cassava"
    assert pest.components["pest_cycle"]["score"] > next(
        s for s in run_engine(PH, {**PH_ANSWERS, "current_crops": one}, CATALOG).strategies
        if s.key == "current").components["pest_cycle"]["score"]


def test_half_covered_planting_and_harvest_months_are_not_mostly_bare():
    current = next(s for s in run_engine(PH, PH_ANSWERS, CATALOG).strategies
                   if s.key == "current")
    assert current.components["erosion"]["metrics"]["bare_months"] == ["May", "Oct", "Nov", "Dec"]


def test_a_twelve_month_crop_is_kept():
    profile = parse_answers(
        {"current_crops": [{"crop": "cassava", "plant_month": 5, "harvest_month": 5}]}, CATALOG)
    assert [s.days for s in profile.slots] == [360]
    assert not any("missing" in a for a in profile.assumptions)


def test_a_country_where_none_of_our_crops_is_grown_widely_still_gets_options():
    result = run_engine(PH, PH_ANSWERS, CATALOG, country="Bahamas")
    assert len(result.strategies) > 1
    assert any("None of the crops SowSmart knows" in g for g in result.gaps)
    assert not any("couldn't tell which country" in g for g in result.gaps)


def test_missing_ecocrop_ranges_are_flagged_not_silent():
    bare = C.load_from_files(TRAITS_CSV, FX / "no_such_ecocrop.csv")
    assert not C.has_ranges(bare) and C.has_ranges(CATALOG)
    assert any("EcoCrop" in g for g in run_engine(PH, PH_ANSWERS, bare).gaps)


def test_crops_in_dry_months_with_unknown_irrigation_mean_some_irrigation():
    guessed = run_engine(PH, {}, CATALOG, country="Philippines")
    assert any("assumed some irrigation" in g for g in guessed.gaps)
    assert len(guessed.strategies) >= 4
    told = run_engine(PH, {"water": "rainfed"}, CATALOG, country="Philippines")
    assert not any("assumed some irrigation" in g for g in told.gaps)


def test_unknown_country_guesses_a_staple_and_does_not_call_it_the_most_grown():
    gaps = run_engine(PH, {}, CATALOG).gaps
    assumed = next(g for g in gaps if g.startswith("You didn't list your crops"))
    assert "alfalfa" not in assumed and "most widely grown" not in assumed
