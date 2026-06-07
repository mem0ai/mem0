"""Tests for operational health endpoints exposed by the REST API server."""

import importlib
import os
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from fastapi.testclient import TestClient


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None

    def execute(self, _statement):
        return None


@pytest.fixture
def server_main():
    mock_memory = MagicMock()

    with patch.dict(
        os.environ,
        {"OPENAI_API_KEY": "fake-key", "ADMIN_API_KEY": "", "AUTH_DISABLED": "true"},
    ):
        with patch("mem0.Memory.from_config", return_value=mock_memory):
            import server.main as server_main

            importlib.reload(server_main)
            yield server_main


@pytest.fixture
def client(server_main):
    return TestClient(server_main.app)


def test_health_returns_liveness_payload(client):
    resp = client.get("/api/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "service": "mem0-api"}


def test_ready_returns_ready_when_dependencies_are_available(client, server_main):
    with patch.object(server_main, "SessionLocal", return_value=_FakeSession()):
        with patch.object(server_main, "get_current_config", return_value={"version": "v1.1"}):
            resp = client.get("/api/ready")

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ready",
        "service": "mem0-api",
        "checks": {"database": "ok", "configuration": "ok"},
    }


def test_ready_returns_503_when_database_is_unavailable(client, server_main):
    with patch.object(server_main, "SessionLocal", side_effect=RuntimeError("database down")):
        with patch.object(server_main, "get_current_config", return_value={"version": "v1.1"}):
            resp = client.get("/api/ready")

    assert resp.status_code == 503
    assert resp.json() == {
        "status": "not_ready",
        "service": "mem0-api",
        "checks": {"database": "error", "configuration": "ok"},
    }


def test_ready_returns_503_when_configuration_is_unavailable(client, server_main):
    with patch.object(server_main, "SessionLocal", return_value=_FakeSession()):
        with patch.object(server_main, "get_current_config", side_effect=RuntimeError("config unavailable")):
            resp = client.get("/api/ready")

    assert resp.status_code == 503
    assert resp.json() == {
        "status": "not_ready",
        "service": "mem0-api",
        "checks": {"database": "ok", "configuration": "error"},
    }
