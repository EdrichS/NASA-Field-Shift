"""Candidate rotations: the farmer's current rotation plus 4 alternatives (CLAUDE.md section 6):
(a) fill the bare gaps with legumes or cover crops, (b) break the pest cycle by changing plant
family, (c) swap the thirstiest crop for a less thirsty one, (d) add a cash crop (a fruit or
vegetable) in the bare months.

Every alternative also fills each bare window it can: a field left bare earns nothing and loses
soil. Each fills it in its own way (soil: legumes and cover crops; pest: other plant families;
water: less thirsty crops; income: fruit and vegetables). A window no suitable local crop fits
stays bare, and the strategy says why and what protects the soil instead.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from statistics import fmean

from app.engine.answers import FarmProfile
from app.engine.catalog import CropInfo
from app.engine.regional import familiarity, tracked_crops
from app.engine.rotation import DAYS_PER_MONTH, Gap, Slot, gap_months, gaps
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
SPLIT_MIN_DAYS = 60  # a crop that leaves this much of a window free gets a second crop after it
SHORT_LEGUME_MAX_DAYS = 150  # gap fillers: true cover crops, or legumes that finish this fast
CATEGORY_PENALTY_MECHANIZED = {"vegetables": 0.6, "roots": 0.8}  # odd fits for big machinery
NEIGHBOR_FAMILY = 0.75  # same family right before or after: its pests and diseases carry over
AFTER_PADDY = 0.8  # a crop that needs drained soil, right after flooded rice
MAX_ALTERNATIVES = 3
# Sold fresh although EcoCrop lists them first as pulses (FAOSTAT counts them as vegetables).
FRESH_MARKET = {"string bean"}


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
    rain = _fit(ctx.annual_rain_mm, (eco.get("rain_opt_min_mm"), eco.get("rain_opt_max_mm")),
                (eco.get("rain_abs_min_mm"), eco.get("rain_abs_max_mm")), 0.6)
    wettest = eco.get("rain_opt_max_mm")
    if wettest is None or ctx.annual_rain_mm <= wettest:  # irrigation adds water, can't remove it
        if water == "irrigated":
            rain = 1.0
        elif water == "mixed":
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
    if "fruit" in cat:
        return "fruits"
    if "root" in cat or "tuber" in cat:
        return "roots"
    return "field"


def is_cash_crop(crop: CropInfo) -> bool:
    """A fruit or vegetable for market: usually more money per hectare than grain, but more
    work, more inputs and a less steady price."""
    return not crop.is_cover and (_category(crop) in ("fruits", "vegetables")
                                  or crop.name in FRESH_MARKET)


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
    known, grown there (FAOSTAT). Never a crop the region doesn't know. Cover crops and green
    manures are the exception: FAOSTAT only counts harvested crops, so it never lists them (their
    seed source is a question for the local expert)."""
    crops = [c for c in catalog.values() if c.name not in profile.wont_grow]
    if profile.local is not None:
        untracked = tracked_crops()
        crops = [c for c in crops if c.name in profile.local
                 or (c.is_cover and c.name not in untracked)]
    return sorted(crops, key=lambda c: c.name)


def value_factor(crop: CropInfo, profile: FarmProfile) -> float:
    """1.0 without price data; otherwise grows with the crop's typical gross value per hectare
    (FAOSTAT yield x farm-gate price) relative to the country's main crop."""
    if not profile.values or not profile.value_ref or crop.name not in profile.values:
        return 1.0
    ratio = profile.values[crop.name].value_usd_ha / profile.value_ref
    return 1.0 + 0.5 * math.log2(1.0 + ratio)


def _machinery_factor(crop: CropInfo, profile: FarmProfile) -> float:
    if profile.equipment != "full_machinery":
        return 1.0
    return CATEGORY_PENALTY_MECHANIZED.get(_category(crop), 1.0)


@dataclass(frozen=True)
class Fill:
    """A crop placed in a bare window, and other good local crops for the same window."""
    slot: Slot
    crop: CropInfo
    gap: Gap
    suit: Suitability
    alternatives: tuple[str, ...] = ()


@dataclass(frozen=True)
class BareWindow:
    """A window still bare after filling, with the reason."""
    year: int
    start_month: int
    end_month: int
    days: int
    reason: str


@dataclass
class Candidate:
    key: str
    years: list[list[Slot]]
    crop: CropInfo | None = None
    replaced: str | None = None
    gap: Gap | None = None
    suit: Suitability | None = None
    note: str = ""
    fills: list[Fill] = field(default_factory=list)
    bare: list[BareWindow] = field(default_factory=list)


