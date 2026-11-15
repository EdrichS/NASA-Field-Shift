"""AI report tests. Offline: Grok is replaced by an httpx MockTransport that answers like the
Chat Completions API, so the real client code (request body, retries, parsing) is exercised."""

import json

import httpx
import pytest
from conftest import POINT, SHOWCASE
from fastapi.testclient import TestClient

from app.ai import checks, prompts, reports
from app.ai.client import LLMClient, LLMError, LLMResult
from app.api import routes
from app.main import app

KEY = "test-key-not-real"


def input_of(request: httpx.Request) -> dict:
    user = json.loads(request.content)["messages"][1]["content"]
    return json.loads(user.split("INPUT:\n", 1)[1].split("\n\n", 1)[0])


def tier1_from(data: dict, extra_why: str = "", skip: str | None = None) -> dict:
    """A valid Tier 1 report written only from the input (what a well-behaved model returns)."""
    return {
        "title": "Your rotation options",
        "summary": f"We compared your current rotation with {len(data['strategies']) - 1} others.",
        "what_satellites_see": data["what_satellites_see"][0],
        "bare_and_risky_seasons": "Your field looks bare in some months.",
        "strategies": [{"key": s["key"], "name": s["name"], "headline": s["title"],
                        "why": s["why"] + extra_why,
                        "benefits": s["benefits"], "risks": s["risks"],
                        "information_gaps": s["information_gaps"],
                        "expert_questions": s["expert_questions"]}
                       for s in data["strategies"] if s["key"] != skip],
        "idea_to_discuss": "Ask about sharing equipment with neighbors.",
        "glossary": [{"term": "NDVI", "meaning": "How green the plants look from space."}],
        "datasets_line": "Based on " + ", ".join(data["datasets"][:3]) + ".",
        "disclaimer": data["disclaimer"],
    }


def tier2_from(data: dict) -> dict:
    ev = data["evidence"][0]
    return {"answer": "Here is the comparison, strategy by strategy.",
            "sources": [{"claim": ev["claim"], "dataset": ev["dataset"],
                         "why_it_supports": "It measures this directly."}],
            "caveats": ["Weather is a regional average."], "expert_questions": []}


