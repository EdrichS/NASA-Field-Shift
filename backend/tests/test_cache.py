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


# --- MemoryCache: repeat reads skip the slower cache behind it -----------------------------------


class CountingCache:
    def __init__(self):
        self.data, self.reads = {}, 0

    def get(self, key, max_age_s=None):
        self.reads += 1
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value


def test_memory_cache_serves_repeat_reads_from_memory():
    from app.data.cache import MemoryCache

    inner = CountingCache()
    inner.data["power:a"] = {"x": 1}
    cache = MemoryCache(inner)
    assert cache.get("power:a") == {"x": 1} and cache.get("power:a") == {"x": 1}
    assert inner.reads == 1
    assert cache.get("missing") is None and cache.get("missing") is None
    assert inner.reads == 3  # misses are not remembered


def test_memory_cache_respects_max_age_and_size(monkeypatch):
    from app.data import cache as cache_mod

    clock = [1000.0]
    monkeypatch.setattr(cache_mod.time, "monotonic", lambda: clock[0])
    inner = CountingCache()
    cache = cache_mod.MemoryCache(inner, max_items=2)
    cache.set("k1", 1)
    clock[0] += 120
    assert cache.get("k1", max_age_s=60) == 1  # re-read from the inner cache, not memory
    assert inner.reads == 1
    cache.set("k2", 2)
    cache.set("k3", 3)  # evicts the oldest entry (k1)
    assert cache.get("k1") == 1 and inner.reads == 2
