"""Rotations on a 12-month calendar.

A slot is one crop from a planting month to a harvest month. Planting and harvest months count
as half months (mid-month to mid-month), so "harvest April, plant June" leaves a 60-day gap.
Crops that share the same months in different years (corn one year, soybean the next) go into
separate rotation years.
"""

from __future__ import annotations

from dataclasses import dataclass

DAYS_PER_MONTH = 30


@dataclass(frozen=True)
class Slot:
    crop: str
    plant_month: int  # 1-12
    harvest_month: int  # 1-12
    new: bool = False  # added or changed by a strategy

    @property
    def length_months(self) -> int:
        return (self.harvest_month - self.plant_month) % 12 or 12

    @property
    def days(self) -> int:
        return self.length_months * DAYS_PER_MONTH

    def occupancy(self) -> dict[int, float]:
        """Share of each month the crop is in the field."""
        months: dict[int, float] = {}
        m = self.plant_month
        for step in range(self.length_months + 1):
            share = 0.5 if step in (0, self.length_months) else 1.0
            months[m] = months.get(m, 0.0) + share
            m = m % 12 + 1
        return {k: min(1.0, v) for k, v in months.items()}

    def months(self) -> list[int]:
        """Months the crop is growing for at least part of the month."""
        return list(self.occupancy())


def overlaps(a: Slot, b: Slot) -> bool:
    occ_a, occ_b = a.occupancy(), b.occupancy()
    return any(occ_a.get(m, 0) + occ_b.get(m, 0) > 1.0 + 1e-9 for m in range(1, 13))


def group_years(slots: list[Slot]) -> list[list[Slot]]:
    """Split slots into rotation years so slots in the same year never overlap."""
    years: list[list[Slot]] = []
    for slot in slots:
        for year in years:
            if not any(overlaps(slot, other) for other in year):
                year.append(slot)
                break
        else:
            years.append([slot])
    return years or [[]]


def cover_by_month(year: list[Slot]) -> list[float]:
    cover = [0.0] * 12
    for slot in year:
        for m, share in slot.occupancy().items():
            cover[m - 1] = min(1.0, cover[m - 1] + share)
    return cover


def bare_by_month(years: list[list[Slot]]) -> list[float]:
    """Average bare share per month across rotation years."""
    covers = [cover_by_month(y) for y in years]
    return [round(1 - sum(c[i] for c in covers) / len(covers), 3) for i in range(12)]


@dataclass(frozen=True)
class Gap:
    year: int
    after: Slot | None
    before: Slot | None
    start_month: int  # the harvest month of `after` (mid-month)
    end_month: int  # the planting month of `before` (mid-month)
    days: int


def gaps(years: list[list[Slot]], min_days: int = 30) -> list[Gap]:
    found = []
    for y, year in enumerate(years):
        ordered = sorted(year, key=lambda s: s.plant_month)
        if not ordered:
            found.append(Gap(y, None, None, 1, 1, 360))
            continue
        for i, before in enumerate(ordered):
            after = ordered[i - 1]
            days = ((before.plant_month - after.harvest_month) % 12) * DAYS_PER_MONTH
            if len(ordered) == 1:
                days = (12 - after.length_months) * DAYS_PER_MONTH
            if days >= min_days:
                found.append(Gap(y, after, before, after.harvest_month, before.plant_month, days))
    return found


def gap_months(gap: Gap) -> list[int]:
    """Months (at least partly) inside a gap, harvest month first."""
    months, m = [gap.start_month], gap.start_month
    for _ in range(gap.days // DAYS_PER_MONTH):
        m = m % 12 + 1
        months.append(m)
    return months
