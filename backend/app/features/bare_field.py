"""When does the field look bare? From the MODIS NDVI monthly normal.

A month counts as bare or newly planted when its normal greenness is in the lowest 30% of this
field's own yearly range (or below 0.3 NDVI). Low greenness can also mean a crop was just
planted, so the satellite card asks the farmer to confirm.
"""

from __future__ import annotations

from app.engine.evidence import Evidence, from_feature
from app.features.harmonize import MONTH_NAMES, FieldFeatures

BARE_FRACTION_OF_RANGE = 0.3
BARE_ABSOLUTE_NDVI = 0.3


def satellite_bare_months(ff: FieldFeatures) -> tuple[list[int], list[Evidence]]:
    ndvi = ff.features.get("ndvi")
    if ndvi is None:
        return [], []
    values = [v for v in ndvi.normal if v is not None]
    if len(values) < 6:
        return [], []
    low, high = min(values), max(values)
    threshold = low + BARE_FRACTION_OF_RANGE * (high - low)
    months = [
        i + 1 for i, v in enumerate(ndvi.normal)
        if v is not None and (v <= threshold or v <= BARE_ABSOLUTE_NDVI)
    ]
    evidence = [
        from_feature(ndvi, f"Greenness in {MONTH_NAMES[m - 1]} is {ndvi.normal[m - 1]:.2f}",
                     ndvi.normal[m - 1], "NDVI")
        for m in months
    ]
    evidence.append(from_feature(
        ndvi, f"Greenest month normal is {high:.2f}; bare threshold {threshold:.2f}", high, "NDVI"
    ))
    return months, evidence


def runs(months: list[int]) -> list[list[int]]:
    """Consecutive month runs, wrapping December -> January. Longest first."""
    chosen = set(months)
    if not chosen:
        return []
    if len(chosen) == 12:
        return [list(range(1, 13))]
    start_candidates = [m for m in sorted(chosen) if (m - 2) % 12 + 1 not in chosen]
    result = []
    for start in start_candidates:
        run, m = [], start
        while m in chosen:
            run.append(m)
            m = m % 12 + 1
        result.append(run)
    return sorted(result, key=len, reverse=True)


def month_range(run: list[int]) -> str:
    if not run:
        return ""
    if len(run) == 1:
        return MONTH_NAMES[run[0] - 1]
    return f"{MONTH_NAMES[run[0] - 1]}–{MONTH_NAMES[run[-1] - 1]}"
