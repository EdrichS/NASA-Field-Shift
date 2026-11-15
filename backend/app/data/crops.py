"""Crop data: FAO EcoCrop ranges + team-curated crop traits + pest-risk weather rules.

- FAO EcoCrop database (via the OpenCLIM/ecocrop repo, Open Government Licence v3): climate,
  soil and growing-season ranges per crop. Column meanings follow FAO EcoCrop.
- data/crops_traits.csv: one row per crop, team-curated, a source on every row.
- data/pest_rules.csv: weather conditions that favor pests and diseases, every rule cited.

Pure functions only (read, validate, convert); scripts/validate_data.py and scripts/load_crops.py
use them, and tests run on small fixtures.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
TRAITS_CSV = ROOT / "data" / "crops_traits.csv"
PEST_RULES_CSV = ROOT / "data" / "pest_rules.csv"
ECOCROP_CSV = ROOT / "data" / "raw" / "EcoCrop_DB.csv"

TRAIT_COLUMNS = [
    "crop", "scientific_name", "family", "is_legume", "root_depth_m", "water_need",
    "heat_tolerance", "drought_tolerance", "waterlogging_tolerance", "cover_crop_role",
    "forage", "labor_need", "source", "notes",
]
PEST_COLUMNS = [
    "pest", "kind", "crops", "description", "t_min_c", "t_max_c", "rh_min_pct", "rh_max_pct",
    "rain_min_mm_day", "consecutive_days", "source", "source_url",
]
LEVEL_COLUMNS = ["water_need", "heat_tolerance", "drought_tolerance", "waterlogging_tolerance",
                 "labor_need"]
LEVELS = {"low", "medium", "high"}
YES_NO = {"yes", "no"}
COVER_ROLES = {"none", "cover", "green_manure"}
PEST_KINDS = {"disease", "insect"}
FAMILY_PATTERN = re.compile(r"^[A-Z][a-z]+aceae$")
ALARM_WORDS = ("outbreak", "infestation", "epidemic")  # alerts only ever say "conditions favor"
TODO = "TODO"

# Pest-rule thresholds: column -> (lowest allowed, highest allowed)
PEST_RANGES = {
    "t_min_c": (-10, 50),
    "t_max_c": (-10, 50),
    "rh_min_pct": (0, 100),
    "rh_max_pct": (0, 100),
    "rain_min_mm_day": (0, 500),
}

# FAO EcoCrop column -> (our key, kind). Rainfall is EcoCrop's annual rainfall in mm.
ECOCROP_FIELDS = {
    "EcoPortCode": ("ecoport_code", "text"),
    "COMNAME": ("common_names", "text"),
    "LIFO": ("life_form", "text"),
    "CAT": ("category", "text"),
    "TOPMN": ("temp_opt_min_c", "num"),
    "TOPMX": ("temp_opt_max_c", "num"),
    "TMIN": ("temp_abs_min_c", "num"),
    "TMAX": ("temp_abs_max_c", "num"),
    "ROPMN": ("rain_opt_min_mm", "num"),
    "ROPMX": ("rain_opt_max_mm", "num"),
    "RMIN": ("rain_abs_min_mm", "num"),
    "RMAX": ("rain_abs_max_mm", "num"),
    "PHOPMN": ("ph_opt_min", "num"),
    "PHOPMX": ("ph_opt_max", "num"),
    "PHMIN": ("ph_abs_min", "num"),
    "PHMAX": ("ph_abs_max", "num"),
    "KTMP": ("killing_temp_c", "num"),
    "KTMPR": ("killing_temp_rest_c", "num"),
    "GMIN": ("cycle_min_days", "num"),
    "GMAX": ("cycle_max_days", "num"),
    "DRA": ("drainage_opt", "text"),
    "DRAR": ("drainage_range", "text"),
    "TEXT": ("texture_opt", "text"),
    "TEXTR": ("texture_range", "text"),
    "DEP": ("soil_depth_opt", "text"),
    "SAL": ("salinity_opt", "text"),
    "PHOTO": ("photoperiod", "text"),
}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# --- reading -------------------------------------------------------------------------------


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Header and rows, with cells stripped. utf-8-sig handles Excel's byte-order mark."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = [h.strip() for h in (reader.fieldnames or [])]
        rows = [{k.strip(): (v or "").strip() for k, v in row.items() if k} for row in reader]
    return header, rows


def load_ecocrop(path: Path = ECOCROP_CSV) -> dict[str, dict[str, str]] | None:
    """EcoCrop rows by scientific name, or None if the file hasn't been downloaded."""
    if not Path(path).exists():
        return None
    with open(path, encoding="latin-1", newline="") as f:
        return {row["ScientificName"].strip(): row for row in csv.DictReader(f)}


