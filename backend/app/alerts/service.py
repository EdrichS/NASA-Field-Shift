"""Alert checks, matching and delivery (steps 4.2-4.3).

- Region-wide (NASA EONET): every open event is stored in natural_events and matched with
  PostGIS against ALL saved fields, so every farmer in the affected area is alerted, not only
  the person whose visit triggered the check.
- Field-specific (FIRMS fires, JAXA GSMaP heavy rain, NASA SMAP dry soil, pest-risk weather from
  NASA POWER + pest_rules.csv): run for one user's fields (app open / "Check now"), or for all
  fields in the 6-hourly background job.
- One alert per (field, type, event): the alerts table's unique key makes re-checks harmless.
- Delivery: in-app always; email and browser push per field preference, each sent once.
"""

from __future__ import annotations

import json
import logging
import math
import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from psycopg.types.json import Jsonb

from app.alerts import push, sources, templates, triggers
from app.alerts.email import EmailError, send_email
from app.api import showcase
from app.store import ALERT_TYPES, _conn

log = logging.getLogger(__name__)
CHECK_EVERY = timedelta(hours=6)
_eonet_lock = threading.Lock()
_eonet_checked: datetime | None = None
APP_LINK = "Open SowSmart to see the alert and your field."


# --- region-wide: NASA EONET ---------------------------------------------------------------

def refresh_events(max_age: timedelta = CHECK_EVERY) -> int:
    """Fetch open EONET events (at most every few hours per process) and store them."""
    global _eonet_checked
    with _eonet_lock:
        if _eonet_checked and datetime.now(UTC) - _eonet_checked < max_age:
            return 0
        events = sources.fetch_eonet()
        store_events(events)
        _eonet_checked = datetime.now(UTC)
        return len(events)


def store_events(events: list[sources.NaturalEvent]) -> None:
    with _conn() as conn:
        for e in events:
            conn.execute(
                """INSERT INTO natural_events (id, title, category, geom, event_date, source_url,
                       simulated)
                   VALUES (%s, %s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET geom = EXCLUDED.geom, title = EXCLUDED.title,
                       event_date = EXCLUDED.event_date, seen_at = now()""",
                (e.id, e.title, e.category, json.dumps(e.geometry), e.event_date, e.url,
                 e.simulated))


