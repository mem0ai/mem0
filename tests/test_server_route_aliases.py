"""Tests for REST API route aliases (versioned paths for SDK compatibility).

Verifies that the versioned route aliases (/v1/, /v2/, /v3/) registered on the
server respond with HTTP 200 and call the underlying Memory methods correctly,
matching the behavior of the base routes without the version prefix.
"""

import importlib
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def _mock_memory():
    """Patch Memory.from_config so the server imports without a real backend."""
    # Add server directory to path so imports work
    server_path = os.path.join(os.path.dirname(__file__), "..", "server")
    if server_path not in sys.path:
        sys.path.insert(0, server_path)

    mock_instance = MagicMock()
    mock_instance.add.return_value = {"results": [{"id": "mem-1", "event": "ADD", "memory": "test"}]}
    mock_instance.search.return_value = [{"id": "mem-1", "memory": "test", "score": 0.9}]
    mock_instance.get.return_value = {"id": "mem-1", "memory": "test memory"}
    mock_instance.get_all.return_value = [{"id": "mem-1", "memory": "test memory"}]
    mock_instance.update.return_value = {"message": "Memory updated"}
    mock_instance.history.return_value = [{"id": "mem-1", "old_memory": "a", "new_memory": "b"}]
    mock_instance.delete.return_value = None
    mock_instance.delete_all.return_value = {"message": "Memories deleted"}
    mock_instance.reset.return_value = None

    env = {"OPENAI_API_KEY": "fake-key", "ADMIN_API_KEY": "", "AUTH_DISABLED": "true"}
    with patch.dict(os.environ, env):
        with patch("mem0.Memory.from_config", return_value=mock_instance):
            yield mock_instance


@pytest.fixture
def client(_mock_memory):
    """Return a TestClient wired to the server app with mocked Memory."""
    import server.auth as server_auth
    import server.main as server_main

    env = {"ADMIN_API_KEY": "", "AUTH_DISABLED": "true"}
    with patch.dict(os.environ, env):
        importlib.reload(server_auth)
        importlib.reload(server_main)

    from db import get_db

    mock_db = MagicMock()
    mock_db.scalar.return_value = None
    server_main.app.dependency_overrides[get_db] = lambda: mock_db
    with patch.object(server_main, "SessionLocal", return_value=mock_db):
        yield TestClient(server_main.app)
    server_main.app.dependency_overrides.clear()


@pytest.fixture
def mock_memory(_mock_memory):
    return _mock_memory


# ===========================================================================
# /v1/ping/ alias
# ===========================================================================


class TestV1PingAlias:
    """Verify that GET /v1/ping/ responds with 200."""

    def test_v1_ping_returns_200(self, client):
        resp = client.get("/v1/ping/")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ===========================================================================
# /v3/memories/add/ and /v3/memories/ aliases
# ===========================================================================


class TestV3MemoriesAddAlias:
    """Verify that POST /v3/memories/add/ calls add_memory."""

    def test_v3_memories_add_calls_add_memory(self, client, mock_memory):
        resp = client.post(
            "/v3/memories/add/",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "user_id": "u1",
            },
        )
        assert resp.status_code == 200
        assert mock_memory.add.called

    def test_v3_memories_with_messages_calls_add(self, client, mock_memory):
        resp = client.post(
            "/v3/memories/",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "user_id": "u1",
            },
        )
        assert resp.status_code == 200
        assert mock_memory.add.called

    def test_v3_memories_without_messages_calls_get_all(self, client, mock_memory):
        resp = client.post("/v3/memories/", json={"user_id": "u1"})
        assert resp.status_code == 200
        mock_memory.get_all.assert_called_once()

    def test_base_memories_still_works(self, client, mock_memory):
        resp = client.post(
            "/memories",
            json={
                "messages": [{"role": "user", "content": "test"}],
                "user_id": "u1",
            },
        )
        assert resp.status_code == 200
        assert mock_memory.add.called


# ===========================================================================
# /v1/memories/ alias (get_all)
# ===========================================================================


class TestV1MemoriesListAlias:
    """Verify that GET /v1/memories/ calls get_all_memories."""

    def test_v1_memories_list_calls_get_all(self, client, mock_memory):
        resp = client.get("/v1/memories/?user_id=u1")
        assert resp.status_code == 200
        assert mock_memory.get_all.called

    def test_base_memories_list_still_works(self, client, mock_memory):
        resp = client.get("/memories?user_id=u1")
        assert resp.status_code == 200
        assert mock_memory.get_all.called


# ===========================================================================
# /v1/memories/{id}/ alias (get)
# ===========================================================================


class TestV1MemoriesGetAlias:
    """Verify that GET /v1/memories/{memory_id}/ calls get_memory."""

    def test_v1_memories_get_calls_memory_get(self, client, mock_memory):
        resp = client.get("/v1/memories/mem-1/")
        assert resp.status_code == 200
        assert mock_memory.get.called

    def test_base_memories_get_still_works(self, client, mock_memory):
        resp = client.get("/memories/mem-1")
        assert resp.status_code == 200
        assert mock_memory.get.called


