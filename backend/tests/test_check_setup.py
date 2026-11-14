import check_setup
from app.config import Settings

ENV_NAMES = [
    "EARTHDATA_USERNAME", "EARTHDATA_PASSWORD", "FIRMS_MAP_KEY", "EE_PROJECT", "XAI_API_KEY",
    "XAI_BASE_URL", "XAI_MODEL", "AUTH0_DOMAIN", "AUTH0_AUDIENCE", "DATABASE_URL",
]


def test_redact_hides_every_secret_form():
    s = Settings(
        _env_file=None,
        firms_map_key="firmskey1234",
        xai_api_key="xai-abcdef",
        database_url="postgres://tsdbadmin:p%40ss#w@host:5432/tsdb",
    )
    msg = (
        "GET https://firms/?MAP_KEY=firmskey1234 failed; Bearer xai-abcdef; "
        "postgres://tsdbadmin:p%40ss#w@host:5432/tsdb; password p@ss#w"
    )
    out = check_setup.redact(msg, check_setup.secret_values(s))
    for secret in ("firmskey1234", "xai-abcdef", "p%40ss", "p@ss#w"):
        assert secret not in out


def test_empty_settings_fail_cleanly_without_network(monkeypatch):
    for name in ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    results = check_setup.run_checks(Settings(_env_file=None))
    assert len(results) == 5
    for r in results:
        assert not r.ok
        assert "is empty" in r.detail


def test_auth0_domain_with_https_is_rejected_without_network():
    r = check_setup.check_auth0(Settings(_env_file=None, auth0_domain="https://x.us.auth0.com"))
    assert not r.ok and "no https://" in r.detail