def match_events(event_ids: list[str] | None = None) -> list[str]:
    """Alert every saved field within each event's radius. Returns new alert ids."""
    new: list[str] = []
    with _conn() as conn:
        rows = conn.execute(
            """SELECT e.id AS event_id, e.title, e.category, e.simulated, e.source_url,
                      f.id AS field_id, f.user_id, f.name AS field_name,
                      COALESCE(u.language, 'en') AS language,
                      ST_Distance(e.geom::geography, f.geom::geography) / 1000 AS km,
                      ST_Y(ST_Centroid(f.geom)) AS lat, ST_X(ST_Centroid(f.geom)) AS lon,
                      ST_AsGeoJSON(e.geom) AS event_geom
                 FROM natural_events e
                 JOIN fields f ON ST_DWithin(e.geom::geography, f.geom::geography,
                     (CASE e.category WHEN 'severeStorms' THEN %(storm)s
                                      WHEN 'floods' THEN %(flood)s
                                      WHEN 'wildfires' THEN %(fire)s
                                      WHEN 'drought' THEN %(drought)s
                                      WHEN 'landslides' THEN %(slide)s
                                      WHEN 'volcanoes' THEN %(volcano)s
                                      ELSE %(temp)s END) * 1000)
                 JOIN users u ON u.id = f.user_id
                 LEFT JOIN alert_preferences p ON p.field_id = f.id AND p.user_id = f.user_id
                WHERE COALESCE(p.alert_types, %(types)s) @> ARRAY['natural_event']
                  AND e.seen_at > now() - interval '30 days'
                  AND (NOT e.simulated OR e.seen_at > now() - interval '6 hours')
                  AND (%(ids)s::text[] IS NULL OR e.id = ANY(%(ids)s))""",
            {"storm": triggers.RADIUS_KM["severeStorms"], "flood": triggers.RADIUS_KM["floods"],
             "fire": triggers.RADIUS_KM["wildfires"], "drought": triggers.RADIUS_KM["drought"],
             "slide": triggers.RADIUS_KM["landslides"], "volcano": triggers.RADIUS_KM["volcanoes"],
             "temp": triggers.RADIUS_KM["tempExtremes"], "types": ALERT_TYPES,
             "ids": event_ids}).fetchall()
        for r in rows:
            geom = json.loads(r["event_geom"])
            track = ([tuple(c) for c in geom["coordinates"]] if geom["type"] == "MultiPoint"
                     else [tuple(geom["coordinates"])] if geom["type"] == "Point" else [])
            closer = r["category"] == "severeStorms" and triggers.approaching(
                track, r["lat"], r["lon"])
            km = max(1, round(r["km"]))
            kind = "natural_event_approaching" if closer else "natural_event"
            message = templates.render(kind, r["language"], simulated=r["simulated"],
                                       event=r["title"], distance=km, field=r["field_name"])
            severity = "warning" if km <= triggers.RADIUS_KM.get(r["category"], 100) / 3 \
                or closer else "watch"
            alert = _insert(conn, r["user_id"], r["field_id"], "natural_event", severity, message,
                            "NASA EONET" + (" (simulated)" if r["simulated"] else ""),
                            r["event_id"], {"event": r["title"], "category": r["category"],
                                            "km": km, "approaching": closer,
                                            "event_geometry": geom, "url": r["source_url"]})
            if alert:
                new.append(alert)
    return new


def _insert(conn: Any, user_id: str, field_id: str, kind: str, severity: str, message: str,
            source: str, event_id: str, data: dict[str, Any]) -> str | None:
    row = conn.execute(
        """INSERT INTO alerts (user_id, field_id, type, severity, message, data, source,
               source_event_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (field_id, type, source_event_id) DO NOTHING
           RETURNING id::text""",
        (user_id, field_id, kind, severity, message, Jsonb(data), source, event_id)).fetchone()
    return row["id"] if row else None


# --- field-specific checks -------------------------------------------------------------------

def _fields(sub: str | None) -> list[dict[str, Any]]:
    with _conn() as conn:
        return [dict(r) for r in conn.execute(
            """SELECT f.id::text AS field_id, f.user_id, f.name, f.geom_hash,
                      ST_Y(ST_Centroid(f.geom)) AS lat, ST_X(ST_Centroid(f.geom)) AS lon,
                      ST_AsGeoJSON(f.geom)::json AS geometry,
                      COALESCE(u.language, 'en') AS language,
                      COALESCE(p.alert_types, %s) AS alert_types,
                      (SELECT request FROM analyses a WHERE a.field_id = f.id
                        ORDER BY created_at DESC LIMIT 1) AS request
                 FROM fields f JOIN users u ON u.id = f.user_id
                 LEFT JOIN alert_preferences p ON p.field_id = f.id AND p.user_id = f.user_id
                WHERE %s::text IS NULL OR f.user_id = %s""",
            (ALERT_TYPES, sub, sub)).fetchall()]


def _crops(request: dict[str, Any] | None) -> set[str]:
    answers = (request or {}).get("answers") or {}
    crops = {str(c.get("crop", "")).strip().lower() for c in answers.get("current_crops") or []}
    return {c for c in crops if c} | {"corn" if c == "maize" else c for c in crops if c} | (
        {"maize"} if "corn" in crops else set())


