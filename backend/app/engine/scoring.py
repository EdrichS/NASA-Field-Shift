"""Score a rotation on 7 components (0-100, higher is better) with evidence, then weight them by
the farmer's goals (CLAUDE.md section 6). Every rule and constant is stated here so it can be
explained in the report and challenged by a local expert.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.engine.catalog import UNKNOWN_CROP, CropInfo
from app.engine.evidence import Evidence, from_crop, from_feature
from app.engine.rotation import Slot, bare_by_month
from app.features.harmonize import MONTH_NAMES, FieldFeatures

DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)
COMPONENTS = ("water", "soil", "erosion", "pest_cycle", "climate_risk", "income", "labor")

# Goal -> component weights (each row sums to 1).
GOAL_WEIGHTS = {
    "save_water":        {"water": .35, "climate_risk": .15, "soil": .10, "erosion": .10,
                          "pest_cycle": .10, "income": .10, "labor": .10},
    "build_soil":        {"soil": .35, "erosion": .20, "pest_cycle": .15, "water": .10,
                          "climate_risk": .10, "income": .05, "labor": .05},
    "earn_more":         {"income": .35, "climate_risk": .15, "labor": .15, "water": .10,
                          "soil": .10, "pest_cycle": .10, "erosion": .05},
    "feed_household":    {"income": .25, "climate_risk": .20, "labor": .15, "water": .15,
                          "soil": .10, "pest_cycle": .10, "erosion": .05},
    "survive_bad_years": {"climate_risk": .35, "water": .20, "soil": .15, "erosion": .10,
                          "pest_cycle": .10, "income": .05, "labor": .05},
}
RANK_SHARES = (0.5, 0.3, 0.2)  # how ranked goals combine

# Relative crop water demand vs reference evapotranspiration (SowSmart assumption from the FAO
# water-need classes; paddy rice also loses water to percolation and its standing water layer).
WATER_FACTOR = {"low": 0.7, "medium": 0.95, "high": 1.15}
PADDY_FACTOR = 1.4
EFFECTIVE_RAIN = 0.8  # share of rain plants can use (FAO effective-rainfall idea)
DEFICIT_FOR_ZERO = 1200  # mm/year beyond rain that scores 0
TOLERANCE = {"low": 0.0, "medium": 0.5, "high": 0.85, None: 0.5}
LABOR_POINTS = {"low": 1, "medium": 2, "high": 3, None: 2}
EQUIPMENT_FACTOR = {"hand_tools": 1.0, "animal": 0.9, "small_tractor": 0.7,
                    "full_machinery": 0.4}


@dataclass
class FieldContext:
    ff: FieldFeatures
    rain: list[float]
    t_mean: list[float]
    t_cold: list[float | None]  # typical coldest hour of each month
    et0: list[float]
    flags: list[set[str]]
    stress_evidence: list[list[Evidence]]
    slope_deg: float | None
    soil_ph: float | None
    texture: str | None
    annual_rain_mm: float

    @classmethod
    def build(cls, ff: FieldFeatures, calendar: list[dict[str, Any]]) -> FieldContext:
        flags = [set(m["flags"]) for m in calendar]
        stress_evidence = [list(m["evidence"]) for m in calendar]
        rain_f, temp_f, solar_f = (ff.features.get(k) for k in ("rain", "t_mean", "solar"))
        if rain_f is None or temp_f is None:
            raise ValueError("NASA POWER weather is required to score rotations")
        rain = [v or 0.0 for v in rain_f.normal]
        t_mean = [v if v is not None else 20.0 for v in temp_f.normal]
        solar = [v or 18.0 for v in (solar_f.normal if solar_f else [None] * 12)]
        # Hargreaves (1975) radiation method: ET0 = 0.0135 (T + 17.8) Rs, Rs in mm/day.
        et0 = [round(max(0.0, 0.0135 * (t + 17.8) * s * 0.408), 2) for t, s in
               zip(t_mean, solar, strict=True)]
        terrain, soil = ff.static.get("terrain") or {}, ff.static.get("soil") or {}
        cold_f = ff.features.get("t_coldest")
        t_cold = list(cold_f.normal) if cold_f else [None] * 12
        return cls(ff, rain, t_mean, t_cold, et0, flags, stress_evidence, terrain.get("slope_deg"),
                   soil.get("ph"), soil.get("texture"),
                   sum(r * d for r, d in zip(rain, DAYS, strict=True)))


@dataclass
class ComponentScore:
    score: float
    summary: str
    evidence: list[Evidence] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


def _clamp(x: float) -> float:
    return round(max(0.0, min(100.0, x)), 1)


def crop_of(name: str, catalog: dict[str, CropInfo]) -> CropInfo:
    return catalog.get(name, UNKNOWN_CROP)


def water_demand_factor(crop: CropInfo) -> float:
    return PADDY_FACTOR if crop.name == "rice" else WATER_FACTOR.get(crop.water_need or "", 0.95)


def water_deficit_mm(year: list[Slot], ctx: FieldContext, catalog: dict[str, CropInfo]) -> float:
    total = 0.0
    for slot in year:
        factor = water_demand_factor(crop_of(slot.crop, catalog))
        for m, share in slot.occupancy().items():
            i = m - 1
            need = factor * ctx.et0[i] - EFFECTIVE_RAIN * ctx.rain[i]
            total += max(0.0, need) * DAYS[i] * share
    return total


def score_rotation(years: list[list[Slot]], ctx: FieldContext, catalog: dict[str, CropInfo],
                   water: str, equipment: str, sellable: set[str]) -> dict[str, ComponentScore]:
    rain_f = ctx.ff.features["rain"]
    slots = [s for y in years for s in y]
    n_years = len(years)
    crops = {s.crop: crop_of(s.crop, catalog) for s in slots}

    # 1. Water: water needed beyond effective rain (irrigation if irrigated, stress if rain-fed)
    deficit = sum(water_deficit_mm(y, ctx, catalog) for y in years) / n_years
    water_score = _clamp(100 * (1 - deficit / DEFICIT_FOR_ZERO))
    water_ev = [
        from_feature(rain_f, "Yearly rainfall (30-year normal)", round(ctx.annual_rain_mm),
                     "mm/year"),
        Evidence("Crop water need beyond rain, per year (Hargreaves ET0 from POWER temperature "
                 "and sunlight x crop factor - 80% of rain)", round(deficit), "mm/year",
                 f"{rain_f.source} + crop traits", rain_f.native_resolution,
                 rain_f.normal_period, "low"),
    ]
    water_ev += [from_crop(c, f"{c.name} water need", c.water_need) for c in crops.values()]
    what = "irrigation" if water == "irrigated" else "water stress"
    water_c = ComponentScore(water_score, f"About {round(deficit)} mm/year of {what} beyond "
                             "rainfall", water_ev, {"deficit_mm": round(deficit)})

    # 2. Soil building: cover, legumes, root depth, cover crops
    bare = bare_by_month(years)
    cover = 1 - sum(bare) / 12
    crop_months = [(crops[s.crop], sum(s.occupancy().values())) for s in slots]
    total_months = sum(m for _, m in crop_months) or 1
    legume_share = sum(m for c, m in crop_months if c.is_legume) / total_months
    roots = [c.root_depth_m or 0.8 for c, _ in crop_months]
    root = min(1.0, (sum(roots) / len(roots) if roots else 0) / 1.5)
    has_cover = any(c.is_cover for c in crops.values())
    soil_score = _clamp(100 * (0.4 * cover + 0.3 * min(1, legume_share * 2) + 0.2 * root
                               + 0.1 * has_cover))
    soil_ev = [Evidence("Share of the year the soil is covered by a crop", round(cover, 2),
                        "fraction", "Farmer's crop calendar + strategy", "field", "", "medium")]
    soil_ev += [from_crop(c, f"{c.name} is a legume (adds nitrogen)", c.is_legume)
                for c in crops.values() if c.is_legume]
    soil_ev += [from_crop(c, f"{c.name} root depth", c.root_depth_m, "m") for c in crops.values()]
    soil_c = ComponentScore(soil_score, f"Soil covered {cover:.0%} of the year; legumes "
                            f"{legume_share:.0%} of crop time", soil_ev,
                            {"cover": round(cover, 2), "legume_share": round(legume_share, 2)})

    # 3. Erosion: bare months x rain x slope
    slope = ctx.slope_deg if ctx.slope_deg is not None else 3.0
    slope_factor = max(0.3, min(3.0, slope / 3))
    weighted_bare = sum(b * (0.5 + ctx.rain[i] / 10) for i, b in enumerate(bare))
    erosion_score = _clamp(100 - 6 * slope_factor * weighted_bare)
    bare_months = [MONTH_NAMES[i] for i, b in enumerate(bare) if b >= 0.5]
    erosion_ev = [Evidence("Average slope", slope, "degrees", "NASA SRTM v3 (SRTMGL1_003)",
                           "30 m", "static", "high"),
                  Evidence("Mostly bare months", ", ".join(bare_months) or "none", "months",
                           "Farmer's crop calendar + strategy", "field", "", "medium")]
    erosion_c = ComponentScore(erosion_score, f"{len(bare_months)} mostly bare month(s) on "
                               f"{slope:.0f}° slope", erosion_ev, {"bare_months": bare_months})

    # 4. Pest-cycle break: plant families in sequence
    sequence = [crops[s.crop].family for y in years for s in sorted(y, key=lambda s: s.plant_month)]
    families = {f for f in sequence if f != "unknown"}
    repeats = sum(1 for i in range(len(sequence)) if sequence[i] == sequence[i - 1]) \
        if len(sequence) > 1 else 0
    base = {0: 50, 1: 30, 2: 70}.get(len(families), 90)
    pest_score = _clamp(base - 20 * repeats / max(1, len(sequence)))
    pest_ev = [Evidence("Plant families in the rotation, in order", " → ".join(sequence),
                        "families", "Crop traits (FAO EcoCrop / team)", "crop-level", "",
                        "medium")]
    pest_c = ComponentScore(pest_score, f"{len(families)} plant famil"
                            f"{'y' if len(families) == 1 else 'ies'}; same family back-to-back "
                            f"{repeats} time(s)", pest_ev, {"families": sorted(families)})

    # 5. Climate risk: crop months that overlap heat, frost, dry or very wet months
    penalty, hits, hit_months = 0.0, [], set()
    for slot in slots:
        c = crops[slot.crop]
        for m, share in slot.occupancy().items():
            f, before = ctx.flags[m - 1], len(hits)
            if "heat" in f:
                penalty += share * (1 - TOLERANCE[c.heat_tolerance])
                hits.append(f"{c.name}: heat in {MONTH_NAMES[m - 1]}")
            if "frost" in f and not survives_frost(c, ctx.t_mean[m - 1], ctx.t_cold[m - 1]):
                penalty += share * 1.5
                hits.append(f"{c.name}: frost in {MONTH_NAMES[m - 1]}")
            if "dry" in f and water != "irrigated":
                penalty += share * (1 - TOLERANCE[c.drought_tolerance])
                hits.append(f"{c.name}: dry month {MONTH_NAMES[m - 1]}")
            if "very_wet" in f:
                penalty += share * (1 - TOLERANCE[c.waterlogging_tolerance])
                hits.append(f"{c.name}: very wet {MONTH_NAMES[m - 1]}")
            if len(hits) > before:
                hit_months.add(m)
    climate_score = _clamp(100 - 10 * penalty / n_years)
    climate_ev = [e for m in sorted(hit_months) for e in ctx.stress_evidence[m - 1]]
    climate_ev += [from_crop(c, f"{c.name} heat / drought / waterlogging tolerance",
                             f"{c.heat_tolerance} / {c.drought_tolerance} / "
                             f"{c.waterlogging_tolerance}") for c in crops.values()]
    climate_c = ComponentScore(climate_score, f"{len(hits)} crop-month(s) overlap heat, frost, "
                               "dry or very wet months", climate_ev, {"overlaps": hits[:12]})

    # 6. Income: harvests per year that can be sold or eaten
    value = 0.0
    for slot in slots:
        c = crops[slot.crop]
        if c.is_cover:
            v = 0.1
        elif sellable:
            v = 1.0 if c.name in sellable else 0.5
        else:
            v = 0.8
        value += v
    income_score = _clamp(100 * min(1.0, value / n_years / 2))
    income_ev = [Evidence("Harvests per year that can be sold or eaten",
                          round(value / n_years, 1), "harvest-equivalents",
                          "Strategy calendar; farmer's sellable crops" if sellable
                          else "Strategy calendar (no market info given)", "field", "", "low")]
    income_c = ComponentScore(income_score, f"{value / n_years:.1f} sellable or edible harvest(s)"
                              " per year", income_ev)

    # 7. Labor: hand work per year, eased by machinery
    points = sum(LABOR_POINTS[crops[s.crop].labor_need] for s in slots) / n_years
    factor = EQUIPMENT_FACTOR.get(equipment, 1.0)
    labor_score = _clamp(100 - 12 * points * factor)
    labor_ev = [from_crop(c, f"{c.name} hand labor need", c.labor_need) for c in crops.values()]
    labor_c = ComponentScore(labor_score, f"Hand work {points:.0f} points/year "
                             f"({equipment.replace('_', ' ')})", labor_ev)

    return {"water": water_c, "soil": soil_c, "erosion": erosion_c, "pest_cycle": pest_c,
            "climate_risk": climate_c, "income": income_c, "labor": labor_c}


COLD_NIGHT_SHARE = 0.6  # typical cold night: 60% of the way from monthly mean to coldest hour


def cold_night_c(month_mean_c: float, month_coldest_c: float | None) -> float:
    if month_coldest_c is None:
        return month_mean_c - 6.0
    return month_mean_c - COLD_NIGHT_SHARE * (month_mean_c - month_coldest_c)


def survives_frost(crop: CropInfo, month_mean_c: float,
                   month_coldest_c: float | None = None) -> bool:
    """Frost-hardy crops survive cold months dormant if a typical cold night stays above their
    FAO EcoCrop killing temperature (rest period). E.g. Iowa January: cold night about -16.6 C,
    so winter rye (-18) survives and oats (-15) winter-kill, as they do in practice."""
    night = cold_night_c(month_mean_c, month_coldest_c)
    rest = crop.eco.get("killing_temp_rest_c")
    if rest is not None:
        return night >= rest
    growth = crop.eco.get("killing_temp_c")
    return growth is not None and night >= growth


def weights_for(goals: list[str]) -> dict[str, float]:
    if not goals:
        return {c: round(1 / len(COMPONENTS), 4) for c in COMPONENTS}
    shares = RANK_SHARES[: len(goals)]
    total = sum(shares)
    weights = dict.fromkeys(COMPONENTS, 0.0)
    for goal, share in zip(goals, shares, strict=False):
        for comp, w in GOAL_WEIGHTS[goal].items():
            weights[comp] += w * share / total
    return {c: round(w, 4) for c, w in weights.items()}


def total_score(components: dict[str, ComponentScore], weights: dict[str, float]) -> float:
    return round(sum(components[c].score * weights[c] for c in COMPONENTS), 1)
