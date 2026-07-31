"""Minimal MCP facade for the self-hosted Mem0 server.

The tools call the same in-process ``Memory`` instance used by the REST routes.
The transport is stateless Streamable HTTP and reuses the server's existing
authentication dependency, including ``X-API-Key`` support.
"""

from __future__ import annotations

import contextvars
import logging
from typing import Annotated, Any

import anyio
from fastapi import APIRouter, Depends, Request
from mcp.server.fastmcp import FastMCP
from mcp.server.streamable_http import StreamableHTTPServerTransport
from pydantic import Field
from starlette.responses import Response

from auth import verify_auth
from server_state import get_memory_instance

logger = logging.getLogger(__name__)

mcp = FastMCP("mem0-self-hosted")
mcp_router = APIRouter()
_is_admin: contextvars.ContextVar[bool] = contextvars.ContextVar("mcp_is_admin", default=False)


def _map_app_id(payload: dict[str, Any]) -> dict[str, Any]:
    """Map the hosted API's ``app_id`` alias to self-hosted ``agent_id``."""
    mapped = dict(payload)
    app_id = mapped.pop("app_id", None)
    if app_id and not mapped.get("agent_id"):
        mapped["agent_id"] = app_id
    return mapped


def _scope_filters(
    filters: dict[str, Any] | None,
    *,
    user_id: str | None,
    agent_id: str | None,
    app_id: str | None,
    run_id: str | None,
) -> dict[str, Any]:
    """Merge explicit MCP scope arguments with caller-provided filters."""
    mapped_scope = _map_app_id(
        {"user_id": user_id, "agent_id": agent_id, "app_id": app_id, "run_id": run_id}
    )
    scope = {key: value for key, value in mapped_scope.items() if value}
    if not scope:
        raise ValueError("Provide at least one of user_id, agent_id/app_id, or run_id.")
    if not filters:
        return scope
    return {"AND": [scope, filters]}


def _tool_failure(exc: Exception) -> dict[str, str]:
    """Return a stable MCP error without leaking provider details."""
    if isinstance(exc, ValueError):
        return {"error": "invalid_request", "detail": str(exc)}
    logger.exception("Mem0 MCP tool failed")
    return {"error": "memory_operation_failed", "detail": "The memory operation failed."}


@mcp.tool(description="Store a durable fact, preference, project decision, or task learning.")
def add_memory(
    text: Annotated[str | None, Field(description="Plain text to store.")] = None,
    messages: Annotated[
        list[dict[str, str]] | None,
        Field(description="Optional role/content messages. Takes precedence over text."),
    ] = None,
    user_id: Annotated[str | None, Field(description="User scope.")] = None,
    agent_id: Annotated[str | None, Field(description="Agent/project scope.")] = None,
    app_id: Annotated[str | None, Field(description="Hosted-compatible alias for agent_id.")] = None,
    run_id: Annotated[str | None, Field(description="Run/session scope.")] = None,
    metadata: Annotated[dict[str, Any] | None, Field(description="Optional memory metadata.")] = None,
    infer: Annotated[bool, Field(description="Extract memories from the supplied messages.")] = True,
) -> dict[str, Any]:
    try:
        if messages is None:
            if not text:
                raise ValueError("Provide text or messages.")
            messages = [{"role": "user", "content": text}]

        scope = _map_app_id(
            {"user_id": user_id, "agent_id": agent_id, "app_id": app_id, "run_id": run_id}
        )
        scope = {key: value for key, value in scope.items() if value}
        if not scope:
            raise ValueError("Provide at least one of user_id, agent_id/app_id, or run_id.")

        params: dict[str, Any] = {**scope, "metadata": metadata, "infer": infer}
        return get_memory_instance().add(
            messages=messages,
            **{key: value for key, value in params.items() if value is not None},
        )
    except Exception as exc:
        return _tool_failure(exc)