def _copy(years: list[list[Slot]]) -> list[list[Slot]]:
    return [list(y) for y in years]


def _family(name: str | None, catalog: dict[str, CropInfo]) -> str | None:
    return crop_of(name, catalog).family if name else None


def _eligible(crop: CropInfo, theme: str, avoid_families: set[str]) -> bool:
    """The crops a strategy prefers in a bare window (its own way of filling it)."""
    if theme == "soil":
        return crop.is_cover or (crop.is_legume and crop.cycle_max_days <= SHORT_LEGUME_MAX_DAYS)
    if theme == "pest":
        return crop.family not in avoid_families
    if theme == "water":
        return crop.water_need != "high"
    if theme == "income":
        return is_cash_crop(crop)
    return True


def _slot_in(crop: CropInfo, gap: Gap, start: int, ctx: FieldContext) -> Slot:
    """The crop's slot from `start`: the whole rest of the window for a crop about as long as
    the window, or a cover crop that rests through frost until the next planting (winter rye);
    else its typical length (a cover crop: its longest season), leaving room for another."""
    left_days = ((gap.end_month - start) % 12 or 12) * DAYS_PER_MONTH
    typical = (crop.cycle_min_days + crop.cycle_max_days) / 2
    if crop.is_cover:
        whole = Slot(crop.name, start, gap.end_month, new=True)
        if any("frost" in ctx.flags[m - 1] for m in whole.months()):
            return whole
        typical = crop.cycle_max_days
    if left_days <= typical + MIN_GAP_DAYS:
        return Slot(crop.name, start, gap.end_month, new=True)
    months = max(1, math.ceil(typical / DAYS_PER_MONTH))
    return Slot(crop.name, start, (start + months - 1) % 12 + 1, new=True)


def growing_days(crop: CropInfo, slot: Slot, ctx: FieldContext) -> float:
    """Days in the slot when the crop can grow: frost months are only rest (a winter cover crop
    rests through them; a grain sown before winter is not ready by spring)."""
    return sum(share * DAYS_PER_MONTH for m, share in slot.occupancy().items()
               if "frost" not in ctx.flags[m - 1])


def _fill_value(crop: CropInfo, slot: Slot, suit: Suitability, gap: Gap, theme: str,
                profile: FarmProfile, ctx: FieldContext, catalog: dict[str, CropInfo],
                neighbors: set[str], avoid_families: set[str]) -> float:
    thirst = min(0.5, water_deficit_mm([slot], ctx, catalog) / 1000)
    value = (suit.score * goal_factor(crop, profile)
             * stress_factor(crop, slot.months(), ctx, profile.water) * (1 - thirst)
             * _machinery_factor(crop, profile) * familiarity(crop.name, profile.local)
             * (0.6 + 0.4 * min(1.0, slot.days / gap.days)))
    if crop.family in neighbors:
        value *= NEIGHBOR_FAMILY
    if gap.after is not None and crop.waterlogging_tolerance == "low" and \
            crop_of(gap.after.crop, catalog).waterlogging_tolerance == "high":
        value *= AFTER_PADDY
    if theme == "soil":
        value *= (1 + 0.3 * crop.is_legume) * (1 + 0.15 * crop.is_cover)
    elif theme == "pest" and crop.family in avoid_families:
        value *= 0.4
    elif theme == "water":
        value *= (1 - thirst) * (1 + 0.3 * TOLERANCE[crop.drought_tolerance])
    elif theme == "income":
        value *= value_factor(crop, profile)
    return value


def _best_fill(gap: Gap, start: int, theme: str, profile: FarmProfile, ctx: FieldContext,
               catalog: dict[str, CropInfo], avoid_families: set[str], strict: bool,
               water_budget: float | None = None
               ) -> tuple[Slot, CropInfo, Suitability, tuple[str, ...]] | None:
    left_days = ((gap.end_month - start) % 12 or 12) * DAYS_PER_MONTH
    neighbors = {f for f in (_family(gap.after.crop if gap.after else None, catalog),
                             _family(gap.before.crop if gap.before else None, catalog)) if f}
    scored = []
    for crop in _pool(profile, catalog):
        if crop.cycle_min_days > left_days:
            continue
        if strict and not _eligible(crop, theme, avoid_families):
            continue
        if gap.after is not None and crop.name == gap.after.crop:
            continue  # the same crop again right after its own harvest
        slot = _slot_in(crop, gap, start, ctx)
        if not crop.is_cover and growing_days(crop, slot, ctx) < crop.cycle_min_days:
            continue
        if water_budget is not None and water_deficit_mm([slot], ctx, catalog) > water_budget:
            continue
        suit = suitability(crop, slot.months(), ctx, profile.water)
        if suit.score < SUITABLE_MIN:
            continue
        value = _fill_value(crop, slot, suit, gap, theme, profile, ctx, catalog, neighbors,
                            avoid_families)
        scored.append(((round(value, 4), crop.name), slot, crop, suit))
    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    _, slot, crop, suit = scored[0]
    others = tuple(c.name for _, _, c, _ in scored[1:1 + MAX_ALTERNATIVES])
    return slot, crop, suit, others


