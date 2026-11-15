"""The "Is this right?" satellite cards shown before any question (CLAUDE.md section 3, step 3).

Each card: a plain statement, the numbers and evidence behind it, a confidence label, and how the
farmer can correct it. Corrections override the estimates in the engine.
"""

from __future__ import annotations

from typing import Any

from app.engine.evidence import CONFIDENCE_BY_DETAIL, Evidence, from_feature
from app.features.bare_field import month_range, runs, satellite_bare_months
from app.features.harmonize import MONTH_NAMES, FieldFeatures
from app.features.stress import stress_calendar

SLOPE_CLASSES = ((2.0, "nearly flat"), (5.0, "gently sloping"), (10.0, "sloping"))


def _card(card_id: str, title: str, statement: str, value: Any, evidence: list[Evidence],
          edit: dict[str, Any]) -> dict[str, Any]:
    levels = [e.confidence for e in evidence] or ["low"]
    confidence = "high" if all(c == "high" for c in levels) else (
        "low" if all(c == "low" for c in levels) else "medium")
    return {"id": card_id, "title": title, "statement": statement, "value": value,
            "confidence": confidence, "evidence": [e.to_dict() for e in evidence], "edit": edit}


def field_warning(ff: FieldFeatures) -> str | None:
    """A friendly message when the spot doesn't look like farmland (never an error)."""
    if "land_cover" not in ff.static:
        return None  # land cover unavailable: say nothing rather than guess
    lc = ff.static["land_cover"].get("shares") or {}
    if not lc:  # WorldCover maps land only: no data means open water
        return "This spot looks like open water. Tap on farmland to analyze a field."
    if lc.get("water", 0) >= 0.5:
        return "This spot looks like water. Tap on farmland to analyze a field."
    if lc.get("built_up", 0) >= 0.5:
        return "This spot is mostly buildings or roads. Tap on farmland to analyze a field."
    if lc.get("cropland", 0) < 0.2:
        main = max(lc, key=lc.get).replace("_", " ")
        return (f"Satellites see mostly {main} here, not cropland. You can still explore it, "
                "but the results fit farmland best.")
    return None


def _months_text(months: list[int]) -> str:
    return ", ".join(month_range(r) for r in sorted(runs(months), key=lambda r: r[0]))


