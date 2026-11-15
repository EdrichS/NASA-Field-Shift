"""API v1: /prefill (satellite cards), /analyze (cards + engine results + Tier 1 AI reports),
/reports/followup (Tier 2, on request) and /showcase (pre-computed demo farms).

Endpoints are plain `def` so FastAPI runs them in a worker thread: the data fetch is blocking.
Guests get results back but nothing is stored (saving comes with sign-in, step 3.4).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from app import store
from app.ai import reports
from app.ai.client import LLMClient, client_from_settings
from app.api import showcase
from app.api.ratelimit import RateLimiter, client_key
from app.auth import MaybeUser
from app.config import get_settings
from app.data.country import country_of
from app.engine.catalog import CropInfo, default_catalog
from app.engine.engine import run_engine
from app.features.harmonize import FieldFeatures, build_field_features, store_features
from app.features.prefill import field_warning, prefill_cards
from app.schemas import (
    AIReportOut,
    AnalyzeRequest,
    AnalyzeResponse,
    FollowupRequest,
    GeometryIn,
    PrefillResponse,
    ShowcaseFarmOut,
)

router = APIRouter()
prefill_limit = RateLimiter(limit=60, window_s=3600)
analyze_limit = RateLimiter(limit=20, window_s=3600)
followup_limit = RateLimiter(limit=20, window_s=3600)
ai_call_limit = RateLimiter(limit=12, window_s=3600)  # actual Grok calls (cache misses)
_stored: set[tuple[str, str]] = set()  # (geom_hash, end_month) already saved by this process


def crop_catalog() -> dict[str, CropInfo]:
    """Crops from TigerData (or the CSV files); default_catalog keeps the first complete one."""
    return default_catalog()


@lru_cache(maxsize=1)
def get_llm() -> LLMClient | None:
    """The Grok client, or None when XAI_API_KEY / XAI_MODEL aren't set."""
    return client_from_settings()


def get_features(geometry: dict[str, Any], tasks: BackgroundTasks | None = None) -> FieldFeatures:
    """Fetch (or read cached) field data. When TigerData is configured, the shared climate rows
    (daily weather + monthly features, no personal data) are saved after the response is sent."""
    features, daily = build_field_features(geometry)
    stored_key = (features.geom_hash, features.end_month)
    if (tasks is not None and stored_key not in _stored
            and get_settings().database_url.get_secret_value()):
        _stored.add(stored_key)
        tasks.add_task(store_features, features, daily)
    return features


def get_country(ff: FieldFeatures) -> str | None:
    """The field's country (FAO name), so suggestions stay to locally grown crops."""
    return country_of(ff.lon, ff.lat)


def unusable(ff: FieldFeatures) -> bool:
    """Open water or mostly buildings: there is no field to analyze."""
    if "land_cover" not in ff.static:
        return False
    shares = ff.static["land_cover"].get("shares") or {}
    return not shares or shares.get("water", 0) >= 0.5 or shares.get("built_up", 0) >= 0.5


def _field(ff: FieldFeatures) -> dict[str, Any]:
    return {"geom_hash": ff.geom_hash, "lat": ff.lat, "lon": ff.lon, "end_month": ff.end_month}


def _ai_allowance(request: Request) -> Callable[[], bool]:
    key = client_key(request)

    def allow() -> bool:
        try:
            ai_call_limit.check(key)
        except HTTPException:
            return False
        return True

    return allow


def _tier1_reports(analysis: dict[str, Any], languages: list[str],
                   allow: Callable[[], bool]) -> tuple[dict[str, Any], dict[str, Any]]:
    client = get_llm()

    def one(language: str) -> tuple[dict[str, Any] | None, dict[str, str]]:
        try:
            report = reports.tier1(analysis, language, client, allow_call=allow)
        except reports.ReportUnavailable as exc:
            return None, {"status": exc.status, "message": str(exc)}
        return report, {"status": "cached" if report["cached"] else "ok", "message": ""}

    with ThreadPoolExecutor(max_workers=2) as pool:  # one call per language, side by side
        results = list(pool.map(one, languages))
    return ({lang: r for lang, (r, _) in zip(languages, results, strict=True)},
            {lang: s for lang, (_, s) in zip(languages, results, strict=True)})


@router.post("/prefill", response_model=PrefillResponse, dependencies=[Depends(prefill_limit)])
def prefill(body: GeometryIn, tasks: BackgroundTasks) -> dict[str, Any]:
    ff = get_features(body.geometry, tasks)
    return {"field": _field(ff), "warning": field_warning(ff),
            "cards": [] if unusable(ff) else prefill_cards(ff), "gaps": ff.gaps}


