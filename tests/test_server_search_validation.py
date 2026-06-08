import importlib
import os
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from fastapi.testclient import TestClient


@pytest.fixture
def mock_memory():
    mock_instance = MagicMock()
    mock_instance.search.return_value = [{"id": "mem-1", "memory": "test", "score": 0.9}]

    with patch.dict(
        os.environ,
        {"OPENAI_API_KEY": "fake-key", "ADMIN_API_KEY": "", "AUTH_DISABLED": "true"},
    ):
        with patch("mem0.Memory.from_config", return_value=mock_instance):
            yield mock_instance


@pytest.fixture
def client(mock_memory):
    import auth
    import server.main as server_main

    with patch.dict(
        os.environ,
        {"OPENAI_API_KEY": "fake-key", "ADMIN_API_KEY": "", "AUTH_DISABLED": "true"},
    ):
        importlib.reload(auth)
        importlib.reload(server_main)
    return TestClient(server_main.app)


def test_search_without_identifier_filters_returns_400(client, mock_memory):
    resp = client.post("/search", json={"query": "food"})

    assert resp.status_code == 400
    assert "filters must contain at least one of" in resp.json()["detail"]
    mock_memory.search.assert_not_called()


def test_search_with_metadata_only_filters_returns_400(client, mock_memory):
    resp = client.post(
        "/search",
        json={
            "query": "food",
            "filters": {"category": "food"},
        },
    )

    assert resp.status_code == 400
    assert "filters must contain at least one of" in resp.json()["detail"]
    mock_memory.search.assert_not_called()
