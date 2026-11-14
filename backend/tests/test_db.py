"""Live checks against TigerData. Run with `make check-db` (skipped by `make check`).

Writes happen inside transactions that are rolled back, so nothing is left in the database
(except one cache row, which the cache test deletes).
"""

import uuid

import psycopg
import pytest

from app.config import get_settings
from app.data.cache import DbCache
from db import migrate

pytestmark = pytest.mark.db

URL = get_settings().database_url.get_secret_value()
EXPECTED_TABLES = {
    "data_cache", "climate_daily", "field_monthly_features", "crops", "pest_rules",
    "users", "farms", "fields", "field_inputs", "rotations", "rotation_steps", "analyses",
    "strategy_results", "ai_reports", "pdf_reports", "alert_preferences", "alerts",
    "schema_migrations",
}


class Rollback(Exception):
    pass


@pytest.fixture(scope="module")
def conn():
    if not URL:
        pytest.skip("DATABASE_URL is not set")
    with psycopg.connect(URL, autocommit=True, connect_timeout=15) as c:
        yield c


def in_rolled_back_transaction(conn, work):
    """Run work(conn) inside a transaction, then roll it back whatever happens."""
    try:
        with conn.transaction():
            work(conn)
            raise Rollback
    except Rollback:
        pass


def insert_user_and_field(c) -> tuple[str, str]:
    user = f"test|{uuid.uuid4()}"
    c.execute("INSERT INTO users (id) VALUES (%s)", (user,))
    field = c.execute(
        "INSERT INTO fields (user_id, geom, geom_hash, input_mode) "
        "VALUES (%s, ST_SetSRID(ST_MakePoint(120.9, 15.6), 4326), 'test', 'point') RETURNING id",
        (user,),
    ).fetchone()[0]
    return user, field


def test_all_tables_exist(conn):
    names = {r[0] for r in conn.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
    )}
    assert EXPECTED_TABLES <= names


def test_every_migration_is_recorded(conn):
    recorded = {r[0] for r in conn.execute("SELECT filename FROM schema_migrations")}
    assert recorded == {m.name for m in migrate.discover()}


def test_climate_daily_is_a_hypertable_on_day(conn):
    row = conn.execute(
        "SELECT column_name FROM timescaledb_information.dimensions "
        "WHERE hypertable_name = 'climate_daily'"
    ).fetchone()
    assert row == ("day",)


def test_postgis_buffer_area(conn):
    ha = conn.execute(
        "SELECT ST_Area(ST_Buffer(ST_SetSRID(ST_MakePoint(120.9, 15.6), 4326)::geography, 250))"
        " / 10000"
    ).fetchone()[0]
    assert 19 < ha < 20  # pi * 250^2 m^2 = 19.6 ha


def test_one_event_never_alerts_a_field_twice(conn):
    def work(c):
        user, field = insert_user_and_field(c)
        sql = (
            "INSERT INTO alerts"
            " (user_id, field_id, type, severity, message, source, source_event_id)"
            " VALUES (%s, %s, 'natural_event', 'warning', 'Typhoon nearby', 'NASA EONET',"
            " 'EONET_1')"
        )
        c.execute(sql, (user, field))
        with pytest.raises(psycopg.errors.UniqueViolation), c.transaction():
            c.execute(sql, (user, field))

    in_rolled_back_transaction(conn, work)


def test_deleting_a_user_deletes_all_their_data(conn):
    def work(c):
        user, field = insert_user_and_field(c)
        c.execute(
            "INSERT INTO alert_preferences (user_id, field_id) VALUES (%s, %s)", (user, field)
        )
        c.execute("DELETE FROM users WHERE id = %s", (user,))
        for table in ("fields", "alert_preferences"):
            left = c.execute(f"SELECT count(*) FROM {table} WHERE user_id = %s", (user,)).fetchone()
            assert left == (0,), table

    in_rolled_back_transaction(conn, work)


def test_alert_preferences_default_to_all_types(conn):
    def work(c):
        user, field = insert_user_and_field(c)
        types = c.execute(
            "INSERT INTO alert_preferences (user_id, field_id) VALUES (%s, %s)"
            " RETURNING alert_types",
            (user, field),
        ).fetchone()[0]
        assert set(types) == {
            "natural_event", "fire", "heavy_rain", "drought", "pest_risk", "new_findings"
        }

    in_rolled_back_transaction(conn, work)


def test_db_cache_round_trip_and_expiry(conn):
    cache = DbCache(URL)
    key = f"test:{uuid.uuid4()}"
    try:
        assert cache.get(key) is None
        cache.set(key, {"rain": [0.7, 19.2]})
        assert cache.get(key) == {"rain": [0.7, 19.2]}
        conn.execute(
            "UPDATE data_cache SET updated_at = now() - interval '2 hours' WHERE key = %s", (key,)
        )
        assert cache.get(key, max_age_s=3600) is None
        assert cache.get(key) == {"rain": [0.7, 19.2]}
        row = conn.execute("SELECT namespace FROM data_cache WHERE key = %s", (key,)).fetchone()
        assert row == ("test",)
    finally:
        conn.execute("DELETE FROM data_cache WHERE key = %s", (key,))
