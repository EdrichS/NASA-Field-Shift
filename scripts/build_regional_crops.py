"""Build data/regional_crops.csv: which of our crops each country actually grows, from FAOSTAT
(FAO, Crops and livestock products: "Area harvested"), averaged over the latest 3 years, plus the
national yield and farm-gate price where FAOSTAT has them.

The engine only suggests crops a country harvests on at least 1,000 ha (see
backend/app/engine/regional.py), so suggestions are crops with local seed, know-how and buyers.
Yield (production / area harvested) x producer price gives a typical gross value per hectare
before costs, which the income score uses to tell a fruit or vegetable from a grain.

Input (downloaded once, gitignored): data/raw/faostat/
  Production_Crops_Livestock_E_All_Data_(Normalized).csv  from
  https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_All_Data_(Normalized).zip
  Prices_E_All_Data_(Normalized).csv  from
  https://bulks-faostat.fao.org/production/Prices_E_All_Data_(Normalized).zip
Usage: make regional-crops
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "faostat" / "Production_Crops_Livestock_E_All_Data_(Normalized).csv"
PRICES = ROOT / "data" / "raw" / "faostat" / "Prices_E_All_Data_(Normalized).csv"
OUT = ROOT / "data" / "regional_crops.csv"

# Our crop -> FAOSTAT item code(s). Forage and cover crops (alfalfa, red clover, sunn hemp,
# sesbania) have no FAOSTAT item; the engine lets cover crops through without one. Fruit trees
# (banana ... pomelo) are for the "beyond the rotation" ideas, not the rotation itself.
ITEMS: dict[str, list[int]] = {
    "rice": [27], "maize": [56], "mungbean": [176], "common bean": [176], "peanut": [242],
    "soybean": [236], "cowpea": [195], "sweet potato": [122], "cassava": [125],
    "sorghum": [83], "pearl millet": [79], "wheat": [15], "barley": [44], "oats": [75],
    "cereal rye": [71], "hairy vetch": [205], "buckwheat": [89], "onion": [403],
    "tomato": [388], "cabbage": [358], "chili pepper": [401, 689], "squash": [394],
    "sunflower": [267], "canola": [270],
    "watermelon": [567], "melon": [568], "cucumber": [397], "eggplant": [399], "okra": [430],
    "string bean": [423], "pak choi": [358],
    "banana": [486, 489], "papaya": [600], "mango": [571], "pineapple": [574],
    "coconut": [249], "cacao": [661], "mandarin": [495], "pomelo": [507],
}
AREA, PRODUCTION, PRICE_USD = "5312", "5510", "5532"
YEARS = 3
PRICE_MAX_AGE = 6  # years


def _prices(code_to_crops: dict[int, list[str]]) -> dict[str, dict[str, dict[int, float]]]:
    """area -> crop -> year -> producer price (USD/tonne, annual value)."""
    out: dict[str, dict[str, dict[int, float]]] = defaultdict(lambda: defaultdict(dict))
    if not PRICES.exists():
        return out
    with PRICES.open(newline="", encoding="latin-1") as f:
        for row in csv.DictReader(f):
            if row["Element Code"] != PRICE_USD or row["Months"] != "Annual value":
                continue
            code = int(row["Item Code"])
            if code not in code_to_crops or not row["Value"]:
                continue
            for crop in code_to_crops[code]:
                out[row["Area"]][crop].setdefault(int(row["Year"]), float(row["Value"]))
    return out


def main() -> int:
    code_to_crops = defaultdict(list)
    for crop, codes in ITEMS.items():
        for code in codes:
            code_to_crops[code].append(crop)
    # element -> area -> crop -> year -> value (ha or tonnes)
    data: dict[str, dict[str, dict[str, dict[int, float]]]] = {
        e: defaultdict(lambda: defaultdict(dict)) for e in (AREA, PRODUCTION)}
    latest = 0
    with RAW.open(newline="", encoding="latin-1") as f:
        for row in csv.DictReader(f):
            element = row["Element Code"]
            if element not in data:
                continue
            code = int(row["Item Code"])
            if code not in code_to_crops or int(row["Area Code"]) >= 5000:  # skip regions
                continue
            year = int(row["Year"])
            value = float(row["Value"] or 0)
            if element == AREA:
                latest = max(latest, year)
            for crop in code_to_crops[code]:
                cell = data[element][row["Area"]][crop]
                cell[year] = cell.get(year, 0.0) + value
    prices = _prices(code_to_crops)
    first = latest - YEARS + 1
    window = range(first, latest + 1)
    rows = []
    for area, crops in data[AREA].items():
        for crop, years in crops.items():
            avg = sum(years.get(y, 0.0) for y in window) / YEARS
            if avg <= 0:
                continue
            produced = data[PRODUCTION][area][crop]
            pairs = [(years[y], produced[y]) for y in window if years.get(y) and produced.get(y)]
            yield_t = sum(t for _, t in pairs) / sum(ha for ha, _ in pairs) if pairs else None
            # the latest 3 years with a price (price series often end a year earlier); an
            # old price says little about today's market, so none older than PRICE_MAX_AGE
            priced = [(y, v) for y, v in sorted(prices[area][crop].items())
                      if y > latest - PRICE_MAX_AGE][-YEARS:]
            price = sum(v for _, v in priced) / len(priced) if priced else None
            value = yield_t * price if yield_t and price else None
            rows.append((area, crop, round(avg),
                         "" if yield_t is None else f"{yield_t:.2f}",
                         "" if price is None else f"{price:.0f}",
                         "" if value is None else f"{value:.0f}",
                         f"{priced[0][0]}-{priced[-1][0]}" if priced else ""))
    rows.sort()
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["country", "crop", "area_ha", "years", "yield_t_ha", "price_usd_t",
                    "value_usd_ha", "price_years", "source"])
        for area, crop, ha, yield_t, price, value, price_years in rows:
            w.writerow([area, crop, ha, f"{first}-{latest}", yield_t, price, value, price_years,
                        "FAOSTAT Crops and livestock products (area harvested, production); "
                        "FAOSTAT Producer prices (USD/tonne)"])
    priced_rows = sum(1 for r in rows if r[5])
    print(f"{len(rows)} rows ({priced_rows} with a value per ha), {len({r[0] for r in rows})} "
          f"countries, years {first}-{latest} -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
