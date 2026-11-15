"""Tier 1 (automatic, short) and Tier 2 (on request, detailed) AI reports.

Flow per report: cache lookup -> one Grok call -> schema check -> "no new numbers" check -> if any
unknown number, one retry that names them -> anything still unknown is removed. Every report is
labeled AI-written and keeps the engine's ranking.

Caching: guest reports live in this process's memory only (CLAUDE.md: results are stored only for
signed-in users). Saved analyses go to the ai_reports table (step 3.4); showcase farms are
pre-computed into files (step 2.4).
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ValidationError

from app.ai import checks
from app.ai.client import LLMClient, LLMError, LLMResult
from app.ai.prompts import (
    PROMPT_VERSION,
    TIER1_MAX_OUTPUT_TOKENS,
    TIER2_MAX_OUTPUT_TOKENS,
    Tier1Report,
    Tier2Answer,
    as_user_message,
    compact_input,
    schema_of,
    tier1_system,
    tier2_input,
    tier2_system,
)
from app.data.cache import MemoryCache

log = logging.getLogger(__name__)

IDEA_LABEL = "AI-suggested idea to discuss with your local expert (not scored by SowSmart)"


class _Nowhere:
    def get(self, key: str, max_age_s: float | None = None) -> None:
        return None

    def set(self, key: str, value: Any) -> None:
        pass


REPORT_CACHE = MemoryCache(_Nowhere(), max_items=256, ttl_s=24 * 3600)


class ReportUnavailable(RuntimeError):
    """No report: AI not configured, limit reached, or the call failed. Message is user-safe."""

    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


def cache_key(tier: int, language: str, level: str, question: str, model: str,
              data: dict[str, Any]) -> str:
    blob = json.dumps({"v": PROMPT_VERSION, "tier": tier, "language": language, "level": level,
                       "question": question, "model": model, "input": data},
                      sort_keys=True, ensure_ascii=False)
    return f"ai:{hashlib.sha256(blob.encode()).hexdigest()}"


def _generate(client: LLMClient, system: str, data: dict[str, Any], question: str | None,
              model_cls: type[BaseModel], name: str, max_tokens: int
              ) -> tuple[dict[str, Any], dict[str, Any], list[LLMResult]]:
    allowed = checks.allowed_numbers({"input": data, "question": question or ""})
    user = as_user_message(data, question)
    calls: list[LLMResult] = []
    report: dict[str, Any] = {}
    unknown: list[str] = []
    for attempt in (1, 2):
        result = client.complete_json(system, user, name, schema_of(model_cls), max_tokens)
        calls.append(result)
        try:
            report = model_cls.model_validate(result.data).model_dump()
        except ValidationError as exc:
            if attempt == 2:
                raise LLMError("the AI answer did not match the report format") from exc
            continue
        unknown = checks.find_unknown(report, allowed)
        if not unknown:
            break
        if attempt == 1:
            log.info("AI report used %d number(s) not in the input; retrying", len(unknown))
            user = (as_user_message(data, question) + "\n\nYour previous answer used numbers "
                    f"that are not in INPUT: {', '.join(unknown)}. Write it again using only "
                    "numbers from INPUT.")
    report, removed = checks.scrub(report, allowed)
    check = {"numbers_ok": not unknown, "retried": len(calls) > 1,
             "unknown_numbers": unknown, "removed_items": removed}
    return report, check, calls


def _meta(calls: list[LLMResult]) -> dict[str, Any]:
    costs = [c.cost_usd for c in calls]
    return {
        "model": calls[-1].model, "calls": len(calls), "prompt_version": PROMPT_VERSION,
        "input_tokens": sum(c.input_tokens for c in calls),
        "cached_tokens": sum(c.cached_tokens for c in calls),
        "output_tokens": sum(c.output_tokens for c in calls),
        "reasoning_tokens": sum(c.reasoning_tokens for c in calls),
        "seconds": round(sum(c.seconds for c in calls), 2),
        "cost_usd": None if None in costs else round(sum(costs), 6),
    }


def _run(tier: int, client: LLMClient | None, language: str, level: str, question: str,
         data: dict[str, Any], build: Callable[[LLMClient], tuple[dict, dict, list]],
         cache: Any, allow_call: Callable[[], bool] | None) -> dict[str, Any]:
    if client is None:
        raise ReportUnavailable("unavailable", "AI reports are not set up on this server.")
    cache = cache if cache is not None else REPORT_CACHE
    key = cache_key(tier, language, level, question, client.model, data)
    cached = cache.get(key)
    if cached is not None:
        return {**cached, "cached": True}
    if allow_call is not None and not allow_call():
        raise ReportUnavailable("limit", "Report limit reached for now. Please try again later.")
    try:
        report, check, calls = build(client)
    except LLMError as exc:
        log.warning("AI report failed: %s", exc)
        raise ReportUnavailable("failed", "The AI report could not be written right now. "
                                          "The comparison above is still complete.") from exc
    out = {"tier": tier, "language": language, "language_level": level, "question": question,
           "ai_generated": True, "content": report, "checks": check, "meta": _meta(calls),
           "cached": False}
    cache.set(key, out)
    return out


def tier1(analysis: dict[str, Any], language: str, client: LLMClient | None, *,
          cache: Any = None, allow_call: Callable[[], bool] | None = None
          ) -> dict[str, Any]:
    data = compact_input(analysis)

    def build(c: LLMClient) -> tuple[dict, dict, list]:
        report, check, calls = _generate(c, tier1_system(language), data, None, Tier1Report,
                                         "tier1_report", TIER1_MAX_OUTPUT_TOKENS)
        report["strategies"] = _align_strategies(report["strategies"], data["strategies"])
        report["idea_label"] = IDEA_LABEL
        return report, check, calls

    return _run(1, client, language, "farmer", "", data, build, cache, allow_call)


def tier2(analysis: dict[str, Any], language: str, level: str, question: str | None,
          client: LLMClient | None, *, cache: Any = None,
          allow_call: Callable[[], bool] | None = None) -> dict[str, Any]:
    data = tier2_input(analysis)
    q = (question or "").strip()

    def build(c: LLMClient) -> tuple[dict, dict, list]:
        return _generate(c, tier2_system(language, level), data, q or None, Tier2Answer,
                         "tier2_answer", TIER2_MAX_OUTPUT_TOKENS)

    return _run(2, client, language, level, q, data, build, cache, allow_call)


def _align_strategies(written: list[dict[str, Any]], engine: list[dict[str, Any]]
                      ) -> list[dict[str, Any]]:
    """Same strategies, same order as the engine. A strategy the AI skipped falls back to the
    engine's own (English) text, marked as such."""
    by_key = {s["key"]: s for s in written}
    out = []
    for s in engine:
        text = by_key.get(s["key"])
        if text is None:
            text = {"key": s["key"], "name": s["name"], "headline": s["title"], "why": s["why"],
                    "benefits": s["benefits"], "risks": s["risks"],
                    "information_gaps": s["information_gaps"],
                    "expert_questions": s["expert_questions"], "fallback": True}
        out.append({**text, "rank": s["rank"], "engine_name": s["name"]})
    return out