def prefill_cards(ff: FieldFeatures) -> list[dict[str, Any]]:
    cards = []

    lc = ff.static.get("land_cover")
    if lc and lc.get("shares"):
        top = [kv for kv in sorted(lc["shares"].items(), key=lambda kv: -kv[1])[:2]
               if kv[1] >= 0.05] or [max(lc["shares"].items(), key=lambda kv: kv[1])]
        text = " and ".join(f"{share:.0%} {name.replace('_', ' ')}" for name, share in top)
        cards.append(_card(
            "land_cover", "What the land is", f"From space this spot looks like {text}.",
            lc["shares"],
            [Evidence("Land cover share of the field", lc["shares"], "share", lc["dataset"],
                      lc["native_resolution"], "2021", "high")],
            {"type": "choice", "options": ["it's farmland", "it's not farmland"]},
        ))

    bare, bare_ev = satellite_bare_months(ff)
    if bare:
        cards.append(_card(
            "bare_months", "When your field looks bare",
            f"Your field usually looks bare or newly planted in {_months_text(bare)}.",
            bare, bare_ev, {"type": "months"},
        ))

    sm = ff.features.get("soil_moisture_root")
    if sm is not None and all(v is not None for v in sm.normal):
        driest = sorted(range(12), key=lambda i: sm.normal[i])[:2]
        wettest = max(range(12), key=lambda i: sm.normal[i])
        cards.append(_card(
            "driest_soil", "When the soil is driest",
            f"The soil where roots drink is driest in {MONTH_NAMES[driest[0]]} and wettest "
            f"in {MONTH_NAMES[wettest]}.",
            [i + 1 for i in sorted(driest)],
            [from_feature(sm, f"Root-zone soil moisture in {MONTH_NAMES[i]}", sm.normal[i])
             for i in driest + [wettest]],
            {"type": "months"},
        ))

    rain = ff.features.get("rain")
    if rain is not None and all(v is not None for v in rain.normal):
        lo = min(range(12), key=lambda i: rain.normal[i])
        hi = max(range(12), key=lambda i: rain.normal[i])
        annual = round(sum(v * d for v, d in zip(rain.normal, _DAYS, strict=True)))
        cards.append(_card(
            "rain", "Typical rain",
            f"About {annual} mm of rain a year: as little as {rain.normal[lo]:.1f} mm/day in "
            f"{MONTH_NAMES[lo]}, up to {rain.normal[hi]:.1f} mm/day in {MONTH_NAMES[hi]}.",
            rain.normal,
            [from_feature(rain, "Yearly rainfall (30-year normal)", annual, "mm/year"),
             from_feature(rain, f"Driest month: {MONTH_NAMES[lo]}", rain.normal[lo]),
             from_feature(rain, f"Wettest month: {MONTH_NAMES[hi]}", rain.normal[hi])],
            {"type": "choice", "options": ["drier than this", "about right", "wetter than this"]},
        ))

    calendar = stress_calendar(ff)
    heat = [m["month"] for m in calendar if "heat" in m["flags"]]
    frost = [m["month"] for m in calendar if "frost" in m["flags"]]
    heat_ev = [e for m in calendar for e in m["evidence"] if "35 °C" in e.claim]
    frost_ev = [e for m in calendar for e in m["evidence"] if "0 °C" in e.claim]
    hot = ff.features.get("t_hottest")
    if hot is not None:
        statement = (f"Heat of 35 °C or more is common in {_months_text(heat)}." if heat
                     else "Heat of 35 °C or more is rare here.")
        cards.append(_card("heat", "Hot spells", statement, heat,
                           heat_ev or [from_feature(hot, "Typical hottest hour by month",
                                                    hot.normal)],
                           {"type": "months"}))
    cold = ff.features.get("t_coldest")
    if cold is not None:
        statement = (f"Frost (0 °C or below) is likely in {_months_text(frost)}." if frost
                     else "No frost (0 °C or below) in the last 30 years.")
        cards.append(_card("frost", "Frost", statement, frost,
                           frost_ev or [from_feature(cold, "Typical coldest hour by month",
                                                     cold.normal)],
                           {"type": "months"}))

    terrain = ff.static.get("terrain")
    if terrain and terrain.get("slope_deg") is not None:
        slope = terrain["slope_deg"]
        label = next((name for limit, name in SLOPE_CLASSES if slope < limit), "steep")
        cards.append(_card(
            "slope", "Slope", f"The land is {label} (about {slope:.0f}°).", slope,
            [Evidence("Average slope over the field", slope, "degrees", terrain["dataset"],
                      terrain["native_resolution"], "static", "high")],
            {"type": "choice", "options": ["flat", "gentle slope", "steep"]},
        ))

    soil = ff.static.get("soil")
    if soil and soil.get("texture"):
        cards.append(_card(
            "soil", "Soil",
            f"The soil is probably {soil['texture']} (about {soil['clay_pct']:.0f}% clay, "
            f"pH {soil['ph']:.1f}). A soil test would be more accurate.",
            soil["texture"],
            [Evidence("Estimated soil texture (0-30 cm)", soil["texture"], "USDA class",
                      soil["dataset"], soil["native_resolution"], "static", "medium"),
             Evidence("Estimated soil pH (0-30 cm)", soil["ph"], "pH", soil["dataset"],
                      soil["native_resolution"], "static", "medium")],
            {"type": "choice",
             "options": ["sandy", "loam", "clay", "silty", "I have a soil test"]},
        ))

    water = ff.static.get("water_storage")
    if water and water.get("trend_cm_per_year") is not None:
        trend = water["trend_cm_per_year"]
        word = "stable" if abs(trend) < 0.3 else ("falling" if trend < 0 else "rising")
        cards.append(_card(
            "groundwater", "Regional water storage",
            f"Water stored underground in the wider region has been {word} since 2002. "
            "This is a regional picture, not your well.",
            trend,
            [Evidence("Regional water storage trend", trend, "cm/year", water["source"],
                      water["native_resolution"], water["period"],
                      CONFIDENCE_BY_DETAIL["regional"])],
            {"type": "choice", "options": ["my water is getting scarcer", "about right",
                                           "I don't know"]},
        ))
    return cards


_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
