import importlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

pytest.importorskip("mcp", reason="mcp package not installed")
pytest.importorskip("httpx", reason="httpx not installed")

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

SERVER_DIR = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

os.environ.setdefault("AUTH_DISABLED", "true")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

mcp_server = importlib.import_module("mcp_server")

MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


def _jsonrpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": method,
        "params": params or {},
    }


def _initialize_payload(req_id: int = 1) -> dict:
    return _jsonrpc(
        "initialize",
        {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "0.1.0"},
        },
        req_id=req_id,
    )


@pytest.fixture
def test_app():
    app = FastAPI()
    app.dependency_overrides[mcp_server.verify_auth] = lambda: None
    app.include_router(mcp_server.mcp_router)
    return app


@pytest_asyncio.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_mcp_initialize(client):
    response = await client.post(
        "/mcp/codex/http/alice",
        json=_initialize_payload(),
        headers=MCP_HEADERS,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["jsonrpc"] == "2.0"
    assert data["id"] == 1
    assert data["result"]["serverInfo"]["name"] == "mem0-self-hosted-mcp"


@pytest.mark.asyncio
async def test_mcp_tools_list_exposes_memory_tools(client):
    await client.post("/mcp/codex/http/alice", json=_initialize_payload(), headers=MCP_HEADERS)

    response = await client.post(
        "/mcp/codex/http/alice",
        json=_jsonrpc("tools/list", req_id=2),
        headers=MCP_HEADERS,
    )

    assert response.status_code == 200
    tool_names = {tool["name"] for tool in response.json()["result"]["tools"]}
    assert {
        "add_memory",
        "search_memories",
        "get_memories",
        "get_memory",
        "update_memory",
        "delete_memory",
        "delete_all_memories",
    }.issubset(tool_names)


@pytest.mark.asyncio
async def test_mcp_add_memory_forwards_path_scope_and_client_metadata(client):
    mock_memory = MagicMock()
    mock_memory.add.return_value = {"results": [{"id": "mem-1", "memory": "Remember this.", "event": "ADD"}]}

    with patch.object(mcp_server, "get_memory_instance", return_value=mock_memory):
        response = await client.post(
            "/mcp/codex/http/alice",
            json=_jsonrpc(
                "tools/call",
                {
                    "name": "add_memory",
                    "arguments": {
                        "text": "Remember this.",
                        "infer": False,
                        "agent_id": "agent-1",
                        "metadata": {"kind": "preference"},
                    },
                },
                req_id=3,
            ),
            headers=MCP_HEADERS,
        )

    assert response.status_code == 200
    tool_text = response.json()["result"]["content"][0]["text"]
    assert json.loads(tool_text)["results"][0]["id"] == "mem-1"

    mock_memory.add.assert_called_once()
    args, kwargs = mock_memory.add.call_args
    assert args == ("Remember this.",)
    assert kwargs["user_id"] == "alice"
    assert kwargs["agent_id"] == "agent-1"
    assert kwargs["infer"] is False
    assert kwargs["metadata"] == {
        "kind": "preference",
        "mcp_client": "codex",
        "source": "self_hosted_mcp",
    }


@pytest.mark.asyncio
async def test_mcp_search_forces_path_user_over_user_filter(client):
    mock_memory = MagicMock()
    mock_memory.search.return_value = {"results": [{"id": "mem-1", "memory": "Scoped"}]}

    with patch.object(mcp_server, "get_memory_instance", return_value=mock_memory):
        response = await client.post(
            "/mcp/codex/http/alice",
            json=_jsonrpc(
                "tools/call",
                {
                    "name": "search_memories",
                    "arguments": {
                        "query": "scoped",
                        "top_k": 5,
                        "filters": {"user_id": "mallory", "topic": "work"},
                    },
                },
                req_id=4,
            ),
            headers=MCP_HEADERS,
        )

    assert response.status_code == 200
    _, kwargs = mock_memory.search.call_args
    assert kwargs["query"] == "scoped"
    assert kwargs["top_k"] == 5
    assert kwargs["filters"] == {"user_id": "alice", "topic": "work"}
