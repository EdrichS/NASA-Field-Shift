"""Pre-compute both showcase farms, Tier 1 reports included, into data/showcase/<id>.json.

  python scripts/precache_showcase.py [--only tagum-rice] [--no-ai]

Runs the same code as /analyze. Reports use XAI_MODEL from .env; for the demo recording run
  XAI_MODEL=grok-4.7 python scripts/precache_showcase.py
(an environment variable overrides .env). A farm whose reports fail is not saved, so a good
earlier file is never replaced by a worse one. Each AI call is one paid request (~$0.01).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api import showcase  # noqa: E402
from app.api.routes import run_analysis  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.features.harmonize import build_field_features, store_features  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="one farm id")
    parser.add_argument("--no-ai", action="store_true", help="comparison only, no Grok calls")
    args = parser.parse_args()

    farms = [f for f in showcase.farms() if not args.only or f["id"] == args.only]
    if not farms:
        print(f"❌ no showcase farm with id {args.only!r}")
        return 1
    ok_all, total_cost = True, 0.0
    for farm in farms:
        print(f"\n== {farm['name']} ({farm['id']})")
        body = showcase.request_for(farm, generate_reports=not args.no_ai)
        t0 = time.perf_counter()
        ff, daily = build_field_features(body.geometry)
        if get_settings().database_url.get_secret_value():
            rows = store_features(ff, daily)
            print(f"   TigerData: {rows}")
        result = run_analysis(body)
        print(f"   analyzed in {time.perf_counter() - t0:.1f} s; gaps: {len(result['gaps'])}")
        for s in sorted(result["strategies"], key=lambda s: s["rank"]):
            print(f"   #{s['rank']} {s['name']}: {s['title']} [{s['total']}]")
        reports_ok = True
        for lang, status in result["report_status"].items():
            report = result["reports_tier1"][lang]
            if report:
                meta, check = report["meta"], report["checks"]
                total_cost += meta["cost_usd"] or 0
                print(f"   report {lang}: {status['status']}, {meta['model']}, "
                      f"{meta['input_tokens']}+{meta['output_tokens']} tokens, "
                      f"{meta['seconds']} s, ${meta['cost_usd']}; numbers ok: "
                      f"{check['numbers_ok']}, retried: {check['retried']}")
            else:
                reports_ok = reports_ok and args.no_ai
                print(f"   report {lang}: {status['status']} {status['message']}")
        if reports_ok:
            path = showcase.save(farm, body, result)
            print(f"   ✅ saved {path.relative_to(ROOT)}")
        else:
            ok_all = False
            print("   ❌ not saved (reports missing); any earlier file was kept")
    print(f"\nAI cost this run: ${total_cost:.4f}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
