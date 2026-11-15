"""Write the API's OpenAPI schema to shared/contracts/openapi.json (offline, no server needed).
The frontend's TypeScript types are generated from this file."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.main import app  # noqa: E402

OUT = ROOT / "shared" / "contracts" / "openapi.json"

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(app.openapi(), indent=2) + "\n")
    print(f"✅ wrote {OUT.relative_to(ROOT)} ({len(app.openapi()['paths'])} paths)")