@mcp.tool(description="Search long-term memories relevant to a natural-language query.")
def search_memories(
    query: Annotated[str, Field(description="Natural-language search query.")],
    user_id: Annotated[str | None, Field(description="User scope.")] = None,
    agent_id: Annotated[str | None, Field(description="Agent/project scope.")] = None,
    app_id: Annotated[str | None, Field(description="Hosted-compatible alias for agent_id.")] = None,
    run_id: Annotated[str | None, Field(description="Run/session scope.")] = None,
    filters: Annotated[dict[str, Any] | None, Field(description="Additional structured filters.")] = None,
    top_k: Annotated[int, Field(ge=1, le=100, description="Maximum number of results.")] = 10,
    threshold: Annotated[float | None, Field(description="Optional minimum similarity score.")] = None,
) -> dict[str, Any]:
    try:
        scoped = _scope_filters(
            filters,
            user_id=user_id,
            agent_id=agent_id,
            app_id=app_id,
            run_id=run_id,
        )
        params: dict[str, Any] = {"filters": scoped, "top_k": top_k}
        if threshold is not None:
            params["threshold"] = threshold
        return get_memory_instance().search(query=query, **params)
    except Exception as exc:
        return _tool_failure(exc)


@mcp.tool(description="List memories in a user, project/agent, or run scope.")
def get_memories(
    user_id: Annotated[str | None, Field(description="User scope.")] = None,
    agent_id: Annotated[str | None, Field(description="Agent/project scope.")] = None,
    app_id: Annotated[str | None, Field(description="Hosted-compatible alias for agent_id.")] = None,
    run_id: Annotated[str | None, Field(description="Run/session scope.")] = None,
    filters: Annotated[dict[str, Any] | None, Field(description="Additional structured filters.")] = None,
    top_k: Annotated[int, Field(ge=1, le=1000, description="Maximum number of memories.")] = 100,
) -> dict[str, Any]:
    try:
        scoped = _scope_filters(
            filters,
            user_id=user_id,
            agent_id=agent_id,
            app_id=app_id,
            run_id=run_id,
        )
        return get_memory_instance().get_all(filters=scoped, top_k=top_k)
    except Exception as exc:
        return _tool_failure(exc)


@mcp.tool(description="Delete every memory in one explicit user, project/agent, or run scope.")
def delete_all_memories(
    user_id: Annotated[str | None, Field(description="User scope.")] = None,
    agent_id: Annotated[str | None, Field(description="Agent/project scope.")] = None,
    app_id: Annotated[str | None, Field(description="Hosted-compatible alias for agent_id.")] = None,
    run_id: Annotated[str | None, Field(description="Run/session scope.")] = None,
) -> dict[str, Any]:
    try:
        if not _is_admin.get():
            return {"error": "forbidden", "detail": "Admin authentication is required for bulk deletion."}
        scope = _map_app_id(
            {"user_id": user_id, "agent_id": agent_id, "app_id": app_id, "run_id": run_id}
        )
        scope = {key: value for key, value in scope.items() if value}
        if len(scope) != 1:
            raise ValueError("Provide exactly one of user_id, agent_id/app_id, or run_id.")
        get_memory_instance().delete_all(**scope)
        return {"message": "All relevant memories deleted"}
    except Exception as exc:
        return _tool_failure(exc)


@mcp_router.api_route("/mcp", methods=["POST", "GET", "DELETE"], include_in_schema=False)
async def handle_mcp(request: Request, authenticated_user=Depends(verify_auth)) -> Response:
    """Serve one stateless Streamable HTTP MCP request."""
    auth_type = getattr(request.state, "auth_type", "none")
    admin = auth_type in {"admin_api_key", "disabled"} or (
        authenticated_user is not None and authenticated_user.role == "admin"
    )
    admin_token = _is_admin.set(admin)

    response_started = False
    response_status = 200
    response_headers: list[tuple[bytes, bytes]] = []
    response_body = bytearray()

    async def capture_send(message: dict[str, Any]) -> None:
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
        _is_admin.reset(admin_token)

    if not response_started:
        return Response(status_code=500, content="MCP transport did not produce a response.")

    return Response(
        content=bytes(response_body),
        status_code=response_status,
        headers={key.decode(): value.decode() for key, value in response_headers},
    )


def setup_mcp_server(app) -> None:
    """Register the self-hosted MCP endpoint on a FastAPI application."""
    app.include_router(mcp_router)
