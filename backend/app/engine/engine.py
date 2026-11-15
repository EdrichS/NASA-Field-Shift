"""The engine: field features + farmer answers -> current rotation + 3 scored alternatives, each
with why, benefits, risks, information gaps, expert questions and evidence. Deterministic: the
same inputs always give the same result. Grok only rewrites this output in plain words.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.engine import corrections, regional
from app.engine.answers import FarmProfile, parse_answers
from app.engine.candidates import (
    MIN_GAP_DAYS,
    SUITABLE_MIN,
    BareWindow,
    Candidate,
    Fill,
    add_income,
    break_pest,
    explore,
    fill_bare,
    is_cash_crop,
    save_water,
)
from app.engine.catalog import CropInfo, default_catalog
from app.engine.evidence import Evidence
from app.engine.perennials import fruit_ideas
from app.engine.rotation import Slot, bare_by_month, cover_by_month, gaps, group_years
from app.engine.scoring import (
    COMPONENTS,
    ComponentScore,
    FieldContext,
    Market,
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
         "break_pest": "Break the pest cycle", "save_water": "Save water",
         "add_income": "Add a cash crop"}
BENEFIT_TEXT = {
    "water": "Needs less water beyond rainfall",
    "soil": "Builds soil",  # made specific by _soil_benefit
    "erosion": "Less bare soil exposed to rain",
    "pest_cycle": "Breaks pest and disease cycles with a different plant family",
    "climate_risk": "Less exposure to heat, frost, dry spells or flooding",
    "income": "More to sell or eat",
    "labor": "Less hand work",
}
TRADEOFF_TEXT = {
    "water": "Needs more water beyond rainfall",
    "soil": "Covers or feeds the soil less",
    "erosion": "Leaves soil bare longer",
    "pest_cycle": "Less variety of plant families",
    "climate_risk": "More exposure to heat, frost, dry spells or flooding",
    "income": "Less to sell or eat",
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
    fruit_ideas: list[dict[str, Any]] = field(default_factory=list)
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


def _title(years: list[list[Slot]]) -> str:
    return " + ".join(_slot_text(s) for y in years for s in sorted(y, key=lambda s: s.plant_month))


def _slot_text(slot: Slot) -> str:
    start, end = MONTH_NAMES[slot.plant_month - 1], MONTH_NAMES[slot.harvest_month - 1]
    return f"{slot.crop} ({start}–{end})"


def _when(start: int, end: int) -> str:
    return f"mid-{MONTH_NAMES[start - 1]} to mid-{MONTH_NAMES[end - 1]}"


def _windows_text(windows: list[tuple[int, int, int]]) -> str:
    parts = [f"{_when(a, b)} (about {days} days)" for a, b, days in windows]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _kind(crop: CropInfo, cash_first: bool = False) -> str:
    if cash_first and is_cash_crop(crop):
        return "a fruit for market" if "fruit" in (crop.eco.get("category") or "").split(",")[0] \
            else "a vegetable for market"
    if crop.cover_crop_role == "green_manure":
        return ("a green manure: a legume you grow and then mix into the soil to feed it"
                if crop.is_legume else "a green manure you mix into the soil to feed it")
    if crop.is_cover:
        return "a cover crop that protects the soil"
    if crop.is_legume:
        return "a legume that adds nitrogen"
    if is_cash_crop(crop):
        return "a fruit for market" if "fruit" in (crop.eco.get("category") or "").split(",")[0] \
            else "a vegetable for market"
    return "a food crop"


def _crop_line(crop: CropInfo) -> str:
    source = crop.eco.get("cycle_source") or "FAO EcoCrop"
    return (f"{crop.name.capitalize()} needs as little as {crop.cycle_min_days} days ({source}) "
            f"and is {_kind(crop)}.")


def _unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _fill_changes(fills: list[Fill]) -> list[str]:
    out = []
    for f in fills:
        after = f" after {f.gap.after.crop}" if f.gap.after and not f.gap.after.new else ""
        also = f" (also fits: {', '.join(f.alternatives)})" if f.alternatives else ""
        out.append(f"Add {f.crop.name} from {_when(f.slot.plant_month, f.slot.harvest_month)}"
                   f"{after}{also}")
    return _unique(out)


def _bare_changes(bare: list[BareWindow]) -> list[str]:
    return _unique([f"M{_when(b.start_month, b.end_month)[1:]} stays bare ({b.reason}): "
                    "keep crop residue or mulch on the soil to protect it" for b in bare])


def _value_text(crop: CropInfo, profile: FarmProfile) -> str:
    if profile.local is None or crop.name not in profile.local:
        return ""
    text = (f" It is grown on about {round(profile.local[crop.name]):,} ha in "
            f"{_country_text(profile.country)} (FAOSTAT).")
    values, ref = profile.values or {}, profile.value_ref
    mine = values.get(crop.name)
    ref_crop = next((c for c, v in values.items() if v.value_usd_ha == ref), None)
    if mine and ref and ref_crop and ref_crop != crop.name:
        text += (f" At the national average yield and farm-gate price, one harvest is worth "
                 f"about {round(mine.value_usd_ha):,} USD per hectare before costs, against "
                 f"about {round(ref):,} USD for {ref_crop}.")
    return text


def _why(cand: Candidate, current: dict[str, ComponentScore], comps: dict[str, ComponentScore],
         catalog: dict[str, CropInfo], profile: FarmProfile,
         windows: list[tuple[int, int, int]]) -> tuple[str, list[str]]:
    crop = cand.crop
    changes = _fill_changes(cand.fills) + _bare_changes(cand.bare)
    others = _unique([f.crop.name for f in cand.fills if crop is None or f.crop.name != crop.name])
    bare = f"Your field sits bare from {_windows_text(windows)}. " if windows else ""
    if cand.key == "fill_bare" and crop:
        lines = " ".join(_crop_line(c) for c in _unique_crops(cand.fills)[:3])
        return bare + lines, changes
    if cand.key == "break_pest" and crop and cand.replaced:
        old = crop_of(cand.replaced, catalog)
        why = (f"Growing the {old.family} family again and again lets its pests and diseases "
               f"carry over ({cand.note}). {crop.name.capitalize()} is from the {crop.family} "
               f"family, so they lose their host for a season.")
        if others:
            fams = ", ".join(f"{n} ({crop_of(n, catalog).family})" for n in others)
            why += f" The bare months get {fams}"
            why += (", so the same family rarely follows itself." if all(
                crop_of(n, catalog).family != old.family for n in others)
                else ": the only crops that fit there.")
        return why, [f"Grow {crop.name} instead of {cand.replaced} once in the rotation",
                     *changes]
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
        why = f"{cand.replaced.capitalize()} is the thirstiest crop in your rotation. {detail}"
        if others:
            needs = ", ".join(f"{n} ({crop_of(n, catalog).water_need} water need)"
                              for n in others)
            why += f" The bare months get {needs}."
        return why, [f"Grow {crop.name} instead of {cand.replaced}", *changes]
    if cand.key == "add_income" and crop:
        what = _kind(crop, cash_first=True).replace(" for market", "")
        if cand.replaced:
            reason = ("No fruit or vegetable fits the bare months here" if windows
                      else "Your field is rarely bare")
            why = (f"{reason}, so this grows {crop.name}, {what}, instead of {cand.replaced} "
                   "once.")
            changes = [f"Grow {crop.name} instead of {cand.replaced} once (start with part of "
                       "the field)", *changes]
        else:
            why = bare + f"{crop.name.capitalize()} is {what} that fits that window here."
        why += _value_text(crop, profile)
        why += " Fruit and vegetables take more work and need a buyer nearby."
        return why, changes
    return "", changes


def _unique_crops(fills: list[Fill]) -> list[CropInfo]:
    seen: dict[str, CropInfo] = {}
    for f in sorted(fills, key=lambda f: -f.gap.days):
        seen.setdefault(f.crop.name, f.crop)
    return list(seen.values())


MAX_RISKS, MAX_QUESTIONS = 6, 5  # the report format's limits per strategy


def _names(crops: list[str]) -> str:
    crops = list(dict.fromkeys(crops))
    return crops[0] if len(crops) == 1 else ", ".join(crops[:-1]) + " and " + crops[-1]


# Starting options (no current rotation): strengths and weaknesses on their own terms.
STRENGTH_TEXT = {
    "water": "Needs little water beyond rain here",
    "soil": "Builds soil",
    "erosion": "Keeps the soil covered most of the year",
    "pest_cycle": "Mixes plant families, so pests don't build up",
    "climate_risk": "Fits this field's heat, frost and rain pattern",
    "income": "Gives harvests to sell or eat",
    "labor": "Fits your equipment and labor",
}
WEAKNESS_TEXT = {
    "water": "Needs a lot of water beyond rain here",
    "soil": "Adds little to the soil",
    "erosion": "Leaves the soil bare for long stretches",
    "pest_cycle": "One plant family only: pests can build up over the years",
    "climate_risk": "Meets heat, frost or very wet months while it grows",
    "income": "Few harvests to sell or eat",
    "labor": "Needs more work than your equipment makes easy",
}


def _explore_why(cand: Candidate, profile: FarmProfile) -> tuple[str, list[str]]:
    crop = cand.crop
    if crop is None or cand.suit is None:
        return "", []
    months = list(cand.suit.months)
    plant, harvest = MONTH_NAMES[months[0] - 1], MONTH_NAMES[months[-1] - 1]
    local = (f" It is one of the crops widely grown in {_country_text(profile.country)}."
             if profile.local and crop.name in profile.local else "")
    why = (f"{crop.name.capitalize()} suits this field's climate and soil when planted in "
           f"{plant} (harvest around {harvest}).{local}")
    changes = [f"Plant {crop.name} in {plant}"]
    if cand.note:
        why += f" {cand.note.capitalize()} can follow it to cover and feed the soil."
        changes.append(f"Then grow {cand.note} right after the harvest")
    return why, changes + _fill_changes(cand.fills) + _bare_changes(cand.bare)


def _risks_and_questions(cand: Candidate, ctx: FieldContext, catalog: dict[str, CropInfo],
                         profile: FarmProfile) -> tuple[list[str], list[str]]:
    """Risks and questions for the strategy's main crop and every crop it adds, one line per
    kind of risk ("Okra and sweet potato need well-drained soil ...")."""
    placed = []
    if cand.crop is not None and (cand.replaced or cand.key.startswith("explore_")):
        placed.append((cand.crop, cand.suit.months if cand.suit else (), None))
    placed += [(f.crop, tuple(f.slot.months()), f.gap) for f in cand.fills]
    heavy = "clay" in (ctx.texture or "")
    wet, after_paddy, hot, dry, buyers, seeds, unverified = [], False, [], [], [], [], []
    timing: list[tuple[CropInfo, int]] = []
    for crop, months, gap in placed:
        paddy = gap is not None and gap.after is not None and \
            crop_of(gap.after.crop, catalog).waterlogging_tolerance == "high"
        if crop.waterlogging_tolerance == "low" and (heavy or paddy):
            wet.append(crop.name)
            after_paddy = after_paddy or paddy
        if any("heat" in ctx.flags[m - 1] for m in months) and crop.heat_tolerance != "high":
            hot.append(crop.name)
        if gap is not None and crop.cycle_min_days > 0.85 * gap.days:
            timing.append((crop, gap.days))
        if profile.water != "irrigated" and crop.drought_tolerance != "high" and \
                any("dry" in ctx.flags[m - 1] for m in months):
            dry.append(crop.name)
        if not crop.is_cover and (not profile.sellable or crop.name not in profile.sellable):
            buyers.append(crop.name)
        seeds.append(crop.name)
        if not crop.verified:
            unverified.append(crop.name)
    risks, questions = [], []
    if wet:
        where = (f"after paddy rice on {ctx.texture or 'heavy'} soil the field may stay wet"
                 if after_paddy else f"{ctx.texture} soil can stay wet after heavy rain")
        one = len(set(wet)) == 1
        risks.append(f"{_names(wet).capitalize()} need{'s' if one else ''} well-drained soil; "
                     f"{where}")
        questions.append(f"Can the field drain well enough for {_names(wet)}, or should "
                         f"{'it' if one else 'they'} go on raised beds?")
    if hot:
        risks.append(f"Heat of 35 °C+ is common while {_names(hot)} grow"
                     f"{'s' if len(set(hot)) == 1 else ''}")
        questions.append(f"Which {_names(hot)} varieties handle heat above 35 °C here?")
    if any(is_cash_crop(c) for c, _, _ in placed):
        risks.append("Fruit and vegetable prices swing more than grain prices; plan where to "
                     "sell before you plant")
    if buyers:
        questions.append(f"Is there a buyer or local market for {_names(buyers)}?")
    legumes = any(c.is_legume for c, _, _ in placed)
    questions.append(f"Where can I get good {_names(seeds)} seed"
                     + (" and the right inoculant (rhizobia) for the legumes?" if legumes
                        else "?"))
    for crop, days in timing[:1]:
        risks.append(f"Tight timing: {crop.name} needs {crop.cycle_min_days}+ days and the gap "
                     f"is about {days} days")
        questions.append(f"Is there an early-maturing {crop.name} variety (under "
                         f"{days - 10} days)?")
    if dry:
        risks.append(f"{_names(dry).capitalize()} meet{'s' if len(set(dry)) == 1 else ''} a "
                     "dry month without irrigation")
        questions.append("Is there water for one or two irrigations if rains are late?")
    if unverified:
        risks.append(f"Trait data for {_names(unverified)} is not verified yet")
    return risks, questions[:MAX_QUESTIONS]


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


RELAXED_MIN = 0.01  # when no locally grown crop fits well: the best local one, never a stranger


def _unique_windows(years: list[list[Slot]]) -> list[tuple[int, int, int]]:
    """The current rotation's bare windows (start, end, days), each once across years."""
    return list(dict.fromkeys((g.start_month, g.end_month, g.days)
                              for g in gaps(years, MIN_GAP_DAYS) if g.after is not None))