# ===========================================================================
# /v3/memories/search/ alias
# ===========================================================================


class TestV3MemoriesSearchAlias:
    """Verify that POST /v3/memories/search/ calls search_memories."""

    def test_v3_memories_search_calls_search(self, client, mock_memory):
        resp = client.post(
            "/v3/memories/search/",
            json={"query": "food", "user_id": "u1"},
        )
        assert resp.status_code == 200
        assert mock_memory.search.called

    def test_base_search_still_works(self, client, mock_memory):
        resp = client.post(
            "/search",
            json={"query": "food", "user_id": "u1"},
        )
        assert resp.status_code == 200
        assert mock_memory.search.called


# ===========================================================================
# /v1/memories/{id}/ PUT alias (update)
# ===========================================================================


class TestV1MemoriesUpdateAlias:
    """Verify that PUT /v1/memories/{memory_id}/ calls update_memory."""

    def test_v1_memories_update_calls_update(self, client, mock_memory):
        resp = client.put(
            "/v1/memories/mem-1/",
            json={"text": "Updated text"},
        )
        assert resp.status_code == 200
        assert mock_memory.update.called

    def test_base_memories_update_still_works(self, client, mock_memory):
        resp = client.put(
            "/memories/mem-1",
            json={"text": "Updated text"},
        )
        assert resp.status_code == 200
        assert mock_memory.update.called


# ===========================================================================
# /v1/memories/{id}/history/ alias
# ===========================================================================


class TestV1MemoriesHistoryAlias:
    """Verify that GET /v1/memories/{memory_id}/history/ calls memory_history."""

    def test_v1_memories_history_calls_history(self, client, mock_memory):
        resp = client.get("/v1/memories/mem-1/history/")
        assert resp.status_code == 200
        assert mock_memory.history.called

    def test_base_memories_history_still_works(self, client, mock_memory):
        resp = client.get("/memories/mem-1/history")
        assert resp.status_code == 200
        assert mock_memory.history.called


# ===========================================================================
# /v1/memories/{id}/ DELETE alias
# ===========================================================================


class TestV1MemoriesDeleteAlias:
    """Verify that DELETE /v1/memories/{memory_id}/ calls delete_memory."""

    def test_v1_memories_delete_calls_delete(self, client, mock_memory):
        resp = client.delete("/v1/memories/mem-1/")
        assert resp.status_code == 200
        assert mock_memory.delete.called

    def test_base_memories_delete_still_works(self, client, mock_memory):
        resp = client.delete("/memories/mem-1")
        assert resp.status_code == 200
        assert mock_memory.delete.called


# ===========================================================================
# /v1/memories/ DELETE alias (delete_all)
# ===========================================================================


class TestV1MemoriesDeleteAllAlias:
    """Verify that DELETE /v1/memories/ calls delete_all_memories."""

    def test_v1_memories_delete_all_calls_delete_all(self, client, mock_memory):
        resp = client.delete("/v1/memories/?user_id=u1")
        assert resp.status_code == 200
        assert mock_memory.delete_all.called

    def test_base_memories_delete_all_still_works(self, client, mock_memory):
        resp = client.delete("/memories?user_id=u1")
        assert resp.status_code == 200
        assert mock_memory.delete_all.called


# ===========================================================================
# /v1/reset/ alias
# ===========================================================================


class TestV1ResetAlias:
    """Verify that POST /v1/reset/ calls reset_memory."""

    def test_v1_reset_calls_reset(self, client, mock_memory):
        resp = client.post("/v1/reset/")
        assert resp.status_code == 200
        assert mock_memory.reset.called

    def test_base_reset_still_works(self, client, mock_memory):
        resp = client.post("/reset")
        assert resp.status_code == 200
        assert mock_memory.reset.called


# ===========================================================================
# /v1/entities/ alias
# ===========================================================================


class TestV1EntitiesListAlias:
    """Verify that GET /v1/entities/ calls list_entities."""

    def test_v1_entities_list(self, client, mock_memory):
        # Mock the vector_store.list() method since list_entities calls it
        mock_memory.vector_store.list.return_value = [[], []]
        resp = client.get("/v1/entities/")
        assert resp.status_code == 200

    def test_base_entities_list_still_works(self, client, mock_memory):
        mock_memory.vector_store.list.return_value = [[], []]
        resp = client.get("/entities")
        assert resp.status_code == 200


# ===========================================================================
# /v2/entities/{type}/{id}/ alias
# ===========================================================================


class TestV2EntitiesDeleteAlias:
    """Verify that DELETE /v2/entities/{entity_type}/{entity_id}/ calls delete_entity."""

    def test_v2_entities_delete(self, client, mock_memory):
        resp = client.delete("/v2/entities/user/user-1/")
        assert resp.status_code == 200
        assert mock_memory.delete_all.called

    def test_base_entities_delete_still_works(self, client, mock_memory):
        resp = client.delete("/entities/user/user-1")
        assert resp.status_code == 200
        assert mock_memory.delete_all.called
