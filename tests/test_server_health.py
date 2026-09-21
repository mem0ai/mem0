"""Tests for server /health and /api/health endpoints (#7397)."""
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure server module is discoverable
server_dir = Path(__file__).resolve().parent.parent / "server"
if str(server_dir) not in sys.path:
    sys.path.insert(0, str(server_dir))

pytest.importorskip("fastapi", reason="fastapi not installed")
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a TestClient with mocked background dependencies."""
    with patch.dict(os.environ, {"AUTH_DISABLED": "true", "OPENAI_API_KEY": "fake-key"}):
        mock_memory = MagicMock()
        with patch("mem0.Memory.from_config", return_value=mock_memory):
            import server.main as server_main
            return TestClient(server_main.app)


def test_health_endpoint_healthy(client):
    """Verify /health returns 200 when database probe succeeds."""
    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = None

    with patch("server.main.SessionLocal", return_value=mock_session):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "database": "connected"}
        mock_session.execute.assert_called_once()


def test_api_health_endpoint_healthy(client):
    """Verify /api/health returns 200 when database probe succeeds."""
    mock_session = MagicMock()
    mock_session.__enter__.return_value = mock_session
    mock_session.__exit__.return_value = None

    with patch("server.main.SessionLocal", return_value=mock_session):
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy", "database": "connected"}
        mock_session.execute.assert_called_once()


def test_health_endpoint_db_failure(client):
    """Verify /health returns 503 when database probe fails."""
    mock_session = MagicMock()
    mock_session.__enter__.side_effect = Exception("DB connection refused")
    mock_session.__exit__.return_value = None

    with patch("server.main.SessionLocal", return_value=mock_session):
        response = client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert "DB connection refused" in data["error"]


def test_health_endpoints_unauthenticated(client):
    """Verify /health and /api/health are accessible without auth even if admin key is set."""
    with patch("server.main.ADMIN_API_KEY", "very-secret-admin-key-123456"):
        with patch("server.main.AUTH_DISABLED", False):
            mock_session = MagicMock()
            mock_session.__enter__.return_value = mock_session
            mock_session.__exit__.return_value = None

            with patch("server.main.SessionLocal", return_value=mock_session):
                resp1 = client.get("/health")
                assert resp1.status_code == 200
                resp2 = client.get("/api/health")
                assert resp2.status_code == 200


def test_skipped_request_log_paths_includes_health():
    """Verify /health is in SKIPPED_REQUEST_LOG_PATHS to prevent request log spam."""
    import server.main as server_main
    assert "/health" in server_main.SKIPPED_REQUEST_LOG_PATHS
    assert "/api/health" in server_main.SKIPPED_REQUEST_LOG_PATHS
