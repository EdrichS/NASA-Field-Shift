"""Check the team's data files: data/crops_traits.csv and data/pest_rules.csv.

Usage:  make validate-data            (TODO sources and blank traits are warnings)
        make validate-data STRICT=1   (they become errors: use before the demo)

Exits 1 if there are errors. Runs offline (part of `make check`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.data.crops import validate_all  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="fail on TODO sources / blank traits")
    args = parser.parse_args()

    reports = validate_all(strict=args.strict)
    failed = False
    for name, report in reports.items():
        status = "❌" if report.errors else ("⚠️ " if report.warnings else "✅")
        print(f"{status} {name}: {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
        for message in report.errors:
            print(f"     error:   {message}")
        for message in report.warnings:
            print(f"     warning: {message}")
        failed = failed or bool(report.errors)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