def check_field(f: dict[str, Any]) -> list[str]:
    """Fires, heavy rain, dry soil and pest-risk weather for one field. New alert ids."""
    new: list[str] = []
    types = set(f["alert_types"])
    lang, name = f["language"], f["name"]
    today = datetime.now(UTC).date().isoformat()
    found: list[tuple[str, str, str, str, str, dict[str, Any]]] = []

    if "fire" in types:
        try:
            fires = sources.fetch_fires(f["lat"], f["lon"], triggers.FIRE_RADIUS_KM,
                                        triggers.FIRE_DAYS)
            near = [x for x in fires if triggers.haversine_km(f["lat"], f["lon"], x.lat, x.lon)
                    <= triggers.FIRE_RADIUS_KM]
            if near:
                km = min(triggers.haversine_km(f["lat"], f["lon"], x.lat, x.lon) for x in near)
                found.append(("fire", "warning" if km < 2 else "watch",
                              templates.render("fire", lang, distance=max(1, round(km)),
                                               field=name, days=triggers.FIRE_DAYS),
                              "NASA FIRMS (VIIRS)", f"FIRMS-{today}",
                              {"detections": len(near), "km": round(km, 1),
                               "points": [[x.lon, x.lat] for x in near[:20]]}))
        except Exception as exc:  # one source failing never stops the others
            log.info("fire check skipped: %s", type(exc).__name__)

    if "heavy_rain" in types or "drought" in types:
        try:
            from app.features.harmonize import build_field_features

            ff, _ = build_field_features(f["geometry"])
        except Exception as exc:
            ff = None
            log.info("field features unavailable: %s", type(exc).__name__)
        if "heavy_rain" in types:
            try:
                mm, when = sources.rain_last_24h(f["lat"], f["lon"])
                month = datetime.now(UTC).month - 1
                normal = None
                if ff is not None and ff.features.get("rain") is not None:
                    normal = ff.features["rain"].normal[month]
                severity = triggers.heavy_rain(mm, normal)
                if severity:
                    found.append(("heavy_rain", severity,
                                  templates.render("heavy_rain", lang, field=name,
                                                   mm=round(mm or 0), hours=24),
                                  "JAXA GSMaP v8 (operational)", f"GSMaP-{(when or today)[:10]}",
                                  {"mm_24h": mm, "normal_mm_day": normal, "image_time": when}))
            except Exception as exc:
                log.info("rain check skipped: %s", type(exc).__name__)
        if "drought" in types and ff is not None:
            sm = ff.features.get("soil_moisture_root")
            hit = triggers.drought(sm.recent, sm.normal, sm.recent_months) if sm else None
            if hit:
                found.append(("drought", hit.severity,
                              templates.render("drought", lang, field=name,
                                               pct=round(hit.share * 100),
                                               month=triggers.month_name(hit.month)),
                              "NASA SMAP L4", f"SMAP-{hit.month}",
                              {"share_of_normal": round(hit.share, 2), "month": hit.month}))

    if "pest_risk" in types:
        crops = _crops(f.get("request"))
        if crops:
            try:
                rows = sources.recent_weather(f["lat"], f["lon"])
                rules = {r["pest"]: r for r in sources.pest_rules()}
                for hit in triggers.pest_hits(list(rules.values()), rows, crops):
                    week = hit.last_day.isocalendar()
                    found.append(("pest_risk", "watch",
                                  templates.render("pest_risk", lang, field=name, pest=hit.pest,
                                                   crop=hit.crop,
                                                   rule=triggers.rule_text(rules[hit.pest])),
                                  "NASA POWER daily weather + team pest rules",
                                  f"{hit.pest}-{week.year}-W{week.week:02d}",
                                  {"pest": hit.pest, "crop": hit.crop, "days": hit.days,
                                   "last_day": hit.last_day.isoformat(),
                                   "rule_source": hit.source}))
            except Exception as exc:
                log.info("pest check skipped: %s", type(exc).__name__)

    if found:
        with _conn() as conn:
            for kind, severity, message, source, event_id, data in found:
                alert = _insert(conn, f["user_id"], f["field_id"], kind, severity, message,
                                source, event_id, data)
                if alert:
                    new.append(alert)
    return new