def _num(value: str) -> float | None:
    value = (value or "").strip()
    if value in ("", "NA"):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def ecocrop_record(row: dict[str, str]) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for column, (key, kind) in ECOCROP_FIELDS.items():
        raw = (row.get(column) or "").strip()
        if kind == "num":
            record[key] = _num(raw)
        else:
            record[key] = None if raw in ("", "NA") else raw
    return record


def crop_record(traits: dict[str, str], ecocrop_row: dict[str, str] | None) -> dict[str, Any]:
    """One `crops` table row from a traits row plus its EcoCrop row."""

    def level(col: str) -> str | None:
        return traits.get(col) or None

    def yes_no(col: str) -> bool | None:
        value = traits.get(col, "")
        return None if value == "" else value == "yes"

    source = traits.get("source", "")
    return {
        "name": traits["crop"],
        "scientific_name": traits["scientific_name"],
        "family": traits["family"],
        "is_legume": traits["is_legume"] == "yes",
        "root_depth_m": _num(traits.get("root_depth_m", "")),
        "water_need": level("water_need"),
        "heat_tolerance": level("heat_tolerance"),
        "drought_tolerance": level("drought_tolerance"),
        "waterlogging_tolerance": level("waterlogging_tolerance"),
        "cover_crop_role": level("cover_crop_role"),
        "forage": yes_no("forage"),
        "labor_need": level("labor_need"),
        "traits_source": None if source in ("", TODO) else source,  # NULL = not verified yet
        "notes": traits.get("notes") or None,
        "ecocrop": ecocrop_record(ecocrop_row) if ecocrop_row else {},
    }


def pest_rule_record(row: dict[str, str]) -> dict[str, Any]:
    rule: dict[str, Any] = {col: _num(row.get(col, "")) for col in PEST_RANGES}
    rule["consecutive_days"] = int(float(row["consecutive_days"]))
    return {
        "pest": row["pest"],
        "kind": row["kind"],
        "crops": [c.strip() for c in row["crops"].split(";") if c.strip()],
        "description": row["description"],
        "rule": rule,
        "source": row["source"],
        "source_url": row["source_url"],
    }


# --- validation ----------------------------------------------------------------------------


def validate_traits(
    header: list[str],
    rows: list[dict[str, str]],
    ecocrop_names: set[str] | None,
    strict: bool = False,
) -> Report:
    report = Report()
    if header != TRAIT_COLUMNS:
        report.errors.append(f"columns must be exactly: {', '.join(TRAIT_COLUMNS)}")
        return report
    if ecocrop_names is None:
        report.warnings.append("EcoCrop not downloaded (run `make ecocrop`): names not checked")

    seen: set[str] = set()
    todo_sources, missing_traits = [], []
    for i, row in enumerate(rows, start=2):  # row 1 is the header
        crop = row["crop"]
        where = f"row {i} ({crop or 'no crop name'})"
        if not crop:
            report.errors.append(f"{where}: crop is empty")
        elif crop.lower() in seen:
            report.errors.append(f"{where}: duplicate crop")
        seen.add(crop.lower())
        if not row["scientific_name"]:
            report.errors.append(f"{where}: scientific_name is empty")
        elif ecocrop_names is not None and row["scientific_name"] not in ecocrop_names:
            report.errors.append(
                f"{where}: scientific_name '{row['scientific_name']}' is not in EcoCrop"
            )
        if not FAMILY_PATTERN.match(row["family"]):
            report.errors.append(f"{where}: family '{row['family']}' should look like 'Fabaceae'")
        if row["is_legume"] not in YES_NO:
            report.errors.append(f"{where}: is_legume must be yes or no")
        elif (row["family"] == "Fabaceae") != (row["is_legume"] == "yes"):
            report.errors.append(f"{where}: is_legume should be yes exactly for family Fabaceae")
        for col in LEVEL_COLUMNS:
            if row[col] and row[col] not in LEVELS:
                report.errors.append(f"{where}: {col} '{row[col]}' must be low, medium or high")
        if row["root_depth_m"]:
            depth = _num(row["root_depth_m"])
            if depth is None or not 0.05 <= depth <= 5:
                report.errors.append(f"{where}: root_depth_m must be metres between 0.05 and 5")
        if row["cover_crop_role"] and row["cover_crop_role"] not in COVER_ROLES:
            report.errors.append(f"{where}: cover_crop_role must be none, cover or green_manure")
        if row["forage"] and row["forage"] not in YES_NO:
            report.errors.append(f"{where}: forage must be yes or no")
        if not row["source"]:
            report.errors.append(f"{where}: source is empty (every row needs one)")
        elif row["source"] == TODO:
            todo_sources.append(crop)
        trait_cols = ["root_depth_m", *LEVEL_COLUMNS, "cover_crop_role", "forage"]
        if any(not row[c] for c in trait_cols):
            missing_traits.append(crop)

    for label, crops_list in (("source still TODO", todo_sources),
                              ("some traits still blank", missing_traits)):
        if crops_list:
            message = f"{len(crops_list)} crop(s) with {label}: {', '.join(crops_list)}"
            (report.errors if strict else report.warnings).append(message)
    return report


