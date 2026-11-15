"""Candidate rotations: the farmer's current rotation plus 3 alternatives (CLAUDE.md section 6):
(a) fill a bare gap with a legume or cover crop, (b) break the pest cycle by changing plant
family, (c) swap the thirstiest crop for a less thirsty one.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from statistics import fmean

from app.engine.answers import FarmProfile
from app.engine.catalog import CropInfo
from app.engine.regional import familiarity
from app.engine.rotation import Gap, Slot, gap_months, gaps
from app.engine.scoring import (
    TOLERANCE,
    FieldContext,
    crop_of,
    survives_frost,
    water_deficit_mm,
    water_demand_factor,
)

SUITABLE_MIN = 0.6
MIN_GAP_DAYS = 45
SHORT_LEGUME_MAX_DAYS = 150  # gap fillers: true cover crops, or legumes that finish this fast
CATEGORY_PENALTY_MECHANIZED = {"vegetables": 0.6, "roots": 0.8}  # odd fits for big machinery


@dataclass(frozen=True)
class Suitability:
    score: float
    temp: float
    rain: float
    ph: float
    months: tuple[int, ...]


def _fit(value: float | None, opt: tuple, absolute: tuple, default: float) -> float:
    if value is None or None in opt:
        return default
    if opt[0] <= value <= opt[1]:
        return 1.0
    lo, hi = absolute
    if (lo is None or lo <= value) and (hi is None or value <= hi):
        return 0.5
    return 0.1


def suitability(crop: CropInfo, months: list[int], ctx: FieldContext, water: str) -> Suitability:
    eco = crop.eco
    omin, omax = eco.get("temp_opt_min_c"), eco.get("temp_opt_max_c")
    amin, amax = eco.get("temp_abs_min_c"), eco.get("temp_abs_max_c")
    rest = eco.get("killing_temp_rest_c")
    per_month = []
    for m in months:
        t = ctx.t_mean[m - 1]
        if "frost" in ctx.flags[m - 1] and not survives_frost(crop, t, ctx.t_cold[m - 1]):
            per_month.append(0.0)
        elif omin is None or omax is None:
            per_month.append(0.6)
        elif omin <= t <= omax:
            per_month.append(1.0)
        elif (amin is None or amin <= t) and (amax is None or t <= amax):
            per_month.append(0.5)
        elif rest is not None and amin is not None and rest <= t < amin:
            per_month.append(0.5)  # dormant through the cold months
        else:
            per_month.append(0.0)
    temp = fmean(per_month) if per_month else 0.0
    if water == "irrigated":
        rain = 1.0
    else:
        rain = _fit(ctx.annual_rain_mm, (eco.get("rain_opt_min_mm"), eco.get("rain_opt_max_mm")),
                    (eco.get("rain_abs_min_mm"), eco.get("rain_abs_max_mm")), 0.6)
        if water == "mixed":
            rain = max(0.75, rain)
    ph = _fit(ctx.soil_ph, (eco.get("ph_opt_min"), eco.get("ph_opt_max")),
              (eco.get("ph_abs_min"), eco.get("ph_abs_max")), 0.8)
    score = 0.0 if any(s == 0 for s in per_month) else round(0.5 * temp + 0.3 * rain + 0.2 * ph, 3)
    return Suitability(score, round(temp, 3), round(rain, 3), round(ph, 3), tuple(months))


def _category(crop: CropInfo) -> str:
    """EcoCrop's first listed category (canola lists forage first, vegetables second)."""
    cat = (crop.eco.get("category") or "").lower().split(",")[0]
    if "vegetable" in cat:
        return "vegetables"
    if "root" in cat or "tuber" in cat:
        return "roots"
    return "field"


