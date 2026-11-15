"""Copy the pre-computed showcase farms into the frontend (frontend/public/demo/) so the built
app can show them with no backend, e.g. on Cloudflare Pages after the event.

Run after `make showcase`:  make bundle-demo
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.api import showcase  # noqa: E402

OUT = ROOT / "frontend" / "public" / "demo"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    farms = [f for f in showcase.list_farms() if f["available"]]
    if not farms:
        print("No pre-computed showcase farms found; run `make showcase` first.")
        return 1
    for farm in farms:
        shutil.copyfile(showcase.SHOWCASE_DIR / f"{farm['id']}.json", OUT / f"{farm['id']}.json")
        print(f"  {farm['id']}.json")
    (OUT / "index.json").write_text(json.dumps(farms, ensure_ascii=False, indent=1) + "\n")
    print(f"Bundled {len(farms)} demo farm(s) into {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
