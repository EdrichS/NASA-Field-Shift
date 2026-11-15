"""ADMIN ONLY: simulate a storm near a demo farm for the demo. Runs on the server (needs the
database in .env); there is no button or API route for it, so users can't fake alerts.

Every saved field (any account) within 300 km of the simulated track gets one alert, delivered
like a real NASA EONET event: in the app, by email and as push, per each field's settings.

  make simulate-storm                      # Tagum City (Philippines) demo farm
  make simulate-storm FARM=iowa-corn-soybean
  make simulate-storm NEW=1                # a new storm even if one ran this hour (resends)
  make clear-simulations                   # remove all simulated storms and their alerts
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.alerts import service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--farm", default="tagum-rice")
    parser.add_argument("--new", action="store_true", help="a new storm even within the hour")
    parser.add_argument("--clear", action="store_true", help="remove simulated storms + alerts")
    args = parser.parse_args()
    if args.clear:
        print("Removed:", service.clear_simulations())
        return 0
    result = service.simulate(args.farm, fresh=args.new)
    print(f"{result['title']} ({result['event_id']}): {result['new']} new alert(s) sent.")
    if not result["new"]:
        print("No new alerts: no saved fields in range, or this storm already ran this hour "
              "(use NEW=1).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