def run_check(sub: str | None, *, force: bool = False) -> dict[str, Any]:
    """The full check for one user (app open / Check now) or for everyone (background)."""
    if sub is not None and not force:
        with _conn() as conn:
            row = conn.execute("SELECT last_alert_check FROM users WHERE id = %s",
                               (sub,)).fetchone()
        last = row["last_alert_check"] if row else None
        if last and datetime.now(UTC) - last < CHECK_EVERY:
            return {"checked": False, "new": 0, "last_check": last.isoformat()}
    new: list[str] = []
    try:
        refresh_events(timedelta(0) if force else CHECK_EVERY)
    except Exception as exc:
        log.info("EONET unavailable: %s", type(exc).__name__)
    new += match_events()
    for f in _fields(sub):
        new += check_field(f)
    now = datetime.now(UTC)
    if sub is not None:
        with _conn() as conn:
            conn.execute("UPDATE users SET last_alert_check = %s WHERE id = %s", (now, sub))
    deliver(new)
    return {"checked": True, "new": len(new), "last_check": now.isoformat()}


# --- simulation (demo) -----------------------------------------------------------------------

def simulate(farm_id: str, *, fresh: bool = False) -> dict[str, Any]:
    """ADMIN ONLY (scripts/simulate_storm.py; no API route): a simulated storm moving toward a
    demo farm, matched against every saved field like a real NASA EONET event, so every account
    with a field in range gets one alert. Same hour = same event (re-running sends nothing new)
    unless fresh=True."""
    farm = next((f for f in showcase.farms() if f["id"] == farm_id), None)
    if farm is None:
        raise LookupError(f"unknown demo farm {farm_id!r}")
    lon, lat = farm["geometry"]["coordinates"][:2]
    tropical = abs(lat) < 25
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S" if fresh else "%Y%m%d%H")
    event_id = f"SIM-{farm['id']}-{stamp}"
    # Track: four points from ~450 km east to ~60 km east of the farm, moving west.
    km_per_deg_lon = 111 * max(0.2, abs(math.cos(math.radians(lat))))
    track = [(lon + d / km_per_deg_lon, lat + 0.2 * i)
             for i, d in enumerate((450, 300, 160, 60))]
    title = "Simulated Typhoon Amihan" if tropical else "Simulated severe storm"
    store_events([sources.NaturalEvent(event_id, title, "severeStorms", track,
                                       {"type": "MultiPoint", "coordinates": [list(p) for p in
                                                                              track]},
                                       datetime.now(UTC).isoformat(), None, simulated=True)])
    new = match_events([event_id])
    deliver(new)
    return {"event_id": event_id, "new": len(new), "title": title}


def clear_simulations() -> dict[str, int]:
    """ADMIN ONLY: remove every simulated event and the alerts it created."""
    with _conn() as conn:
        alerts = conn.execute(
            "DELETE FROM alerts WHERE type = 'natural_event' AND source_event_id LIKE 'SIM-%'"
        ).rowcount
        events = conn.execute("DELETE FROM natural_events WHERE simulated").rowcount
    return {"alerts": alerts, "events": events}


# --- delivery --------------------------------------------------------------------------------