def stress_factor(crop: CropInfo, months: list[int] | tuple[int, ...], ctx: FieldContext,
                  water: str) -> float:
    """Down-weight crops placed in months they handle badly (heat, very wet, dry)."""
    penalty = 0.0
    for m in months:
        f = ctx.flags[m - 1]
        if "heat" in f:
            penalty += 1 - TOLERANCE[crop.heat_tolerance]
        if "very_wet" in f:
            penalty += 1 - TOLERANCE[crop.waterlogging_tolerance]
        if "dry" in f and water != "irrigated":
            penalty += 1 - TOLERANCE[crop.drought_tolerance]
    return max(0.3, 1 - 0.12 * penalty)


def goal_factor(crop: CropInfo, profile: FarmProfile) -> float:
    """The farmer's goals shape which crop is proposed, not only how strategies are ranked."""
    factor = 1.0
    if {"earn_more", "feed_household"} & set(profile.goals) and not crop.is_cover:
        factor += 0.3  # something to sell or eat
    if "build_soil" in profile.goals and (crop.cover_crop_role == "green_manure"
                                          or crop.is_legume):
        factor += 0.2
    if {"save_water", "survive_bad_years"} & set(profile.goals):
        factor += 0.2 * TOLERANCE[crop.drought_tolerance]
    return factor


def _pool(profile: FarmProfile, catalog: dict[str, CropInfo]) -> list[CropInfo]:
    """Crops we may suggest: not on the farmer's won't-grow list and, when the country is
    known, grown there (FAOSTAT). Never a crop the region doesn't know."""
    crops = [c for c in catalog.values() if c.name not in profile.wont_grow]
    if profile.local is not None:
        crops = [c for c in crops if c.name in profile.local]
    return sorted(crops, key=lambda c: c.name)


def _machinery_factor(crop: CropInfo, profile: FarmProfile) -> float:
    if profile.equipment != "full_machinery":
        return 1.0
    return CATEGORY_PENALTY_MECHANIZED.get(_category(crop), 1.0)


@dataclass
class Candidate:
    key: str
    years: list[list[Slot]]
    crop: CropInfo | None = None
    replaced: str | None = None
    gap: Gap | None = None
    suit: Suitability | None = None
    note: str = ""


def _copy(years: list[list[Slot]]) -> list[list[Slot]]:
    return [list(y) for y in years]


def fill_bare(profile: FarmProfile, years: list[list[Slot]], ctx: FieldContext,
              catalog: dict[str, CropInfo], min_suit: float = SUITABLE_MIN) -> Candidate | None:
    best = None
    for gap in gaps(years, MIN_GAP_DAYS):
        for crop in _pool(profile, catalog):
            short_legume = crop.is_legume and crop.cycle_max_days <= SHORT_LEGUME_MAX_DAYS
            if not (crop.is_cover or short_legume) or crop.cycle_min_days > gap.days:
                continue
            if gap.after is None:  # nothing grown yet: try every start month
                options = [[(start + k - 1) % 12 + 1 for k in range(crop.cycle_months + 1)]
                           for start in range(1, 13)]
            else:
                options = [gap_months(gap)]
            for months in options:
                suit = suitability(crop, months, ctx, profile.water)
                if suit.score < min_suit:
                    continue
                trial = Slot(crop.name, months[0], months[-1])
                thirst = min(0.5, water_deficit_mm([trial], ctx, catalog) / 1000)
                value = (suit.score * (1 + 0.3 * crop.is_legume) * goal_factor(crop, profile)
                         * stress_factor(crop, months, ctx, profile.water) * (1 - thirst)
                         * (1 + gap.days / 720) * _machinery_factor(crop, profile)
                         * familiarity(crop.name, profile.local))
                key = (round(value, 4), crop.name)
                if best is None or key > best[0]:
                    best = (key, gap, crop, suit)
    if best is None:
        return None
    _, gap, crop, suit = best
    new_years = _copy(years)
    if gap.after is None:
        months = list(suit.months)
        new_years[gap.year].append(Slot(crop.name, months[0], months[-1], new=True))
    else:
        for y, year in enumerate(new_years):  # same gap in every rotation year
            if any(g.year == y and g.start_month == gap.start_month
                   and g.end_month == gap.end_month for g in gaps(years, MIN_GAP_DAYS)):
                year.append(Slot(crop.name, gap.start_month, gap.end_month, new=True))
    return Candidate("fill_bare", new_years, crop, None, gap, suit)


