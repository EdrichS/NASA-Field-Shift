"""Build data/regional_crops.csv: which of our crops each country actually grows, from FAOSTAT
(FAO, Crops and livestock products: "Area harvested"), averaged over the latest 3 years.

The engine only suggests crops a country harvests on at least 1,000 ha (see
backend/app/engine/regional.py), so suggestions are crops with local seed, know-how and buyers.

Input (downloaded once, gitignored): data/raw/faostat/
  Production_Crops_Livestock_E_All_Data_(Normalized).csv  from
  https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_All_Data_(Normalized).zip
Usage: make regional-crops
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "faostat" / "Production_Crops_Livestock_E_All_Data_(Normalized).csv"
OUT = ROOT / "data" / "regional_crops.csv"

# Our crop -> FAOSTAT item code(s). Forage-only crops (alfalfa, red clover, sunn hemp) have no
# FAOSTAT item, so they are never suggested where the country is known.
ITEMS: dict[str, list[int]] = {
    "rice": [27], "maize": [56], "mungbean": [176], "common bean": [176], "peanut": [242],
    "soybean": [236], "cowpea": [195], "sweet potato": [122], "cassava": [125],
    "sorghum": [83], "pearl millet": [79], "wheat": [15], "barley": [44], "oats": [75],
    "cereal rye": [71], "hairy vetch": [205], "buckwheat": [89], "onion": [403],
    "tomato": [388], "cabbage": [358], "chili pepper": [401, 689], "squash": [394],
    "sunflower": [267], "canola": [270],
}
YEARS = 3


def main() -> int:
    code_to_crops = defaultdict(list)
    for crop, codes in ITEMS.items():
        for code in codes:
            code_to_crops[code].append(crop)
    # area -> crop -> year -> ha
    data: dict[str, dict[str, dict[int, float]]] = defaultdict(lambda: defaultdict(dict))
    latest = 0
    with RAW.open(newline="", encoding="latin-1") as f:
        for row in csv.DictReader(f):
            if row["Element Code"] != "5312":  # Area harvested
                continue
            code = int(row["Item Code"])
            if code not in code_to_crops or int(row["Area Code"]) >= 5000:  # skip regions
                continue
            year = int(row["Year"])
            value = float(row["Value"] or 0)
            latest = max(latest, year)
            for crop in code_to_crops[code]:
                cell = data[row["Area"]][crop]
                cell[year] = cell.get(year, 0.0) + value
    first = latest - YEARS + 1
    rows = []
    for area, crops in data.items():
        for crop, years in crops.items():
            values = [years.get(y, 0.0) for y in range(first, latest + 1)]
            avg = sum(values) / YEARS
            if avg > 0:
                rows.append((area, crop, round(avg)))
    rows.sort()
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["country", "crop", "area_ha", "years", "source"])
        for area, crop, ha in rows:
            w.writerow([area, crop, ha, f"{first}-{latest}",
                        "FAOSTAT Crops and livestock products, Area harvested"])
    print(f"{len(rows)} rows, {len({r[0] for r in rows})} countries, years {first}-{latest} "
          f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
