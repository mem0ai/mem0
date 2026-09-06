"""Regression tests for the admin listing endpoints backed by ``vector_store.list()``.

``GET /memories`` (without entity filters) and ``GET /entities`` read directly from
``vector_store.list()``. That method does not return the same shape on every backend:

* pgvector returns ``[[row, ...]]`` (rows wrapped in a list),
* Qdrant returns the raw ``(rows, next_offset)`` tuple from ``client.scroll()``.

The server only unwrapped the pgvector shape. With Qdrant it iterated over the tuple
itself, so the dashboard showed two empty "memories" and no entity at all, whatever
the size of the collection. Both shapes must yield the same result.
"""

import importlib
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from fastapi.testclient import TestClient  # noqa: E402

ROWS = [
    SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        payload={"data": "Likes hiking", "user_id": "alice", "hash": "h1", "created_at": "2026-01-02T03:04:05Z"},
    ),
    SimpleNamespace(
        id="22222222-2222-2222-2222-222222222222",
        payload={"data": "Prefers tea", "user_id": "alice", "agent_id": "bot", "created_at": "2026-01-03T00:00:00Z"},
    ),
]

QDRANT_SHAPE = (ROWS, None)  # what qdrant_client.scroll() returns
PGVECTOR_SHAPE = [ROWS]  # what mem0's PGVector.list() returns


@pytest.fixture
def mock_memory():
    """Patch Memory.from_config so the server imports without a real backend."""
    mock_instance = MagicMock()
    env = {
        "OPENAI_API_KEY": "fake-key",
        "ADMIN_API_KEY": "",
        "AUTH_DISABLED": "true",
        "JWT_SECRET": "test-secret-long-enough-for-the-startup-check-0123456789",
    }
    with patch.dict(os.environ, env):
        with patch("mem0.Memory.from_config", return_value=mock_instance):
            yield mock_instance


@pytest.fixture
def client(mock_memory):
    import server.main as server_main

    importlib.reload(server_main)
    return TestClient(server_main.app)


@pytest.mark.parametrize("shape", [QDRANT_SHAPE, PGVECTOR_SHAPE], ids=["qdrant-tuple", "pgvector-list"])
def test_list_all_memories_unwraps_both_shapes(client, mock_memory, shape):
    mock_memory.vector_store.list.return_value = shape

    response = client.get("/memories?top_k=10")

    assert response.status_code == 200
    results = response.json()["results"]
    assert [r["id"] for r in results] == [row.id for row in ROWS]
    assert results[0]["memory"] == "Likes hiking"
    assert results[0]["user_id"] == "alice"
    assert results[1]["agent_id"] == "bot"


@pytest.mark.parametrize("shape", [QDRANT_SHAPE, PGVECTOR_SHAPE], ids=["qdrant-tuple", "pgvector-list"])
def test_list_entities_unwraps_both_shapes(client, mock_memory, shape):
    mock_memory.vector_store.list.return_value = shape

    response = client.get("/entities")

    assert response.status_code == 200
    entities = {(e["type"], e["id"]): e["total_memories"] for e in response.json()}
    assert entities == {("user", "alice"): 2, ("agent", "bot"): 1}


def test_list_all_memories_empty_backend(client, mock_memory):
    mock_memory.vector_store.list.return_value = ([], None)

    response = client.get("/memories?top_k=10")

    assert response.status_code == 200
    assert response.json() == {"results": []}
