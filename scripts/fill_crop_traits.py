"""Fill data/crops_traits.csv from cited FAO sources with documented rules.

Run once (re-runnable):  .venv/bin/python scripts/fill_crop_traits.py
Keeps crop, scientific_name, family and is_legume; fills every other column and cites the source
of each value in the row's `source` column. Anything without a direct source is marked
`estimate` in notes.

Sources and rules:
- root_depth_m: midpoint of FAO-56 Table 22 "maximum effective root depth" range.
  https://www.fao.org/4/x0490e/x0490e0e.htm
- water_need / drought_tolerance: FAO Irrigation Water Management Training Manual 3, Table 14
  (crop water need, mm per growing period, and sensitivity to drought).
  https://www.fao.org/4/s2022e/s2022e07.htm
  water_need from the midpoint: <= 450 mm low, <= 650 mm medium, > 650 mm high. Paddy rice is high
  because it also needs water for soil saturation, percolation and the standing water layer
  (same manual, ch. 4: https://www.fao.org/4/s2022e/s2022e08.htm).
  drought_tolerance is the inverse of sensitivity: low -> high, low-medium -> medium,
  medium-high or high -> low.
  Crops not in Table 14 use FAO EcoCrop instead: optimal annual rainfall midpoint <= 800 mm low,
  <= 1200 mm medium, else high; absolute minimum rainfall <= 500 mm drought tolerance high,
  <= 800 mm medium, else low.
- heat_tolerance: FAO EcoCrop optimal maximum temperature (TOPMX): >= 35 C high, >= 30 C medium,
  else low.  https://gaez.fao.org/pages/ecocrop
- waterlogging_tolerance: FAO EcoCrop drainage: optimal "poorly (saturated)" -> high; tolerated
  range includes it -> medium; otherwise low.
- forage: FAO EcoCrop category includes "forage/pasture".
- cover_crop_role: SARE "Managing Cover Crops Profitably" (3rd ed.) for cover and green-manure
  species; food, feed and cash crops are "none".
  https://www.sare.org/resources/managing-cover-crops-profitably-3rd-edition/
- cover_crop_role for sesbania: PROSEA (Plant Resources of South-East Asia), Sesbania rostrata.
  https://uses.plantnet-project.org/en/Sesbania_rostrata_(PROSEA)
- labor_need: team estimate of hand labor without machinery (transplanting, hand harvesting).
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.data.crops import (  # noqa: E402
    CYCLE_FALLBACK,
    TRAIT_COLUMNS,
    TRAITS_CSV,
    load_ecocrop,
    read_csv,
)

FAO56 = "FAO-56 Table 22"
T14 = "FAO Irrigation Water Mgmt Manual 3 Table 14"
ECO = "FAO EcoCrop"
SARE = "SARE Managing Cover Crops Profitably 3rd ed."

# FAO-56 Table 22 rows: crop -> (min m, max m, table row). None = not in the table.
ROOT_DEPTH = {
    "rice": (0.5, 1.0, "Rice"),
    "maize": (1.0, 1.7, "Maize field grain"),
    "mungbean": (0.6, 1.0, "Green Gram and Cowpeas"),
    "peanut": (0.5, 1.0, "Groundnut (Peanut)"),
    "soybean": (0.6, 1.3, "Soybeans"),
    "cowpea": (0.6, 1.0, "Green Gram and Cowpeas"),
    "sweet potato": (1.0, 1.5, "Sweet Potato"),
    "cassava": (0.5, 0.8, "Cassava year 1"),
    "sorghum": (1.0, 2.0, "Sorghum grain"),
    "pearl millet": (1.0, 2.0, "Millet"),
    "wheat": (1.0, 1.5, "Spring Wheat"),
    "barley": (1.0, 1.5, "Barley"),
    "oats": (1.0, 1.5, "Oats"),
    "alfalfa": (1.0, 2.0, "Alfalfa for hay"),
    "red clover": (0.6, 0.9, "Clover hay Berseem"),
    "common bean": (0.6, 0.9, "Beans dry and Pulses"),
    "onion": (0.3, 0.6, "Onions dry"),
    "tomato": (0.7, 1.5, "Tomato"),
    "cabbage": (0.5, 0.8, "Cabbage"),
    "chili pepper": (0.5, 1.0, "Sweet Peppers (bell)"),
    "squash": (1.0, 1.5, "Pumpkin Winter Squash"),
    "sunflower": (0.8, 1.5, "Sunflower"),
    "canola": (1.0, 1.5, "Rapeseed Canola"),
    "watermelon": (0.8, 1.5, "Watermelon"),
    "melon": (0.8, 1.5, "Melons"),
    "cucumber": (0.7, 1.2, "Cucumber"),
    "eggplant": (0.7, 1.2, "Egg plant"),
    "string bean": (0.5, 0.7, "Beans green"),
}
# Not in Table 22: closest listed relative, marked estimate.
ROOT_DEPTH_ESTIMATE = {
    "cereal rye": (1.0, 1.5, "small grains (Barley/Oats)"),
    "hairy vetch": (0.6, 0.9, "Beans dry and Pulses"),
    "sunn hemp": (0.6, 1.0, "Green Gram and Cowpeas"),
    "buckwheat": (0.5, 0.7, "Beans green"),
    "okra": (0.7, 1.2, "Egg plant"),
    "pak choi": (0.3, 0.5, "Spinach"),
    "sesbania": (0.6, 1.0, "Green Gram and Cowpeas"),
}
# FAO Table 14: crop -> (min mm, max mm, drought sensitivity, table row)
WATER = {
    "rice": (450, 700, "high", "Rice (paddy)"),
    "maize": (500, 800, "medium-high", "Maize"),
    "peanut": (500, 700, "low-medium", "Peanut"),
    "soybean": (450, 700, "low-medium", "Soybean"),
    "sorghum": (450, 650, "low", "Sorghum/Millet"),
    "pearl millet": (450, 650, "low", "Sorghum/Millet"),
    "wheat": (450, 650, "low-medium", "Barley/Oats/Wheat"),
    "barley": (450, 650, "low-medium", "Barley/Oats/Wheat"),
    "oats": (450, 650, "low-medium", "Barley/Oats/Wheat"),
    "cereal rye": (450, 650, "low-medium", "Barley/Oats/Wheat (analog)"),
    "alfalfa": (800, 1600, "low-medium", "Alfalfa"),
    "common bean": (300, 500, "medium-high", "Bean"),
    "onion": (350, 550, "medium-high", "Onion"),
    "tomato": (400, 800, "medium-high", "Tomato"),
    "cabbage": (350, 500, "medium-high", "Cabbage"),
    "chili pepper": (600, 900, "medium-high", "Pepper"),
    "squash": (400, 600, "medium-high", "Melon (analog)"),
    "sunflower": (600, 1000, "low-medium", "Sunflower"),
    "melon": (400, 600, "medium-high", "Melon"),
    "watermelon": (400, 600, "medium-high", "Melon (analog)"),
    "cucumber": (400, 600, "medium-high", "Melon (analog)"),
    "eggplant": (400, 800, "medium-high", "Tomato (analog)"),
    "string bean": (300, 500, "medium-high", "Bean"),
    "pak choi": (350, 500, "medium-high", "Cabbage (analog)"),
}
SENSITIVITY_TO_TOLERANCE = {"low": "high", "low-medium": "medium", "medium-high": "low",
                            "high": "low"}
COVER_ROLE = {"cereal rye": "cover", "oats": "cover", "buckwheat": "cover",
              "hairy vetch": "green_manure", "red clover": "green_manure",
              "sunn hemp": "green_manure", "sesbania": "green_manure"}
# Green manures SARE doesn't cover: crop -> source of the cover role.
COVER_ROLE_SOURCE = {"sesbania": "PROSEA Sesbania rostrata (green manure for lowland rice, "
                                 "incorporated after 45-60 days)"}
# Team estimate: hand labor per hectare without machinery.
LABOR = {
    "rice": "high", "maize": "medium", "mungbean": "high", "peanut": "high", "soybean": "medium",
    "cowpea": "medium", "sweet potato": "high", "cassava": "medium", "sorghum": "medium",
    "pearl millet": "medium", "wheat": "medium", "barley": "medium", "oats": "low",
    "cereal rye": "low", "alfalfa": "medium", "red clover": "low", "hairy vetch": "low",
    "sunn hemp": "low", "buckwheat": "low", "common bean": "medium", "onion": "high",
    "tomato": "high", "cabbage": "high", "chili pepper": "high", "squash": "medium",
    "sunflower": "medium", "canola": "medium", "watermelon": "medium", "melon": "medium",
    "cucumber": "high", "eggplant": "high", "okra": "high", "string bean": "high",
    "pak choi": "medium", "sesbania": "low",
}
# EcoCrop has no drainage entry for these: general agronomy, marked estimate.
WATERLOGGING_ESTIMATE = {"maize": "low", "soybean": "low", "peanut": "low", "cassava": "low",
                         "sweet potato": "low", "tomato": "low", "onion": "low",
                         "squash": "low", "chili pepper": "low", "cabbage": "medium"}


def num(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def level_from_mm(mm: float) -> str:
    return "low" if mm <= 450 else "medium" if mm <= 650 else "high"


def fill(row: dict[str, str], eco: dict[str, str]) -> dict[str, str]:
    crop = row["crop"]
    sources, estimates = [], []

    if crop in ROOT_DEPTH:
        lo, hi, label = ROOT_DEPTH[crop]
        sources.append(f"{FAO56} ({label})")
    else:
        lo, hi, label = ROOT_DEPTH_ESTIMATE[crop]
        sources.append(f"{FAO56} analog ({label})")
        estimates.append("root depth from closest FAO-56 crop")
    row["root_depth_m"] = f"{(lo + hi) / 2:.2f}"

    if crop in WATER:
        wlo, whi, sens, label = WATER[crop]
        row["water_need"] = "high" if crop == "rice" else level_from_mm((wlo + whi) / 2)
        row["drought_tolerance"] = SENSITIVITY_TO_TOLERANCE[sens]
        sources.append(f"{T14} ({label})" + (" + ch.4 paddy water" if crop == "rice" else ""))
        if "analog" in label:
            estimates.append("water need from closest FAO Table 14 crop")
    else:
        opt = [num(eco.get("ROPMN")), num(eco.get("ROPMX"))]
        rmin = num(eco.get("RMIN"))
        mid = sum(opt) / 2 if None not in opt else None
        row["water_need"] = ("" if mid is None else
                             "low" if mid <= 800 else "medium" if mid <= 1200 else "high")
        row["drought_tolerance"] = ("" if rmin is None else
                                    "high" if rmin <= 500 else "medium" if rmin <= 800 else "low")
        sources.append(f"{ECO} rainfall ranges")

    topmx = num(eco.get("TOPMX"))
    row["heat_tolerance"] = ("" if topmx is None else
                             "high" if topmx >= 35 else "medium" if topmx >= 30 else "low")

    dra, drar = (eco.get("DRA") or "").lower(), (eco.get("DRAR") or "").lower()
    if dra.startswith("poorly"):
        row["waterlogging_tolerance"] = "high"
    elif "poorly" in drar:
        row["waterlogging_tolerance"] = "medium"
    elif dra or drar:
        row["waterlogging_tolerance"] = "low"
    else:
        row["waterlogging_tolerance"] = WATERLOGGING_ESTIMATE.get(crop, "")
        estimates.append("waterlogging tolerance (no EcoCrop drainage data)")

    row["forage"] = "yes" if "forage" in (eco.get("CAT") or "").lower() else "no"
    row["cover_crop_role"] = COVER_ROLE.get(crop, "none")
    sources.append(f"{ECO} (heat, drainage, category)")
    if crop in COVER_ROLE_SOURCE:
        sources.append(COVER_ROLE_SOURCE[crop])
    elif crop in COVER_ROLE:
        sources.append(SARE)
    if row["scientific_name"] in CYCLE_FALLBACK:
        sources.append("FAO-56 Table 11 (growing period)")
    row["labor_need"] = LABOR[crop]
    estimates.append("labor need")

    row["source"] = " | ".join(sources)
    row["notes"] = "estimate: " + "; ".join(estimates)
    return row


def main() -> int:
    ecocrop = load_ecocrop()
    if ecocrop is None:
        print("EcoCrop missing: run `make ecocrop`")
        return 1
    _, rows = read_csv(TRAITS_CSV)
    filled = [fill(dict(row), ecocrop[row["scientific_name"]]) for row in rows]
    with open(TRAITS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRAIT_COLUMNS)
        writer.writeheader()
        writer.writerows(filled)
    cols = ["crop", "root_depth_m", "water_need", "heat_tolerance", "drought_tolerance",
            "waterlogging_tolerance", "cover_crop_role", "forage", "labor_need"]
    print(" | ".join(f"{c[:12]:12}" for c in cols))
    for r in filled:
        print(" | ".join(f"{r[c][:12]:12}" for c in cols))
    return 0


if __name__ == "__main__":
    sys.exit(main())
