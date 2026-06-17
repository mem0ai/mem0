"""Redis-backed read cache for embedding vectors and search results (ADR-005)."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_query(query: str) -> str:
    """Normalize a query for stable cache keys (trim, lowercase, collapse ws)."""
    return _WHITESPACE_RE.sub(" ", (query or "").strip().lower())


class ReadCache:
    """Cache Redis de embedding e de resultado de busca."""

    def __init__(
        self,
        redis_url: str | None = None,
        embed_ttl: int | None = None,
        search_ttl: int | None = None,
    ):
        self._redis_url = redis_url if redis_url is not None else os.getenv("REDIS_URL")
        self._embed_ttl = int(
            embed_ttl if embed_ttl is not None else os.getenv("REDIS_EMBED_TTL", "3600")
        )
        self._search_ttl = int(
            search_ttl if search_ttl is not None else os.getenv("REDIS_SEARCH_TTL", "300")
        )
        self._client = None
        self._disabled = False

    def _redis(self):
        if self._disabled or not self._redis_url:
            return None
        if self._client is None:
            try:
                import redis

                self._client = redis.from_url(self._redis_url, decode_responses=True)
                self._client.ping()
            except Exception as exc:  # noqa: BLE001 - graceful degradation
                logger.warning("Redis unavailable, read cache disabled: %s", exc)
                self._disabled = True
                return None
        return self._client

    @staticmethod
    def _sha(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    def _embed_key(self, model: str, query: str) -> str:
        return f"embed:v1:{model}:{self._sha(normalize_query(query))}"

    def _search_key(self, project: str, query: str, top_k: int, filter_hash: str) -> str:
        return (
            f"search:v1:{project}:{self._sha(normalize_query(query))}"
            f":{top_k}:{filter_hash}"
        )

    def get_embedding(self, model: str, query: str) -> list[float] | None:
        client = self._redis()
        if client is None:
            return None
        try:
            raw = client.get(self._embed_key(model, query))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            logger.debug("embed cache get failed: %s", exc)
            return None

    def set_embedding(self, model: str, query: str, vector: list[float]) -> None:
        client = self._redis()
        if client is None:
            return
        try:
            client.setex(
                self._embed_key(model, query),
                self._embed_ttl,
                json.dumps(vector),
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("embed cache set failed: %s", exc)

    def get_search(
        self,
        project: str,
        query: str,
        top_k: int,
        filter_hash: str,
    ) -> list[dict] | None:
        client = self._redis()
        if client is None:
            return None
        try:
            raw = client.get(self._search_key(project, query, top_k, filter_hash))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            logger.debug("search cache get failed: %s", exc)
            return None

    def set_search(
        self,
        project: str,
        query: str,
        top_k: int,
        filter_hash: str,
        hits: list[dict],
    ) -> None:
        client = self._redis()
        if client is None:
            return
        try:
            client.setex(
                self._search_key(project, query, top_k, filter_hash),
                self._search_ttl,
                json.dumps(hits),
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("search cache set failed: %s", exc)

    def invalidate_search(self, project: str) -> None:
        """Drop all cached search results for ``project`` after a write."""
        client = self._redis()
        if client is None:
            return
        pattern = f"search:v1:{project}:*"
        try:
            cursor = 0
            while True:
                cursor, keys = client.scan(cursor=cursor, match=pattern, count=200)
                if keys:
                    client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:  # noqa: BLE001
            logger.debug("search cache invalidate failed: %s", exc)


read_cache = ReadCache()
