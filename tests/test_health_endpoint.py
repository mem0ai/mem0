"""Tests for the health-check router.

GET /api/health is the unauthenticated probe for load balancers and
orchestrators: 200 when the app is up and the database answers SELECT 1,
503 when the probe raises. The endpoint carries no auth dependency and no
rate limit, so it must answer before any admin is configured -- and its
error body is a fixed shape that cannot leak connection details.
"""

import os
import sys

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

# server/ modules use bare imports (from db import ...), so the server
# directory itself must be importable, mirroring how it runs in Docker.
_SERVER_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "server")
if _SERVER_DIR not in sys.path:
    sys.path.insert(0, _SERVER_DIR)

from routers import health as health_router  # noqa: E402


class _OKSession:
    """Stands in for a SQLAlchemy session against a reachable database."""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args, **_kwargs):
        return None


class _RaisingSession:
    """Stands in for a SQLAlchemy session whose database is unreachable."""

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, *_args, **_kwargs):
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(health_router.router)
    return app


def test_health_returns_200_when_database_connected(app, monkeypatch):
    monkeypatch.setattr(health_router, "SessionLocal", lambda: _OKSession())
    resp = TestClient(app).get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "database": "connected"}


def test_health_returns_503_when_database_unreachable(app, monkeypatch):
    monkeypatch.setattr(health_router, "SessionLocal", lambda: _RaisingSession())
    resp = TestClient(app).get("/api/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "error"
    assert body["database"] == "disconnected"