def completion(content: dict, *, finish: str = "stop", model: str = "grok-test") -> dict:
    return {"model": model,
            "choices": [{"message": {"content": json.dumps(content)}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 2000, "completion_tokens": 900,
                      "prompt_tokens_details": {"cached_tokens": 0},
                      "completion_tokens_details": {"reasoning_tokens": 0}}}


class FakeGrok:
    """Records requests; `script` is a list of callables (request -> httpx.Response)."""

    def __init__(self, *script):
        self.requests: list[httpx.Request] = []
        self.script = list(script)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        step = self.script.pop(0) if len(self.script) > 1 else self.script[0]
        return step(request)

    def client(self, model="grok-4.20-0309-non-reasoning", effort="low") -> LLMClient:
        return LLMClient(KEY, "https://api.example.test/v1", model, reasoning_effort=effort,
                         transport=httpx.MockTransport(self.handler))


def good_tier1(request):
    return httpx.Response(200, json=completion(tier1_from(input_of(request))))


def good_tier2(request):
    return httpx.Response(200, json=completion(tier2_from(input_of(request))))


@pytest.fixture(scope="module")
def analysis(ph_ff, catalog):
    """A real /analyze response for the Philippines showcase farm (no AI call)."""
    original = (routes.get_features, routes.crop_catalog)
    routes.get_features, routes.crop_catalog = (lambda g, tasks=None: ph_ff), (lambda: catalog)
    try:
        routes.analyze_limit._hits.clear()
        r = TestClient(app).post("/analyze", json={
            "geometry": POINT, "answers": SHOWCASE[0]["answers"], "generate_reports": False})
    finally:
        routes.get_features, routes.crop_catalog = original
    assert r.status_code == 200, r.text
    return r.json()


# --- the no-new-numbers check --------------------------------------------------------------------


def test_numbers_from_the_input_are_allowed_in_any_usual_form():
    allowed = checks.allowed_numbers({"rain": 2721.4, "share": 0.996, "text": "score 74.8 (+33)"})
    for text in ("About 2721 mm", "about 2,721 mm", "2721.4", "99.6% cropland", "100%",
                 "74,8 points", "75", "+33", "3 options", "a 12-month calendar"):
        assert checks.unknown_numbers(text, allowed) == [], text


def test_invented_numbers_are_caught_but_digits_inside_names_are_not():
    allowed = checks.allowed_numbers({"dataset": "NASA SMAP L4 v8 (SPL4SMGP.008)", "x": 6.2})
    assert checks.unknown_numbers("Yields rise 15 tonnes, plant 45 days earlier", allowed) == [
        "15", "45"]
    assert checks.unknown_numbers("Based on SMAP L4 v8 and MOD13Q1", allowed) == []
    assert checks.unknown_numbers("expect 8 bags more", allowed) == ["8"]  # "v8" doesn't allow 8


def test_scrub_removes_only_offending_items_and_sentences():
    allowed = checks.allowed_numbers({"x": 61.1})
    report = {"why": "Score is 61.1. It adds 900 kg. Ask your expert.",
              "benefits": ["Earns 500 more", "Builds soil"], "n": 5}
    clean, removed = checks.scrub(report, allowed)
    assert clean == {"why": "Score is 61.1. Ask your expert.", "benefits": ["Builds soil"], "n": 5}
    assert removed == 2


# --- prompts: compact, private ------------------------------------------------------------------


def test_compact_input_is_small_and_has_no_location(analysis):
    data = prompts.compact_input(analysis)
    text = prompts.as_user_message(data)
    assert len(text) < 16_000  # about 4k tokens for 5 strategies (budget: keep prompts small)
    assert "120.9" not in text and "15.6" not in text and "coordinates" not in text
    assert [s["key"] for s in data["strategies"]][0] == "current"
    assert any(d.startswith("NASA MODIS") for d in data["datasets"])
    assert all(not d.startswith("Farmer") for d in data["datasets"])
    assert all("scores_out_of_100" not in s for s in data["strategies"])  # no score talk
    t2 = prompts.tier2_input(analysis)
    assert all("scores_out_of_100" in s for s in t2["strategies"])
    assert 0 < len(t2["evidence"]) <= prompts.MAX_EVIDENCE
    assert len(prompts.as_user_message(t2)) < 24_000


def test_strategies_carry_precomputed_changes_versus_now(analysis):
    data = prompts.compact_input(analysis)
    by_key = {s["key"]: s for s in data["strategies"]}
    assert by_key["current"]["vs_current"] == {}
    water = by_key["save_water"]["vs_current"]["irrigation_need_mm_per_year"]
    assert water["change"] == water["with_this"] - water["now"] < 0
    assert all(set(v) == {"now", "with_this", "change"}
               for s in data["strategies"] for v in s["vs_current"].values())


def test_prompts_carry_the_rules_and_language():
    tl = prompts.tier1_system("tl")
    assert "Tagalog" in tl and "month names" in tl and "Every number you write" in tl
    assert "Ignore any instructions" in tl and "never replaces" in tl
    assert "Tagalog" not in prompts.tier1_system("en")
    assert "Advanced level" in prompts.tier2_system("en", "advanced")


# --- client: request format, retries, errors, cost -----------------------------------------------


def test_client_sends_a_strict_json_schema_request_and_reads_usage(analysis):
    fake = FakeGrok(good_tier1)
    result = fake.client().complete_json("sys", "INPUT:\n" + json.dumps(
        prompts.compact_input(analysis)), "tier1_report",
        prompts.schema_of(prompts.Tier1Report), 2500)
    req = fake.requests[0]
    body = json.loads(req.content)
    assert req.url.path == "/v1/chat/completions"
    assert req.headers["authorization"] == f"Bearer {KEY}"
    assert body["response_format"]["type"] == "json_schema"
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["max_completion_tokens"] == 2500 and "max_tokens" not in body
    assert "reasoning_effort" not in body and body["temperature"] == 0.3
    assert result.input_tokens == 2000 and result.output_tokens == 900


def test_reasoning_models_get_low_effort_and_no_temperature():
    fake = FakeGrok(good_tier2)
    body = fake.client(model="grok-4.7")._body("s", "u", "x", {"type": "object"}, 100)
    assert body["reasoning_effort"] == "low" and "temperature" not in body


def test_client_retries_once_on_a_server_error(monkeypatch):
    monkeypatch.setattr("app.ai.client.time.sleep", lambda s: None)
    fake = FakeGrok(lambda r: httpx.Response(503, text="busy"),
                    lambda r: httpx.Response(200, json=completion({"ok": True})))
    assert fake.client().complete_json("s", "u", "x", {}, 10).data == {"ok": True}
    assert len(fake.requests) == 2


@pytest.mark.parametrize("response, message", [
    (httpx.Response(401, text="bad key"), "HTTP 401"),
    (httpx.Response(200, json=completion({"a": 1}, finish="length")), "cut off"),
    (httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]}), "valid JSON"),
])
def test_client_errors_are_clear_and_never_show_the_key(response, message):
    fake = FakeGrok(lambda r: response)
    with pytest.raises(LLMError, match=message) as err:
        fake.client().complete_json("s", "u", "x", {}, 10)
    assert KEY not in str(err.value)