def validate_pest_rules(
    header: list[str], rows: list[dict[str, str]], crop_names: set[str], strict: bool = False
) -> Report:
    report = Report()
    if header != PEST_COLUMNS:
        report.errors.append(f"pest_rules.csv columns must be exactly: {', '.join(PEST_COLUMNS)}")
        return report
    if not rows:
        (report.errors if strict else report.warnings).append("pest_rules.csv has no rules yet")

    seen: set[tuple[str, str]] = set()
    for i, row in enumerate(rows, start=2):
        where = f"row {i} ({row['pest'] or 'no pest name'})"
        if not row["pest"]:
            report.errors.append(f"{where}: pest is empty")
        if row["kind"] not in PEST_KINDS:
            report.errors.append(f"{where}: kind must be disease or insect")
        crops_listed = [c.strip() for c in row["crops"].split(";") if c.strip()]
        if not crops_listed:
            report.errors.append(f"{where}: crops is empty")
        for crop in crops_listed:
            if crop not in crop_names:
                report.errors.append(
                    f"{where}: crop '{crop}' is not in crops_traits.csv (use the crop column)"
                )
        description = row["description"]
        if not description:
            report.errors.append(f"{where}: description is empty")
        elif any(word in description.lower() for word in ALARM_WORDS):
            report.errors.append(f"{where}: description must say 'conditions favor', not outbreak")
        values = {}
        for col, (low, high) in PEST_RANGES.items():
            if row[col]:
                value = _num(row[col])
                if value is None or not low <= value <= high:
                    report.errors.append(f"{where}: {col} must be a number from {low} to {high}")
                values[col] = value
        if not values:
            report.errors.append(f"{where}: needs at least one temperature, humidity or rain rule")
        for low_col, high_col in (("t_min_c", "t_max_c"), ("rh_min_pct", "rh_max_pct")):
            lo, hi = values.get(low_col), values.get(high_col)
            if lo is not None and hi is not None and lo > hi:
                report.errors.append(f"{where}: {low_col} is above {high_col}")
        days = _num(row["consecutive_days"])
        if days is None or days != int(days) or not 1 <= days <= 30:
            report.errors.append(f"{where}: consecutive_days must be a whole number from 1 to 30")
        if not row["source"]:
            report.errors.append(f"{where}: source is empty")
        if not row["source_url"].startswith(("http://", "https://")):
            report.errors.append(f"{where}: source_url must be a link (http...)")
        key = (row["pest"].lower(), description.lower())
        if key in seen:
            report.errors.append(f"{where}: duplicate pest + description")
        seen.add(key)
    return report


def validate_all(
    traits_path: Path = TRAITS_CSV,
    pests_path: Path = PEST_RULES_CSV,
    ecocrop_path: Path = ECOCROP_CSV,
    strict: bool = False,
) -> dict[str, Report]:
    ecocrop = load_ecocrop(ecocrop_path)
    header, rows = read_csv(traits_path)
    traits = validate_traits(header, rows, set(ecocrop) if ecocrop is not None else None, strict)
    crop_names = {r.get("crop", "") for r in rows}
    p_header, p_rows = read_csv(pests_path)
    pests = validate_pest_rules(p_header, p_rows, crop_names, strict)
    return {"crops_traits.csv": traits, "pest_rules.csv": pests}
