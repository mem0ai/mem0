import os

import pytest

# ruff: noqa: E402


os.environ.setdefault("OPENAI_API_KEY", "test-key")

# Import the module under test
from app.mcp_server import (  # noqa: E402
    add_memories,
    client_name_var,
    delete_all_memories,
    list_memories,
    search_memory,
    setup_mcp_server,
    user_id_var,
)
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.mark.asyncio
async def test_tools_require_context_user_id():
    # Ensure no context is set
    # Directly call tool; should error on missing user_id
    result = await add_memories("hello")
    assert isinstance(result, str)
    assert "user_id not provided" in result


@pytest.mark.asyncio
async def test_tools_require_context_client_name():
    # Set user_id, leave client_name missing
    token = user_id_var.set("test-user")
    try:
        result = await add_memories("hello")
        assert isinstance(result, str)
        assert "client_name not provided" in result
    finally:
        user_id_var.reset(token)


@pytest.mark.asyncio
async def test_add_memories_handles_unavailable_memory_client(monkeypatch):
    # Provide both context vars
    user_token = user_id_var.set("test-user")
    client_token = client_name_var.set("test-client")

    # Force memory client to be unavailable
    import app.mcp_server as m

    monkeypatch.setattr(m, "get_memory_client_safe", lambda: None)

    try:
        result = await add_memories("remember this")
        assert "Memory system is currently unavailable" in result
    finally:
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)


@pytest.mark.asyncio
async def test_search_memory_handles_unavailable_memory_client(monkeypatch):
    user_token = user_id_var.set("test-user")
    client_token = client_name_var.set("test-client")
    import app.mcp_server as m
    monkeypatch.setattr(m, "get_memory_client_safe", lambda: None)
    try:
        result = await search_memory("query")
        assert "Memory system is currently unavailable" in result
    finally:
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)


@pytest.mark.asyncio
async def test_list_memories_handles_unavailable_memory_client(monkeypatch):
    user_token = user_id_var.set("test-user")
    client_token = client_name_var.set("test-client")
    import app.mcp_server as m
    monkeypatch.setattr(m, "get_memory_client_safe", lambda: None)
    try:
        result = await list_memories()
        assert "Memory system is currently unavailable" in result
    finally:
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)


@pytest.mark.asyncio
async def test_delete_all_memories_handles_unavailable_memory_client(monkeypatch):
    user_token = user_id_var.set("test-user")
    client_token = client_name_var.set("test-client")
    import app.mcp_server as m
    monkeypatch.setattr(m, "get_memory_client_safe", lambda: None)
    try:
        result = await delete_all_memories()
        assert "Memory system is currently unavailable" in result
    finally:
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)


def test_mcp_tools_registered_basic():
    # The FastMCP instance should exist and expose our tool callables
    # We at least ensure the callables are defined
    assert callable(add_memories)
    assert callable(search_memory)
    assert callable(list_memories)
    assert callable(delete_all_memories)


def test_router_included_on_setup():
    app = FastAPI()
    setup_mcp_server(app)
    paths = {getattr(r, "path", None) for r in app.router.routes}
    # Core MCP endpoints should be present
    assert "/mcp/{client_name}/sse/{user_id}" in paths
    # messages endpoints may be registered twice via different decorators
    assert "/mcp/messages/" in paths
    assert "/mcp/{client_name}/sse/{user_id}/messages/" in paths


def test_post_messages_endpoint_works():
    app = FastAPI()
    setup_mcp_server(app)
    client = TestClient(app)
    # Body content is forwarded to SSE transport; any bytes are fine for this smoke check
    resp = client.post("/mcp/messages/", data=b"{}")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