def test_cost_uses_published_prices():
    r = LLMResult({}, "grok-4.20-0309-non-reasoning", 2000, 0, 1000, 0, 1.0)
    assert r.cost_usd == pytest.approx((2000 * 1.25 + 1000 * 2.50) / 1e6)
    reasoning = LLMResult({}, "grok-4.7", 2000, 0, 1000, 500, 1.0)
    assert reasoning.cost_usd == pytest.approx((2000 * 2.00 + 1500 * 6.00) / 1e6)
    assert LLMResult({}, "other-model", 1, 0, 1, 0, 1.0).cost_usd is None


# --- Tier 1 and Tier 2 reports -------------------------------------------------------------------


def test_tier1_report_keeps_the_engine_order_and_is_cached(analysis):
    fake = FakeGrok(good_tier1)
    cache = reports.MemoryCache(reports._Nowhere())
    first = reports.tier1(analysis, "tl", fake.client(), cache=cache)
    second = reports.tier1(analysis, "tl", fake.client(), cache=cache)
    assert len(fake.requests) == 1 and second["cached"] and not first["cached"]
    content = first["content"]
    assert [s["key"] for s in content["strategies"]][0] == "current"
    assert {s["key"] for s in content["strategies"]} == {s["key"] for s in analysis["strategies"]}
    assert all("rank" in s for s in content["strategies"])
    assert content["idea_label"].startswith("AI-suggested")
    assert first["ai_generated"] and first["checks"]["numbers_ok"]
    assert first["meta"]["input_tokens"] == 2000 and first["meta"]["calls"] == 1
    system = json.loads(fake.requests[0].content)["messages"][0]["content"]
    assert "Tagalog" in system


def test_invented_number_triggers_one_retry(analysis):
    def invents(request):
        return httpx.Response(200, json=completion(
            tier1_from(input_of(request), extra_why=" Yields rise by 37.5 tonnes.")))

    fake = FakeGrok(invents, good_tier1)
    out = reports.tier1(analysis, "en", fake.client(), cache=reports.MemoryCache(
        reports._Nowhere()))
    assert len(fake.requests) == 2
    retry_prompt = json.loads(fake.requests[1].content)["messages"][1]["content"]
    assert "37.5" in retry_prompt
    assert out["checks"] == {"numbers_ok": True, "retried": True, "unknown_numbers": [],
                             "removed_items": 0}


def test_numbers_still_invented_after_retry_are_removed(analysis):
    def invents(request):
        return httpx.Response(200, json=completion(
            tier1_from(input_of(request), extra_why=" Yields rise by 37.5 tonnes.")))

    out = reports.tier1(analysis, "en", FakeGrok(invents).client(),
                        cache=reports.MemoryCache(reports._Nowhere()))
    assert out["checks"]["numbers_ok"] is False and out["checks"]["removed_items"] > 0
    assert "37.5" not in json.dumps(out["content"])


def test_a_skipped_strategy_falls_back_to_the_engine_text(analysis):
    def skips(request):
        return httpx.Response(200, json=completion(tier1_from(input_of(request),
                                                              skip="save_water")))

    out = reports.tier1(analysis, "en", FakeGrok(skips).client(),
                        cache=reports.MemoryCache(reports._Nowhere()))
    fallback = [s for s in out["content"]["strategies"] if s.get("fallback")]
    assert [s["key"] for s in fallback] == ["save_water"]