def run_analysis(body: AnalyzeRequest, *, tasks: BackgroundTasks | None = None,
                 allow_ai: Callable[[], bool] | None = None,
                 features: FieldFeatures | None = None,
                 country: str | None = None) -> dict[str, Any]:
    """The full analysis behind /analyze (also used by scripts/precache_showcase.py, which can
    pass stored features and the country to re-run the engine offline)."""
    t0 = time.perf_counter()
    ff = features or get_features(body.geometry, tasks)
    t1 = time.perf_counter()
    if unusable(ff):
        raise HTTPException(status_code=422, detail=field_warning(ff))
    answers = body.answers.model_dump()
    answers["mode"] = body.mode
    try:
        result = run_engine(ff, answers, crop_catalog(),
                            country=country or get_country(ff)).to_dict()
    except ValueError as exc:  # e.g. NASA POWER unavailable for this spot right now
        raise HTTPException(status_code=503,
                            detail=f"Not enough data to analyze yet: {exc}") from exc
    t2 = time.perf_counter()
    features = ff.to_dict()
    response = {
        "analysis_id": None,
        "field": _field(ff),
        "warning": field_warning(ff),
        "prefill": prefill_cards(ff),
        "features": features["features"],
        "static": features["static"],
        "profile": result["profile"],
        "weights": result["weights"],
        "bare_months": result["bare_months"],
        "stress_calendar": result["stress_calendar"],
        "strategies": result["strategies"],
        "gaps": result["gaps"],
        "feature_gaps": ff.gaps,
        "fruit_ideas": result["fruit_ideas"],
        "disclaimer": result["disclaimer"],
    }
    if body.generate_reports:
        response["reports_tier1"], response["report_status"] = _tier1_reports(
            response, body.report_languages, allow_ai or (lambda: True))
    else:
        response["reports_tier1"] = dict.fromkeys(body.report_languages)
        response["report_status"] = {lang: {"status": "skipped", "message": ""}
                                     for lang in body.report_languages}
    t3 = time.perf_counter()
    response["timings_ms"] = {"data": round((t1 - t0) * 1000), "engine": round((t2 - t1) * 1000),
                              "reports": round((t3 - t2) * 1000)}
    return response


@router.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(analyze_limit)])
def analyze(body: AnalyzeRequest, tasks: BackgroundTasks, request: Request) -> dict[str, Any]:
    cached = showcase.match(body)  # showcase farms: pre-computed, never wait on outside APIs
    if cached is not None:
        return cached
    return run_analysis(body, tasks=tasks, allow_ai=_ai_allowance(request))


@router.get("/showcase", response_model=list[ShowcaseFarmOut])
def showcase_list() -> list[dict[str, Any]]:
    """The demo farms, with whether their pre-computed analysis is available."""
    return showcase.list_farms()


@router.get("/showcase/{farm_id}", response_model=AnalyzeResponse)
def showcase_analysis(farm_id: str) -> dict[str, Any]:
    analysis = showcase.analysis(farm_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"No pre-computed analysis for {farm_id!r}")
    return analysis


@router.post("/reports/followup", response_model=AIReportOut,
             dependencies=[Depends(followup_limit)])
def followup(body: FollowupRequest, request: Request,
             user: MaybeUser) -> dict[str, Any]:
    """Tier 2: a detailed answer with the dataset behind each claim. Only on request.
    Guests send the analysis itself; signed-in users can send a saved analysis_id, and the
    answer is stored with it (ai_reports) and served from there next time."""
    question = (body.question or "").strip()
    if body.analysis_id:
        if user is None:
            raise HTTPException(status_code=401, detail="Please log in to open a saved analysis.")
        analysis = store.get_analysis(user.sub, body.analysis_id) if _uuid(body.analysis_id) \
            else None
        if analysis is None:
            raise HTTPException(status_code=404, detail="Analysis not found")
        kept = store.get_report(user.sub, body.analysis_id, 2, body.language,
                                body.language_level, question)
        if kept is not None:
            return {**kept, "cached": True}
    else:
        assert body.analysis_payload is not None
        analysis = body.analysis_payload.model_dump()
    try:
        report = reports.tier2(analysis, body.language, body.language_level, question,
                               get_llm(), allow_call=_ai_allowance(request))
    except reports.ReportUnavailable as exc:
        raise HTTPException(status_code=429 if exc.status == "limit" else 503,
                            detail=str(exc)) from exc
    if body.analysis_id and user is not None:
        store.store_report(user.sub, body.analysis_id, report)
    return report


def _uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True
