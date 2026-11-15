"""Crop catalog for the engine: crop traits + FAO EcoCrop ranges, from TigerData or the files."""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.data import crops as crop_data

log = logging.getLogger(__name__)

ALIASES = {
    "corn": "maize", "mung bean": "mungbean", "mung": "mungbean", "rye": "cereal rye",
    "peanuts": "peanut", "groundnut": "peanut", "soybeans": "soybean", "soya": "soybean",
    "sweetpotato": "sweet potato", "millet": "pearl millet", "bean": "common bean",
    "beans": "common bean", "pepper": "chili pepper", "chili": "chili pepper",
    "pumpkin": "squash", "clover": "red clover", "vetch": "hairy vetch", "palay": "rice",
    "mais": "maize", "munggo": "mungbean",
    "soy": "soybean", "soya bean": "soybean", "soy bean": "soybean", "green gram": "mungbean",
    "paddy": "rice", "manioc": "cassava", "yuca": "cassava", "kamote": "sweet potato",
    "chilli": "chili pepper", "chile": "chili pepper", "chili peppers": "chili pepper",
    "hot pepper": "chili pepper", "oat": "oats", "lucerne": "alfalfa", "rapeseed": "canola",
    "kidney bean": "common bean", "dry bean": "common bean", "brinjal": "eggplant",
    "aubergine": "eggplant", "talong": "eggplant", "bok choy": "pak choi",
    "pechay": "pak choi", "sitaw": "string bean", "long bean": "string bean",
    "yardlong bean": "string bean", "green bean": "string bean",
}


def _singular(word: str) -> str:
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("oes", "shes", "ches")):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


@dataclass(frozen=True)
class CropInfo:
    name: str
    scientific_name: str
    family: str
    is_legume: bool
    root_depth_m: float | None
    water_need: str | None
    heat_tolerance: str | None
    drought_tolerance: str | None
    waterlogging_tolerance: str | None
    cover_crop_role: str | None
    forage: bool | None
    labor_need: str | None
    traits_source: str | None
    notes: str | None
    eco: dict[str, Any] = field(default_factory=dict)

    @property
    def cycle_min_days(self) -> int:
        return int(self.eco.get("cycle_min_days") or 90)

    @property
    def cycle_max_days(self) -> int:
        return int(self.eco.get("cycle_max_days") or max(self.cycle_min_days, 150))

    @property
    def cycle_months(self) -> int:
        return max(1, math.ceil(self.cycle_min_days / 30))

    @property
    def is_cover(self) -> bool:
        return self.cover_crop_role in ("cover", "green_manure")

    @property
    def verified(self) -> bool:
        return bool(self.traits_source)


UNKNOWN_CROP = CropInfo(
    name="unknown crop", scientific_name="", family="unknown", is_legume=False,
    root_depth_m=0.8, water_need="medium", heat_tolerance="medium", drought_tolerance="medium",
    waterlogging_tolerance="medium", cover_crop_role="none", forage=None, labor_need="medium",
    traits_source=None, notes="no trait data: neutral values used",
)


def from_record(rec: dict[str, Any]) -> CropInfo:
    return CropInfo(
        name=rec["name"], scientific_name=rec["scientific_name"], family=rec["family"],
        is_legume=bool(rec["is_legume"]), root_depth_m=rec.get("root_depth_m"),
        water_need=rec.get("water_need"), heat_tolerance=rec.get("heat_tolerance"),
        drought_tolerance=rec.get("drought_tolerance"),
        waterlogging_tolerance=rec.get("waterlogging_tolerance"),
        cover_crop_role=rec.get("cover_crop_role"), forage=rec.get("forage"),
        labor_need=rec.get("labor_need"), traits_source=rec.get("traits_source"),
        notes=rec.get("notes"), eco=rec.get("ecocrop") or {},
    )


def load_from_files(traits_csv: Path = crop_data.TRAITS_CSV,
                    ecocrop_csv: Path = crop_data.ECOCROP_CSV) -> dict[str, CropInfo]:
    ecocrop = crop_data.load_ecocrop(ecocrop_csv) or {}
    _, rows = crop_data.read_csv(traits_csv)
    return {
        row["crop"]: from_record(crop_data.crop_record(row, ecocrop.get(row["scientific_name"])))
        for row in rows
    }


def load_from_db() -> dict[str, CropInfo]:
    from psycopg.rows import dict_row

    from app.db import connect

    with connect() as conn, conn.cursor(row_factory=dict_row) as cur:
        rows = cur.execute(
            "SELECT name, scientific_name, family, is_legume, root_depth_m, water_need,"
            " heat_tolerance, drought_tolerance, waterlogging_tolerance, cover_crop_role, forage,"
            " labor_need, traits_source, notes, ecocrop FROM crops"
        ).fetchall()
    return {r["name"]: from_record(r) for r in rows}


def has_ranges(catalog: dict[str, CropInfo]) -> bool:
    """False when FAO EcoCrop wasn't loaded: then no crop has temperature or rain limits."""
    return any(c.eco for c in catalog.values())


_loaded: dict[str, CropInfo] | None = None


def default_catalog() -> dict[str, CropInfo]:
    """TigerData when reachable and loaded, otherwise the CSV + EcoCrop files. Only a catalog
    with EcoCrop ranges is kept, so a database that is slow at startup is retried later."""
    global _loaded
    if _loaded is not None:
        return _loaded
    catalog: dict[str, CropInfo] = {}
    try:
        catalog = load_from_db()
    except Exception as e:
        log.warning("crop catalog: database unavailable (%s), using the CSV files",
                    type(e).__name__)
    catalog = catalog or load_from_files()
    if has_ranges(catalog):
        _loaded = catalog
    else:
        log.error("crop catalog has no FAO EcoCrop ranges: run `make load-crops` "
                  "(or `make ecocrop`); every crop counts as suitable until then")
    return catalog


def resolve(name: str, catalog: dict[str, CropInfo]) -> CropInfo | None:
    """Catalog crop for a farmer's spelling: 'Sweet potatoes', 'Mung beans', 'soya bean'."""
    key = re.sub(r"\s+", " ", (name or "").strip().lower())
    for k in (key, _singular(key), " ".join(_singular(w) for w in key.split(" "))):
        k = ALIASES.get(k, k)
        if k in catalog:
            return catalog[k]
        if k.replace(" ", "") in ALIASES:
            return catalog.get(ALIASES[k.replace(" ", "")])
    return None
