"""Database connection helper. Only the backend talks to TigerData."""

from __future__ import annotations

import psycopg

from app.config import get_settings


def database_url() -> str:
    return get_settings().database_url.get_secret_value()


def connect() -> psycopg.Connection:
    """A new autocommit connection. Raises RuntimeError if DATABASE_URL is not set."""
    url = database_url()
    if not url:
        raise RuntimeError("DATABASE_URL is empty")
    return psycopg.connect(url, autocommit=True, connect_timeout=10)