def _bare_reason(months: list[int], days: int, ctx: FieldContext, water: str) -> str:
    flags = set().union(*(ctx.flags[m - 1] for m in months)) if months else set()
    if "frost" in flags:
        return "frost months: no locally grown crop survives them"
    if "dry" in flags and water != "irrigated":
        return "too dry for a crop without irrigation"
    return f"no locally grown crop fits a {days}-day window here"


def fill_gaps(profile: FarmProfile, years: list[list[Slot]], ctx: FieldContext,
              catalog: dict[str, CropInfo], theme: str,
              avoid_families: set[str] | None = None,
              water_budget: float | None = None) -> tuple[list[list[Slot]], list[Fill],
                                                          list[BareWindow]]:
    """Fill every bare window of at least MIN_GAP_DAYS: the strategy's preferred crops first,
    then any suitable local crop (covered soil beats bare soil). A long window can take two
    crops. Windows nothing fits are returned with the reason. With a water budget (mm/year
    beyond rain, per rotation year), the added crops together never need more than that."""
    avoid = avoid_families or set()
    budget = None if water_budget is None else water_budget * len(years)
    new_years, fills, bare = _copy(years), [], []
    for gap in gaps(years, MIN_GAP_DAYS):
        if gap.after is None:
            continue  # an empty year: handled by the strategies that start from nothing
        start, after = gap.start_month, gap.after
        for _ in range(3):  # at most three crops per window
            left = Gap(gap.year, after, gap.before, start, gap.end_month,
                       ((gap.end_month - start) % 12 or 12) * DAYS_PER_MONTH)
            if left.days < MIN_GAP_DAYS:
                break
            pick = (_best_fill(left, start, theme, profile, ctx, catalog, avoid, True, budget)
                    or _best_fill(left, start, theme, profile, ctx, catalog, avoid, False,
                                  budget))
            if pick is None:
                limited = budget is not None and _best_fill(
                    left, start, theme, profile, ctx, catalog, avoid, False) is not None
                reason = ("left bare to save water: every local crop that fits would need "
                          "more irrigation than this option saves" if limited else
                          _bare_reason(gap_months(left), left.days, ctx, profile.water))
                bare.append(BareWindow(gap.year, start, gap.end_month, left.days, reason))
                break
            slot, crop, suit, others = pick
            if budget is not None:
                budget -= water_deficit_mm([slot], ctx, catalog)
            new_years[gap.year].append(slot)
            fills.append(Fill(slot, crop, left, suit, others))
            remaining = ((gap.end_month - slot.harvest_month) % 12) * DAYS_PER_MONTH
            if remaining < SPLIT_MIN_DAYS:  # a short tail is land preparation time
                break
            start, after = slot.harvest_month, slot
    return new_years, fills, bare


def _start_from_nothing(profile: FarmProfile, years: list[list[Slot]], ctx: FieldContext,
                        catalog: dict[str, CropInfo], theme: str,
                        min_suit: float) -> tuple[list[list[Slot]], Fill] | None:
    """No crops yet: the best crop of the strategy's kind and its best start month."""
    best = None
    for crop in _pool(profile, catalog):
        if not _eligible(crop, theme, set()):
            continue
        for start in range(1, 13):
            months = [(start + k - 1) % 12 + 1 for k in range(crop.cycle_months + 1)]
            suit = suitability(crop, months, ctx, profile.water)
            if suit.score < min_suit:
                continue
            slot = Slot(crop.name, months[0], months[-1], new=True)
            thirst = min(0.5, water_deficit_mm([slot], ctx, catalog) / 1000)
            value = (suit.score * (1 + 0.3 * crop.is_legume * (theme == "soil"))
                     * goal_factor(crop, profile) * stress_factor(crop, months, ctx,
                                                                 profile.water)
                     * (1 - thirst) * _machinery_factor(crop, profile)
                     * familiarity(crop.name, profile.local)
                     * (value_factor(crop, profile) if theme == "income" else 1.0))
            key = (round(value, 4), crop.name, -start)
            if best is None or key > best[0]:
                best = (key, slot, crop, suit)
    if best is None:
        return None
    _, slot, crop, suit = best
    new_years = _copy(years)
    new_years[0].append(slot)
    gap = Gap(0, None, None, slot.plant_month, slot.harvest_month, slot.days)
    return new_years, Fill(slot, crop, gap, suit)


