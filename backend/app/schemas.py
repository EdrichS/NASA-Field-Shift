"""Request and response schemas for the API (CLAUDE.md section 13). The frontend's TypeScript
types are generated from the OpenAPI schema these produce (shared/contracts/openapi.json)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.data.geometry import validate as validate_geometry

LANGUAGES = {"en": "English", "tl": "Tagalog", "es": "Spanish", "fr": "French",
             "pt": "Portuguese", "hi": "Hindi", "id": "Indonesian", "vi": "Vietnamese",
             "sw": "Swahili"}
Water = Literal["irrigated", "rainfed", "mixed", "unknown"]
Equipment = Literal["hand_tools", "animal", "small_tractor", "full_machinery", "unknown"]
Goal = Literal["save_water", "build_soil", "earn_more", "feed_household", "survive_bad_years"]


def _check_language(code: str) -> str:
    if code not in LANGUAGES:
        raise ValueError(f"unsupported language {code!r}; use one of {sorted(LANGUAGES)}")
    return code


class GeometryIn(BaseModel):
    geometry: dict[str, Any] = Field(
        description="GeoJSON Point (buffered to 250 m) or Polygon/MultiPolygon, EPSG:4326",
        examples=[{"type": "Point", "coordinates": [120.9, 15.6]}],
    )

    @field_validator("geometry")
    @classmethod
    def _valid(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_geometry(value)


class CropEntry(BaseModel):
    crop: str = Field(min_length=1, max_length=60)
    plant_month: int = Field(ge=1, le=12)
    harvest_month: int = Field(ge=1, le=12)


class Answers(BaseModel):
    """Quick-mode answers; detailed-mode sections may add more keys (kept, not required)."""

    model_config = ConfigDict(extra="allow")
    current_crops: list[CropEntry] = Field(default_factory=list, max_length=6)
    not_farming: bool = False
    water: Water | None = None
    equipment: Equipment | None = None
    top_goal: Goal | None = None
    ranked_goals: list[Goal] = Field(default_factory=list, max_length=3)
    wont_grow: list[str] = Field(default_factory=list, max_length=30)
    sellable_crops: list[str] = Field(default_factory=list, max_length=30)


class AnalyzeRequest(GeometryIn):
    mode: Literal["quick", "detailed", "exploring"] = "quick"
    answers: Answers = Field(default_factory=Answers)
    report_languages: list[str] = Field(default_factory=lambda: ["en"], min_length=1,
                                        max_length=2)
    generate_reports: bool = Field(
        True, description="False returns the comparison only (no AI call), e.g. for tests")

    @field_validator("report_languages")
    @classmethod
    def _languages(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(_check_language(code) for code in value))


class EvidenceOut(BaseModel):
    claim: str
    value: Any
    unit: str
    dataset: str
    native_resolution: str
    period: str
    confidence: str


class CardOut(BaseModel):
    id: str
    title: str
    statement: str
    value: Any
    confidence: str
    evidence: list[EvidenceOut]
    edit: dict[str, Any]


class FieldOut(BaseModel):
    geom_hash: str
    lat: float
    lon: float
    end_month: str


class PrefillResponse(BaseModel):
    field: FieldOut
    warning: str | None = Field(description="Friendly message if the spot isn't farmland")
    cards: list[CardOut]
    gaps: list[str]


class ComponentOut(BaseModel):
    score: float
    summary: str
    evidence: list[EvidenceOut]
    metrics: dict[str, Any]


class StrategyOut(BaseModel):
    key: str
    name: str
    title: str
    rotation: list[list[dict[str, Any]]]
    calendar: list[dict[str, Any]]
    components: dict[str, ComponentOut]
    total: float
    rank: int
    confidence: str
    why: str
    changes: list[str]
    benefits: list[str]
    risks: list[str]
    gaps: list[str]
    expert_questions: list[str]


class AIReportOut(BaseModel):
    """An AI-written report. Tier 1: content follows Tier1Report; Tier 2: Tier2Answer
    (app/ai/prompts.py). Always labeled AI-written; the engine's ranking is unchanged."""

    tier: int
    language: str
    language_level: str
    question: str
    ai_generated: bool
    content: dict[str, Any]
    checks: dict[str, Any] = Field(description="Result of the no-new-numbers check")
    meta: dict[str, Any] = Field(description="Model, tokens, seconds and cost")
    cached: bool


class ReportStatus(BaseModel):
    status: Literal["ok", "cached", "skipped", "unavailable", "limit", "failed"]
    message: str = ""


class AnalyzeResponse(BaseModel):
    analysis_id: str | None = Field(description="Set only for signed-in users who save")
    field: FieldOut
    warning: str | None
    prefill: list[CardOut]
    features: dict[str, dict[str, Any]]
    static: dict[str, Any]
    profile: dict[str, Any]
    weights: dict[str, float]
    bare_months: dict[str, Any]
    stress_calendar: list[dict[str, Any]]
    strategies: list[StrategyOut]
    gaps: list[str]
    disclaimer: str
    reports_tier1: dict[str, AIReportOut | None] = Field(
        description="One plain-language report per chosen language, or null (see report_status)")
    report_status: dict[str, ReportStatus]
    timings_ms: dict[str, int]


class FollowupRequest(BaseModel):
    analysis_payload: AnalyzeResponse = Field(
        description="The /analyze response (guests). Saved analyses will send analysis_id.")
    language: str = "en"
    language_level: Literal["farmer", "advanced"] = "farmer"
    question: str | None = Field(None, max_length=500)

    @field_validator("language")
    @classmethod
    def _language(cls, value: str) -> str:
        return _check_language(value)


class ShowcaseFarmOut(BaseModel):
    id: str
    name: str
    persona: str
    country: str
    place: str
    story: str
    geometry: dict[str, Any]
    report_languages: list[str]
    available: bool = Field(description="True when the pre-computed analysis exists")
    generated_at: str | None
    model: str | None = Field(description="AI model that wrote the stored reports")
