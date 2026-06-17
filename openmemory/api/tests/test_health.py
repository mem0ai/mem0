"""Tests for /health and /metrics endpoints (task_07)."""

import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("OPENAI_API_KEY", "test-key")


def _load_router(name: str, filename: str):
    path = Path(__file__).resolve().parents[1] / "app" / "routers" / filename
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def health_mod():
    return _load_router("health_mod", "health.py")


@pytest.fixture
def ops_app(health_mod):
    app = FastAPI()
    app.include_router(health_mod.router)
    app.include_router(_load_router("metrics_mod", "ops_metrics.py").router)
    return app


@pytest_asyncio.fixture
async def client(ops_app):
    transport = ASGITransport(app=ops_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealth:
    @pytest.mark.asyncio
    async def test_healthy_when_dependencies_ok(self, client, health_mod):
        with (
            patch.object(health_mod, "_check_database", return_value=("ok", None)),
            patch.object(health_mod, "_check_qdrant", return_value=("ok", None)),
            patch.object(health_mod, "_check_memory_client", return_value=("ok", None)),
            patch.object(health_mod, "_check_queue", return_value=("ok", {"depth": 0})),
        ):
            resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_unhealthy_when_database_fails(self, client, health_mod):
        with (
            patch.object(health_mod, "_check_database", return_value=("error", "down")),
            patch.object(health_mod, "_check_qdrant", return_value=("ok", None)),
            patch.object(health_mod, "_check_memory_client", return_value=("ok", None)),
            patch.object(health_mod, "_check_queue", return_value=("ok", {"depth": 0})),
        ):
            resp = await client.get("/health")
        assert resp.status_code == 503
        assert resp.json()["status"] == "unhealthy"


class TestMetrics:
    @pytest.mark.asyncio
    async def test_metrics_prometheus_format(self, client):
        resp = await client.get("/metrics")
        assert resp.status_code == 200
        assert "mcp_search_latency_seconds" in resp.text
        assert "write_queue_depth" in resp.text
        assert "embed_cache_hit_total" in resp.text
