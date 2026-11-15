"""The farmer's corrections to the satellite cards override the estimates (CLAUDE.md section 6:
"The farmer's answers override the estimates").

The frontend sends them as answers["confirmed_prefill"] = {card_id: {"status": "confirmed" |
"corrected" | "unsure", "value": ...}}. Only "corrected" changes anything. Every change is stated
in plain words and returned as a note, so the report shows what the farmer changed. Detailed-mode
soil test values (answers["detailed"]["soil_test"]) override the SoilGrids pH.
"""

from __future__ import annotations

from typing import Any

from app.engine.evidence import Evidence
from app.engine.scoring import FieldContext

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
FARMER = "Farmer's answer"

# Representative slope for each answer, inside the same classes the slope card uses
# (app.features.prefill.SLOPE_CLASSES: <2° nearly flat, <5° gently sloping, <10° sloping).
SLOPE_DEG = {"flat": 1.0, "gentle slope": 3.5, "steep": 12.0}
# Texture words the engine reads ("clay" in the name = slow drainage risk).
TEXTURE = {"sandy": "sandy loam", "loam": "loam", "clay": "clay", "silty": "silt loam"}
RAIN_FACTOR = {"drier than this": 0.85, "wetter than this": 1.15}


def _months(value: Any) -> list[int] | None:
    if not isinstance(value, list):
        return None
    out = sorted({int(m) for m in value if isinstance(m, (int, float)) and 1 <= int(m) <= 12})
    return out


def _text(months: list[int]) -> str:
    return ", ".join(MONTH_NAMES[m - 1] for m in months) or "none"


def corrected(raw_answers: dict[str, Any] | None) -> dict[str, Any]:
    """{card_id: value} for cards the farmer corrected."""
    cards = (raw_answers or {}).get("confirmed_prefill") or {}
    if not isinstance(cards, dict):
        return {}
    return {cid: a.get("value") for cid, a in cards.items()
            if isinstance(a, dict) and a.get("status") == "corrected"}


def apply_to_calendar(calendar: list[dict[str, Any]], fixes: dict[str, Any]) -> list[str]:
    """Heat and frost months from the farmer replace the satellite flags (in place)."""
    notes = []
    for card, flag, label in (("heat", "heat", "Hot spells"), ("frost", "frost", "Frost")):
        months = _months(fixes.get(card))
        if months is None:
            continue
        for m in calendar:
            flags = set(m["flags"])
            if m["month"] in months:
                if flag not in flags:
                    m["evidence"] = [*m["evidence"], Evidence(
                        f"{label} in {m['name']} (you told us)", True, "", FARMER, "your field",
                        "farmer", "high")]
                flags.add(flag)
            else:
                flags.discard(flag)
            m["flags"] = sorted(flags)
        notes.append(f"You corrected {label.lower()} months to: {_text(months)}")
    return notes


def apply_to_context(ctx: FieldContext, fixes: dict[str, Any],
                     raw_answers: dict[str, Any] | None) -> list[str]:
    notes = []
    slope = fixes.get("slope")
    if slope in SLOPE_DEG:
        ctx.slope_deg = SLOPE_DEG[slope]
        notes.append(f"You said the land is {slope}: slope set to about {ctx.slope_deg:g}° "
                     "instead of the NASA SRTM estimate")
    soil = fixes.get("soil")
    if soil in TEXTURE:
        ctx.texture = TEXTURE[soil]
        notes.append(f"You said the soil is {soil}: used instead of the SoilGrids estimate")
    rain = fixes.get("rain")
    if rain in RAIN_FACTOR:
        factor = RAIN_FACTOR[rain]
        ctx.rain = [r * factor for r in ctx.rain]
        ctx.annual_rain_mm *= factor
        notes.append(f"You said your rain is {rain.replace(' than this', '')} than the satellite "
                     f"average: rainfall adjusted by {round((factor - 1) * 100):+d}% for scoring")
    test = ((raw_answers or {}).get("detailed") or {}).get("soil_test") or {}
    try:
        ph = float(str(test.get("ph", "")).replace(",", "."))
    except ValueError:
        ph = None
    if ph is not None and 3 <= ph <= 10:
        ctx.soil_ph = ph
        notes.append(f"Your soil test pH {ph:g} replaces the SoilGrids estimate")
    if fixes.get("land_cover") == "it's not farmland":
        notes.append("You said this spot is not farmland; the results assume it will be farmed")
    return notes


def bare_months(sat_bare: list[int], fixes: dict[str, Any]) -> tuple[list[int], list[str]]:
    months = _months(fixes.get("bare_months"))
    if months is None:
        return sat_bare, []
    return months, [f"You corrected the months your field looks bare to: {_text(months)}"]
