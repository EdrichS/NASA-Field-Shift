"""Migration runner logic and schema rules. Offline: reads the SQL files, no database."""

import re

import pytest

from db import migrate

SHARED = (migrate.MIGRATIONS_DIR / "002_shared_data.sql").read_text()
USER = (migrate.MIGRATIONS_DIR / "003_user_data.sql").read_text()


def create_table_blocks(sql: str) -> dict[str, str]:
    return dict(re.findall(r"CREATE TABLE (\w+) \((.*?)\n\)", sql, flags=re.S))


def test_real_migrations_are_discovered_in_order():
    names = [m.name for m in migrate.discover()]
    assert names == sorted(names)
    assert names[:3] == ["001_extensions.sql", "002_shared_data.sql", "003_user_data.sql"]


def test_pending_skips_applied_and_returns_new(tmp_path):
    (tmp_path / "001_a.sql").write_text("SELECT 1;")
    (tmp_path / "002_b.sql").write_text("SELECT 2;")
    found = migrate.discover(tmp_path)
    applied = {"001_a.sql": found[0].checksum}
    assert [m.name for m in migrate.pending(found, applied)] == ["002_b.sql"]
    assert migrate.pending(found, {m.name: m.checksum for m in found}) == []


def test_editing_an_applied_migration_is_refused(tmp_path):
    (tmp_path / "001_a.sql").write_text("SELECT 1;")
    found = migrate.discover(tmp_path)
    with pytest.raises(migrate.MigrationError, match="changed after it was applied"):
        migrate.pending(found, {"001_a.sql": "old-checksum"})


@pytest.mark.parametrize("name", ["1_a.sql", "001-a.sql", "001_A.sql"])
def test_bad_file_names_are_refused(tmp_path, name):
    (tmp_path / name).write_text("SELECT 1;")
    with pytest.raises(migrate.MigrationError):
        migrate.discover(tmp_path)


def test_duplicate_numbers_are_refused(tmp_path):
    (tmp_path / "001_a.sql").write_text("SELECT 1;")
    (tmp_path / "001_b.sql").write_text("SELECT 2;")
    with pytest.raises(migrate.MigrationError, match="share a number"):
        migrate.discover(tmp_path)


def test_every_user_table_is_owned_and_cascades():
    tables = create_table_blocks(USER)
    assert "users" in tables and len(tables) == 12
    for name, body in tables.items():
        if name == "users":
            continue
        assert re.search(
            r"user_id\s+text NOT NULL REFERENCES users \(id\) ON DELETE CASCADE", body
        ), f"{name} must carry user_id with ON DELETE CASCADE"


def test_shared_tables_hold_no_user_data():
    tables = create_table_blocks(SHARED)
    assert set(tables) == {
        "data_cache", "climate_daily", "field_monthly_features", "crops", "pest_rules"
    }
    for name, body in tables.items():
        assert "user_id" not in body, f"{name} is shared data and must not reference users"
