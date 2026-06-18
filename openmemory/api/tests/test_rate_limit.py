"""Tests for rate limiting per (project, hostname) (task_10 / ADR-006)."""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.rate_limit import RateLimitMiddleware, RedisSlidingWindowLimiter


class FakeRedis:
    def __init__(self):
        self.z = {}

    def zremrangebyscore(self, k, mn, mx):
        d = self.z.get(k, {})
        self.z[k] = {m: s for m, s in d.items() if not (mn <= s <= mx)}

    def zcard(self, k):
        return len(self.z.get(k, {}))

    def zadd(self, k, mapping):
        self.z.setdefault(k, {}).update(mapping)

    def zrange(self, k, a, b, withscores=False):
        items = sorted(self.z.get(k, {}).items(), key=lambda x: x[1])
        sl = items[a:(b + 1) if b >= 0 else None]
        return [(m, s) for m, s in sl] if withscores else [m for m, _ in sl]

    def expire(self, k, t):
        pass


def _limiter(clock_val=1000.0):
    return RedisSlidingWindowLimiter(client=FakeRedis(), clock=lambda: clock_val)


# -- limiter unit tests ----------------------------------------------------

def test_allow_within_limit():
    lim = _limiter()
    for _ in range(3):
        ok, retry = lim.allow("k", limit=3, window=60)
        assert ok and retry == 0


def test_block_over_limit_with_retry():
    lim = _limiter()
    for _ in range(2):
        assert lim.allow("k", 2, 60)[0] is True
    ok, retry = lim.allow("k", 2, 60)
    assert ok is False and retry > 0


def test_independent_keys():
    lim = _limiter()
    assert lim.allow("a", 1, 60)[0] is True
    assert lim.allow("a", 1, 60)[0] is False
    assert lim.allow("b", 1, 60)[0] is True  # chave distinta não afetada


def test_fail_open_without_redis():
    lim = RedisSlidingWindowLimiter(redis_url=None)
    assert lim.allow("k", 1, 60) == (True, 0)


# -- middleware integration ------------------------------------------------

def _app(limiter):
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/x")
    def x():
        return {"ok": True}

    @app.get("/health")
    def health():
        return {"ok": True}

    return app


def test_middleware_blocks_after_search_limit(monkeypatch):
    monkeypatch.setenv("RL_SEARCH_PER_MIN", "2")
    monkeypatch.setenv("RL_BURST", "100")
    with TestClient(_app(_limiter())) as client:
        assert client.get("/x", headers={"x-hostname": "h1"}).status_code == 200
        assert client.get("/x", headers={"x-hostname": "h1"}).status_code == 200
        resp = client.get("/x", headers={"x-hostname": "h1"})
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 0


def test_middleware_independent_projects(monkeypatch):
    monkeypatch.setenv("RL_SEARCH_PER_MIN", "1")
    monkeypatch.setenv("RL_BURST", "100")
    with TestClient(_app(_limiter())) as client:
        h = {"x-hostname": "h1"}
        assert client.get("/x", headers={**h, "x-project": "p1"}).status_code == 200
        # mesmo project esgota
        assert client.get("/x", headers={**h, "x-project": "p1"}).status_code == 429
        # project distinto tem cota própria
        assert client.get("/x", headers={**h, "x-project": "p2"}).status_code == 200


def test_middleware_skips_health(monkeypatch):
    monkeypatch.setenv("RL_SEARCH_PER_MIN", "1")
    monkeypatch.setenv("RL_BURST", "1")
    with TestClient(_app(_limiter())) as client:
        for _ in range(5):
            assert client.get("/health").status_code == 200
