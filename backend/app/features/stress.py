"""Monthly stress calendar: heat, frost, dry and very wet months (CLAUDE.md sections 3, 6).

Thresholds (documented so they can be explained and changed):
- heat:     35 °C+ reached in at least 10 of the last 30 years (POWER yearly extremes)
- frost:    0 °C or below reached in at least 3 of the last 30 years
- dry:      30-year normal rainfall below 1.5 mm/day (~45 mm/month), only in growing months
            (mean air temperature 5 °C or more; frozen months use little water)
- very wet: 30-year normal rainfall of 12 mm/day or more (~360 mm/month)
"""

from __future__ import annotations

from typing import Any

from app.engine.evidence import Evidence, from_feature
from app.features.harmonize import MONTH_NAMES, FieldFeatures

HEAT_YEARS_MIN = 10
FROST_YEARS_MIN = 3
DRY_MM_DAY = 1.5
VERY_WET_MM_DAY = 12.0
GROWING_MEAN_C = 5.0


def stress_calendar(ff: FieldFeatures) -> list[dict[str, Any]]:
    rain = ff.features.get("rain")
    hot = ff.features.get("t_hottest")
    cold = ff.features.get("t_coldest")
    mean = ff.features.get("t_mean")
    months = []
    for i in range(12):
        name = MONTH_NAMES[i]
        flags: list[str] = []
        evidence: list[Evidence] = []
        if hot is not None:
            years = hot.extra.get("heat_years")
            if years is not None and years[i] >= HEAT_YEARS_MIN:
                flags.append("heat")
                evidence.append(from_feature(
                    hot, f"{name} reached 35 °C or more in {years[i]} of the last 30 years",
                    years[i], "years of 30", hot.extra.get("years"),
                ))
        if cold is not None:
            years = cold.extra.get("frost_years")
            if years is not None and years[i] >= FROST_YEARS_MIN:
                flags.append("frost")
                evidence.append(from_feature(
                    cold, f"{name} dropped to 0 °C or below in {years[i]} of the last 30 years",
                    years[i], "years of 30", cold.extra.get("years"),
                ))
        growing = mean is None or mean.normal[i] is None or mean.normal[i] >= GROWING_MEAN_C
        if rain is not None and rain.normal[i] is not None:
            if rain.normal[i] < DRY_MM_DAY and growing:
                flags.append("dry")
                evidence.append(from_feature(
                    rain, f"{name} usually gets only {rain.normal[i]:.1f} mm of rain per day",
                    rain.normal[i],
                ))
            elif rain.normal[i] >= VERY_WET_MM_DAY:
                flags.append("very_wet")
                evidence.append(from_feature(
                    rain, f"{name} usually gets {rain.normal[i]:.1f} mm of rain per day",
                    rain.normal[i],
                ))
        months.append({"month": i + 1, "name": name, "flags": flags, "evidence": evidence})
    return months


def flags_by_month(calendar: list[dict[str, Any]]) -> list[set[str]]:
    return [set(m["flags"]) for m in calendar]
