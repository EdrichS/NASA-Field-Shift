"""Showcase farms: the committed pre-computed analyses are complete and current, and the
endpoints serve them without any outside call."""

import pytest
from conftest import POINT
from fastapi.testclient import TestClient

from app.ai.prompts import PROMPT_VERSION
from app.api import routes, showcase
from app.main import app
from app.schemas import AnalyzeResponse

FARMS = showcase.farms()
client = TestClient(app)


@pytest.mark.parametrize("farm", FARMS, ids=[f["id"] for f in FARMS])
def test_committed_showcase_analysis_is_complete_and_current(farm):
    entry = showcase.stored(farm["id"])
    assert entry is not None, "run `make showcase` to pre-compute this farm"
    analysis = AnalyzeResponse.model_validate(entry["analysis"])
    assert len(analysis.strategies) >= 4  # current + 3 or 4 alternatives
    assert entry["request_key"] == showcase.request_key(showcase.request_for(farm)), \
        "the farm's answers changed since the last `make showcase`"
    for lang in farm["report_languages"]:
        report = analysis.reports_tier1[lang]
        assert report is not None and report.checks["numbers_ok"], lang
        assert report.meta["prompt_version"] == PROMPT_VERSION, \
            "the prompt changed since the last `make showcase`"
        assert len(report.content["strategies"]) == len(analysis.strategies)


def test_showcase_endpoints_list_and_serve_the_farms():
    farms = client.get("/showcase").json()
    assert [f["id"] for f in farms] == [f["id"] for f in FARMS]
    assert all(f["available"] and f["generated_at"] for f in farms)
    r = client.get(f"/showcase/{FARMS[0]['id']}")
    assert r.status_code == 200 and len(r.json()["strategies"]) == 5
    assert client.get("/showcase/nowhere").status_code == 404
    assert client.get("/showcase/..%2F..%2F.env").status_code == 404


def test_analyze_serves_a_showcase_farm_without_fetching_anything(monkeypatch):
    def no_fetch(*args, **kwargs):
        raise AssertionError("a showcase request must not fetch data")

    monkeypatch.setattr(routes, "get_features", no_fetch)
    routes.analyze_limit._hits.clear()
    body = showcase.request_for(FARMS[0]).model_dump()
    r = client.post("/analyze", json=body)
    assert r.status_code == 200 and r.json()["reports_tier1"]["en"]["content"]["summary"]


def test_only_exact_showcase_requests_use_the_stored_copy():
    farm = FARMS[0]
    assert showcase.match(showcase.request_for(farm)) is not None
    assert showcase.match(showcase.request_for(farm, generate_reports=False)) is None
    other = showcase.request_for(farm).model_copy(update={"geometry": POINT | {
        "coordinates": [121.0, 15.6]}})
    assert showcase.match(other) is None
