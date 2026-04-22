import importlib
import os
import sys
from types import ModuleType
from unittest.mock import MagicMock, call, patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")

from fastapi.testclient import TestClient


@pytest.fixture
def oss_server_client():
    mock_memory = MagicMock()
    mock_memory.add.return_value = {"results": [{"id": "mem-1", "memory": "test"}]}
    mock_memory.get.return_value = {"id": "mem-1", "memory": "test"}
    mock_memory.get_all.return_value = [{"id": "mem-1", "memory": "test"}]
    mock_memory.search.return_value = [{"id": "mem-1", "memory": "test", "score": 0.9}]
    mock_memory.update.return_value = {"message": "Memory updated"}
    mock_memory.history.return_value = [{"id": "mem-1", "event": "UPDATE"}]
    mock_memory.delete.return_value = None
    mock_memory.delete_all.return_value = {"message": "Memories deleted"}
    mock_memory.reset.return_value = None

    memory_cls = MagicMock()
    memory_cls.from_config.return_value = mock_memory
    mem0_module = ModuleType("mem0")
    mem0_module.Memory = memory_cls

    with patch.dict(os.environ, {"OPENAI_API_KEY": "fake-key", "ADMIN_API_KEY": ""}):
        with patch.dict(sys.modules, {"mem0": mem0_module}):
            sys.modules.pop("server.main", None)
            server_main = importlib.import_module("server.main")
            try:
                yield TestClient(server_main.app), mock_memory
            finally:
                sys.modules.pop("server.main", None)


def test_v1_ping_route_matches_python_client_validation_path(oss_server_client):
    client, _ = oss_server_client

    response = client.get("/v1/ping/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_v1_memory_routes_reuse_oss_handlers(oss_server_client):
    client, mock_memory = oss_server_client

    add_response = client.post(
        "/v1/memories/",
        json={"messages": [{"role": "user", "content": "I like tennis"}], "user_id": "user-1"},
    )
    get_all_response = client.get("/v1/memories/", params={"user_id": "user-1"})
    get_response = client.get("/v1/memories/mem-1/")
    search_response = client.post("/v1/search/", json={"query": "tennis", "user_id": "user-1"})
    v2_get_all_response = client.post("/v2/memories/", json={"user_id": "user-1"})
    v2_search_response = client.post("/v2/memories/search/", json={"query": "tennis", "user_id": "user-1"})
    update_response = client.put("/v1/memories/mem-1/", json={"text": "I like squash"})
    history_response = client.get("/v1/memories/mem-1/history/")
    delete_response = client.delete("/v1/memories/mem-1/")
    delete_all_response = client.delete("/v1/memories/", params={"user_id": "user-1"})

    assert add_response.status_code == 200
    assert get_all_response.status_code == 200
    assert get_response.status_code == 200
    assert search_response.status_code == 200
    assert v2_get_all_response.status_code == 200
    assert v2_search_response.status_code == 200
    assert update_response.status_code == 200
    assert history_response.status_code == 200
    assert delete_response.status_code == 200
    assert delete_all_response.status_code == 200

    mock_memory.add.assert_called_once()
    mock_memory.get_all.assert_has_calls([call(user_id="user-1"), call(user_id="user-1")])
    mock_memory.get.assert_called_once_with("mem-1")
    mock_memory.search.assert_has_calls(
        [call(query="tennis", user_id="user-1"), call(query="tennis", user_id="user-1")]
    )
    mock_memory.update.assert_called_once_with(memory_id="mem-1", data="I like squash", metadata=None)
    mock_memory.history.assert_called_once_with(memory_id="mem-1")
    mock_memory.delete.assert_called_once_with(memory_id="mem-1")
    mock_memory.delete_all.assert_called_once_with(user_id="user-1")