def deliver(alert_ids: list[str]) -> None:
    if not alert_ids:
        return
    with _conn() as conn:
        rows = conn.execute(
            """SELECT a.id::text, a.type, a.message, a.user_id, u.email, u.language,
                      COALESCE(p.email, true) AS want_email, COALESCE(p.push, true) AS want_push
                 FROM alerts a JOIN users u ON u.id = a.user_id
                 LEFT JOIN alert_preferences p ON p.field_id = a.field_id AND p.user_id = a.user_id
                WHERE a.id = ANY(%s::uuid[])""", (alert_ids,)).fetchall()
        subs: dict[str, list[dict[str, Any]]] = {}
        for s in conn.execute("SELECT * FROM push_subscriptions WHERE user_id = ANY(%s)",
                              (list({r["user_id"] for r in rows}),)).fetchall():
            subs.setdefault(s["user_id"], []).append(dict(s))
        for r in rows:
            title = templates.title(r["type"], r["language"])
            if r["want_email"] and r["email"]:
                try:
                    send_email(r["email"], f"SowSmart alert: {title}",
                               f"{r['message']}\n\n{APP_LINK}")
                    conn.execute("UPDATE alerts SET emailed_at = now() WHERE id = %s", (r["id"],))
                except EmailError as exc:
                    log.info("alert email not sent: %s", exc)
            if r["want_push"] and push.configured():
                sent = False
                for s in subs.get(r["user_id"], []):
                    try:
                        push.send(s, {"title": f"SowSmart: {title}", "body": r["message"],
                                      "tag": r["id"], "url": "/"})
                        sent = True
                    except push.PushGone:
                        conn.execute("DELETE FROM push_subscriptions WHERE id = %s", (s["id"],))
                    except Exception as exc:
                        log.info("push not sent: %s", type(exc).__name__)
                if sent:
                    conn.execute("UPDATE alerts SET pushed_at = now() WHERE id = %s", (r["id"],))


# --- user-facing reads and settings ---------------------------------------------------------

def list_alerts(sub: str, limit: int = 50) -> list[dict[str, Any]]:
    with _conn() as conn:
        return [dict(r) for r in conn.execute(
            """SELECT a.id::text, a.field_id::text, f.name AS field_name, a.type, a.severity,
                      a.message, a.source, a.data, a.triggered_at, a.read_at,
                      ST_Y(ST_Centroid(f.geom)) AS lat, ST_X(ST_Centroid(f.geom)) AS lon
                 FROM alerts a JOIN fields f ON f.id = a.field_id
                WHERE a.user_id = %s ORDER BY a.triggered_at DESC LIMIT %s""",
            (sub, limit)).fetchall()]


def mark_read(sub: str, alert_id: str) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE alerts SET read_at = COALESCE(read_at, now()) WHERE id = %s AND user_id = %s",
            (alert_id, sub))
        return cur.rowcount == 1


def set_preferences(sub: str, field_id: str, alert_types: list[str], email: bool,
                    push_on: bool) -> bool:
    with _conn() as conn:
        owned = conn.execute("SELECT 1 FROM fields WHERE id = %s AND user_id = %s",
                             (field_id, sub)).fetchone()
        if not owned:
            return False
        conn.execute(
            """INSERT INTO alert_preferences (user_id, field_id, alert_types, email, push)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (user_id, field_id) DO UPDATE SET alert_types = EXCLUDED.alert_types,
                   email = EXCLUDED.email, push = EXCLUDED.push""",
            (sub, field_id, [t for t in alert_types if t in ALERT_TYPES], email, push_on))
        return True


def add_subscription(sub: str, endpoint: str, p256dh: str, auth: str) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO push_subscriptions (user_id, endpoint, p256dh, auth)
               VALUES (%s, %s, %s, %s)
               ON CONFLICT (endpoint) DO UPDATE SET user_id = EXCLUDED.user_id,
                   p256dh = EXCLUDED.p256dh, auth = EXCLUDED.auth""",
            (sub, endpoint, p256dh, auth))


def remove_subscription(sub: str, endpoint: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM push_subscriptions WHERE user_id = %s AND endpoint = %s",
                     (sub, endpoint))


# --- background job --------------------------------------------------------------------------

def start_background(interval_hours: float) -> threading.Event:
    """Run the check for everyone every `interval_hours` while the backend is up."""
    stop = threading.Event()

    def loop() -> None:
        while not stop.wait(interval_hours * 3600):
            try:
                result = run_check(None, force=True)
                log.info("background alert check: %s new", result["new"])
            except Exception as exc:
                log.warning("background alert check failed: %s", type(exc).__name__)

    threading.Thread(target=loop, name="alert-check", daemon=True).start()
    return stop
