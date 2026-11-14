"""Apply SQL migrations in backend/db/migrations/ to the database in DATABASE_URL.

Usage:  make migrate   (or, from backend/: ../.venv/bin/python -m db.migrate)

Each file runs once, in name order, inside its own transaction, and is recorded in
schema_migrations with a checksum. Re-running applies nothing new. Editing a file that was
already applied is an error: add a new numbered migration instead.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
NAME_PATTERN = re.compile(r"^\d{3}_[a-z0-9_]+\.sql$")
LOCK_ID = 7_202_611  # any constant; stops two runners applying migrations at the same time


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    name: str
    sql: str
    checksum: str


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    migrations = []
    for path in sorted(directory.glob("*.sql")):
        if not NAME_PATTERN.match(path.name):
            raise MigrationError(f"bad migration file name: {path.name} (want 001_name.sql)")
        sql = path.read_text(encoding="utf-8")
        migrations.append(Migration(path.name, sql, hashlib.sha256(sql.encode()).hexdigest()))
    numbers = [m.name[:3] for m in migrations]
    if len(numbers) != len(set(numbers)):
        raise MigrationError(f"two migrations share a number: {numbers}")
    return migrations


def pending(migrations: list[Migration], applied: dict[str, str]) -> list[Migration]:
    """Migrations not applied yet. `applied` maps file name -> checksum stored at apply time."""
    todo = []
    for m in migrations:
        if m.name not in applied:
            todo.append(m)
        elif applied[m.name] != m.checksum:
            raise MigrationError(
                f"{m.name} changed after it was applied. Revert the edit and add a new migration."
            )
    return todo


def apply_all(database_url: str, directory: Path = MIGRATIONS_DIR) -> list[str]:
    import psycopg

    migrations = discover(directory)
    with psycopg.connect(database_url, autocommit=True, connect_timeout=15) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                " filename text PRIMARY KEY, checksum text NOT NULL,"
                " applied_at timestamptz NOT NULL DEFAULT now())"
            )
            applied = dict(conn.execute("SELECT filename, checksum FROM schema_migrations"))
            done = []
            for m in pending(migrations, applied):
                with conn.transaction():
                    conn.execute(m.sql)
                    conn.execute(
                        "INSERT INTO schema_migrations (filename, checksum) VALUES (%s, %s)",
                        (m.name, m.checksum),
                    )
                done.append(m.name)
            return done
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.config import get_settings

    url = get_settings().database_url.get_secret_value()
    if not url:
        print("DATABASE_URL is empty")
        return 1
    try:
        done = apply_all(url)
    except MigrationError as exc:
        print(f"❌ {exc}")
        return 1
    if done:
        print(f"Applied {len(done)} migration(s): {', '.join(done)}")
    else:
        print("Nothing to apply: the database is up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
