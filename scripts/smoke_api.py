"""Live check of /prefill and /analyze against the running backend (showcase farm 1).

Calls each endpoint twice: the second call must come from the cache and be fast.
  python scripts/smoke_api.py [--api http://localhost:8000] [--save] [--with-ai]
--save also writes the request/response pairs to shared/contracts/ as frontend samples.
No Grok call unless --with-ai (sponsor credits are limited; `make smoke` never spends them).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "shared" / "contracts"
SECOND_CALL_MAX_S = 3.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--with-ai", action="store_true", help="also generate Tier 1 reports")
    args = parser.parse_args()

    farm = json.loads((ROOT / "data" / "showcase_farms.json").read_text())["farms"][0]
    geometry = farm["geometry"]
    requests = {
        "prefill": {"geometry": geometry},
        "analyze": {"geometry": geometry, "mode": farm["answers"].get("mode", "quick"),
                    "answers": farm["answers"], "report_languages": farm["report_languages"],
                    "generate_reports": args.with_ai},
    }
    ok = True
    results = {}
    with httpx.Client(base_url=args.api, timeout=180) as client:
        for name, body in requests.items():
            seconds = []
            for _ in range(2):
                t0 = time.perf_counter()
                r = client.post(f"/{name}", json=body)
                seconds.append(time.perf_counter() - t0)
                if r.status_code != 200:
                    print(f"❌ /{name}: HTTP {r.status_code} {r.text[:200]}")
                    return 1
            results[name] = r.json()
            fast = seconds[1] <= SECOND_CALL_MAX_S
            ok &= fast
            print(f"{'✅' if fast else '❌'} /{name}: {seconds[0]:.1f} s first, "
                  f"{seconds[1]:.2f} s cached")

    prefill, analyze = results["prefill"], results["analyze"]
    checks = {
        "prefill has a land cover card first": prefill["cards"][0]["id"] == "land_cover",
        "prefill: no farmland warning": prefill["warning"] is None,
        "analyze: 4 strategies ranked 1-4":
            sorted(s["rank"] for s in analyze["strategies"]) == [1, 2, 3, 4],
        "analyze: every strategy has a 12-month calendar":
            all(len(s["calendar"]) == 12 for s in analyze["strategies"]),
        "analyze: one report slot per language":
            set(analyze["reports_tier1"]) == set(farm["report_languages"]),
        "analyze: disclaimer present": bool(analyze["disclaimer"]),
    }
    for label, passed in checks.items():
        ok &= passed
        print(f"{'✅' if passed else '❌'} {label}")
    top = min(analyze["strategies"], key=lambda s: s["rank"])
    print(f"   top strategy: {top['name']} ({top['total']}); gaps: {len(analyze['gaps'])}; "
          f"data {analyze['timings_ms']['data']} ms, engine {analyze['timings_ms']['engine']} ms")

    if args.save:
        CONTRACTS.mkdir(parents=True, exist_ok=True)
        for name in requests:
            (CONTRACTS / f"{name}_request.sample.json").write_text(
                json.dumps(requests[name], indent=2, ensure_ascii=False) + "\n")
            (CONTRACTS / f"{name}_response.sample.json").write_text(
                json.dumps(results[name], indent=2, ensure_ascii=False) + "\n")
        print(f"   samples saved to {CONTRACTS.relative_to(ROOT)}/")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