def _main_fill(fills: list[Fill], prefer=None) -> Fill | None:
    """The fill a strategy is named after: its preferred kind of crop, in the longest window."""
    chosen = [f for f in fills if prefer is None or prefer(f.crop)] or fills
    return max(chosen, key=lambda f: (f.gap.days, f.slot.days, f.crop.name), default=None)


def fill_bare(profile: FarmProfile, years: list[list[Slot]], ctx: FieldContext,
              catalog: dict[str, CropInfo], min_suit: float = SUITABLE_MIN) -> Candidate | None:
    if all(not y for y in years):
        start = _start_from_nothing(profile, years, ctx, catalog, "soil", min_suit)
        if start is None:
            return None
        years, first = start
        new_years, fills, bare = fill_gaps(profile, years, ctx, catalog, "soil")
        fills = [first, *fills]
    else:
        new_years, fills, bare = fill_gaps(profile, years, ctx, catalog, "soil")
    if not fills:
        return None
    main = _main_fill(fills, lambda c: c.is_legume or c.is_cover)
    return Candidate("fill_bare", new_years, main.crop, None, main.gap, main.suit,
                     fills=fills, bare=bare)


EXPLORE_OPTIONS = 3


def explore(profile: FarmProfile, ctx: FieldContext, catalog: dict[str, CropInfo],
            min_suit: float = SUITABLE_MIN) -> list[Candidate]:
    """No current rotation: the best main crops for this land (locally grown, best planting
    month), each followed by a short legume or cover crop when one fits, and the rest of the
    year filled like any bare window. Different plant families first, so the options differ."""
    scored = []
    for crop in _pool(profile, catalog):
        if crop.is_cover:
            continue
        best = None
        for start in range(1, 13):
            months = [(start + k - 1) % 12 + 1 for k in range(crop.cycle_months + 1)]
            suit = suitability(crop, months, ctx, profile.water)
            if suit.score < min_suit:
                continue
            value = (suit.score * goal_factor(crop, profile)
                     * stress_factor(crop, months, ctx, profile.water)
                     * _machinery_factor(crop, profile) * familiarity(crop.name, profile.local))
            if best is None or value > best[0]:
                best = (value, months, suit)
        if best is not None:
            scored.append((round(best[0], 4), crop.name, crop, best[1], best[2]))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    picked, families = [], set()
    for item in scored:  # one per family first
        if item[2].family not in families:
            picked.append(item)
            families.add(item[2].family)
        if len(picked) == EXPLORE_OPTIONS:
            break
    for item in scored:
        if len(picked) == EXPLORE_OPTIONS:
            break
        if item not in picked:
            picked.append(item)
    out = []
    for i, (_, _, crop, months, suit) in enumerate(picked, start=1):
        main = Slot(crop.name, months[0], months[-1], new=True)
        follow = _follow_up(profile, ctx, catalog, crop, months[-1])
        # the rest of the year: filled like any other bare window, or left bare with the reason
        years, fills, bare = fill_gaps(profile, [[main] + ([follow] if follow else [])], ctx,
                                       catalog, "soil")
        out.append(Candidate(f"explore_{i}", years, crop, None, None, suit,
                             note=follow.crop if follow else "", fills=fills, bare=bare))
    return out


