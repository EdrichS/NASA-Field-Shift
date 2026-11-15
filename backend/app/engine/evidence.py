"""Evidence objects: the record behind every number the engine shows (CLAUDE.md section 6)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

# How much a number says about *this field*, from the data's native resolution.
CONFIDENCE_BY_DETAIL = {"field": "high", "local": "medium", "regional": "low"}


@dataclass(frozen=True)
class Evidence:
    claim: str
    value: Any
    unit: str
    dataset: str
    native_resolution: str
    period: str
    confidence: str  # "high" | "medium" | "low"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def from_feature(feature: Any, claim: str, value: Any, unit: str | None = None,
                 period: str | None = None) -> Evidence:
    """Evidence for a value taken from a harmonized Feature."""
    return Evidence(
        claim=claim,
        value=value,
        unit=unit if unit is not None else feature.unit,
        dataset=feature.source,
        native_resolution=feature.native_resolution,
        period=period or feature.normal_period,
        confidence=CONFIDENCE_BY_DETAIL.get(feature.spatial_detail, "medium"),
    )


def from_crop(crop: Any, claim: str, value: Any, unit: str = "") -> Evidence:
    """Evidence for a crop trait (crop-level facts, not specific to this field)."""
    estimate = bool(crop.notes and "estimate" in crop.notes and claim_uses_estimate(claim))
    return Evidence(
        claim=claim,
        value=value,
        unit=unit,
        dataset=crop.traits_source or "FAO EcoCrop",
        native_resolution="crop-level",
        period="",
        confidence="low" if (estimate or not crop.traits_source) else "medium",
    )


def claim_uses_estimate(claim: str) -> bool:
    return any(word in claim.lower() for word in ("labor", "hand work"))
