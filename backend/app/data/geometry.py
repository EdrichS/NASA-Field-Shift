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
MAX_FIELD_SPAN_DEG = 0.5  # ~55 km: wider is a region, not a field (the app draws up to 2,000 ha)


def _round(coords: Any, decimals: int) -> Any:
    if isinstance(coords, (int, float)):
        return round(float(coords), decimals)
    return [_round(c, decimals) for c in coords]


def _position(p: Any) -> list[float]:
    if not (isinstance(p, (list, tuple)) and len(p) >= 2):
        raise ValueError("each position needs [lon, lat]")
    try:
        lon, lat = float(p[0]), float(p[1])
    except (TypeError, ValueError):
        raise ValueError("coordinates must be numbers") from None
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError(f"point out of range: lon {lon}, lat {lat}")
    return [lon, lat]


def _polygons(kind: str, coords: Any) -> list[list[list[list[float]]]]:
    polygons = [coords] if kind == "Polygon" else coords
    if not (isinstance(polygons, list) and polygons):
        raise ValueError(f"a {kind} needs coordinates")
    clean = []
    for poly in polygons:
        if not (isinstance(poly, list) and poly):
            raise ValueError(f"a {kind} needs rings of [lon, lat] positions")
        rings = []
        for ring in poly:
            if not (isinstance(ring, list) and len(ring) >= 4):
                raise ValueError("each ring needs at least 4 positions")
            rings.append([_position(p) for p in ring])
        clean.append(rings)
    lons = [p[0] for poly in clean for ring in poly for p in ring]
    lats = [p[1] for poly in clean for ring in poly for p in ring]
    if max(lons) - min(lons) > MAX_FIELD_SPAN_DEG or max(lats) - min(lats) > MAX_FIELD_SPAN_DEG:
        raise ValueError("that outline is bigger than one field; draw a single field")
    return clean


def validate(geometry: dict[str, Any]) -> dict[str, Any]:
    """Return a clean {type, coordinates} dict, or raise ValueError."""
    kind = geometry.get("type") if isinstance(geometry, dict) else None
    if kind not in SUPPORTED_TYPES:
        raise ValueError(f"geometry type must be one of {sorted(SUPPORTED_TYPES)}, got {kind!r}")
    coords = geometry.get("coordinates")
    if kind == "Point":
        coords = _position(coords)
    else:
        polygons = _polygons(kind, coords)
        coords = polygons[0] if kind == "Polygon" else polygons
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
