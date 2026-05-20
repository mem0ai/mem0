import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http import StreamableHTTPServerTransport
from starlette.responses import Response

from auth import verify_auth
from server_state import get_memory_instance

logger = logging.getLogger(__name__)

# Initialize FastMCP
mcp = FastMCP("mem0-local")

@mcp.tool()
def add_memory(messages: List[Dict[str, str]], user_id: str, agent_id: Optional[str] = None, run_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Store new memories. Provide a list of messages with 'role' and 'content'."""
    try:
        res = get_memory_instance().add(messages, user_id=user_id, agent_id=agent_id, run_id=run_id, metadata=metadata)
        return json.dumps(res)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def search_memories(query: str, user_id: Optional[str] = None, agent_id: Optional[str] = None, run_id: Optional[str] = None, filters: Optional[Dict[str, Any]] = None, top_k: int = 10) -> str:
    """Search for relevant memories."""
    try:
        # Move entity IDs into filters for search()
        effective_filters = filters or {}
        if user_id: effective_filters["user_id"] = user_id
        if agent_id: effective_filters["agent_id"] = agent_id
        if run_id: effective_filters["run_id"] = run_id

        res = get_memory_instance().search(query, filters=effective_filters, top_k=top_k)
        return json.dumps(res)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_memories(user_id: Optional[str] = None, agent_id: Optional[str] = None, run_id: Optional[str] = None) -> str:
    """List memories for a given user, agent, or run."""
    try:
        # Move entity IDs into filters for get_all()
        filters = {}
        if user_id: filters["user_id"] = user_id
        if agent_id: filters["agent_id"] = agent_id
        if run_id: filters["run_id"] = run_id

        res = get_memory_instance().get_all(filters=filters)
        return json.dumps(res)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def get_memory(memory_id: str) -> str:
    """Retrieve a specific memory by its ID."""
    try:
        res = get_memory_instance().get(memory_id)
        return json.dumps(res)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def update_memory(memory_id: str, data: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    """Update an existing memory's content or metadata."""
    try:
        res = get_memory_instance().update(memory_id, data, metadata=metadata)
        return json.dumps(res)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def delete_memory(memory_id: str) -> str:
    """Delete a specific memory by its ID."""
    try:
        get_memory_instance().delete(memory_id)
        return "Memory deleted successfully"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def delete_all_memories(user_id: Optional[str] = None, agent_id: Optional[str] = None, run_id: Optional[str] = None) -> str:
    """Delete all memories for a given identifier."""
    try:
        # delete_all() supports top-level kwargs
        get_memory_instance().delete_all(user_id=user_id, agent_id=agent_id, run_id=run_id)
        return "Memories deleted successfully"
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def list_entities() -> str:
    """List all users, agents, and runs that have stored memories."""
    try:
        SCAN_LIMIT = 10_000
        results = get_memory_instance().vector_store.list(top_k=SCAN_LIMIT)

        # Robustly extract rows from different vector store return formats
        rows = []
        if isinstance(results, tuple):
            rows = results[0]
        elif isinstance(results, list):
            if results and isinstance(results[0], list):
                rows = results[0]
            else:
                rows = results

        payloads = [getattr(row, "payload", None) or {} for row in rows]

        buckets = defaultdict(lambda: {"total_memories": 0})
        for payload in payloads:
            for entity_type, field in [("user", "user_id"), ("agent", "agent_id"), ("run", "run_id")]:
                value = payload.get(field)
                if value:
                    buckets[(entity_type, str(value))]["total_memories"] += 1

        entities = [{"id": eid, "type": etype, **data} for (etype, eid), data in buckets.items()]
        return json.dumps(entities)
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool()
def delete_entities(entity_type: str, entity_id: str) -> str:
    """Delete all memories for a specific entity type (user, agent, or run)."""
    try:
        TYPE_TO_FIELD = {"user": "user_id", "agent": "agent_id", "run": "run_id"}
        if entity_type not in TYPE_TO_FIELD:
            return "Error: entity_type must be 'user', 'agent', or 'run'"

        get_memory_instance().delete_all(**{TYPE_TO_FIELD[entity_type]: entity_id})
        return f"Entity {entity_id} ({entity_type}) deleted successfully"
    except Exception as e:
        return f"Error: {str(e)}"

# Router for the MCP endpoints
router = APIRouter(dependencies=[Depends(verify_auth)])

# Initialize SSE transport
sse = SseServerTransport("/mcp/messages")

@router.get("/mcp/sse")
async def handle_sse(request: Request):
    """Entry point for MCP clients using SSE transport."""
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await mcp._mcp_server.run(
            read_stream,
            write_stream,
            mcp._mcp_server.create_initialization_options()
        )

@router.post("/mcp/messages")
async def handle_messages(request: Request):
    """Message endpoint for SSE transport."""
    await sse.handle_post_message(request.scope, request.receive, request._send)

@router.api_route("/mcp", methods=["POST", "GET", "DELETE"])
async def handle_streamable_http(request: Request):
    """Entry point for MCP clients using Streamable HTTP transport."""

    response_started = False
    response_status = 200
    response_headers: List[tuple[bytes, bytes]] = []
    response_body = bytearray()

    async def capture_send(message):
        nonlocal response_started, response_status
        if message["type"] == "http.response.start":
            response_started = True
            response_status = message["status"]
            response_headers.extend(message.get("headers", []))
        elif message["type"] == "http.response.body":
            response_body.extend(message.get("body", b""))

    try:
        transport = StreamableHTTPServerTransport(
            mcp_session_id=None,
            is_json_response_enabled=True,
        )

        async with anyio.create_task_group() as tg:
            async def run_server(*, task_status=anyio.TASK_STATUS_IGNORED):
                async with transport.connect() as (read_stream, write_stream):
                    task_status.started()
                    await mcp._mcp_server.run(
                        read_stream,
                        write_stream,
                        mcp._mcp_server.create_initialization_options(),
                        stateless=True,
                    )

            await tg.start(run_server)
            await transport.handle_request(request.scope, request.receive, capture_send)
            await transport.terminate()
            tg.cancel_scope.cancel()
    except Exception as e:
        logger.error(f"MCP transport error: {e}", exc_info=True)
        return Response(status_code=500, content=str(e).encode())

    if not response_started:
        return Response(status_code=500, content=b"Transport did not produce a response")

    return Response(
        content=bytes(response_body),
        status_code=response_status,
        headers={k.decode(): v.decode() for k, v in response_headers},
    )
