"""Build data/perennials.csv: fruit trees and plants for the "beyond the rotation" ideas, with their
FAO EcoCrop climate and soil ranges copied in (so the app needs no EcoCrop download to use them).

They are not rotation crops: each stays in the ground for years. The engine offers them for bunds,
field edges or part of the farm, filtered by the field's climate (every month) and by FAOSTAT
(grown in the country, see scripts/build_regional_crops.py).

Usage: python scripts/build_perennials.py   (needs data/raw/EcoCrop_DB.csv: make ecocrop)
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.data.crops import ECOCROP_FIELDS, ecocrop_record, load_ecocrop  # noqa: E402

OUT = ROOT / "data" / "perennials.csv"
# crop -> (EcoCrop scientific name, plant family)
PERENNIALS = {
    "banana": ("Musa acuminata", "Musaceae"),
    "papaya": ("Carica papaya", "Caricaceae"),
    "pineapple": ("Ananas comosus", "Bromeliaceae"),
    "mango": ("Mangifera indica", "Anacardiaceae"),
    "coconut": ("Cocos nucifera", "Arecaceae"),
    "cacao": ("Theobroma cacao", "Malvaceae"),
    "mandarin": ("Citrus reticulata", "Rutaceae"),
    "pomelo": ("Citrus grandis", "Rutaceae"),
}
KEYS = [key for key, kind in ECOCROP_FIELDS.values()
        if key not in ("ecoport_code", "common_names")]


def main() -> int:
    ecocrop = load_ecocrop()
    if ecocrop is None:
        print("EcoCrop missing: run `make ecocrop`")
        return 1
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["crop", "scientific_name", "family", *KEYS, "source"])
        for crop, (name, family) in PERENNIALS.items():
            eco = ecocrop_record(ecocrop[name])
            w.writerow([crop, name, family,
                        *["" if eco.get(k) is None else eco[k] for k in KEYS],
                        "FAO EcoCrop (via OpenCLIM/ecocrop)"])
    print(f"{len(PERENNIALS)} perennials -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
