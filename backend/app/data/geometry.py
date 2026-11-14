"""Field geometry helpers. Pure functions; no Earth Engine import.

A field is a GeoJSON Point (buffered to FIELD_BUFFER_M around it) or a Polygon/MultiPolygon,
always in EPSG:4326 (lon, lat). geom_hash() gives a stable short ID for a location, used to key
shared climate data and caches without storing who the field belongs to.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

FIELD_BUFFER_M = 250  # a clicked or located point stands for a ~20 ha field around it
HASH_DECIMALS = 5  # ~1 m: tiny float noise from the browser maps to the same hash
SUPPORTED_TYPES = {"Point", "Polygon", "MultiPolygon"}


def _round(coords: Any, decimals: int) -> Any:
    if isinstance(coords, (int, float)):
        return round(float(coords), decimals)
    return [_round(c, decimals) for c in coords]


def validate(geometry: dict[str, Any]) -> dict[str, Any]:
    """Return a clean {type, coordinates} dict, or raise ValueError."""
    kind = geometry.get("type") if isinstance(geometry, dict) else None
    if kind not in SUPPORTED_TYPES:
        raise ValueError(f"geometry type must be one of {sorted(SUPPORTED_TYPES)}, got {kind!r}")
    coords = geometry.get("coordinates")
    if kind == "Point":
        if not (isinstance(coords, (list, tuple)) and len(coords) >= 2):
            raise ValueError("a Point needs [lon, lat]")
        lon, lat = float(coords[0]), float(coords[1])
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError(f"point out of range: lon {lon}, lat {lat}")
        coords = [lon, lat]
    elif not coords:
        raise ValueError(f"a {kind} needs coordinates")
    return {"type": kind, "coordinates": coords}


def geom_hash(geometry: dict[str, Any]) -> str:
    g = validate(geometry)
    payload = {"type": g["type"], "coordinates": _round(g["coordinates"], HASH_DECIMALS)}
    if g["type"] == "Point":
        payload["buffer_m"] = FIELD_BUFFER_M
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def centroid(geometry: dict[str, Any]) -> tuple[float, float]:
    """(lon, lat) of the field: the point itself, or the average of a polygon's outer ring
    (close enough for fields; used to pick the POWER weather cell)."""
    g = validate(geometry)
    if g["type"] == "Point":
        return g["coordinates"][0], g["coordinates"][1]
    ring = g["coordinates"][0] if g["type"] == "Polygon" else g["coordinates"][0][0]
    pts = ring[:-1] if len(ring) > 1 and ring[0] == ring[-1] else ring
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def to_ee_geometry(ee: Any, geometry: dict[str, Any]) -> Any:
    """The field as an ee.Geometry (points are buffered to FIELD_BUFFER_M)."""
    g = validate(geometry)
    if g["type"] == "Point":
        return ee.Geometry.Point(g["coordinates"]).buffer(FIELD_BUFFER_M)
    return ee.Geometry(g)
