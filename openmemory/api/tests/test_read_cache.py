"""Tests for ReadCache (task_05 / ADR-005)."""

from unittest.mock import MagicMock, patch


from app.utils.read_cache import ReadCache, normalize_query


class TestNormalizeQuery:
    def test_trim_lowercase_collapse_whitespace(self):
        assert normalize_query("  Hello   World  ") == "hello world"


class TestReadCacheUnit:
    def test_embedding_miss_then_hit(self):
        store = {}
        client = MagicMock()

        def _get(key):
            return store.get(key)

        def _setex(key, ttl, value):
            store[key] = value

        client.get.side_effect = _get
        client.setex.side_effect = _setex
        client.ping.return_value = True

        cache = ReadCache(redis_url="redis://localhost:6379/0", embed_ttl=60)
        with patch("redis.from_url", return_value=client):
            assert cache.get_embedding("m1", "query") is None
            cache.set_embedding("m1", "query", [0.1, 0.2])
            assert cache.get_embedding("m1", "query") == [0.1, 0.2]

    def test_equivalent_queries_share_key(self):
        cache = ReadCache(redis_url="redis://x")
        k1 = cache._embed_key("m", "Foo  Bar")
        k2 = cache._embed_key("m", "foo bar")
        assert k1 == k2

    def test_redis_unavailable_returns_miss(self):
        cache = ReadCache(redis_url="redis://bad:1")
        with patch("redis.from_url", side_effect=ConnectionError("down")):
            assert cache.get_embedding("m", "q") is None
            assert cache.get_search("p", "q", 5, "fh") is None

    def test_invalidate_search_deletes_project_keys(self):
        client = MagicMock()
        client.ping.return_value = True
        client.scan.side_effect = [
            (0, ["search:v1:proj-a:abc:5:fh", "search:v1:proj-a:def:5:fh"]),
        ]
        cache = ReadCache(redis_url="redis://x")
        with patch("redis.from_url", return_value=client):
            cache.invalidate_search("proj-a")
        client.delete.assert_called_once()

    def test_search_roundtrip(self):
        store = {}
        client = MagicMock()
        client.ping.return_value = True
        client.get.side_effect = lambda k: store.get(k)
        client.setex.side_effect = lambda k, ttl, v: store.__setitem__(k, v)

        cache = ReadCache(redis_url="redis://x", search_ttl=30)
        hits = [{"id": "1", "memory": "x"}]
        with patch("redis.from_url", return_value=client):
            cache.set_search("proj", "q", 10, "fh", hits)
            raw = cache.get_search("proj", "q", 10, "fh")
        assert raw == hits
