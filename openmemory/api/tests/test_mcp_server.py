"""Tests for the MCP server endpoints (SSE and Streamable HTTP transports).

Covers the Streamable HTTP transport (MCP spec 2025-03-26+) and the legacy SSE
transport.  Tests exercise the full JSON-RPC flow — initialize, tools/list,
tools/call — as well as error handling and context-variable isolation.
"""

import os

# Set dummy keys before any imports that trigger client initialization
os.environ.setdefault("OPENAI_API_KEY", "test-key")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.mcp_server import client_name_var, mcp, mcp_router, user_id_var

# MCP Streamable HTTP requires the Accept header to include application/json.
# Including text/event-stream as well satisfies GET (SSE) requests.
MCP_HEADERS = {"Accept": "application/json, text/event-stream"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_app():
    """Create a minimal FastAPI app with just the MCP router for testing."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(mcp_router)
    return app


@pytest_asyncio.fixture
async def client(test_app):
    """Async HTTP client wired to the test app via ASGI transport."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _jsonrpc(method: str, params: dict | None = None, req_id: int = 1) -> dict:
    """Build a JSON-RPC 2.0 request envelope."""
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


# ---------------------------------------------------------------------------
# Streamable HTTP — route existence & basic protocol
# ---------------------------------------------------------------------------

class TestStreamableHTTPBasic:
    """Verify the Streamable HTTP route is registered and responds."""

    @pytest.mark.asyncio
    async def test_post_initialize(self, client):
        """POST initialize should return a valid JSON-RPC result."""
        resp = await client.post(
            "/mcp/testclient/http/user1",
            json=_initialize_payload(),
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        result = data["result"]
        assert "serverInfo" in result
        assert "capabilities" in result
        assert result["protocolVersion"] == "2025-03-26"

    @pytest.mark.asyncio
    async def test_delete_returns_method_not_allowed(self, client):
        """DELETE in stateless mode should return 405 (no session to terminate)."""
        resp = await client.delete(
            "/mcp/testclient/http/user1",
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 405

    @pytest.mark.asyncio
    async def test_missing_accept_header_returns_406(self, client):
        """POST without the required Accept header should return 406."""
        resp = await client.post(
            "/mcp/testclient/http/user1",
            json=_initialize_payload(),
        )
        assert resp.status_code == 406

    @pytest.mark.asyncio
    async def test_invalid_json_returns_400(self, client):
        """POST with unparseable body should return 400."""
        resp = await client.post(
            "/mcp/testclient/http/user1",
            content=b"not json",
            headers={**MCP_HEADERS, "Content-Type": "application/json"},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_route_not_found_for_wrong_path(self, client):
        """Requests to a non-existent path should 404."""
        resp = await client.post(
            "/mcp/testclient/nonexistent/user1",
            json=_initialize_payload(),
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Streamable HTTP — full protocol flow
# ---------------------------------------------------------------------------

class TestStreamableHTTPProtocol:
    """End-to-end JSON-RPC flows over Streamable HTTP."""

    @pytest.mark.asyncio
    async def test_tools_list(self, client):
        """tools/list should return all registered MCP tools."""
        init_resp = await client.post(
            "/mcp/testclient/http/user1",
            json=_initialize_payload(),
            headers=MCP_HEADERS,
        )
        assert init_resp.status_code == 200

        resp = await client.post(
            "/mcp/testclient/http/user1",
            json=_jsonrpc("tools/list", req_id=2),
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "result" in data
        tool_names = {t["name"] for t in data["result"]["tools"]}
        expected = {"add_memories", "search_memory", "list_memories",
                    "delete_memories", "delete_all_memories"}
        assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"

    @pytest.mark.asyncio
    async def test_tools_list_has_descriptions(self, client):
        """Every tool returned by tools/list should have a non-empty description."""
        await client.post(
            "/mcp/testclient/http/user1",
            json=_initialize_payload(),
            headers=MCP_HEADERS,
        )
        resp = await client.post(
            "/mcp/testclient/http/user1",
            json=_jsonrpc("tools/list", req_id=2),
            headers=MCP_HEADERS,
        )
        for tool in resp.json()["result"]["tools"]:
            assert tool.get("description"), f"Tool {tool['name']} has no description"

    @pytest.mark.asyncio
    async def test_tools_list_has_input_schemas(self, client):
        """Every tool should declare an inputSchema."""
        await client.post(
            "/mcp/testclient/http/user1",
            json=_initialize_payload(),
            headers=MCP_HEADERS,
        )
        resp = await client.post(
            "/mcp/testclient/http/user1",
            json=_jsonrpc("tools/list", req_id=2),
            headers=MCP_HEADERS,
        )
        for tool in resp.json()["result"]["tools"]:
            assert "inputSchema" in tool, f"Tool {tool['name']} missing inputSchema"

    @pytest.mark.asyncio
    async def test_call_unknown_tool_returns_error(self, client):
        """Calling a non-existent tool should return a JSON-RPC error."""
        await client.post(
            "/mcp/testclient/http/user1",
            json=_initialize_payload(),
            headers=MCP_HEADERS,
        )
        resp = await client.post(
            "/mcp/testclient/http/user1",
            json=_jsonrpc("tools/call", {"name": "no_such_tool", "arguments": {}}, req_id=2),
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data or (
            "result" in data and data["result"].get("isError")
        )

    @pytest.mark.asyncio
    async def test_unknown_jsonrpc_method(self, client):
        """An unknown JSON-RPC method should return an error."""
        resp = await client.post(
            "/mcp/testclient/http/user1",
            json=_jsonrpc("nonexistent/method"),
            headers=MCP_HEADERS,
        )
        assert resp.status_code in (200, 400)

    @pytest.mark.asyncio
    async def test_response_content_type_is_json(self, client):
        """Responses should have Content-Type: application/json."""
        resp = await client.post(
            "/mcp/testclient/http/user1",
            json=_initialize_payload(),
            headers=MCP_HEADERS,
        )
        ct = resp.headers.get("content-type", "")
        assert "application/json" in ct


# ---------------------------------------------------------------------------
# Streamable HTTP — context variable handling
# ---------------------------------------------------------------------------

class TestStreamableHTTPContext:
    """Verify that user_id and client_name context variables are set correctly."""

    @pytest.mark.asyncio
    async def test_context_vars_set_during_tool_call(self, client):
        """Context vars should reflect the path parameters during tool execution."""
        captured = {}

        @mcp.tool(name="__test_ctx", description="test only")
        async def _capture(query: str = "") -> str:
            captured["user_id"] = user_id_var.get(None)
            captured["client_name"] = client_name_var.get(None)
            return "ok"

        try:
            await client.post(
                "/mcp/my-app/http/alice",
                json=_initialize_payload(),
                headers=MCP_HEADERS,
            )
            resp = await client.post(
                "/mcp/my-app/http/alice",
                json=_jsonrpc("tools/call", {"name": "__test_ctx", "arguments": {}}, req_id=2),
                headers=MCP_HEADERS,
            )
            assert resp.status_code == 200
            assert captured.get("user_id") == "alice"
            assert captured.get("client_name") == "my-app"
        finally:
            mcp._tool_manager._tools.pop("__test_ctx", None)

    @pytest.mark.asyncio
    async def test_different_users_are_isolated(self, client):
        """Sequential requests with different user_ids must not leak state."""
        results = []

        @mcp.tool(name="__test_uid_iso", description="test only")
        async def _capture_uid(query: str = "") -> str:
            results.append(user_id_var.get(None))
            return "ok"

        try:
            for uid in ("userA", "userB", "userC"):
                await client.post(
                    f"/mcp/app1/http/{uid}",
                    json=_initialize_payload(),
                    headers=MCP_HEADERS,
                )
                await client.post(
                    f"/mcp/app1/http/{uid}",
                    json=_jsonrpc("tools/call", {"name": "__test_uid_iso", "arguments": {}}, req_id=2),
                    headers=MCP_HEADERS,
                )

            assert results == ["userA", "userB", "userC"]
        finally:
            mcp._tool_manager._tools.pop("__test_uid_iso", None)

    @pytest.mark.asyncio
    async def test_different_clients_are_isolated(self, client):
        """Sequential requests with different client_names must not leak state."""
        results = []

        @mcp.tool(name="__test_cn_iso", description="test only")
        async def _capture_cn(query: str = "") -> str:
            results.append(client_name_var.get(None))
            return "ok"

        try:
            for cn in ("cursor", "windsurf", "claude"):
                await client.post(
                    f"/mcp/{cn}/http/user1",
                    json=_initialize_payload(),
                    headers=MCP_HEADERS,
                )
                await client.post(
                    f"/mcp/{cn}/http/user1",
                    json=_jsonrpc("tools/call", {"name": "__test_cn_iso", "arguments": {}}, req_id=2),
                    headers=MCP_HEADERS,
                )

            assert results == ["cursor", "windsurf", "claude"]
        finally:
            mcp._tool_manager._tools.pop("__test_cn_iso", None)


# ---------------------------------------------------------------------------
# Streamable HTTP — response correctness
# ---------------------------------------------------------------------------

class TestStreamableHTTPResponses:
    """Verify that captured responses are returned correctly to the caller."""

    @pytest.mark.asyncio
    async def test_error_status_codes_are_preserved(self, client):
        """Transport error codes (e.g. 406) must be forwarded, not masked as 200."""
        resp = await client.post(
            "/mcp/testclient/http/user1",
            json=_initialize_payload(),
        )
        assert resp.status_code == 406

    @pytest.mark.asyncio
    async def test_delete_status_code_preserved(self, client):
        """DELETE 405 from stateless transport must not be masked."""
        resp = await client.delete(
            "/mcp/testclient/http/user1",
            headers=MCP_HEADERS,
        )
        assert resp.status_code == 405

    @pytest.mark.asyncio
    async def test_multiple_sequential_requests(self, client):
        """Multiple requests in sequence should each get independent responses."""
        for i in range(5):
            resp = await client.post(
                "/mcp/testclient/http/user1",
                json=_initialize_payload(req_id=i + 1),
                headers=MCP_HEADERS,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == i + 1
            assert "result" in data

    @pytest.mark.asyncio
    async def test_wrong_content_type_returns_error(self, client):
        """POST with wrong Content-Type should return an error status."""
        resp = await client.post(
            "/mcp/testclient/http/user1",
            content=b'{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}',
            headers={**MCP_HEADERS, "Content-Type": "text/plain"},
        )
        assert resp.status_code in (400, 415)


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

class TestRouteRegistration:
    """Verify all expected routes are registered in the router."""

    def test_sse_route_is_registered(self, test_app):
        routes = [r.path for r in test_app.routes if hasattr(r, "path")]
        assert "/mcp/{client_name}/sse/{user_id}" in routes

    def test_sse_post_messages_route_is_registered(self, test_app):
        routes = [r.path for r in test_app.routes if hasattr(r, "path")]
        assert "/mcp/messages/" in routes or "/mcp/{client_name}/sse/{user_id}/messages/" in routes

    def test_streamable_http_route_is_registered(self, test_app):
        routes = [r.path for r in test_app.routes if hasattr(r, "path")]
        assert "/mcp/{client_name}/http/{user_id}" in routes