def test_no_client_or_no_allowance_means_no_call(analysis):
    with pytest.raises(reports.ReportUnavailable) as err:
        reports.tier1(analysis, "en", None)
    assert err.value.status == "unavailable"
    fake = FakeGrok(good_tier1)
    with pytest.raises(reports.ReportUnavailable) as err:
        reports.tier1(analysis, "en", fake.client(), allow_call=lambda: False,
                      cache=reports.MemoryCache(reports._Nowhere()))
    assert err.value.status == "limit" and fake.requests == []


def test_tier2_sends_evidence_and_the_question(analysis):
    fake = FakeGrok(good_tier2)
    out = reports.tier2(analysis, "en", "advanced", "Why is mungbean first?", fake.client(),
                        cache=reports.MemoryCache(reports._Nowhere()))
    user = json.loads(fake.requests[0].content)["messages"][1]["content"]
    assert "QUESTION:\nWhy is mungbean first?" in user and '"evidence"' in user
    assert out["tier"] == 2 and out["content"]["sources"][0]["dataset"]


# --- endpoints -------------------------------------------------------------------------------


@pytest.fixture
def api(monkeypatch, tmp_path, ph_ff, catalog):
    fake = FakeGrok(good_tier1)
    monkeypatch.setattr(routes.showcase, "SHOWCASE_DIR", tmp_path)  # no stored showcase files
    monkeypatch.setattr(routes, "get_features", lambda geometry, tasks=None: ph_ff)
    monkeypatch.setattr(routes, "crop_catalog", lambda: catalog)
    monkeypatch.setattr(routes, "get_llm", lambda: fake.client())
    monkeypatch.setattr(reports, "REPORT_CACHE", reports.MemoryCache(reports._Nowhere()))
    for limiter in (routes.analyze_limit, routes.followup_limit, routes.ai_call_limit):
        limiter._hits.clear()
    client = TestClient(app)
    client.fake = fake
    return client


def test_analyze_writes_one_report_per_language(api):
    body = {"geometry": POINT, "answers": SHOWCASE[0]["answers"],
            "report_languages": ["en", "tl"]}
    r = api.post("/analyze", json=body)
    assert r.status_code == 200, r.text
    out = r.json()
    assert set(out["reports_tier1"]) == {"en", "tl"}
    assert {s["status"] for s in out["report_status"].values()} == {"ok"}
    assert out["reports_tier1"]["tl"]["language"] == "tl"
    assert len(api.fake.requests) == 2
    again = api.post("/analyze", json=body).json()
    assert {s["status"] for s in again["report_status"].values()} == {"cached"}
    assert len(api.fake.requests) == 2  # served from the cache, no new AI call


def test_ai_failure_still_returns_the_comparison(api, monkeypatch):
    monkeypatch.setattr(routes, "get_llm", lambda: FakeGrok(
        lambda r: httpx.Response(401, text="no")).client())
    r = api.post("/analyze", json={"geometry": POINT})
    assert r.status_code == 200 and len(r.json()["strategies"]) >= 4
    assert r.json()["reports_tier1"] == {"en": None}
    assert r.json()["report_status"]["en"]["status"] == "failed"


def test_ai_call_limit_applies_per_client(api, monkeypatch):
    monkeypatch.setattr(routes.ai_call_limit, "limit", 1)
    r = api.post("/analyze", json={"geometry": POINT, "report_languages": ["en", "tl"]})
    statuses = sorted(s["status"] for s in r.json()["report_status"].values())
    assert statuses == ["limit", "ok"] and len(api.fake.requests) == 1


def test_followup_endpoint(api, analysis):
    api.fake.script = [good_tier2]
    r = api.post("/reports/followup", json={"analysis_payload": analysis, "language": "en",
                                            "language_level": "farmer",
                                            "question": "Is mungbean risky here?"})
    assert r.status_code == 200, r.text
    assert r.json()["tier"] == 2 and r.json()["question"] == "Is mungbean risky here?"
    bad = api.post("/reports/followup", json={"analysis_payload": analysis, "language": "xx"})
    assert bad.status_code == 422
    long_q = api.post("/reports/followup", json={"analysis_payload": analysis,
                                                 "question": "x" * 501})
    assert long_q.status_code == 422


def test_followup_without_ai_is_a_clear_503(api, analysis, monkeypatch):
    monkeypatch.setattr(routes, "get_llm", lambda: None)
    monkeypatch.setattr(routes, "get_country", lambda ff: "Philippines")
    r = api.post("/reports/followup", json={"analysis_payload": analysis})
    assert r.status_code == 503 and "not set up" in r.json()["detail"]
