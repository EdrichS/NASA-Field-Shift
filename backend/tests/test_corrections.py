"""The farmer's corrections to the satellite cards override the estimates."""

from app.engine.engine import run_engine

ANSWERS = {
    "current_crops": [{"crop": "rice", "plant_month": 6, "harvest_month": 10},
                      {"crop": "rice", "plant_month": 12, "harvest_month": 4}],
    "water": "irrigated", "equipment": "small_tractor", "top_goal": "earn_more",
}


def run(ph_ff, catalog, fixes, extra=None):
    cards = {k: {"status": "corrected", "value": v} for k, v in fixes.items()}
    answers = {**ANSWERS, **(extra or {}), "confirmed_prefill": cards}
    return run_engine(ph_ff, answers, catalog).to_dict()


def current(result):
    return next(s for s in result["strategies"] if s["key"] == "current")


def test_confirmed_or_unsure_cards_change_nothing(ph_ff, catalog):
    base = run_engine(ph_ff, ANSWERS, catalog).to_dict()
    same = run_engine(ph_ff, {**ANSWERS, "confirmed_prefill": {
        "slope": {"status": "confirmed"}, "soil": {"status": "unsure"}}}, catalog).to_dict()
    assert [s["total"] for s in base["strategies"]] == [s["total"] for s in same["strategies"]]
    assert not any(g.startswith("You ") for g in same["gaps"])


def test_steep_slope_lowers_erosion_score_and_is_stated(ph_ff, catalog):
    base = current(run_engine(ph_ff, ANSWERS, catalog).to_dict())
    result = run(ph_ff, catalog, {"slope": "steep"})
    erosion = current(result)["components"]["erosion"]["score"]
    assert erosion < base["components"]["erosion"]["score"]
    assert any("land is steep" in g for g in result["gaps"])


def test_heat_and_frost_months_replace_the_satellite_flags(ph_ff, catalog):
    result = run(ph_ff, catalog, {"heat": [], "frost": [1]})
    flags = {m["month"]: set(m["flags"]) for m in result["stress_calendar"]}
    assert not any("heat" in f for f in flags.values())
    assert "frost" in flags[1]
    jan = next(m for m in result["stress_calendar"] if m["month"] == 1)
    assert any(e["dataset"] == "Farmer's answer" for e in jan["evidence"])


def test_sandy_soil_removes_the_wet_soil_drainage_risk(ph_ff, catalog):
    base = run_engine(ph_ff, ANSWERS, catalog).to_dict()
    sandy = run(ph_ff, catalog, {"soil": "sandy"})
    wet = [r for s in base["strategies"] for r in s["risks"] if "stay wet" in r]
    assert wet, "the showcase field's clay soil should raise a drainage risk"
    assert not [r for s in sandy["strategies"] for r in s["risks"] if "clay" in r]


def test_corrected_bare_months_are_used(ph_ff, catalog):
    result = run_engine(ph_ff, {"confirmed_prefill": {
        "bare_months": {"status": "corrected", "value": [3, 4, 5]}}}, catalog).to_dict()
    assert result["bare_months"]["satellite"] == [3, 4, 5]
    assert any("months your field looks bare" in g for g in result["gaps"])


def test_soil_test_ph_overrides_soilgrids(ph_ff, catalog):
    result = run(ph_ff, catalog, {}, {"detailed": {"soil_test": {"ph": "5,2"}}})
    assert any("soil test pH 5.2" in g for g in result["gaps"])


def test_bad_correction_values_are_ignored(ph_ff, catalog):
    result = run(ph_ff, catalog, {"slope": "cliff", "heat": "lots", "bare_months": [13, "x"]})
    assert [s["title"] for s in result["strategies"]] == \
        [s["title"] for s in run(ph_ff, catalog, {})["strategies"]]


# --- regional crops (FAOSTAT) and no "unknown crop" -------------------------------------------

def _crops_in(result):
    return {c["crop"] for s in result["strategies"] for y in s["rotation"] for c in y}


def test_blank_crops_never_show_unknown_crop(ph_ff, catalog):
    for country in (None, "Philippines"):
        result = run_engine(ph_ff, {}, catalog, country=country).to_dict()
        assert "unknown crop" not in _crops_in(result)
        assert not any("unknown crop" in s["title"] for s in result["strategies"])


def test_suggestions_stay_with_crops_the_country_grows(ph_ff, catalog):
    from app.engine.regional import local_crops, tracked_crops

    local = local_crops("Philippines")
    assert local and "rice" in local and "pearl millet" not in local and "sorghum" not in local
    result = run_engine(ph_ff, ANSWERS, catalog, country="Philippines").to_dict()
    new = {c["crop"] for s in result["strategies"] for y in s["rotation"] for c in y if c["new"]}
    # cover crops FAOSTAT never records (sunn hemp, sesbania) are the only exception
    untracked_covers = {n for n, c in catalog.items() if c.is_cover} - tracked_crops()
    assert new and new - untracked_covers <= set(local)
    assert "buckwheat" not in new  # a cover crop FAOSTAT records, but not in the Philippines


def test_no_crops_or_exploring_means_no_comparison_and_nothing_assumed(ph_ff, catalog):
    for answers in ({}, {"mode": "exploring"}, {"not_farming": True}):
        result = run_engine(ph_ff, answers, catalog, country="Philippines").to_dict()
        keys = [s["key"] for s in result["strategies"]]
        assert "current" not in keys and keys and all(k.startswith("explore_") for k in keys)
        assert not any("we assumed" in g for g in result["gaps"])  # no crop is assumed
        assert "starting options" in result["gaps"][0]
        assert result["bare_months"]["current_rotation"] == []


def test_starting_options_are_local_and_different(ph_ff, catalog):
    from app.engine.regional import local_crops

    result = run_engine(ph_ff, {"mode": "exploring"}, catalog, country="Philippines").to_dict()
    mains = [s["rotation"][0][0]["crop"] for s in result["strategies"]]
    assert len(mains) == len(set(mains)) == 3
    assert set(mains) <= set(local_crops("Philippines"))
    assert all(s["why"] and s["name"].startswith("Start with") for s in result["strategies"])
