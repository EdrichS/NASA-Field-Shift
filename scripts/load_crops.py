"""Load FAO EcoCrop ranges + data/crops_traits.csv into the `crops` table, and
data/pest_rules.csv into `pest_rules`. Validates first and refuses to load files with errors.

Usage:  make load-crops     (downloads EcoCrop first if needed; safe to re-run)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from psycopg.types.json import Jsonb  # noqa: E402

from app.data.crops import (  # noqa: E402
    PEST_RULES_CSV,
    TRAITS_CSV,
    crop_record,
    load_ecocrop,
    pest_rule_record,
    read_csv,
    validate_all,
)
from app.db import connect  # noqa: E402

CROP_COLUMNS = [
    "name", "scientific_name", "family", "is_legume", "root_depth_m", "water_need",
    "heat_tolerance", "drought_tolerance", "waterlogging_tolerance", "cover_crop_role",
    "forage", "labor_need", "traits_source", "notes", "ecocrop",
]


def main() -> int:
    reports = validate_all()
    errors = [m for r in reports.values() for m in r.errors]
    if errors:
        print("❌ Fix these first (make validate-data):", *errors, sep="\n   ")
        return 1
    ecocrop = load_ecocrop()
    if ecocrop is None:
        print("❌ EcoCrop file missing: run `make ecocrop`")
        return 1

    _, trait_rows = read_csv(TRAITS_CSV)
    crops = [crop_record(row, ecocrop.get(row["scientific_name"])) for row in trait_rows]
    _, pest_rows = read_csv(PEST_RULES_CSV)
    rules = [pest_rule_record(row) for row in pest_rows]

    placeholders = ", ".join(["%s"] * len(CROP_COLUMNS))
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in CROP_COLUMNS[1:])
    with connect() as conn, conn.cursor() as cur:
        cur.executemany(
            f"INSERT INTO crops ({', '.join(CROP_COLUMNS)}) VALUES ({placeholders})"
            f" ON CONFLICT (name) DO UPDATE SET {updates}, updated_at = now()",
            [
                tuple(Jsonb(c[col]) if col == "ecocrop" else c[col] for col in CROP_COLUMNS)
                for c in crops
            ],
        )
        names = [c["name"] for c in crops]
        cur.execute("DELETE FROM crops WHERE NOT (name = ANY(%s))", (names,))
        cur.execute("DELETE FROM pest_rules")  # the CSV is the single source of truth
        cur.executemany(
            "INSERT INTO pest_rules (pest, kind, crops, description, rule, source, source_url)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            [
                (r["pest"], r["kind"], r["crops"], r["description"], Jsonb(r["rule"]),
                 r["source"], r["source_url"])
                for r in rules
            ],
        )
        n_crops = cur.execute("SELECT count(*) FROM crops").fetchone()[0]
        verified = cur.execute(
            "SELECT count(*) FROM crops WHERE traits_source IS NOT NULL"
        ).fetchone()[0]
        n_rules = cur.execute("SELECT count(*) FROM pest_rules").fetchone()[0]
        sample = cur.execute(
            "SELECT name, family, is_legume, ecocrop->>'temp_opt_min_c',"
            " ecocrop->>'temp_opt_max_c', ecocrop->>'cycle_min_days', ecocrop->>'cycle_max_days',"
            " ecocrop->>'drainage_opt' FROM crops WHERE name = ANY(%s) ORDER BY name",
            (["rice", "mungbean", "maize", "soybean", "cereal rye"],),
        ).fetchall()

    print(f"✅ crops: {n_crops} rows ({verified} with verified trait sources, "
          f"{n_crops - verified} still TODO)")
    print(f"✅ pest_rules: {n_rules} rows")
    print("\nSample (EcoCrop ranges):")
    for name, family, legume, tmin, tmax, gmin, gmax, drainage in sample:
        print(f"  {name:11} {family:14} legume={str(legume):5} optimum {tmin}-{tmax} °C, "
              f"season {gmin}-{gmax} days, drainage: {drainage}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
