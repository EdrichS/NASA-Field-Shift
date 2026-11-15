"""Which country a field is in: FAO GAUL 2024 level-0 boundaries in Earth Engine
(projects/sat-io/open-datasets/FAO/GAUL/GAUL_2024_L0, community catalog), cached per location.
Used to keep crop suggestions to crops the country actually grows (app.engine.regional)."""

from __future__ import annotations

import logging

from app.data.cache import Cache, default_cache

log = logging.getLogger(__name__)
GAUL = "projects/sat-io/open-datasets/FAO/GAUL/GAUL_2024_L0"


def country_of(lon: float, lat: float, cache: Cache | None = None) -> str | None:
    """The country's FAO name (e.g. "Philippines"), or None if unknown (sea, or lookup failed)."""
    cache = cache or default_cache()
    key = f"country:v1:{round(lon, 2)}:{round(lat, 2)}"
    hit = cache.get(key)
    if hit is not None:
        return hit.get("name")
    try:
        from app.data.earthengine import _ee

        ee = _ee()
        feature = ee.FeatureCollection(GAUL).filterBounds(ee.Geometry.Point([lon, lat])).first()
        name = ee.Algorithms.If(feature, ee.Feature(feature).get("gaul0_name"), None).getInfo()
    except Exception as exc:  # a failed lookup only means no regional filter
        log.info("country lookup failed: %s", type(exc).__name__)
        return None
    cache.set(key, {"name": name})
    return name
