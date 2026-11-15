"""The engine: field features + farmer answers -> current rotation + 3 scored alternatives, each
with why, benefits, risks, information gaps, expert questions and evidence. Deterministic: the
same inputs always give the same result. Grok only rewrites this output in plain words.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.engine import corrections
from app.engine.answers import FarmProfile, parse_answers
from app.engine.candidates import Candidate, break_pest, fill_bare, save_water
from app.engine.catalog import CropInfo, default_catalog
from app.engine.evidence import Evidence
from app.engine.rotation import Slot, bare_by_month, cover_by_month, group_years
from app.engine.scoring import (
    COMPONENTS,
    ComponentScore,
    FieldContext,
    crop_of,
    score_rotation,
    total_score,
    weights_for,
)
from app.features.bare_field import runs, satellite_bare_months
from app.features.harmonize import MONTH_NAMES, FieldFeatures
from app.features.stress import stress_calendar

DISCLAIMER = (
    "SowSmart supports your own judgment and local agricultural expertise; it does not replace "
    "them. Check any change with a local expert before you plant."
)
NAMES = {"current": "Your current rotation", "fill_bare": "Fill the bare gap",
         "break_pest": "Break the pest cycle", "save_water": "Save water"}
BENEFIT_TEXT = {
    "water": "Needs less water beyond rainfall",
    "soil": "Builds soil",  # made specific by _soil_benefit
    "erosion": "Less bare soil exposed to rain",
    "pest_cycle": "Breaks pest and disease cycles with a different plant family",
    "climate_risk": "Less exposure to heat, frost, dry spells or flooding",
    "income": "More harvests to sell or eat",
    "labor": "Less hand work",
}
TRADEOFF_TEXT = {
    "water": "Needs more water beyond rainfall",
    "soil": "Covers or feeds the soil less",
    "erosion": "Leaves soil bare longer",
    "pest_cycle": "Less variety of plant families",
    "climate_risk": "More exposure to heat, frost, dry spells or flooding",
    "income": "Fewer harvests to sell or eat",
    "labor": "More hand work",
}


def _soil_benefit(new: dict[str, Any], old: dict[str, Any]) -> str:
    """Say exactly which soil factor improved (an "and/or" text let the AI guess wrong)."""
    n, o = new["soil"].metrics, old["soil"].metrics
    parts = []
    if n.get("cover", 0) > o.get("cover", 0) + 0.02:
        parts.append("the soil is covered more months")
    if n.get("legume_share", 0) > o.get("legume_share", 0):
        parts.append("a legume adds nitrogen")
    if (n.get("root_depth_m") or 0) > (o.get("root_depth_m") or 0) + 0.05:
        parts.append("deeper roots")
    if n.get("cover_crop") and not o.get("cover_crop"):
        parts.append("a cover crop protects and feeds the soil")
    return "Builds soil: " + "; ".join(parts) if parts else "Builds soil"


@dataclass
class Strategy:
    key: str
    name: str
    title: str
    rotation: list[list[dict[str, Any]]]
    calendar: list[dict[str, Any]]
    components: dict[str, dict[str, Any]]
    total: float
    rank: int = 0
    confidence: str = "medium"
    why: str = ""
    changes: list[str] = field(default_factory=list)
    benefits: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    expert_questions: list[str] = field(default_factory=list)


@dataclass
class EngineResult:
    field: dict[str, Any]
    profile: dict[str, Any]
    weights: dict[str, float]
    bare_months: dict[str, Any]
    stress_calendar: list[dict[str, Any]]
    strategies: list[Strategy]
    gaps: list[str]
    disclaimer: str = DISCLAIMER

    def to_dict(self) -> dict[str, Any]:
        def convert(obj: Any) -> Any:
            if isinstance(obj, Evidence):
                return obj.to_dict()
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [convert(v) for v in obj]
            return obj
        return convert(asdict(self))


def _calendar(years: list[list[Slot]], flags: list[set[str]]) -> list[dict[str, Any]]:
    bare = bare_by_month(years)
    out = []
    for i in range(12):
        crops = []
        for y, year in enumerate(years):
            for slot in year:
                share = slot.occupancy().get(i + 1, 0)
                if share:
                    crops.append({"crop": slot.crop, "share": share, "year": y + 1,
                                  "new": slot.new})
        out.append({"month": i + 1, "name": MONTH_NAMES[i], "crops": crops,
                    "bare": bare[i], "stress": sorted(flags[i])})
    return out


def _slot_text(slot: Slot) -> str:
    start, end = MONTH_NAMES[slot.plant_month - 1], MONTH_NAMES[slot.harvest_month - 1]
    return f"{slot.crop} ({start}–{end})"


def _why(cand: Candidate, current: dict[str, ComponentScore], comps: dict[str, ComponentScore],
         catalog: dict[str, CropInfo]) -> tuple[str, list[str]]:
    crop = cand.crop
    if cand.key == "fill_bare" and crop and cand.gap:
        start = MONTH_NAMES[cand.gap.start_month - 1]
        end = MONTH_NAMES[cand.gap.end_month - 1]
        kind = ("a legume that adds nitrogen" if crop.is_legume
                else "a cover crop that protects the soil")
        return (f"Your field sits bare from mid-{start} to mid-{end} (about {cand.gap.days} "
                f"days). {crop.name.capitalize()} needs as little as {crop.cycle_min_days} days "
                f"(FAO EcoCrop) and is {kind}.",
                [f"Add {crop.name} between harvest and the next planting"])
    if cand.key == "break_pest" and crop and cand.replaced:
        old = crop_of(cand.replaced, catalog)
        return (f"Growing the {old.family} family again and again lets its pests and diseases "
                f"carry over ({cand.note}). {crop.name.capitalize()} is from the {crop.family} "
                f"family, so they lose their host for a season.",
                [f"Grow {crop.name} instead of {cand.replaced} once in the rotation"])
    if cand.key == "save_water" and crop and cand.replaced:
        saved = current["water"].metrics["deficit_mm"] - comps["water"].metrics["deficit_mm"]
        old = crop_of(cand.replaced, catalog)
        if saved >= 20:
            detail = (f"{crop.name.capitalize()} needs about {saved} mm less water per year "
                      f"beyond rainfall here and has {crop.drought_tolerance} drought tolerance.")
        else:
            detail = (f"{crop.name.capitalize()} needs about the same water but handles dry "
                      f"spells better ({crop.drought_tolerance} vs {old.drought_tolerance} "
                      "drought tolerance).")
        return (f"{cand.replaced.capitalize()} is the thirstiest crop in your rotation. {detail}",
                [f"Grow {crop.name} instead of {cand.replaced}"])
    return "", []


def _risks_and_questions(cand: Candidate, ctx: FieldContext, catalog: dict[str, CropInfo],
                         profile: FarmProfile) -> tuple[list[str], list[str]]:
    risks, questions = [], []
    crop = cand.crop
    if crop is None:
        return risks, questions
    months = cand.suit.months if cand.suit else ()
    heavy = (ctx.texture or "").find("clay") >= 0
    after_rice = cand.gap is not None and cand.gap.after is not None and \
        cand.gap.after.crop == "rice"
    if crop.waterlogging_tolerance == "low" and (heavy or after_rice):
        where = (f"after paddy rice on {ctx.texture or 'heavy'} soil the field may stay wet"
                 if after_rice else f"{ctx.texture} soil can stay wet after heavy rain")
        risks.append(f"{crop.name.capitalize()} needs well-drained soil; {where}")
        questions.append(f"Can the field drain well enough for {crop.name}?")
    if any("heat" in ctx.flags[m - 1] for m in months) and crop.heat_tolerance != "high":
        risks.append(f"Heat of 35 °C+ is common while {crop.name} grows")
        questions.append(f"Which {crop.name} varieties handle heat above 35 °C here?")
    if cand.gap is not None and crop.cycle_min_days > 0.85 * cand.gap.days:
        risks.append(f"Tight timing: {crop.name} needs {crop.cycle_min_days}+ days and the gap "
                     f"is about {cand.gap.days} days")
        questions.append(f"Is there an early-maturing {crop.name} variety (under "
                         f"{cand.gap.days - 10} days)?")
    if profile.water != "irrigated" and any("dry" in ctx.flags[m - 1] for m in months) \
            and crop.drought_tolerance != "high":
        risks.append(f"{crop.name.capitalize()} meets a dry month without irrigation")
        questions.append("Is there water for one or two irrigations if rains are late?")
    if not crop.is_cover and (not profile.sellable or crop.name not in profile.sellable):
        questions.append(f"Is there a buyer or local market for {crop.name}?")
    seed = f"Where can I get good {crop.name} seed"
    questions.append(seed + (" and the right inoculant (rhizobia)?" if crop.is_legume else "?"))
    if not crop.verified:
        risks.append(f"Trait data for {crop.name} is not verified yet")
    return risks, questions


def _confidence(cand: Candidate | None, profile: FarmProfile, ff: FieldFeatures,
                catalog: dict[str, CropInfo], years: list[list[Slot]]) -> str:
    points = 3
    key_unknowns = ("Irrigation unknown", "Current crops estimated")
    if any(a.startswith(key_unknowns) for a in profile.assumptions):
        points -= 1
    if any(not crop_of(s.crop, catalog).verified for y in years for s in y):
        points -= 1
    if cand is not None and cand.suit is not None and cand.suit.score < 0.75:
        points -= 1
    if ff.gaps:
        points -= 1
    return "high" if points >= 3 else "medium" if points == 2 else "low"


def run_engine(ff: FieldFeatures, raw_answers: dict[str, Any] | None,
               catalog: dict[str, CropInfo] | None = None) -> EngineResult:
    catalog = catalog if catalog is not None else default_catalog()
    calendar = stress_calendar(ff)
    fixes = corrections.corrected(raw_answers)  # the farmer's card corrections win
    notes = corrections.apply_to_calendar(calendar, fixes)
    ctx = FieldContext.build(ff, calendar)
    notes += corrections.apply_to_context(ctx, fixes, raw_answers)
    sat_bare, sat_ev = satellite_bare_months(ff)
    sat_bare, bare_notes = corrections.bare_months(sat_bare, fixes)
    notes += bare_notes
    green = [m for m in range(1, 13) if m not in sat_bare] if sat_bare else []
    profile = parse_answers(raw_answers, catalog, runs(green))
    weights = weights_for(profile.goals)

    current_years = group_years(profile.slots)
    current_comps = score_rotation(current_years, ctx, catalog, profile.water,
                                   profile.equipment, profile.sellable)

    candidates: list[Candidate] = []
    for build in (fill_bare, break_pest):
        cand = build(profile, current_years, ctx, catalog)
        if cand is not None:
            candidates.append(cand)
    water_cand = save_water(profile, current_years, ctx, catalog,
                            [c.years for c in candidates] + [current_years])
    if water_cand is not None:
        candidates.append(water_cand)

    data_gaps = notes + list(profile.assumptions) + list(ff.gaps) + [
        "Weather comes from a ~55 km NASA POWER grid cell: a regional average, not your field",
        "Soil values are SoilGrids estimates; a soil test would be more accurate",
    ]
    if len(candidates) < 3:
        missing = {"fill_bare", "break_pest", "save_water"} - {c.key for c in candidates}
        data_gaps.append("No suitable crop found for: " + ", ".join(sorted(missing)))

    strategies = [Strategy(
        key="current",
        name=NAMES["current"] if profile.rotation_source != "satellite"
        else "Current pattern (estimated from satellite)",
        title=" + ".join(_slot_text(s) for y in current_years for s in y) or "No crops yet",
        rotation=[[asdict(s) for s in y] for y in current_years],
        calendar=_calendar(current_years, ctx.flags),
        components={k: asdict(v) for k, v in current_comps.items()},
        total=total_score(current_comps, weights),
        confidence=_confidence(None, profile, ff, catalog, current_years),
        why="The baseline: what you grow now, scored the same way as the alternatives.",
        gaps=list(profile.assumptions),
    )]
    for cand in candidates:
        comps = score_rotation(cand.years, ctx, catalog, profile.water, profile.equipment,
                               profile.sellable)
        why, changes = _why(cand, current_comps, comps, catalog)
        risks, questions = _risks_and_questions(cand, ctx, catalog, profile)
        harvest_change = (comps["income"].metrics.get("harvests_per_year", 0)
                          - current_comps["income"].metrics.get("harvests_per_year", 0))
        benefits = [(_soil_benefit(comps, current_comps) if c == "soil" else BENEFIT_TEXT[c])
                    + f" (+{comps[c].score - current_comps[c].score:.0f})"
                    for c in COMPONENTS if comps[c].score - current_comps[c].score >= 5
                    and (c != "income" or harvest_change > 0)]  # a cover crop isn't a harvest
        risks += [TRADEOFF_TEXT[c] + f" ({comps[c].score - current_comps[c].score:.0f})"
                  for c in COMPONENTS if comps[c].score - current_comps[c].score <= -5
                  and (c != "income" or harvest_change < 0)]
        title = " + ".join(_slot_text(s) for y in cand.years for s in y)
        strategies.append(Strategy(
            key=cand.key, name=NAMES[cand.key], title=title,
            rotation=[[asdict(s) for s in y] for y in cand.years],
            calendar=_calendar(cand.years, ctx.flags),
            components={k: asdict(v) for k, v in comps.items()},
            total=total_score(comps, weights),
            confidence=_confidence(cand, profile, ff, catalog, cand.years),
            why=why, changes=changes, benefits=benefits, risks=risks,
            gaps=[g for g in data_gaps if "POWER" not in g and "SoilGrids" not in g],
            expert_questions=questions,
        ))
    for rank, strat in enumerate(sorted(strategies, key=lambda s: (-s.total, s.key)), start=1):
        strat.rank = rank

    covers = [cover_by_month(y) for y in current_years]
    calendar_bare = [i + 1 for i in range(12) if sum(c[i] for c in covers) / len(covers) < 0.5]
    return EngineResult(
        field={"geom_hash": ff.geom_hash, "lat": ff.lat, "lon": ff.lon,
               "end_month": ff.end_month},
        profile={"mode": profile.mode, "water": profile.water, "equipment": profile.equipment,
                 "goals": profile.goals, "wont_grow": sorted(profile.wont_grow),
                 "rotation_source": profile.rotation_source},
        weights=weights,
        bare_months={"satellite": sat_bare, "satellite_evidence": sat_ev,
                     "current_rotation": calendar_bare},
        stress_calendar=calendar,
        strategies=sorted(strategies, key=lambda s: s.rank),
        gaps=data_gaps,
    )
