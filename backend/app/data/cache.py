"""Small JSON cache keyed by a string, with two interchangeable backends:

- DbCache: the shared `data_cache` table in TigerData (used whenever DATABASE_URL is set)
- FileCache: JSON files in data/cache/ (gitignored; for tests and offline work)

A cache problem must never break a fetch: DbCache treats database errors as a miss.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    import psycopg

log = logging.getLogger(__name__)

DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "data" / "cache"


class Cache(Protocol):
    def get(self, key: str, max_age_s: float | None = None) -> Any | None: ...

    def set(self, key: str, value: Any) -> None: ...


class FileCache:
    def __init__(self, root: Path | str = DEFAULT_ROOT) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode()).hexdigest()
        return self.root / digest[:2] / f"{digest}.json"

    def get(self, key: str, max_age_s: float | None = None) -> Any | None:
        """Return the cached value, or None if missing, unreadable or older than max_age_s."""
        path = self._path(key)
        try:
            if max_age_s is not None and time.time() - path.stat().st_mtime > max_age_s:
                return None
            return json.loads(path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def set(self, key: str, value: Any) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temp file, then rename, so a crash never leaves a half-written entry.
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(value, f)
        os.replace(tmp, path)


class DbCache:
    """The `data_cache` table. The key's prefix before ':' (e.g. 'power') is its namespace."""

    def __init__(self, database_url: str) -> None:
        self._url = database_url
        self._conn: psycopg.Connection | None = None

    def _connection(self) -> psycopg.Connection:
        import psycopg

        if self._conn is None or self._conn.closed:
            self._conn = psycopg.connect(self._url, autocommit=True, connect_timeout=10)
        return self._conn

    def _run(self, sql: str, params: tuple) -> Any:
        """Run one statement, reconnecting once if the connection dropped (free tiers idle out)."""
        import psycopg

        for attempt in (1, 2):
            try:
                return self._connection().execute(sql, params)
            except psycopg.OperationalError:
                self._conn = None
                if attempt == 2:
                    raise

    def get(self, key: str, max_age_s: float | None = None) -> Any | None:
        import psycopg

        try:
            row = self._run(
                "SELECT value, extract(epoch FROM now() - updated_at) "
                "FROM data_cache WHERE key = %s",
                (key,),
            ).fetchone()
        except psycopg.Error as exc:
            log.warning("data_cache read failed (%s); treating as a miss", type(exc).__name__)
            return None
        if row is None:
            return None
        value, age_s = row
        if max_age_s is not None and float(age_s) > max_age_s:
            return None
        return value

    def set(self, key: str, value: Any) -> None:
        import psycopg
        from psycopg.types.json import Jsonb

        try:
            self._run(
                "INSERT INTO data_cache (key, namespace, value) VALUES (%s, %s, %s) "
                "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now()",
                (key, key.split(":", 1)[0], Jsonb(value)),
            )
        except psycopg.Error as exc:
            log.warning("data_cache write failed (%s); not cached", type(exc).__name__)


@lru_cache
def default_cache() -> Cache:
    """The shared database cache when DATABASE_URL is set, else local files."""
    from app.config import get_settings

    url = get_settings().database_url.get_secret_value()
    return DbCache(url) if url else FileCache()
