"""User data in TigerData: profiles, fields, saved analyses, stored AI reports.

Every function takes the Auth0 `sub` and filters by it (CLAUDE.md section 16): one user can never
read or change another user's rows. Farm locations are personal data: never logged.
"""

from __future__ import annotations

import json
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.db import connect

ALERT_TYPES = ["natural_event", "fire", "heavy_rain", "drought", "pest_risk", "new_findings"]


def _conn() -> psycopg.Connection:
    conn = connect()
    conn.row_factory = dict_row
    return conn


def upsert_user(sub: str, email: str | None = None) -> dict[str, Any]:
    with _conn() as conn:
        row = conn.execute(
            """INSERT INTO users (id, email) VALUES (%s, %s)
               ON CONFLICT (id) DO UPDATE SET email = COALESCE(EXCLUDED.email, users.email)
               RETURNING id, display_name, language, units, email IS NOT NULL AS has_email,
                         created_at""",
            (sub, email)).fetchone()
    return dict(row)


def update_profile(sub: str, display_name: str | None, language: str, units: str) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO users (id, display_name, language, units) VALUES (%s, %s, %s, %s)
               ON CONFLICT (id) DO UPDATE SET display_name = EXCLUDED.display_name,
                   language = EXCLUDED.language, units = EXCLUDED.units""",
            (sub, display_name, language, units))


def delete_user(sub: str) -> None:
    """'Delete my data': the user row and, by ON DELETE CASCADE, every field, analysis,
    report, alert and push subscription."""
    with _conn() as conn:
        conn.execute("DELETE FROM users WHERE id = %s", (sub,))


def list_fields(sub: str) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            """SELECT f.id::text, f.name, f.area_ha, f.input_mode, f.created_at,
                      ST_Y(ST_Centroid(f.geom)) AS lat, ST_X(ST_Centroid(f.geom)) AS lon,
                      a.id::text AS analysis_id, a.top_strategy, a.created_at AS analyzed_at,
                      COALESCE(p.alert_types, %s) AS alert_types,
                      COALESCE(p.email, true) AS email, COALESCE(p.push, true) AS push,
                      (SELECT count(*) FROM alerts al
                        WHERE al.field_id = f.id AND al.read_at IS NULL) AS unread
                 FROM fields f
                 LEFT JOIN LATERAL (SELECT id, top_strategy, created_at FROM analyses
                                     WHERE field_id = f.id AND user_id = f.user_id
                                     ORDER BY created_at DESC LIMIT 1) a ON true
                 LEFT JOIN alert_preferences p ON p.field_id = f.id AND p.user_id = f.user_id
                WHERE f.user_id = %s
                ORDER BY f.created_at""",
            (ALERT_TYPES, sub)).fetchall()
    return [dict(r) for r in rows]


def rename_field(sub: str, field_id: str, name: str) -> bool:
    with _conn() as conn:
        cur = conn.execute("UPDATE fields SET name = %s WHERE id = %s AND user_id = %s",
                           (name, field_id, sub))
        return cur.rowcount == 1


def delete_field(sub: str, field_id: str) -> bool:
    with _conn() as conn:
        cur = conn.execute("DELETE FROM fields WHERE id = %s AND user_id = %s", (field_id, sub))
        return cur.rowcount == 1


def save_analysis(sub: str, request: dict[str, Any], result: dict[str, Any], *,
                  field_name: str, input_mode: str, email: str | None = None
                  ) -> dict[str, Any]:
    """Store one analysis for this user: the field (reused when the same place is saved again),
    the farmer's inputs, the result, one row per strategy and the Tier 1 reports. Raises a
    "new findings" alert when the top recommendation differs from the field's last analysis."""
    geom_hash = result["field"]["geom_hash"]
    strategies = result.get("strategies") or []
    top = min(strategies, key=lambda s: s["rank"])["key"] if strategies else None
    answers = request.get("answers") or {}
    with _conn() as conn, conn.transaction():
        conn.execute(
            """INSERT INTO users (id, email) VALUES (%s, %s)
               ON CONFLICT (id) DO UPDATE SET email = COALESCE(EXCLUDED.email, users.email)""",
            (sub, email))
        field = conn.execute(
            "SELECT id::text FROM fields WHERE user_id = %s AND geom_hash = %s LIMIT 1",
            (sub, geom_hash)).fetchone()
        if field is None:
            field = conn.execute(
                """INSERT INTO fields (user_id, name, geom, geom_hash, area_ha, input_mode)
                   VALUES (%s, %s, ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326), %s,
                           CASE WHEN %s = 'Point' THEN 19.63
                                ELSE ST_Area(ST_SetSRID(ST_GeomFromGeoJSON(%s), 4326)::geography)
                                     / 10000 END,
                           %s)
                   RETURNING id::text""",
                (sub, field_name, json.dumps(request["geometry"]), geom_hash,
                 request["geometry"]["type"], json.dumps(request["geometry"]), input_mode)
            ).fetchone()
        field_id = field["id"]
        previous = conn.execute(
            """SELECT top_strategy FROM analyses WHERE user_id = %s AND field_id = %s
               ORDER BY created_at DESC LIMIT 1""", (sub, field_id)).fetchone()
        conn.execute(
            """INSERT INTO field_inputs (user_id, field_id, mode, answers, confirmed_prefill)
               VALUES (%s, %s, %s, %s, %s)""",
            (sub, field_id, request.get("mode", "quick"), Jsonb(answers),
             Jsonb(answers.get("confirmed_prefill") or {})))
        stored = {**result, "analysis_id": None}
        analysis_id = conn.execute(
            """INSERT INTO analyses (user_id, field_id, mode, request, result, top_strategy)
               VALUES (%s, %s, %s, %s, %s, %s) RETURNING id::text""",
            (sub, field_id, request.get("mode", "quick"), Jsonb(request), Jsonb(stored), top)
        ).fetchone()["id"]
        for s in strategies:
            conn.execute(
                """INSERT INTO strategy_results (user_id, analysis_id, strategy_key, name, rank,
                       total_score, confidence, components)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (sub, analysis_id, s["key"], s["name"], s["rank"], s["total"], s["confidence"],
                 Jsonb(s["components"])))
        for report in (result.get("reports_tier1") or {}).values():
            if report:
                _insert_report(conn, sub, analysis_id, report)
        conn.execute(
            """INSERT INTO alert_preferences (user_id, field_id) VALUES (%s, %s)
               ON CONFLICT DO NOTHING""", (sub, field_id))
        new_findings = bool(previous and previous["top_strategy"] and top
                            and previous["top_strategy"] != top)
        if new_findings:
            name = next(s["name"] for s in strategies if s["key"] == top)
            conn.execute(
                """INSERT INTO alerts (user_id, field_id, type, severity, message, data, source,
                       source_event_id)
                   VALUES (%s, %s, 'new_findings', 'info', %s, %s, 'SowSmart analysis', %s)
                   ON CONFLICT DO NOTHING""",
                (sub, field_id, f"New findings for {field_name}: the best match is now "
                 f"\"{name}\". Open the plan to see why.",
                 Jsonb({"analysis_id": analysis_id, "previous": previous["top_strategy"],
                        "top": top}), analysis_id))
    return {"analysis_id": analysis_id, "field_id": field_id, "new_findings": new_findings}


def _insert_report(conn: psycopg.Connection, sub: str, analysis_id: str,
                   report: dict[str, Any]) -> None:
    meta = report.get("meta") or {}
    conn.execute(
        """INSERT INTO ai_reports (user_id, analysis_id, tier, language, language_level, question,
               content, model, input_tokens, output_tokens)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (analysis_id, tier, language, language_level, question) DO NOTHING""",
        (sub, analysis_id, report["tier"], report["language"], report["language_level"],
         report.get("question") or "", Jsonb(report), meta.get("model") or "unknown",
         meta.get("input_tokens"), meta.get("output_tokens")))


def get_analysis(sub: str, analysis_id: str) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT result FROM analyses WHERE id = %s AND user_id = %s",
            (analysis_id, sub)).fetchone()
    if row is None:
        return None
    return {**row["result"], "analysis_id": analysis_id}


def get_report(sub: str, analysis_id: str, tier: int, language: str, level: str,
               question: str) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute(
            """SELECT content FROM ai_reports
                WHERE user_id = %s AND analysis_id = %s AND tier = %s AND language = %s
                  AND language_level = %s AND question = %s""",
            (sub, analysis_id, tier, language, level, question)).fetchone()
    return row["content"] if row else None


def store_report(sub: str, analysis_id: str, report: dict[str, Any]) -> None:
    with _conn() as conn:
        _insert_report(conn, sub, analysis_id, report)
