"""API tests for /prefill and /analyze. Offline: the data fetch is swapped for the Philippines
fixtures and the crop catalog comes from the CSV + EcoCrop fixture."""

import pytest
from conftest import POINT, SHOWCASE
from fastapi.testclient import TestClient

from app.api import routes
from app.main import app


@pytest.fixture
def client(monkeypatch, tmp_path, ph_ff, catalog):
    """A test client whose data fetch returns `state["ff"]`, with no AI configured and no stored
    showcase files; rate limits reset per test."""
    state = {"ff": ph_ff}
    monkeypatch.setattr(routes.showcase, "SHOWCASE_DIR", tmp_path)
    monkeypatch.setattr(routes, "get_features", lambda geometry, tasks=None: state["ff"])
    monkeypatch.setattr(routes, "crop_catalog", lambda: catalog)
    monkeypatch.setattr(routes, "get_llm", lambda: None)
    monkeypatch.setattr(routes, "get_country", lambda ff: "Philippines")
    for limiter in (routes.prefill_limit, routes.analyze_limit, routes.followup_limit,
                    routes.ai_call_limit):
        limiter._hits.clear()
    c = TestClient(app)
    c.state = state
    return c


def test_prefill_returns_cards_with_evidence(client, ph_ff):
    r = client.post("/prefill", json={"geometry": POINT})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["warning"] is None
    assert body["field"]["lat"] == 15.6 and body["field"]["geom_hash"] == ph_ff.geom_hash
    ids = [c["id"] for c in body["cards"]]
    assert ids[0] == "land_cover" and {"rain", "slope", "soil", "frost"} <= set(ids)
    assert all(c["evidence"] and c["confidence"] in {"high", "medium", "low"}
               for c in body["cards"])


def test_analyze_showcase_farm_returns_four_ranked_strategies(client):
    farm = SHOWCASE[0]
    r = client.post("/analyze", json={"geometry": POINT, "mode": "quick",
                                      "answers": farm["answers"],
                                      "report_languages": ["en", "tl"]})
    assert r.status_code == 200, r.text
    body = r.json()
    strategies = body["strategies"]
    assert len(strategies) == 4
    assert sorted(s["rank"] for s in strategies) == [1, 2, 3, 4]
    assert {s["key"] for s in strategies} == {"current", "fill_bare", "break_pest", "save_water"}
    assert all(len(s["calendar"]) == 12 for s in strategies)
    assert body["profile"]["water"] == "irrigated"
    assert body["reports_tier1"] == {"en": None, "tl": None}  # no AI configured in this test
    assert {v["status"] for v in body["report_status"].values()} == {"unavailable"}
    assert body["disclaimer"] and len(body["stress_calendar"]) == 12
    assert set(body["timings_ms"]) == {"data", "engine", "reports"}
    assert "rain" in body["features"] and "land_cover" in body["static"]


def test_analyze_just_exploring_needs_no_answers(client):
    r = client.post("/analyze", json={"geometry": POINT, "mode": "exploring"})
    assert r.status_code == 200, r.text
    keys = [s["key"] for s in r.json()["strategies"]]
    assert "current" not in keys and len(keys) == 3  # starting options, no comparison
    assert r.json()["reports_tier1"] == {"en": None}


@pytest.mark.parametrize("payload", [
    {"geometry": {"type": "Point", "coordinates": [200, 15]}},
    {"geometry": {"type": "LineString", "coordinates": [[120, 15], [121, 15]]}},
    {"geometry": POINT, "report_languages": ["en", "tl", "es"]},
    {"geometry": POINT, "report_languages": ["xx"]},
    {"geometry": POINT, "report_languages": []},
    {"geometry": POINT, "mode": "expert"},
    {"geometry": POINT, "answers": {"current_crops": [
        {"crop": "rice", "plant_month": 13, "harvest_month": 4}]}},
    {"geometry": POINT, "answers": {"water": "lots"}},
])
def test_bad_requests_are_rejected_with_422(client, payload):
    assert client.post("/analyze", json=payload).status_code == 422


def test_duplicate_languages_are_merged(client):
    r = client.post("/analyze", json={"geometry": POINT, "report_languages": ["tl", "tl"]})
    assert r.status_code == 200 and r.json()["reports_tier1"] == {"tl": None}


def test_open_water_gets_a_friendly_message_not_an_error_page(client, make_ph):
    client.state["ff"] = make_ph(land_cover={"Map": {}})
    r = client.post("/prefill", json={"geometry": POINT})
    assert r.status_code == 200
    assert "water" in r.json()["warning"] and r.json()["cards"] == []
    r = client.post("/analyze", json={"geometry": POINT})
    assert r.status_code == 422 and "water" in r.json()["detail"]


def test_forest_is_allowed_with_a_warning(client, make_ph):
    client.state["ff"] = make_ph(land_cover={"Map": {"10": 900, "40": 100}})
    r = client.post("/analyze", json={"geometry": POINT})
    assert r.status_code == 200
    assert "mostly trees" in r.json()["warning"]


def test_missing_weather_is_a_503_with_a_reason(client, make_ph):
    client.state["ff"] = make_ph(with_power=False)
    r = client.post("/analyze", json={"geometry": POINT})
    assert r.status_code == 503 and "NASA POWER" in r.json()["detail"]


def test_rate_limit_returns_429_with_retry_after(client, monkeypatch):
    monkeypatch.setattr(routes.analyze_limit, "limit", 2)
    for _ in range(2):
        assert client.post("/analyze", json={"geometry": POINT}).status_code == 200
    r = client.post("/analyze", json={"geometry": POINT})
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_rate_limit_is_per_client(client, monkeypatch):
    monkeypatch.setattr(routes.prefill_limit, "limit", 1)
    assert client.post("/prefill", json={"geometry": POINT},
                       headers={"cf-connecting-ip": "1.1.1.1"}).status_code == 200
    assert client.post("/prefill", json={"geometry": POINT},
                       headers={"cf-connecting-ip": "1.1.1.1"}).status_code == 429
    assert client.post("/prefill", json={"geometry": POINT},
                       headers={"cf-connecting-ip": "2.2.2.2"}).status_code == 200