def _replace(years: list[list[Slot]], old: Slot, crop: CropInfo) -> list[list[Slot]]:
    new_years = _copy(years)
    for year in new_years:
        for i, slot in enumerate(year):
            if slot == old:
                year[i] = Slot(crop.name, old.plant_month, old.harvest_month, new=True)
                return new_years
    return new_years


def break_pest(profile: FarmProfile, years: list[list[Slot]], ctx: FieldContext,
               catalog: dict[str, CropInfo], min_suit: float = SUITABLE_MIN) -> Candidate | None:
    slots = [s for y in years for s in y]
    if not slots:
        return None
    families = Counter(crop_of(s.crop, catalog).family for s in slots)
    known = Counter({f: n for f, n in families.items() if f != "unknown"})
    if not known:  # crops we have no family for: no honest pest-cycle advice
        return None
    common = known.most_common(1)[0][0]
    best = None
    for slot in (s for s in slots if crop_of(s.crop, catalog).family == common):
        for crop in _pool(profile, catalog):
            if crop.family in families or crop.is_cover or crop.cycle_min_days > slot.days + 15:
                continue
            suit = suitability(crop, slot.months(), ctx, profile.water)
            if suit.score < min_suit:
                continue
            value = (suit.score * (1 + 0.2 * crop.is_legume) * goal_factor(crop, profile)
                     * stress_factor(crop, slot.months(), ctx, profile.water)
                     * _machinery_factor(crop, profile) * familiarity(crop.name, profile.local))
            key = (round(value, 4), crop.name)
            if best is None or key > best[0]:
                best = (key, slot, crop, suit)
    if best is None:
        return None
    _, slot, crop, suit = best
    return Candidate("break_pest", _replace(years, slot, crop), crop, slot.crop, None, suit,
                     note=f"{common} family grown {families[common]} time(s)")


def save_water(profile: FarmProfile, years: list[list[Slot]], ctx: FieldContext,
               catalog: dict[str, CropInfo], avoid: list[list[list[Slot]]],
               min_suit: float = SUITABLE_MIN) -> Candidate | None:
    slots = [s for y in years for s in y]
    if not slots:
        return None
    target = max(slots, key=lambda s: (water_demand_factor(crop_of(s.crop, catalog)), s.days,
                                       s.plant_month))
    old = crop_of(target.crop, catalog)
    old_factor, old_deficit = water_demand_factor(old), water_deficit_mm([target], ctx, catalog)
    options = []
    for crop in _pool(profile, catalog):
        if crop.name == old.name or crop.is_cover or crop.cycle_min_days > target.days + 15:
            continue
        factor = water_demand_factor(crop)
        drier = TOLERANCE[crop.drought_tolerance] > TOLERANCE[old.drought_tolerance]
        if not (factor < old_factor or (factor == old_factor and drier)):
            continue
        suit = suitability(crop, target.months(), ctx, profile.water)
        if suit.score < min_suit:
            continue
        new_slot = Slot(crop.name, target.plant_month, target.harvest_month)
        saving = old_deficit - water_deficit_mm([new_slot], ctx, catalog)
        if saving <= 0 and not drier:
            continue
        value = (suit.score * (1 + max(saving, 0) / 500) * (1 + 0.1 * crop.is_legume)
                 * goal_factor(crop, profile)
                 * stress_factor(crop, target.months(), ctx, profile.water)
                 * _machinery_factor(crop, profile) * familiarity(crop.name, profile.local))
        options.append(((round(value, 4), crop.name), crop, suit))
    for _, crop, suit in sorted(options, key=lambda o: o[0], reverse=True):
        new_years = _replace(years, target, crop)
        if new_years not in avoid:
            return Candidate("save_water", new_years, crop, target.crop, None, suit)
    return None
