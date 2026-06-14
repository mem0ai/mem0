"""Unit tests for the CAG search cache (app.utils.cache)."""

import time

from app.utils.cache import InProcessSearchCache


def _results(*ids):
    return [{"id": i, "memory": f"m-{i}"} for i in ids]


def test_set_and_exact_get():
    cache = InProcessSearchCache(ttl_seconds=60)
    cache.set("u1", "What is my email?", _results("a", "b"))
    assert cache.get("u1", "What is my email?") == _results("a", "b")


def test_query_normalization_collides():
    cache = InProcessSearchCache(ttl_seconds=60)
    cache.set("u1", "My  Email", _results("a"))
    # Different casing/whitespace must hit the same entry.
    assert cache.get("u1", "my email") == _results("a")


def test_user_isolation():
    cache = InProcessSearchCache(ttl_seconds=60)
    cache.set("u1", "q", _results("a"))
    assert cache.get("u2", "q") is None


def test_ttl_expiry():
    cache = InProcessSearchCache(ttl_seconds=0)  # immediately expired
    cache.set("u1", "q", _results("a"))
    time.sleep(0.01)
    assert cache.get("u1", "q") is None


def test_lru_eviction():
    cache = InProcessSearchCache(ttl_seconds=60, max_entries=2)
    cache.set("u1", "q1", _results("a"))
    cache.set("u1", "q2", _results("b"))
    cache.get("u1", "q1")  # touch q1 so q2 becomes least-recent
    cache.set("u1", "q3", _results("c"))  # evicts q2
    assert cache.get("u1", "q1") == _results("a")
    assert cache.get("u1", "q3") == _results("c")
    assert cache.get("u1", "q2") is None


def test_invalidate_drops_only_target_user():
    cache = InProcessSearchCache(ttl_seconds=60)
    cache.set("u1", "q", _results("a"))
    cache.set("u2", "q", _results("b"))
    cache.invalidate("u1")
    assert cache.get("u1", "q") is None
    assert cache.get("u2", "q") == _results("b")


def test_semantic_similarity_hit():
    cache = InProcessSearchCache(ttl_seconds=60, sim_threshold=0.9)
    cache.set("u1", "stored query", _results("a"), embedding=[1.0, 0.0, 0.0])
    # A different query string but near-identical embedding should hit.
    hit = cache.get("u1", "totally different words", embedding=[0.99, 0.01, 0.0])
    assert hit == _results("a")


def test_semantic_similarity_miss_below_threshold():
    cache = InProcessSearchCache(ttl_seconds=60, sim_threshold=0.99)
    cache.set("u1", "stored query", _results("a"), embedding=[1.0, 0.0, 0.0])
    assert cache.get("u1", "different", embedding=[0.0, 1.0, 0.0]) is None
