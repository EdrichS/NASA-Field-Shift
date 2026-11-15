"""Crop data checks. Offline: EcoCrop rows for our 25 crops are saved as a fixture."""

from pathlib import Path

import pytest

from app.data import crops as C

FX = Path(__file__).parent / "fixtures"
ECOCROP = C.load_ecocrop(FX / "ecocrop_sample.csv")
NAMES = set(ECOCROP)
TEAM_HEADER, TEAM_ROWS = C.read_csv(C.TRAITS_CSV)
CROPS = {"rice", "mungbean", "maize", "soybean"}


def trait_row(**changes):
    row = dict.fromkeys(C.TRAIT_COLUMNS, "")
    row.update(
        crop="mungbean", scientific_name="Vigna radiata", family="Fabaceae", is_legume="yes",
        root_depth_m="0.6", water_need="low", heat_tolerance="high", drought_tolerance="high",
        waterlogging_tolerance="low", cover_crop_role="green_manure", forage="yes",
        labor_need="medium", source="FAO-56 Table 22 | PhilRice guide",
    )
    row.update(changes)
    return row


def pest_row(**changes):
    row = dict.fromkeys(C.PEST_COLUMNS, "")
    row.update(
        pest="rice blast", kind="disease", crops="rice",
        description="Warm, very humid days favor rice blast", t_min_c="24", t_max_c="28",
        rh_min_pct="90", consecutive_days="3", source="IRRI Rice Knowledge Bank",
        source_url="https://example.org/blast",
    )
    row.update(changes)
    return row


# --- the team's actual files ---------------------------------------------------------------


def test_team_traits_file_has_no_errors():
    report = C.validate_traits(TEAM_HEADER, TEAM_ROWS, NAMES)
    assert report.ok, report.errors


def test_team_scientific_names_all_match_ecocrop():
    assert all(r["scientific_name"] in NAMES for r in TEAM_ROWS)


def test_team_pest_rules_file_has_no_errors():
    header, rows = C.read_csv(C.PEST_RULES_CSV)
    report = C.validate_pest_rules(header, rows, {r["crop"] for r in TEAM_ROWS})
    assert report.ok, report.errors


# --- trait rules ---------------------------------------------------------------------------


def test_complete_row_passes_strict():
    report = C.validate_traits(C.TRAIT_COLUMNS, [trait_row()], NAMES, strict=True)
    assert report.ok and not report.warnings


def test_todo_source_is_a_warning_normally_and_an_error_when_strict():
    rows = [trait_row(source="TODO")]
    assert C.validate_traits(C.TRAIT_COLUMNS, rows, NAMES).warnings
    assert not C.validate_traits(C.TRAIT_COLUMNS, rows, NAMES, strict=True).ok


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"water_need": "High"}, "water_need"),
        ({"is_legume": "no"}, "Fabaceae"),
        ({"scientific_name": "Vigna imaginaria"}, "not in EcoCrop"),
        ({"root_depth_m": "60"}, "root_depth_m"),
        ({"family": "Leguminosae"}, "family"),
        ({"cover_crop_role": "mulch"}, "cover_crop_role"),
        ({"forage": "Y"}, "forage"),
        ({"source": ""}, "source is empty"),
    ],
)
def test_bad_trait_values_are_errors(changes, message):
    report = C.validate_traits(C.TRAIT_COLUMNS, [trait_row(**changes)], NAMES)
    assert any(message in e for e in report.errors), report.errors


def test_duplicate_crops_and_wrong_header_are_errors():
    assert not C.validate_traits(C.TRAIT_COLUMNS, [trait_row(), trait_row()], NAMES).ok
    assert not C.validate_traits(["crop", "family"], [trait_row()], NAMES).ok


def test_missing_ecocrop_file_only_warns():
    report = C.validate_traits(C.TRAIT_COLUMNS, [trait_row()], None)
    assert report.ok and any("EcoCrop" in w for w in report.warnings)


# --- pest rules ----------------------------------------------------------------------------


def test_complete_pest_rule_passes():
    assert C.validate_pest_rules(C.PEST_COLUMNS, [pest_row()], CROPS, strict=True).ok


@pytest.mark.parametrize(
    "changes,message",
    [
        ({"description": "Rice blast outbreak likely"}, "conditions favor"),
        ({"crops": "corn"}, "not in crops_traits"),
        ({"t_min_c": "30", "t_max_c": "20"}, "above"),
        ({"source_url": "irri.org/blast"}, "link"),
        ({"consecutive_days": ""}, "whole number"),
        ({"consecutive_days": "2.5"}, "whole number"),
        ({"kind": "fungus"}, "disease or insect"),
        ({"rh_min_pct": "120"}, "rh_min_pct"),
        ({"t_min_c": "", "t_max_c": "", "rh_min_pct": ""}, "at least one"),
    ],
)
def test_bad_pest_rules_are_errors(changes, message):
    report = C.validate_pest_rules(C.PEST_COLUMNS, [pest_row(**changes)], CROPS)
    assert any(message in e for e in report.errors), report.errors


def test_no_pest_rules_yet_warns_unless_strict():
    assert C.validate_pest_rules(C.PEST_COLUMNS, [], CROPS).warnings
    assert not C.validate_pest_rules(C.PEST_COLUMNS, [], CROPS, strict=True).ok


# --- converting to database rows -----------------------------------------------------------------


def test_ecocrop_record_converts_numbers_and_na():
    mungbean = C.ecocrop_record(ECOCROP["Vigna radiata"])
    assert mungbean["cycle_min_days"] == 50 and mungbean["temp_opt_max_c"] == 36
    rice = C.ecocrop_record(ECOCROP["Oryza sativa"])
    assert rice["killing_temp_c"] is None  # "NA" in EcoCrop
    assert "poorly" in rice["drainage_opt"]


def test_crop_record_types_and_unverified_source():
    rec = C.crop_record(trait_row(source="TODO"), ECOCROP["Vigna radiata"])
    assert rec["is_legume"] is True and rec["forage"] is True and rec["root_depth_m"] == 0.6
    assert rec["traits_source"] is None  # TODO means not verified yet
    assert rec["ecocrop"]["cycle_min_days"] == 50


def test_pest_rule_record():
    rec = C.pest_rule_record(pest_row(crops="rice; mungbean"))
    assert rec["crops"] == ["rice", "mungbean"]
    assert rec["rule"]["consecutive_days"] == 3 and rec["rule"]["rh_min_pct"] == 90
    assert rec["rule"]["rain_min_mm_day"] is None
