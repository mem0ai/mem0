"""
CAG (Cache-Augmented Generation) layer for OpenMemory search.

Search on the MCP path costs one embedding call (OpenAI, cross-region) plus one
or two Qdrant Cloud round-trips per query. Repeated/near-duplicate queries are
common (agents re-search the same intent), so a short-lived per-user cache cuts
both latency and external API cost dramatically.

Two backends, selected automatically:

- In-process (default): an LRU + TTL dict, plus optional embedding-similarity
  matching so semantically-equivalent queries ("my email?" vs "what's my email")
  share a cache entry. Zero infra. Per-worker (each uvicorn worker keeps its own).
- Redis (when ``REDIS_URL`` is set): shared across all workers and survives
  restarts. Exact-match only — a cross-key similarity scan in Redis is too costly.

The cache is keyed by ``(user_id, normalized_query)`` and invalidated per-user on
any write (add/update/delete), so it can never serve stale memories.
"""

import json
import logging
import math
import os
import threading
import time
from collections import OrderedDict
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# Defaults are conservative; all tunable via env.
_DEFAULT_TTL_SECONDS = int(os.environ.get("OPENMEMORY_CACHE_TTL", "300"))
_DEFAULT_MAX_ENTRIES = int(os.environ.get("OPENMEMORY_CACHE_MAX_ENTRIES", "1024"))
# Cosine similarity above which two query embeddings are treated as the same query.
_DEFAULT_SIM_THRESHOLD = float(os.environ.get("OPENMEMORY_CACHE_SIM_THRESHOLD", "0.97"))
# Master switch.
_CACHE_ENABLED = os.environ.get("OPENMEMORY_CACHE_ENABLED", "true").lower() == "true"


def _normalize_query(query: str) -> str:
    """Collapse whitespace and lowercase so trivially-different queries collide."""
    return " ".join(query.lower().split())