def _follow_up(profile: FarmProfile, ctx: FieldContext, catalog: dict[str, CropInfo],
               main: CropInfo, harvest_month: int) -> Slot | None:
    """A short legume or cover crop right after the main harvest, for its own season length
    (fill_gaps then fills what is left of the year, or says why it stays bare)."""
    best = None
    for crop in _pool(profile, catalog):
        short_legume = crop.is_legume and crop.cycle_max_days <= SHORT_LEGUME_MAX_DAYS
        if crop.name == main.name or not (crop.is_cover or short_legume):
            continue
        months = [(harvest_month + k - 1) % 12 + 1 for k in range(crop.cycle_months + 1)]
        suit = suitability(crop, months, ctx, profile.water)
        if suit.score < SUITABLE_MIN:
            continue
        value = (suit.score * (1 + 0.3 * crop.is_legume) * goal_factor(crop, profile)
                 * familiarity(crop.name, profile.local))
        if best is None or (round(value, 4), crop.name) > best[0]:
            best = ((round(value, 4), crop.name), Slot(crop.name, months[0], months[-1], new=True))
    return best[1] if best else None


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
    new_years, fills, bare = fill_gaps(profile, _replace(years, slot, crop), ctx, catalog,
                                       "pest", avoid_families={common})
    return Candidate("break_pest", new_years, crop, slot.crop, None, suit,
                     note=f"{common} family grown {families[common]} time(s)", fills=fills,
                     bare=bare)


def save_water(profile: FarmProfile, years: list[list[Slot]], ctx: FieldContext,
               catalog: dict[str, CropInfo], avoid: list[list[list[Slot]]],
               min_suit: float = SUITABLE_MIN) -> Candidate | None:
    slots = [s for y in years for s in y]
    if not slots:
        return None
    # the crop that needs the most water beyond rain here (dry-season rice, not wet-season)
    target = max(slots, key=lambda s: (round(water_deficit_mm([s], ctx, catalog)),
                                       water_demand_factor(crop_of(s.crop, catalog)), s.days,
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
    current_deficit = sum(water_deficit_mm(y, ctx, catalog) for y in years) / len(years)
    for _, crop, suit in sorted(options, key=lambda o: o[0], reverse=True):
        swapped = _replace(years, target, crop)
        saved = current_deficit - sum(water_deficit_mm(y, ctx, catalog)
                                      for y in swapped) / len(swapped)
        # the crops added to bare windows may use up to half the water the swap saves
        new_years, fills, bare = fill_gaps(profile, swapped, ctx, catalog, "water",
                                           water_budget=max(0.0, saved / 2))
        if new_years not in avoid:
            return Candidate("save_water", new_years, crop, target.crop, None, suit,
                             fills=fills, bare=bare)
    return None


def add_income(profile: FarmProfile, years: list[list[Slot]], ctx: FieldContext,
               catalog: dict[str, CropInfo], avoid: list[list[list[Slot]]],
               min_suit: float = SUITABLE_MIN) -> Candidate | None:
    """A fruit or vegetable for market in the bare months (or, when the field is never bare, in
    place of one crop of the most repeated kind)."""
    if all(not y for y in years):
        start = _start_from_nothing(profile, years, ctx, catalog, "income", min_suit)
        if start is None:
            return None
        base, first = start
        new_years, fills, bare = fill_gaps(profile, base, ctx, catalog, "income")
        fills = [first, *fills]
    else:
        new_years, fills, bare = fill_gaps(profile, years, ctx, catalog, "income")
    cash = [f for f in fills if is_cash_crop(f.crop)]
    if cash and new_years not in avoid:
        main = _main_fill(cash)
        return Candidate("add_income", new_years, main.crop, None, main.gap, main.suit,
                         fills=fills, bare=bare)
    slots = [s for y in years for s in y]
    if not slots or profile.equipment == "full_machinery":
        return None  # a whole machine-farmed field of vegetables needs a market few places have
    common = Counter(s.crop for s in slots).most_common(1)[0][0]
    best = None
    for slot in (s for s in slots if s.crop == common):
        for crop in _pool(profile, catalog):
            if not is_cash_crop(crop) or crop.cycle_min_days > slot.days + 15:
                continue
            suit = suitability(crop, slot.months(), ctx, profile.water)
            if suit.score < min_suit:
                continue
            value = (suit.score * value_factor(crop, profile) * goal_factor(crop, profile)
                     * stress_factor(crop, slot.months(), ctx, profile.water)
                     * _machinery_factor(crop, profile) * familiarity(crop.name, profile.local))
            key = (round(value, 4), crop.name)
            if best is None or key > best[0]:
                best = (key, slot, crop, suit)
    if best is None:
        return None
    _, slot, crop, suit = best
    new_years, fills, bare = fill_gaps(profile, _replace(years, slot, crop), ctx, catalog,
                                       "income")
    if new_years in avoid:
        return None
    return Candidate("add_income", new_years, crop, slot.crop, None, suit, fills=fills,
                     bare=bare)
