"""Alerts: the rules (offline) and, with `make check-db`, region-wide matching against TigerData:
one simulated storm must alert two accounts with nearby fields exactly once."""

import json
import uuid
from datetime import date
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

from app import auth
from app.alerts import service, sources, templates, triggers
from app.api import accounts, alerts, routes
from app.config import get_settings
from app.main import app

SHOWCASE = Path(__file__).resolve().parents[2] / "data" / "showcase" / "tagum-rice.json"


# --- rules -----------------------------------------------------------------------------------

def test_haversine_is_about_right():
    # Manila to Cebu is about 570 km.
    assert 540 < triggers.haversine_km(14.6, 121.0, 10.3, 123.9) < 600


def test_storm_moving_toward_the_field_counts_as_approaching():
    field = (15.6, 120.9)
    toward = [(125.0, 15.6), (123.0, 15.6)]
    away = [(123.0, 15.6), (125.0, 15.6)]
    assert triggers.approaching(toward, *field)
    assert not triggers.approaching(away, *field)


@pytest.mark.parametrize(("mm", "normal", "expected"), [
    (None, 5, None), (20, 5, None), (70, 10, "watch"), (120, 10, "warning"),
    (35, 4, "watch"), (35, 10, None),
])
def test_heavy_rain_thresholds(mm, normal, expected):
    assert triggers.heavy_rain(mm, normal) == expected


def test_drought_uses_the_newest_month():
    normal = [0.30] * 12
    recent = [0.29] * 11 + [0.15]
    months = [f"2026-{m:02d}" for m in range(1, 13)]
    hit = triggers.drought(recent, normal, months)
    assert hit is not None and hit.severity == "warning" and hit.month == "2026-12"
    assert triggers.drought([0.28] * 12, normal, months) is None


RULE = {"pest": "bacterial leaf blight", "crops": "rice", "description": "warm and humid",
        "t_min_c": "25", "t_max_c": "34", "rh_min_pct": "70", "rh_max_pct": "",
        "rain_min_mm_day": "", "consecutive_days": "2", "source": "IRRI"}


def day(d, t, rh):
    return {"date": date(2026, 11, d), "T2M": t, "RH2M": rh, "PRECTOTCORR": 0.0}


def test_pest_rule_needs_enough_days_in_a_row_and_a_crop_the_farmer_grows():
    wet = [day(1, 28, 80), day(2, 20, 80), day(3, 29, 85), day(4, 30, 88)]
    hits = triggers.pest_hits([RULE], wet, {"rice"})
    assert len(hits) == 1 and hits[0].days == 2 and hits[0].last_day == date(2026, 11, 4)
    assert triggers.pest_hits([RULE], wet, {"maize"}) == []
    assert triggers.pest_hits([RULE], [day(1, 28, 80), day(2, 20, 80)], {"rice"}) == []


def test_pest_alerts_say_conditions_favor_never_an_outbreak():
    for lang in ("en", "tl"):
        text = templates.render("pest_risk", lang, field="North", pest="blast", crop="rice",
                                rule=triggers.rule_text(RULE))
        assert "outbreak" in text.lower()
    en = templates.render("pest_risk", "en", field="North", pest="blast", crop="rice", rule="x")
    assert "favors" in en and "check your field" in en and "not a confirmed outbreak" in en
    assert triggers.rule_text(RULE) == "25-34 °C and humidity above 70% for 2+ days in a row"


def test_unknown_language_falls_back_to_english():
    assert templates.render("fire", "sw", distance=3, field="A", days=2).startswith("Active fire")


def test_eonet_parsing_keeps_hazards_and_the_track_order():
    payload = {"events": [
        {"id": "EONET_1", "title": "Typhoon Test", "link": "x",
         "categories": [{"id": "severeStorms"}],
         "geometry": [{"type": "Point", "date": "2026-11-12T00:00:00Z", "coordinates": [125, 15]},
                      {"type": "Point", "date": "2026-11-11T00:00:00Z", "coordinates": [127, 14]}]},
        {"id": "EONET_2", "title": "Iceberg", "categories": [{"id": "seaLakeIce"}],
         "geometry": [{"type": "Point", "date": "2026-11-12", "coordinates": [0, -70]}]},
    ]}
    events = sources.parse_eonet(payload)
    assert [e.id for e in events] == ["EONET_1"]
    assert events[0].track == [(127.0, 14.0), (125.0, 15.0)]
    assert events[0].geometry["type"] == "MultiPoint"


def test_firms_csv_parsing():
    text = ("latitude,longitude,bright_ti4,acq_date,satellite,confidence\n"
            "15.61,120.91,330,2026-11-14,N20,n\n")
    fires = sources.parse_firms(text)
    assert len(fires) == 1 and fires[0].lat == 15.61


# --- endpoints and live matching -------------------------------------------------------------

@pytest.fixture
def client(monkeypatch):
    def fake_decode(token: str) -> dict:
        if not token.startswith("token-"):
            raise jwt.InvalidSignatureError("bad")
        return {"sub": token.removeprefix("token-"), "exp": 9e9, "iat": 0}

    monkeypatch.setattr(auth, "decode_token", fake_decode)
    monkeypatch.setattr(accounts, "email_of", lambda user: None)
    monkeypatch.setattr(routes, "get_llm", lambda: None)
    for limiter in (alerts.check_limit, accounts.save_limit):
        limiter._hits.clear()
    return TestClient(app)