def _cosine(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two equal-length vectors. Returns 0.0 on mismatch."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


class BaseSearchCache:
    """Interface for the search cache backends."""

    def get(self, user_id: str, query: str, embedding: Optional[List[float]] = None) -> Optional[List[Any]]:
        raise NotImplementedError

    def set(
        self,
        user_id: str,
        query: str,
        results: List[Any],
        embedding: Optional[List[float]] = None,
    ) -> None:
        raise NotImplementedError

    def invalidate(self, user_id: str) -> None:
        raise NotImplementedError


class InProcessSearchCache(BaseSearchCache):
    """Thread-safe LRU + TTL cache with optional embedding-similarity matching."""

    def __init__(
        self,
        ttl_seconds: int = _DEFAULT_TTL_SECONDS,
        max_entries: int = _DEFAULT_MAX_ENTRIES,
        sim_threshold: float = _DEFAULT_SIM_THRESHOLD,
    ):
        self._ttl = ttl_seconds
        self._max_entries = max_entries
        self._sim_threshold = sim_threshold
        self._lock = threading.RLock()
        # key -> {"results", "expiry", "embedding"}; OrderedDict gives LRU eviction.
        self._store: "OrderedDict[tuple, dict]" = OrderedDict()

    def _key(self, user_id: str, query: str) -> tuple:
        return (user_id, _normalize_query(query))

    def _purge_expired_locked(self, now: float) -> None:
        expired = [k for k, v in self._store.items() if v["expiry"] <= now]
        for k in expired:
            self._store.pop(k, None)

    def get(self, user_id: str, query: str, embedding: Optional[List[float]] = None) -> Optional[List[Any]]:
        now = time.monotonic()
        key = self._key(user_id, query)
        with self._lock:
            entry = self._store.get(key)
            if entry and entry["expiry"] > now:
                self._store.move_to_end(key)
                return entry["results"]
            if entry:
                self._store.pop(key, None)

            # Semantic fallback: scan this user's live entries for a near-identical query.
            if embedding is None:
                return None
            best = None
            best_sim = self._sim_threshold
            for k, v in self._store.items():
                if k[0] != user_id or v["expiry"] <= now or not v.get("embedding"):
                    continue
                sim = _cosine(embedding, v["embedding"])
                if sim >= best_sim:
                    best_sim = sim
                    best = k
            if best is not None:
                self._store.move_to_end(best)
                return self._store[best]["results"]
            return None

    def set(
        self,
        user_id: str,
        query: str,
        results: List[Any],
        embedding: Optional[List[float]] = None,
    ) -> None:
        now = time.monotonic()
        key = self._key(user_id, query)
        with self._lock:
            self._purge_expired_locked(now)
            self._store[key] = {
                "results": results,
                "expiry": now + self._ttl,
                "embedding": embedding,
            }
            self._store.move_to_end(key)
            while len(self._store) > self._max_entries:
                self._store.popitem(last=False)

    def invalidate(self, user_id: str) -> None:
        with self._lock:
            for k in [k for k in self._store if k[0] == user_id]:
                self._store.pop(k, None)


class RedisSearchCache(BaseSearchCache):
    """Exact-match cache shared across workers, backed by Redis.

    Per-user entries are tracked in a Redis set so invalidation can drop them all
    in one round-trip without a key scan.
    """

    def __init__(self, redis_url: str, ttl_seconds: int = _DEFAULT_TTL_SECONDS):
        import redis  # imported lazily so redis is only required when REDIS_URL is set

        self._client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl_seconds

    def _entry_key(self, user_id: str, query: str) -> str:
        return f"om:cache:{user_id}:{_normalize_query(query)}"

    def _index_key(self, user_id: str) -> str:
        return f"om:cache:index:{user_id}"

    def get(self, user_id: str, query: str, embedding: Optional[List[float]] = None) -> Optional[List[Any]]:
        try:
            raw = self._client.get(self._entry_key(user_id, query))
            return json.loads(raw) if raw else None
        except Exception as e:  # never let cache failures break search
            logger.warning(f"Redis cache get failed: {e}")
            return None

    def set(
        self,
        user_id: str,
        query: str,
        results: List[Any],
        embedding: Optional[List[float]] = None,
    ) -> None:
        try:
            entry_key = self._entry_key(user_id, query)
            pipe = self._client.pipeline()
            pipe.set(entry_key, json.dumps(results), ex=self._ttl)
            pipe.sadd(self._index_key(user_id), entry_key)
            pipe.expire(self._index_key(user_id), self._ttl)
            pipe.execute()
        except Exception as e:
            logger.warning(f"Redis cache set failed: {e}")

    def invalidate(self, user_id: str) -> None:
        try:
            index_key = self._index_key(user_id)
            members = self._client.smembers(index_key)
            pipe = self._client.pipeline()
            for m in members:
                pipe.delete(m)
            pipe.delete(index_key)
            pipe.execute()
        except Exception as e:
            logger.warning(f"Redis cache invalidate failed: {e}")


_cache_instance: Optional[BaseSearchCache] = None
_cache_lock = threading.Lock()


def get_search_cache() -> Optional[BaseSearchCache]:
    """Return the process-wide cache singleton, or None if caching is disabled."""
    global _cache_instance
    if not _CACHE_ENABLED:
        return None
    if _cache_instance is not None:
        return _cache_instance
    with _cache_lock:
        if _cache_instance is not None:
            return _cache_instance
        redis_url = os.environ.get("REDIS_URL")
        if redis_url:
            try:
                _cache_instance = RedisSearchCache(redis_url)
                logger.info("Search cache: using Redis backend")
            except Exception as e:
                logger.warning(f"Redis cache unavailable ({e}); falling back to in-process cache")
                _cache_instance = InProcessSearchCache()
        else:
            _cache_instance = InProcessSearchCache()
            logger.info("Search cache: using in-process backend")
    return _cache_instance


def reset_search_cache() -> None:
    """Reset the cache singleton (used by tests)."""
    global _cache_instance
    with _cache_lock:
        _cache_instance = None
