"""Beyond the rotation: fruit trees and plants for bunds, field edges or a corner of the farm.

They stay in the ground for years, so they are not part of the 12-month rotation and are not
scored with the strategies. They pass the same filters: FAO EcoCrop temperature ranges in every
month of the year plus yearly rain and soil pH (data/perennials.csv), and FAOSTAT (grown in the
field's country, so plants, know-how and buyers exist locally).
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.engine.answers import FarmProfile
from app.engine.candidates import SUITABLE_MIN, suitability
from app.engine.catalog import CropInfo
from app.engine.evidence import Evidence
from app.engine.regional import familiarity
from app.engine.scoring import FieldContext, crop_of

CSV = Path(__file__).resolve().parents[3] / "data" / "perennials.csv"
MAX_IDEAS = 4
TEXT_KEYS = {"life_form", "category", "drainage_opt", "drainage_range", "texture_opt",
             "texture_range", "soil_depth_opt", "salinity_opt", "photoperiod"}


@lru_cache(maxsize=1)
def perennials() -> list[CropInfo]:
    if not CSV.exists():
        return []
    out = []
    with CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            eco: dict[str, Any] = {}
            for key, raw in row.items():
                if key in ("crop", "scientific_name", "family", "source"):
                    continue
                eco[key] = (raw or None) if key in TEXT_KEYS else (float(raw) if raw else None)
            out.append(CropInfo(
                name=row["crop"], scientific_name=row["scientific_name"], family=row["family"],
                is_legume=False, root_depth_m=None, water_need=None, heat_tolerance=None,
                drought_tolerance=None, waterlogging_tolerance=None, cover_crop_role="none",
                forage=None, labor_need=None, traits_source=row["source"], notes=None, eco=eco))
    return out


def _wet_field(ctx: FieldContext, slots: list[str], catalog: dict[str, CropInfo]) -> bool:
    """Flooded or heavy soil: paddy rice, or a crop that likes waterlogging, or clay."""
    return any(crop_of(c, catalog).waterlogging_tolerance == "high" for c in slots) or \
        "clay" in (ctx.texture or "")


def fruit_ideas(profile: FarmProfile, ctx: FieldContext,
                catalog: dict[str, CropInfo]) -> list[dict[str, Any]]:
    """Up to MAX_IDEAS fruit trees or plants that suit this field's climate all year."""
    water = "mixed" if profile.water == "irrigated" else profile.water  # trees sit off the paddy
    wet = _wet_field(ctx, [s.crop for s in profile.slots], catalog)
    ideas = []
    for crop in perennials():
        if crop.name in profile.wont_grow:
            continue
        if profile.local is not None and crop.name not in profile.local:
            continue
        suit = suitability(crop, list(range(1, 13)), ctx, water)
        if suit.score < SUITABLE_MIN:
            continue
        value = profile.values.get(crop.name) if profile.values else None
        well_drained = "poorly" not in (crop.eco.get("drainage_opt") or "")
        where = ("On bunds, raised beds or the field's edge: it needs well-drained soil, and "
                 "this field stays wet" if wet and well_drained
                 else "On part of the farm or along the field's edge")
        evidence = [Evidence(f"{crop.name} fits this field's temperature in every month, its "
                             "yearly rain and soil pH", suit.score, "score 0-1",
                             "FAO EcoCrop + NASA POWER + ISRIC SoilGrids",
                             "crop-level", "", "medium")]
        if profile.local is not None:
            evidence.append(Evidence(f"{crop.name} harvested in {profile.country}",
                                     round(profile.local[crop.name]), "ha",
                                     "FAOSTAT crop production",
                                     "national", "latest 3 years", "high"))
        if value:
            evidence.append(Evidence(f"{crop.name}: typical gross value per hectare before "
                                     "costs", round(value.value_usd_ha), "USD/ha",
                                     "FAOSTAT crop production + producer prices", "national",
                                     value.price_years, "low"))
        ideas.append(((round(suit.score * familiarity(crop.name, profile.local), 4), crop.name), {
            "crop": crop.name,
            "scientific_name": crop.scientific_name,
            "kind": "tree" if "tree" in (crop.eco.get("life_form") or "") else "plant",
            "suitability": suit.score,
            "country_area_ha": round(profile.local[crop.name]) if profile.local else None,
            "value_usd_ha": round(value.value_usd_ha) if value else None,
            "where": where,
            "evidence": evidence,
        }))
    ideas.sort(key=lambda x: x[0], reverse=True)
    return [idea for _, idea in ideas[:MAX_IDEAS]]