def bearer(sub):
    return {"Authorization": f"Bearer token-{sub}"}


def test_one_failing_field_does_not_stop_the_others_or_delivery(monkeypatch):
    fields = [{"id": "f1"}, {"id": "f2"}, {"id": "f3"}]
    delivered = []

    def check(field):
        if field["id"] == "f2":
            raise RuntimeError("field deleted mid-run")
        return [f"alert-{field['id']}"]

    monkeypatch.setattr(service, "refresh_events", lambda age: None)
    monkeypatch.setattr(service, "match_events", lambda: ["storm"])
    monkeypatch.setattr(service, "_fields", lambda sub: fields)
    monkeypatch.setattr(service, "check_field", check)
    monkeypatch.setattr(service, "deliver", delivered.extend)
    assert service.run_check(None)["new"] == 3
    assert delivered == ["storm", "alert-f1", "alert-f3"]


def test_alert_routes_need_login(client):
    assert client.get("/alerts").status_code == 401
    assert client.post("/alerts/check", json={}).status_code == 401


def test_there_is_no_simulate_route_for_users(client):
    # Simulations are admin-only (scripts/simulate_storm.py): no user can fake an alert.
    r = client.post("/alerts/simulate", headers=bearer("anyone"), json={"field_id": "x"})
    assert r.status_code in (404, 405)


def test_simulating_an_unknown_farm_fails():
    with pytest.raises(LookupError):
        service.simulate("not-a-farm")


def test_push_key_is_public(client):
    r = client.get("/alerts/push-key")
    assert r.status_code == 200 and "public_key" in r.json()


def _save_field(client, sub, lon, lat, name):
    stored = json.loads(SHOWCASE.read_text())
    farms = json.loads((SHOWCASE.parents[1] / "showcase_farms.json").read_text())["farms"]
    farm = next(f for f in farms if f["id"] == stored["farm_id"])
    analysis = json.loads(json.dumps(stored["analysis"]))
    geometry = {"type": "Point", "coordinates": [lon, lat]}
    from app.data.geometry import geom_hash
    analysis["field"]["geom_hash"] = geom_hash(geometry)
    request = {"geometry": geometry, "mode": "quick", "answers": farm["answers"],
               "report_languages": ["en"]}
    r = client.post("/analyses/save", headers=bearer(sub),
                    json={"request": request, "analysis": analysis, "field_name": name})
    assert r.status_code == 200, r.text
    return r.json()["field_id"]


@pytest.fixture
def two_farmers(client):
    if not get_settings().database_url.get_secret_value():
        pytest.skip("DATABASE_URL is not set")
    subs = [f"test|{uuid.uuid4().hex[:12]}", f"test|{uuid.uuid4().hex[:12]}"]
    with service._conn() as conn:
        started = conn.execute("SELECT now() AS t").fetchone()["t"]
    yield subs
    for sub in subs:
        client.delete("/me", headers=bearer(sub))
    with service._conn() as conn:  # simulated storms made by these tests must not alert others
        conn.execute("DELETE FROM alerts WHERE source_event_id IN (SELECT id FROM natural_events"
                     " WHERE simulated AND seen_at >= %s)", (started,))
        conn.execute("DELETE FROM natural_events WHERE simulated AND seen_at >= %s", (started,))


@pytest.mark.db
def test_one_simulated_storm_alerts_both_nearby_farmers_once(client, two_farmers, monkeypatch):
    monkeypatch.setattr(service, "deliver", lambda ids: None)  # no email/push from tests
    alice, bob = two_farmers
    _save_field(client, alice, 125.7513, 7.4945, "Alice's paddy")
    _save_field(client, bob, 125.79, 7.51, "Bob's paddy")  # about 5 km away

    first = service.simulate("tagum-rice")
    assert first["new"] >= 2
    again = service.simulate("tagum-rice")
    assert again["event_id"] == first["event_id"] and again["new"] == 0  # no duplicates

    for sub in (alice, bob):
        storm = [a for a in client.get("/alerts", headers=bearer(sub)).json()
                 if a["type"] == "natural_event" and a["data"]["category"] == "severeStorms"]
        assert len(storm) == 1, sub
        assert storm[0]["message"].startswith("(Simulation for the demo)")
        assert storm[0]["data"]["approaching"] is True

    alert_id = client.get("/alerts", headers=bearer(bob)).json()[0]["id"]
    assert client.post(f"/alerts/{alert_id}/read", headers=bearer(bob)).status_code == 204
    assert client.post(f"/alerts/{alert_id}/read", headers=bearer(alice)).status_code == 404


@pytest.mark.db
def test_turning_off_natural_events_stops_them(client, two_farmers, monkeypatch):
    monkeypatch.setattr(service, "deliver", lambda ids: None)
    alice, bob = two_farmers
    _save_field(client, alice, 125.7513, 7.4945, "A")
    field_b = _save_field(client, bob, 125.79, 7.51, "B")
    r = client.put("/alerts/preferences", headers=bearer(bob),
                   json={"field_id": field_b, "alert_types": ["fire"], "email": False,
                         "push": False})
    assert r.status_code == 204
    service.simulate("tagum-rice", fresh=True)
    assert not [a for a in client.get("/alerts", headers=bearer(bob)).json()
                if a["type"] == "natural_event"]
