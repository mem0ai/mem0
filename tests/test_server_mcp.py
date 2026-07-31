from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from auth import verify_auth
from server.mcp_server import (
    _is_admin,
    _map_app_id,
    _scope_filters,
    add_memory,
    delete_all_memories,
    get_memories,
    mcp_router,
    search_memories,
)


def test_map_app_id_preserves_explicit_agent_id():
    assert _map_app_id({"app_id": "alias", "agent_id": "explicit"}) == {"agent_id": "explicit"}


def test_scope_filters_maps_app_id_and_combines_metadata():
    filters = _scope_filters(
        {"metadata": {"type": "decision"}},
        user_id="alice",
        agent_id=None,
        app_id="repo",
        run_id=None,
    )

    assert filters == {
        "AND": [
            {"user_id": "alice", "agent_id": "repo"},
            {"metadata": {"type": "decision"}},
        ]
    }


def test_scope_filters_rejects_unscoped_access():
    with pytest.raises(ValueError, match="at least one"):
        _scope_filters(None, user_id=None, agent_id=None, app_id=None, run_id=None)


@patch("server.mcp_server.get_memory_instance")
def test_add_memory_uses_shared_memory_instance(get_memory_instance):
    memory = Mock()
    memory.add.return_value = {"results": [{"id": "memory-1"}]}
    get_memory_instance.return_value = memory

    result = add_memory(text="Use Postgres", user_id="alice", app_id="repo")

    assert result == {"results": [{"id": "memory-1"}]}
    memory.add.assert_called_once_with(
        messages=[{"role": "user", "content": "Use Postgres"}],
        user_id="alice",
        agent_id="repo",
        infer=True,
    )


@patch("server.mcp_server.get_memory_instance")
def test_search_memory_is_scoped(get_memory_instance):
    memory = Mock()
    memory.search.return_value = {"results": []}
    get_memory_instance.return_value = memory

    search_memories(query="database", user_id="alice", app_id="repo", top_k=5)

    memory.search.assert_called_once_with(
        query="database",
        filters={"user_id": "alice", "agent_id": "repo"},
        top_k=5,
    )


@patch("server.mcp_server.get_memory_instance")
def test_get_memories_is_scoped(get_memory_instance):
    memory = Mock()
    memory.get_all.return_value = {"results": []}
    get_memory_instance.return_value = memory

    get_memories(user_id="alice", app_id="repo", top_k=20)

    memory.get_all.assert_called_once_with(
        filters={"user_id": "alice", "agent_id": "repo"},
        top_k=20,
    )


@patch("server.mcp_server.get_memory_instance")
def test_delete_all_requires_admin(get_memory_instance):
    result = delete_all_memories(user_id="alice")

    assert result["error"] == "forbidden"
    get_memory_instance.assert_not_called()


@patch("server.mcp_server.get_memory_instance")
def test_delete_all_allows_one_scope_for_admin(get_memory_instance):
    memory = Mock()
    get_memory_instance.return_value = memory
    token = _is_admin.set(True)
    try:
        result = delete_all_memories(app_id="repo")
    finally:
        _is_admin.reset(token)

    assert result == {"message": "All relevant memories deleted"}
    memory.delete_all.assert_called_once_with(agent_id="repo")


def test_streamable_http_protocol_lists_public_tools():
    app = FastAPI()
    app.include_router(mcp_router)
    app.dependency_overrides[verify_auth] = lambda: Mock(role="user")

    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {},
    }
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json=request,
            headers={"Accept": "application/json, text/event-stream"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    assert payload["id"] == 1
    assert {tool["name"] for tool in payload["result"]["tools"]} == {
        "add_memory",
        "search_memories",
        "get_memories",
        "delete_all_memories",
    }


@patch("server.mcp_server.get_memory_instance")
def test_streamable_http_protocol_calls_tool(get_memory_instance):
    memory = Mock()
    memory.search.return_value = {"results": [{"id": "memory-1", "memory": "Use Postgres"}]}
    get_memory_instance.return_value = memory

    app = FastAPI()
    app.include_router(mcp_router)
    app.dependency_overrides[verify_auth] = lambda: Mock(role="user")

    request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "search_memories",
            "arguments": {
                "query": "database",
                "user_id": "alice",
                "app_id": "repo",
                "top_k": 5,
            },
        },
    }
    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json=request,
            headers={"Accept": "application/json, text/event-stream"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["jsonrpc"] == "2.0"
    assert payload["id"] == 2
    assert payload["result"]["isError"] is False
    memory.search.assert_called_once_with(
        query="database",
        filters={"user_id": "alice", "agent_id": "repo"},
        top_k=5,
    )


def test_streamable_http_protocol_requires_authentication():
    async def reject_auth():
        raise HTTPException(status_code=401, detail="Authentication required.")

    app = FastAPI()
    app.include_router(mcp_router)
    app.dependency_overrides[verify_auth] = reject_auth

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}},
            headers={"Accept": "application/json, text/event-stream"},
        )

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}
