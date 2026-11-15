"""A small client for any OpenAI-compatible Chat Completions API (xAI Grok by default).

Swapping providers means changing XAI_BASE_URL and XAI_MODEL only. We call the endpoint with
httpx (already a dependency) using the same wire format the OpenAI SDK sends. Checked against
docs.x.ai on Nov 14, 2026:
- POST {base}/chat/completions with response_format {"type": "json_schema", "json_schema": ...}
  returns JSON that matches the schema.
- max_completion_tokens caps visible output only (not reasoning tokens); max_tokens is deprecated.
- grok-4.7 always reasons (reasoning_effort low/medium/high/xhigh, default high); "-non-reasoning"
  models take no reasoning_effort.
The API key is only ever sent in the Authorization header. It is never logged or returned.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)

# USD per 1M tokens (input, cached input, output) from docs.x.ai/developers/models, Nov 14 2026.
# None = not published: cached tokens are then priced as normal input (an upper bound).
PRICES = {
    "grok-4.20-0309-non-reasoning": (1.25, 0.20, 2.50),
    "grok-4.20-non-reasoning": (1.25, 0.20, 2.50),
    "grok-4.7": (2.00, None, 6.00),
}
RETRY_STATUSES = {429, 500, 502, 503, 504}


class LLMError(RuntimeError):
    """The model could not produce a usable answer (network, HTTP error, cut off, bad JSON)."""


@dataclass
class LLMResult:
    data: dict[str, Any]
    model: str
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    reasoning_tokens: int
    seconds: float

    @property
    def cost_usd(self) -> float | None:
        price = PRICES.get(self.model) or next(
            (p for name, p in PRICES.items() if self.model.startswith(name)), None)
        if price is None:
            return None
        p_in, p_cached, p_out = price
        p_cached = p_in if p_cached is None else p_cached
        fresh = max(self.input_tokens - self.cached_tokens, 0)
        out = self.output_tokens + self.reasoning_tokens
        return round((fresh * p_in + self.cached_tokens * p_cached + out * p_out) / 1e6, 6)

    def meta(self) -> dict[str, Any]:
        info = asdict(self)
        info.pop("data")
        info["cost_usd"] = self.cost_usd
        return info


class LLMClient:
    def __init__(self, api_key: str, base_url: str, model: str, *, reasoning_effort: str = "",
                 timeout_s: float = 120.0, transport: httpx.BaseTransport | None = None) -> None:
        if not api_key or not model:
            raise ValueError("an API key and a model name are required")
        self.model = model
        self.reasoning_effort = reasoning_effort
        self._http = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_s,
                                  headers={"Authorization": f"Bearer {api_key}"},
                                  transport=transport)

    def _body(self, system: str, user: str, schema_name: str, schema: dict[str, Any],
              max_output_tokens: int) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "response_format": {"type": "json_schema",
                                "json_schema": {"name": schema_name, "schema": schema,
                                                "strict": True}},
            "max_completion_tokens": max_output_tokens,
        }
        if self.reasoning_effort and "non-reasoning" not in self.model:
            body["reasoning_effort"] = self.reasoning_effort
        else:
            body["temperature"] = 0.3  # steady wording; reasoning models pick their own
        return body

    def complete_json(self, system: str, user: str, schema_name: str, schema: dict[str, Any],
                      max_output_tokens: int) -> LLMResult:
        body = self._body(system, user, schema_name, schema, max_output_tokens)
        t0 = time.perf_counter()
        response = None
        for attempt in (1, 2):
            try:
                response = self._http.post("/chat/completions", json=body)
            except httpx.TransportError as exc:
                if attempt == 2:
                    raise LLMError(f"could not reach the AI service ({type(exc).__name__})") \
                        from exc
                time.sleep(2)
                continue
            if response.status_code in RETRY_STATUSES and attempt == 1:
                time.sleep(2)
                continue
            break
        assert response is not None
        if response.status_code != 200:
            raise LLMError(f"AI service returned HTTP {response.status_code}: "
                           f"{response.text[:200]}")
        payload = response.json()
        choice = payload["choices"][0]
        if choice.get("finish_reason") == "length":
            raise LLMError("the AI answer was cut off (output limit reached)")
        try:
            data = json.loads(choice["message"]["content"])
        except (TypeError, json.JSONDecodeError) as exc:
            raise LLMError("the AI answer was not valid JSON") from exc
        usage = payload.get("usage") or {}
        return LLMResult(
            data=data,
            model=payload.get("model") or self.model,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            cached_tokens=int((usage.get("prompt_tokens_details") or {}).get("cached_tokens")
                              or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            reasoning_tokens=int((usage.get("completion_tokens_details") or {})
                                 .get("reasoning_tokens") or 0),
            seconds=round(time.perf_counter() - t0, 2),
        )


def client_from_settings() -> LLMClient | None:
    """The configured client, or None when no key/model is set (reports are then skipped)."""
    from app.config import get_settings

    s = get_settings()
    key = s.xai_api_key.get_secret_value()
    model = s.xai_model or s.xai_model_dev
    if not key or not model:
        return None
    return LLMClient(key, s.xai_base_url, model, reasoning_effort=s.xai_reasoning_effort)
