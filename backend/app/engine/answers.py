"""Farmer answers -> a normalized farm profile. Every answer is optional; "I don't know" gets a
safe default that is recorded as an information gap (team decision, Nov 14)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.engine.catalog import CropInfo, resolve
from app.engine.regional import MarketValue
from app.engine.rotation import Slot

GOALS = ("save_water", "build_soil", "earn_more", "feed_household", "survive_bad_years")
WATER = {"irrigated", "rainfed", "mixed"}
EQUIPMENT = {"hand_tools", "animal", "small_tractor", "full_machinery"}
EQUIPMENT_ALIASES = {"hand": "hand_tools", "animal_drawn": "animal", "tractor": "small_tractor",
                     "machinery": "full_machinery"}


@dataclass
class FarmProfile:
    mode: str
    slots: list[Slot]
    water: str  # irrigated | rainfed | mixed (default rainfed when unknown)
    equipment: str
    goals: list[str]  # ranked; empty = balanced
    wont_grow: set[str]
    sellable: set[str]
    rotation_source: str  # "farmer" | "satellite" | "none"
    assumptions: list[str] = field(default_factory=list)
    country: str | None = None
    local: dict[str, float] | None = None  # crops grown in the country (ha); None = no filter
    values: dict[str, MarketValue] | None = None  # FAOSTAT gross value per ha, by crop
    value_ref: float | None = None  # value per ha of the country's main crop


def _month(value: Any) -> int | None:
    try:
        m = int(value)
    except (TypeError, ValueError):
        return None
    return m if 1 <= m <= 12 else None


def parse_answers(raw: dict[str, Any] | None, catalog: dict[str, CropInfo],
                  satellite_green_runs: list[list[int]] | None = None) -> FarmProfile:
    raw = raw or {}
    assumptions: list[str] = []
    slots: list[Slot] = []
    for item in raw.get("current_crops") or []:
        crop = resolve(str(item.get("crop", "")), catalog)
        plant, harvest = _month(item.get("plant_month")), _month(item.get("harvest_month"))
        if plant is None or harvest is None or plant == harvest:
            assumptions.append(f"Months for '{item.get('crop')}' were missing; crop left out")
            continue
        if crop is None:
            assumptions.append(f"No trait data for '{item.get('crop')}': neutral values used")
            slots.append(Slot(str(item.get("crop")), plant, harvest))
        else:
            slots.append(Slot(crop.name, plant, harvest))
    rotation_source = "farmer" if slots else "none"
    if not slots and raw.get("not_farming") is not True and satellite_green_runs:
        for run in satellite_green_runs:
            if len(run) >= 2:
                slots.append(Slot("unknown crop", run[0], run[-1] % 12 + 1))
        if slots:
            rotation_source = "satellite"
            assumptions.append("Current crops estimated from when the field looks green")

    water = raw.get("water")
    if water not in WATER:
        water = "rainfed"
        assumptions.append("Irrigation unknown: assumed rain-fed")
    equipment = EQUIPMENT_ALIASES.get(raw.get("equipment"), raw.get("equipment"))
    if equipment not in EQUIPMENT:
        equipment = "hand_tools"
        assumptions.append("Equipment unknown: assumed hand tools")

    goals = [g for g in (raw.get("ranked_goals") or []) if g in GOALS]
    if not goals and raw.get("top_goal") in GOALS:
        goals = [raw["top_goal"]]
    if not goals:
        assumptions.append("No goal chosen: all goals weighted equally")

    def names(key: str) -> set[str]:
        out = set()
        for value in raw.get(key) or []:
            crop = resolve(str(value), catalog)
            out.add(crop.name if crop else str(value).strip().lower())
        return out

    return FarmProfile(
        mode=raw.get("mode") or "quick",
        slots=slots,
        water=water,
        equipment=equipment,
        goals=goals,
        wont_grow=names("wont_grow"),
        sellable=names("sellable_crops"),
        rotation_source=rotation_source,
        assumptions=assumptions,
    )
