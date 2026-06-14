import asyncio
import contextvars
import json
import logging
from typing import Any, Dict, Optional

import anyio
from fastapi import Depends, FastAPI, Request
from fastapi.routing import APIRouter
from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import StreamableHTTPServerTransport
from starlette.responses import Response

from auth import verify_auth
from server_state import get_memory_instance

logger = logging.getLogger(__name__)

mcp = FastMCP("mem0-self-hosted-mcp")
mcp_router = APIRouter(prefix="/mcp")

user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("mcp_user_id")
client_name_var: contextvars.ContextVar[str] = contextvars.ContextVar("mcp_client_name")


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)


def _scoped_filters(
    *,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    uid = user_id_var.get(None)
    scoped_filters = dict(filters or {})
    scoped_filters["user_id"] = uid
    if agent_id:
        scoped_filters["agent_id"] = agent_id
    if run_id:
        scoped_filters["run_id"] = run_id
    return scoped_filters


@mcp.tool(name="add_memory", description="Add a memory for the current self-hosted Mem0 user.")
async def add_memory(
    text: str,
    infer: bool = True,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"

    memory_metadata = dict(metadata or {})
    if client_name:
        memory_metadata.setdefault("mcp_client", client_name)
    memory_metadata.setdefault("source", "self_hosted_mcp")

    kwargs = {
        "user_id": uid,
        "infer": infer,
        "metadata": memory_metadata,
    }
    if agent_id:
        kwargs["agent_id"] = agent_id
    if run_id:
        kwargs["run_id"] = run_id

    try:
        result = await asyncio.to_thread(get_memory_instance().add, text, **kwargs)
        return _json(result)
    except Exception as exc:
        logger.exception("Error adding memory through MCP")
        return f"Error adding memory: {exc}"


@mcp.tool(name="search_memories", description="Search memories for the current self-hosted Mem0 user.")
async def search_memories(
    query: str,
    top_k: int = 10,
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    filters: Optional[Dict[str, Any]] = None,
) -> str:
    try:
        result = await asyncio.to_thread(
            get_memory_instance().search,
            query=query,
            top_k=top_k,
            filters=_scoped_filters(agent_id=agent_id, run_id=run_id, filters=filters),
        )
        return _json(result)
    except Exception as exc:
        logger.exception("Error searching memories through MCP")
        return f"Error searching memories: {exc}"


@mcp.tool(name="get_memories", description="List memories for the current self-hosted Mem0 user.")
async def get_memories(
    agent_id: Optional[str] = None,
    run_id: Optional[str] = None,
    limit: int = 100,
) -> str:
    try:
        result = await asyncio.to_thread(
            get_memory_instance().get_all,
            filters=_scoped_filters(agent_id=agent_id, run_id=run_id),
            top_k=limit,
        )
        return _json(result)
    except Exception as exc:
        logger.exception("Error listing memories through MCP")
        return f"Error listing memories: {exc}"


@mcp.tool(name="get_memory", description="Get one memory by ID from the self-hosted Mem0 server.")
async def get_memory(memory_id: str) -> str:
    try:
        result = await asyncio.to_thread(get_memory_instance().get, memory_id)
        return _json(result)
    except Exception as exc:
        logger.exception("Error getting memory through MCP")
        return f"Error getting memory: {exc}"


@mcp.tool(name="update_memory", description="Update one memory by ID on the self-hosted Mem0 server.")
async def update_memory(
    memory_id: str,
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    try:
        result = await asyncio.to_thread(get_memory_instance().update, memory_id, data=text, metadata=metadata)
        return _json(result)
    except Exception as exc:
        logger.exception("Error updating memory through MCP")
        return f"Error updating memory: {exc}"


@mcp.tool(name="delete_memory", description="Delete one memory by ID from the self-hosted Mem0 server.")
async def delete_memory(memory_id: str) -> str:
    try:
        await asyncio.to_thread(get_memory_instance().delete, memory_id=memory_id)
        return _json({"message": "Memory deleted successfully"})
    except Exception as exc:
        logger.exception("Error deleting memory through MCP")
        return f"Error deleting memory: {exc}"


@mcp.tool(name="delete_all_memories", description="Delete all memories scoped to the current self-hosted Mem0 user.")
async def delete_all_memories(agent_id: Optional[str] = None, run_id: Optional[str] = None) -> str:
    kwargs = {"user_id": user_id_var.get(None)}
    if agent_id:
        kwargs["agent_id"] = agent_id
    if run_id:
        kwargs["run_id"] = run_id

    try:
        await asyncio.to_thread(get_memory_instance().delete_all, **kwargs)
        return _json({"message": "All relevant memories deleted"})
    except Exception as exc:
        logger.exception("Error deleting memories through MCP")
        return f"Error deleting memories: {exc}"


@mcp_router.api_route("/{client_name}/http/{user_id}", methods=["POST", "GET", "DELETE"], include_in_schema=False)
async def handle_streamable_http(request: Request, _auth=Depends(verify_auth)):
    uid = request.path_params.get("user_id")
    user_token = user_id_var.set(uid or "")
    client_name = request.path_params.get("client_name")
    client_token = client_name_var.set(client_name or "")

    response_started = False
    response_status = 200
    response_headers: list[tuple[bytes, bytes]] = []
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

        async with anyio.create_task_group() as task_group:

            async def run_server(*, task_status=anyio.TASK_STATUS_IGNORED):
                async with transport.connect() as (read_stream, write_stream):
                    task_status.started()
                    await mcp._mcp_server.run(
                        read_stream,
                        write_stream,
                        mcp._mcp_server.create_initialization_options(),
                        stateless=True,
                    )

            await task_group.start(run_server)
            await transport.handle_request(request.scope, request.receive, capture_send)
            await transport.terminate()
            task_group.cancel_scope.cancel()
    finally:
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)

    if not response_started:
        return Response(status_code=500, content=b"Transport did not produce a response")

    return Response(
        content=bytes(response_body),
        status_code=response_status,
        headers={key.decode(): value.decode() for key, value in response_headers},
    )


def setup_mcp_server(app: FastAPI) -> None:
    mcp._mcp_server.name = "mem0-self-hosted-mcp"
    app.include_router(mcp_router)
