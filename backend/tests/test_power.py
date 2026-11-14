"""NASA POWER fetcher tests. No network: fixtures are real responses saved on Nov 14, 2026."""

import json
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

from app.data import power
from app.data.cache import FileCache

FIXTURES = Path(__file__).parent / "fixtures"
DAILY = json.loads((FIXTURES / "power_daily_15.6_120.9_2024.json").read_text())
CLIM = json.loads((FIXTURES / "power_climatology_15.6_120.9_1991-2020.json").read_text())
LAT, LON = 15.6, 120.9
Y2024 = (date(2024, 1, 1), date(2024, 12, 31))


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(power, "_sleep", lambda seconds: None)


def replay_client(responses, calls):
    """An httpx client that replays responses in order and records every request it gets.

    Each response is (status, body) or an exception class to raise (e.g. httpx.ReadTimeout).
    """
    queue = iter(responses)

    def handler(request):
        calls.append(request)
        item = next(queue)
        if isinstance(item, type) and issubclass(item, Exception):
            raise item("simulated", request=request)
        status, body = item
        if isinstance(body, dict):
            return httpx.Response(status, json=body)
        return httpx.Response(status, text=body)

    return httpx.Client(transport=httpx.MockTransport(handler))


# --- parsing ---------------------------------------------------------------------------------


def test_parse_daily_2024():
    d = power.parse_daily(DAILY)
    assert len(d.rows) == 366  # 2024 is a leap year
    assert (d.start, d.end) == Y2024
    assert set(power.PARAMETERS) <= set(d.rows[0])
    assert d.units["PRECTOTCORR"] == "mm/day"
    assert d.units["T2M"] == "C"
    assert all(r[p] is not None for r in d.rows for p in power.PARAMETERS)
    for r in d.rows:
        assert 10 < r["T2M"] < 40
        assert r["PRECTOTCORR"] >= 0
        assert 0 <= r["RH2M"] <= 100
    assert d.native_resolution.startswith("0.5°")


def test_parse_climatology_shows_wet_and_dry_seasons():
    c = power.parse_climatology(CLIM)
    assert c.period == "1991-2020"
    assert all(len(values) == 12 for values in c.monthly.values())
    rain = c.monthly["PRECTOTCORR"]
    assert min(rain[6:9]) > 3 * max(rain[0:3])  # Jul-Sep far wetter than Jan-Mar in Central Luzon
    assert c.annual["T2M"] is not None


def test_climatology_min_is_the_coldest_hour_not_the_average_night():
    c = power.parse_climatology(CLIM)
    jan_nights = [r["T2M_MIN"] for r in power.parse_daily(DAILY).rows if r["date"].month == 1]
    assert c.monthly["T2M_MIN"][0] < sum(jan_nights) / len(jan_nights)


def test_fill_values_become_none():
    payload = {
        "geometry": {"coordinates": [1.0, 2.0, 3.0]},
        "properties": {"parameter": {"T2M": {"20240101": -999.0, "20240102": 21.5}}},
        "header": {"fill_value": -999.0},
        "parameters": {"T2M": {"units": "C"}},
    }
    assert [r["T2M"] for r in power.parse_daily(payload).rows] == [None, 21.5]


def test_unexpected_response_raises_power_error():
    with pytest.raises(power.PowerError):
        power.parse_daily({"messages": ["something went wrong"]})


# --- requests --------------------------------------------------------------------------------


@pytest.mark.parametrize("lat,lon", [(91, 0), (-91, 0), (0, 181), (0, -181)])
def test_rejects_bad_coordinates(lat, lon):
    with pytest.raises(ValueError):
        power.daily_request(lat, lon, *Y2024)


def test_rejects_bad_dates():
    with pytest.raises(ValueError):
        power.daily_request(LAT, LON, date(2024, 2, 1), date(2024, 1, 1))
    with pytest.raises(ValueError):
        power.daily_request(LAT, LON, date(1980, 1, 1), date(1980, 12, 31))


# --- fetching: cache and retries ---------------------------------------------------------------


def test_second_call_comes_from_cache(tmp_path):
    calls = []
    client = replay_client([(200, DAILY)], calls)
    cache = FileCache(tmp_path)
    first = power.fetch_daily(LAT, LON, *Y2024, client=client, cache=cache)
    second = power.fetch_daily(LAT, LON, *Y2024, client=client, cache=cache)
    assert len(calls) == 1
    assert first.rows == second.rows
    query = calls[0].url.params
    assert query["community"] == "AG"
    assert (query["start"], query["end"]) == ("20240101", "20241231")
    assert query["parameters"].split(",") == list(power.PARAMETERS)


def test_recent_ranges_expire_after_a_day():
    class SpyCache:
        def __init__(self):
            self.max_ages = []

        def get(self, key, max_age_s=None):
            self.max_ages.append(max_age_s)
            return DAILY

        def set(self, key, value):
            pass

    spy = SpyCache()
    last_week = (date.today() - timedelta(days=10), date.today() - timedelta(days=3))
    power.fetch_daily_payload(LAT, LON, *last_week, cache=spy)
    power.fetch_daily_payload(LAT, LON, *Y2024, cache=spy)
    assert spy.max_ages == [power.RECENT_MAX_AGE_S, None]


def test_retries_server_errors_then_succeeds(tmp_path):
    calls = []
    client = replay_client([(503, "busy"), (200, CLIM)], calls)
    c = power.fetch_climatology(LAT, LON, client=client, cache=FileCache(tmp_path))
    assert len(calls) == 2
    assert c.period == "1991-2020"


def test_retries_timeouts(tmp_path):
    calls = []
    client = replay_client([httpx.ReadTimeout, (200, CLIM)], calls)
    power.fetch_climatology(LAT, LON, client=client, cache=FileCache(tmp_path))
    assert len(calls) == 2


def test_gives_up_after_max_attempts(tmp_path):
    calls = []
    client = replay_client([(503, "busy")] * power.MAX_ATTEMPTS, calls)
    with pytest.raises(power.PowerError, match=f"after {power.MAX_ATTEMPTS} attempts"):
        power.fetch_climatology(LAT, LON, client=client, cache=FileCache(tmp_path))
    assert len(calls) == power.MAX_ATTEMPTS


def test_bad_request_is_not_retried(tmp_path):
    calls = []
    client = replay_client([(422, "bad parameter")], calls)
    with pytest.raises(power.PowerError, match="HTTP 422"):
        power.fetch_climatology(LAT, LON, client=client, cache=FileCache(tmp_path))
    assert len(calls) == 1
