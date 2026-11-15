"""Signed-in endpoints (step 3.4).

Offline tests: tokens are required and checked. Live tests (`make check-db`): save, list, read,
"new findings", stored follow-ups and "delete my data" against TigerData, with throwaway users
that are deleted at the end. Auth0 itself is faked: decode_token returns the test user's claims.
"""

import json
import uuid
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

from app import auth
from app.api import accounts, routes
from app.config import get_settings
from app.main import app

SHOWCASE = Path(__file__).resolve().parents[2] / "data" / "showcase" / "tagum-rice.json"


@pytest.fixture
def client(monkeypatch):
    """Tokens are 'token-<sub>'; anything else is rejected like a bad signature."""
    def fake_decode(token: str) -> dict:
        if not token.startswith("token-"):
            raise jwt.InvalidSignatureError("bad signature")
        return {"sub": token.removeprefix("token-"), "exp": 9e9, "iat": 0}

    monkeypatch.setattr(auth, "decode_token", fake_decode)
    monkeypatch.setattr(accounts, "email_of", lambda user: None)
    monkeypatch.setattr(routes, "get_llm", lambda: None)
    accounts.save_limit._hits.clear()
    routes.followup_limit._hits.clear()
    return TestClient(app)


def bearer(sub: str) -> dict[str, str]:
    return {"Authorization": f"Bearer token-{sub}"}


def test_signed_in_routes_need_a_token(client):
    for method, path in [("get", "/me"), ("get", "/fields"), ("delete", "/me"),
                         ("post", "/analyses/save"), ("get", f"/analyses/{uuid.uuid4()}")]:
        r = getattr(client, method)(path)
        assert r.status_code == 401, (path, r.status_code)


def test_bad_token_is_401_not_500(client):
    r = client.get("/me", headers={"Authorization": "Bearer forged"})
    assert r.status_code == 401
    assert "log in again" in r.json()["detail"]


def test_real_decoder_refuses_when_auth0_is_not_configured(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth0_domain", "")
    with pytest.raises(jwt.InvalidTokenError):
        auth.decode_token("anything")


def test_followup_needs_an_analysis(client):
    r = client.post("/reports/followup", json={"language": "en"})
    assert r.status_code == 422


def test_followup_on_saved_analysis_needs_login(client):
    r = client.post("/reports/followup", json={"analysis_id": str(uuid.uuid4())})
    assert r.status_code == 401


# --- live, against TigerData -------------------------------------------------------------

def _stored():
    stored = json.loads(SHOWCASE.read_text())
    farm = next(f for f in json.loads(
        (SHOWCASE.parents[1] / "showcase_farms.json").read_text())["farms"]
        if f["id"] == stored["farm_id"])
    request = {"geometry": farm["geometry"], "mode": "quick", "answers": farm["answers"],
               "report_languages": farm["report_languages"]}
    return request, stored["analysis"]


@pytest.fixture
def users(client):
    if not get_settings().database_url.get_secret_value():
        pytest.skip("DATABASE_URL is not set")
    subs = [f"test|{uuid.uuid4().hex[:12]}", f"test|{uuid.uuid4().hex[:12]}"]
    yield subs
    for sub in subs:
        client.delete("/me", headers=bearer(sub))


@pytest.mark.db
def test_save_list_read_and_isolation(client, users):
    alice, bob = users
    request, analysis = _stored()
    r = client.post("/analyses/save", headers=bearer(alice),
                    json={"request": request, "analysis": analysis, "field_name": "North paddy",
                          "input_mode": "point"})
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["new_findings"] is False

    me = client.get("/me", headers=bearer(alice)).json()
    assert [f["name"] for f in me["fields"]] == ["North paddy"]
    field = me["fields"][0]
    top = min(analysis["strategies"], key=lambda s: s["rank"])["key"]
    assert field["analysis_id"] == saved["analysis_id"] and field["top_strategy"] == top
    assert round(field["lat"], 1) == 7.5 and field["area_ha"] == pytest.approx(19.63, abs=0.01)
    assert "natural_event" in field["alert_types"]

    got = client.get(f"/analyses/{saved['analysis_id']}", headers=bearer(alice))
    assert got.status_code == 200 and got.json()["analysis_id"] == saved["analysis_id"]
    assert got.json()["reports_tier1"]["tl"]["content"]["summary"]

    # Bob can't see Alice's field or analysis.
    assert client.get("/me", headers=bearer(bob)).json()["fields"] == []
    assert client.get(f"/analyses/{saved['analysis_id']}", headers=bearer(bob)).status_code == 404
    assert client.delete(f"/fields/{saved['field_id']}", headers=bearer(bob)).status_code == 404


@pytest.mark.db
def test_saving_again_reuses_the_field_and_flags_new_findings(client, users):
    alice, _ = users
    request, analysis = _stored()
    first = client.post("/analyses/save", headers=bearer(alice),
                        json={"request": request, "analysis": analysis}).json()
    changed = json.loads(json.dumps(analysis))
    for s in changed["strategies"]:  # pretend the ranking changed: #1 and #2 swap
        s["rank"] = {1: 2, 2: 1}.get(s["rank"], s["rank"])
    second = client.post("/analyses/save", headers=bearer(alice),
                         json={"request": request, "analysis": changed}).json()
    assert second["field_id"] == first["field_id"]
    assert second["new_findings"] is True
    me = client.get("/me", headers=bearer(alice)).json()
    assert len(me["fields"]) == 1 and me["fields"][0]["unread"] == 1


@pytest.mark.db
def test_mismatched_geometry_is_refused(client, users):
    alice, _ = users
    request, analysis = _stored()
    request["geometry"] = {"type": "Point", "coordinates": [0.0, 0.0]}
    r = client.post("/analyses/save", headers=bearer(alice),
                    json={"request": request, "analysis": analysis})
    assert r.status_code == 422


@pytest.mark.db
def test_followup_on_saved_analysis_is_stored_and_reused(client, users, monkeypatch):
    alice, _ = users
    request, analysis = _stored()
    saved = client.post("/analyses/save", headers=bearer(alice),
                        json={"request": request, "analysis": analysis}).json()
    calls = []

    def fake_tier2(analysis, language, level, question, client_, allow_call=None):
        calls.append(question)
        return {"tier": 2, "language": language, "language_level": level, "question": question,
                "ai_generated": True, "cached": False, "checks": {"numbers_ok": True},
                "meta": {"model": "fake"},
                "content": {"answer": "Because mungbean breaks the cycle.", "sources": [],
                            "caveats": [], "expert_questions": []}}

    monkeypatch.setattr(routes.reports, "tier2", fake_tier2)
    body = {"analysis_id": saved["analysis_id"], "language": "en", "question": "Why mungbean?"}
    first = client.post("/reports/followup", headers=bearer(alice), json=body)
    again = client.post("/reports/followup", headers=bearer(alice), json=body)
    assert first.status_code == again.status_code == 200
    assert calls == ["Why mungbean?"] and again.json()["cached"] is True


@pytest.mark.db
def test_delete_my_data_removes_everything(client, users):
    alice, _ = users
    request, analysis = _stored()
    client.post("/analyses/save", headers=bearer(alice),
                json={"request": request, "analysis": analysis})
    assert client.delete("/me", headers=bearer(alice)).status_code == 204
    assert client.get("/me", headers=bearer(alice)).json()["fields"] == []
