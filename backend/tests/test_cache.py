import os
import time

from app.data.cache import DbCache, FileCache


def test_db_cache_errors_are_a_miss_not_a_crash():
    # Nothing listens on port 1, so every call fails fast. A cache problem must not break fetches.
    cache = DbCache("postgresql://nobody:nothing@127.0.0.1:1/none")
    assert cache.get("power:anything") is None
    cache.set("power:anything", {"a": 1})  # must not raise


def test_round_trip(tmp_path):
    cache = FileCache(tmp_path)
    cache.set("key", {"a": [1, 2.5, None]})
    assert cache.get("key") == {"a": [1, 2.5, None]}


def test_missing_key_returns_none(tmp_path):
    assert FileCache(tmp_path).get("nope") is None


def test_max_age_expires_old_entries(tmp_path):
    cache = FileCache(tmp_path)
    cache.set("key", 1)
    an_hour_ago = time.time() - 3600
    os.utime(cache._path("key"), (an_hour_ago, an_hour_ago))
    assert cache.get("key", max_age_s=60) is None
    assert cache.get("key") == 1  # no max age: never expires


def test_corrupt_entry_returns_none(tmp_path):
    cache = FileCache(tmp_path)
    cache.set("key", 1)
    cache._path("key").write_text("{not json")
    assert cache.get("key") is None