def _country_text(name: str | None) -> str:
    """'the Philippines', 'the United States of America', 'Kenya'."""
    if not name:
        return ""
    plural = name.endswith(("ines", "lands", "ives", "amas")) or name.startswith(("United ",))
    return f"the {name}" if plural or " of " in name else name


def run_engine(ff: FieldFeatures, raw_answers: dict[str, Any] | None,
               catalog: dict[str, CropInfo] | None = None,
               country: str | None = None) -> EngineResult:
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
    profile.country = country
    profile.local = regional.local_crops(country)
    profile.values = regional.crop_values(country)
    ref_crop = regional.reference_value(profile.local, profile.values,
                                        {n for n, c in catalog.items() if not c.is_cover})
    market = None
    if ref_crop and profile.values and country:
        profile.value_ref = profile.values[ref_crop].value_usd_ha
        market = Market(_country_text(country), profile.values, ref_crop)
    weights = weights_for(profile.goals)

    current_years = group_years(profile.slots)
    exploring = not profile.slots  # no crops given: options for the land, no comparison
    current_comps = {} if exploring else score_rotation(
        current_years, ctx, catalog, profile.water, profile.equipment, profile.sellable, market)
    windows = _unique_windows(current_years)

    candidates: list[Candidate] = []
    if exploring:
        candidates = explore(profile, ctx, catalog)
        if not candidates and profile.local:
            candidates = explore(profile, ctx, catalog, min_suit=RELAXED_MIN)
    for build in () if exploring else (fill_bare, break_pest):
        cand = build(profile, current_years, ctx, catalog)
        if cand is None and profile.local:
            cand = build(profile, current_years, ctx, catalog, min_suit=RELAXED_MIN)
        if cand is not None:
            candidates.append(cand)
    avoid = [c.years for c in candidates] + [current_years]
    water_cand = None if exploring else save_water(profile, current_years, ctx, catalog, avoid)
    if water_cand is None and profile.local and not exploring:
        water_cand = save_water(profile, current_years, ctx, catalog, avoid,
                                min_suit=RELAXED_MIN)
    if water_cand is not None:
        candidates.append(water_cand)
    income_cand = None if exploring else add_income(
        profile, current_years, ctx, catalog, [c.years for c in candidates] + [current_years])
    if income_cand is not None:
        candidates.append(income_cand)
    weak = [c for c in candidates if c.suit is not None and c.suit.score < SUITABLE_MIN]

    data_gaps = notes + list(profile.assumptions) + list(ff.gaps) + [
        "Weather comes from a ~55 km NASA POWER grid cell: a regional average, not your field",
        "Soil values are SoilGrids estimates; a soil test would be more accurate",
    ]
    if profile.local is None:
        data_gaps.append("We couldn't tell which country this field is in, so suggestions "
                         "aren't limited to locally grown crops")
    for c in weak:
        place = _country_text(profile.country)
        data_gaps.append(f"Few crops grown in {place} suit this field well; "
                         f"{c.crop.name if c.crop else 'this option'} is the best local fit "
                         "but scored low. Check it with a local expert.")
    if exploring:
        data_gaps.insert(0, "You didn't list crops you grow now, so these are starting options for "
                            "this land, not changes to a current rotation")
    elif len(candidates) < 4:
        missing = {"fill_bare", "break_pest", "save_water", "add_income"} - \
            {c.key for c in candidates}
        if "add_income" in missing:
            missing.discard("add_income")
            data_gaps.append("No fruit or vegetable grown in "
                             f"{_country_text(profile.country) or 'this region'} fits this "
                             "field's bare months, so there is no cash-crop option")
        if missing:
            data_gaps.append("No suitable crop found for: " + ", ".join(sorted(missing)))
    covers = sorted({f.crop.name for c in candidates for f in c.fills if f.crop.is_cover})
    if covers and profile.local is not None:
        data_gaps.append(f"FAO harvest statistics don't count cover crops, so we can't confirm "
                         f"that {' or '.join(covers)} seed is sold near you")
    if market is not None:
        data_gaps.append("Crop values are national averages (FAOSTAT yields and farm-gate "
                         "prices) before costs; your own yields and prices will differ")

    strategies = [] if exploring else [Strategy(
        key="current",
        name=NAMES["current"] if profile.rotation_source != "satellite"
        else "Current pattern (estimated from satellite)",
        title=_title(current_years) or "No crops yet",
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
                               profile.sellable, market)
        risks, questions = _risks_and_questions(cand, ctx, catalog, profile)
        if exploring:
            why, changes = _explore_why(cand, profile)
            benefits = [STRENGTH_TEXT[c] for c in COMPONENTS if comps[c].score >= 70]
            risks += [WEAKNESS_TEXT[c] for c in COMPONENTS if comps[c].score <= 40]
        else:
            why, changes = _why(cand, current_comps, comps, catalog, profile, windows)
            new_inc, old_inc = comps["income"].metrics, current_comps["income"].metrics
            more = [new_inc.get(k, 0) - old_inc.get(k, 0) for k in ("harvests_per_year",
                                                                     "gross_usd_ha")]
            income_up, income_down = any(d > 0 for d in more), all(d <= 0 for d in more) and \
                any(d < 0 for d in more)  # a cover crop isn't a harvest
            benefits = [(_soil_benefit(comps, current_comps) if c == "soil" else BENEFIT_TEXT[c])
                        + f" (+{comps[c].score - current_comps[c].score:.0f})"
                        for c in COMPONENTS if comps[c].score - current_comps[c].score >= 5
                        and (c != "income" or income_up)]
            risks += [TRADEOFF_TEXT[c] + f" ({comps[c].score - current_comps[c].score:.0f})"
                      for c in COMPONENTS if comps[c].score - current_comps[c].score <= -5
                      and (c != "income" or income_down)]
        risks = risks[:MAX_RISKS]
        title = _title(cand.years)
        strategies.append(Strategy(
            key=cand.key, name=NAMES.get(cand.key) or f"Start with {cand.crop.name}",
            title=title,
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
    calendar_bare = [] if exploring else [
        i + 1 for i in range(12) if covers and sum(c[i] for c in covers) / len(covers) < 0.5]
    return EngineResult(
        field={"geom_hash": ff.geom_hash, "lat": ff.lat, "lon": ff.lon,
               "end_month": ff.end_month},
        profile={"mode": profile.mode, "water": profile.water, "equipment": profile.equipment,
                 "goals": profile.goals, "wont_grow": sorted(profile.wont_grow),
                 "rotation_source": profile.rotation_source, "country": profile.country},
        weights=weights,
        bare_months={"satellite": sat_bare, "satellite_evidence": sat_ev,
                     "current_rotation": calendar_bare},
        stress_calendar=calendar,
        strategies=sorted(strategies, key=lambda s: s.rank),
        gaps=data_gaps,
        fruit_ideas=fruit_ideas(profile, ctx, catalog),
    )
