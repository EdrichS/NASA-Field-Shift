"""Showcase farms: analyses pre-computed by scripts/precache_showcase.py and stored in
data/showcase/<id>.json (committed), so the live demo never waits on an outside API.

The farm list comes from data/showcase_farms.json. Only ids from that list are ever read, so a URL
can't point at another file.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.schemas import AnalyzeRequest

ROOT = Path(__file__).resolve().parents[3]
FARMS_JSON = ROOT / "data" / "showcase_farms.json"
SHOWCASE_DIR = ROOT / "data" / "showcase"
_loaded: dict[Path, tuple[float, dict[str, Any]]] = {}  # path -> (mtime, content)


def farms() -> list[dict[str, Any]]:
    return json.loads(FARMS_JSON.read_text())["farms"]


def request_for(farm: dict[str, Any], *, generate_reports: bool = True) -> AnalyzeRequest:
    return AnalyzeRequest(geometry=farm["geometry"], mode=farm["answers"].get("mode", "quick"),
                          answers=farm["answers"], report_languages=farm["report_languages"],
                          generate_reports=generate_reports)


def request_key(body: AnalyzeRequest) -> str:
    canonical = body.model_dump(exclude={"generate_reports"})
    blob = json.dumps(canonical, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def _path(farm_id: str) -> Path | None:
    ids = {f["id"] for f in farms()}
    return SHOWCASE_DIR / f"{farm_id}.json" if farm_id in ids else None


def stored(farm_id: str) -> dict[str, Any] | None:
    path = _path(farm_id)
    if path is None or not path.exists():
        return None
    mtime = path.stat().st_mtime
    hit = _loaded.get(path)
    if hit is None or hit[0] != mtime:
        hit = (mtime, json.loads(path.read_text()))
        _loaded[path] = hit
    return hit[1]


def analysis(farm_id: str) -> dict[str, Any] | None:
    entry = stored(farm_id)
    return entry["analysis"] if entry else None


def match(body: AnalyzeRequest) -> dict[str, Any] | None:
    """The stored analysis when a request is exactly a showcase farm's (with reports)."""
    if not body.generate_reports:
        return None  # comparison-only requests (tests, smoke) always run the live pipeline
    key = request_key(body)
    for farm in farms():
        entry = stored(farm["id"])
        if entry and entry["request_key"] == key:
            return entry["analysis"]
    return None


def list_farms() -> list[dict[str, Any]]:
    out = []
    for farm in farms():
        entry = stored(farm["id"])
        out.append({**{k: farm[k] for k in ("id", "name", "persona", "country", "place",
                                            "story", "geometry", "report_languages")},
                    "available": entry is not None,
                    "generated_at": entry["generated_at"] if entry else None,
                    "model": entry.get("model") if entry else None})
    return out


def save(farm: dict[str, Any], body: AnalyzeRequest, result: dict[str, Any]) -> Path:
    models = {r["meta"]["model"] for r in result["reports_tier1"].values() if r}
    entry = {"farm_id": farm["id"],
             "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
             "model": ", ".join(sorted(models)) or None,
             "request_key": request_key(body),
             "analysis": result}
    SHOWCASE_DIR.mkdir(parents=True, exist_ok=True)
    path = SHOWCASE_DIR / f"{farm['id']}.json"
    path.write_text(json.dumps(entry, indent=1, ensure_ascii=False) + "\n")
    return path
