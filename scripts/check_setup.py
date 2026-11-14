"""Check every outside service without spending credits. Never prints secret values.

Usage:  make check-setup   (or: .venv/bin/python scripts/check_setup.py)

Checks: TigerData (connection + extensions), Earth Engine (1+1), FIRMS (mapkey_status),
xAI (/models list, free), Auth0 (public JWKS). Exits 1 if anything fails.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import Settings  # noqa: E402

TIMEOUT = 20.0


@dataclass
class Result:
    name: str
    ok: bool
    detail: str


# --- secret handling -------------------------------------------------------------------


def secret_values(s: Settings) -> list[str]:
    """Every secret string that must never appear in output (including the DB password alone)."""
    db_url = s.database_url.get_secret_value()
    values = [
        s.earthdata_password.get_secret_value(),
        s.firms_map_key.get_secret_value(),
        s.xai_api_key.get_secret_value(),
        db_url,
    ]
    # Pull the password out of scheme://user:PASSWORD@host by pattern, not urlsplit: urlsplit
    # cuts at an unencoded '#' or '?' and would miss part of the password.
    match = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://[^:/@]*:(.+)@[^@/]+", db_url)
    if match:
        password = match.group(1)
        values += [password, unquote(password)]
    return [v for v in values if v and len(v) >= 4]


def redact(text: str, secrets: list[str]) -> str:
    for value in sorted(secrets, key=len, reverse=True):
        text = text.replace(value, "***")
    return text


# --- checks ----------------------------------------------------------------------------


def check_database(s: Settings) -> Result:
    name = "TigerData (Postgres)"
    url = s.database_url.get_secret_value()
    if not url:
        return Result(name, False, "DATABASE_URL is empty")
    import psycopg

    with psycopg.connect(url, connect_timeout=10) as conn:
        installed = dict(conn.execute("SELECT extname, extversion FROM pg_extension").fetchall())
        available = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM pg_available_extensions WHERE name IN ('postgis', 'timescaledb')"
            ).fetchall()
        }
    parts, ok = [], True
    for ext in ("timescaledb", "postgis"):
        if ext in installed:
            parts.append(f"{ext} {installed[ext]}")
        elif ext in available:
            parts.append(f"{ext} available (created by the step 1.1 migrations)")
        else:
            parts.append(f"{ext} NOT available on this service")
            ok = False
    return Result(name, ok, "connected; " + "; ".join(parts))


def check_earth_engine(s: Settings) -> Result:
    name = "Earth Engine"
    if not s.ee_project:
        return Result(name, False, "EE_PROJECT is empty")
    import ee

    ee.Initialize(project=s.ee_project)
    two = ee.Number(1).add(1).getInfo()
    return Result(name, two == 2, f"project {s.ee_project}: 1+1 = {two}")


def check_firms(s: Settings) -> Result:
    name = "NASA FIRMS"
    key = s.firms_map_key.get_secret_value()
    if not key:
        return Result(name, False, "FIRMS_MAP_KEY is empty")
    r = httpx.get(
        "https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/",
        params={"MAP_KEY": key},
        timeout=TIMEOUT,
    )
    if r.status_code != 200:
        return Result(name, False, f"HTTP {r.status_code}: {r.text.strip()[:200]}")
    try:
        data = r.json()
    except ValueError:
        return Result(name, False, f"unexpected reply: {r.text.strip()[:200]}")
    used, limit = data.get("current_transactions"), data.get("transaction_limit")
    interval = data.get("transaction_interval", "")
    return Result(name, limit is not None, f"key active; used {used} of {limit} per {interval}")


def check_xai(s: Settings) -> Result:
    name = "xAI (Grok)"
    key = s.xai_api_key.get_secret_value()
    if not key:
        return Result(name, False, "XAI_API_KEY is empty")
    r = httpx.get(
        f"{s.xai_base_url.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {key}"},
        timeout=TIMEOUT,
    )
    if r.status_code == 401:
        return Result(name, False, "HTTP 401: XAI_API_KEY was rejected (wrong or truncated key)")
    if r.status_code == 403:
        return Result(name, False, "HTTP 403: key accepted but no access (credits not applied?)")
    if r.status_code != 200:
        return Result(name, False, f"HTTP {r.status_code}: {r.text.strip()[:200]}")
    ids = sorted(m["id"] for m in r.json().get("data", []))
    detail = f"{len(ids)} models: {', '.join(ids)}"
    ok = bool(ids)
    if s.xai_model:
        found = s.xai_model in ids
        detail += f" | XAI_MODEL '{s.xai_model}' {'found' if found else 'NOT in the list'}"
        ok = ok and found
    return Result(name, ok, detail)


def check_auth0(s: Settings) -> Result:
    name = "Auth0"
    domain = s.auth0_domain.strip()
    if not domain:
        return Result(name, False, "AUTH0_DOMAIN is empty")
    if domain.startswith(("http://", "https://")) or domain.endswith("/"):
        return Result(
            name, False, "AUTH0_DOMAIN must look like name.us.auth0.com (no https://, no slash)"
        )
    r = httpx.get(f"https://{domain}/.well-known/jwks.json", timeout=TIMEOUT)
    if r.status_code != 200:
        return Result(name, False, f"JWKS HTTP {r.status_code} from {domain}")
    keys = r.json().get("keys", [])
    detail = f"{len(keys)} signing key(s) at {domain}"
    ok = bool(keys)
    if not s.auth0_audience:
        detail += " | AUTH0_AUDIENCE is empty"
        ok = False
    return Result(name, ok, detail)


CHECKS: list[Callable[[Settings], Result]] = [
    check_database,
    check_earth_engine,
    check_firms,
    check_xai,
    check_auth0,
]

NAMES = {
    check_database: "TigerData (Postgres)",
    check_earth_engine: "Earth Engine",
    check_firms: "NASA FIRMS",
    check_xai: "xAI (Grok)",
    check_auth0: "Auth0",
}


def run_checks(s: Settings) -> list[Result]:
    secrets = secret_values(s)
    results = []
    for check in CHECKS:
        try:
            result = check(s)
        except Exception as exc:  # report every failure; one broken service must not stop the rest
            result = Result(NAMES[check], False, f"{type(exc).__name__}: {exc}")
        result.detail = redact(result.detail, secrets)
        results.append(result)
    return results


def main() -> int:
    print("Setup check (secret values are never printed)\n")
    results = run_checks(Settings())
    for r in results:
        print(f"{'✅' if r.ok else '❌'} {r.name}: {r.detail}")
    failed = sum(not r.ok for r in results)
    print(f"\n{len(results) - failed}/{len(results)} services OK")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
