"""
MCP Server for OpenMemory with resilient memory client handling.

This module implements an MCP (Model Context Protocol) server that provides
memory operations for OpenMemory. The memory client is initialized lazily
to prevent server crashes when external dependencies (like Ollama) are
unavailable. If the memory client cannot be initialized, the server will
continue running with limited functionality and appropriate error messages.

Key features:
- Lazy memory client initialization
- Graceful error handling for unavailable dependencies
- Fallback to database-only mode when vector store is unavailable
- Proper logging for debugging connection issues
- Environment variable parsing for API keys
"""

import contextvars
import datetime
import json
import logging
import uuid
import asyncio

from app.database import SessionLocal
from app.models import Memory, MemoryAccessLog, MemoryState, MemoryStatusHistory
from app.utils.db import get_user_and_app
# Utility helpers and database functions
from app.utils.memory import get_memory_client, get_default_user_id
from app.utils.permissions import check_memory_access_permissions
from app.utils.mcp_helpers import with_error_handling, validate_memory_client, retry_operation
# Import argument models from the routes package. When this code runs inside the
# Docker image, the working directory is the `openmemory` package itself, so we
# reference the sibling `routes` package directly without the top-level
# `openmemory` prefix to avoid import errors.
from routes.mcp import SearchMemoryArgs, AddMemoriesArgs
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.routing import APIRouter
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from qdrant_client import models as qdrant_models

# Load environment variables
load_dotenv()

# Initialize MCP
mcp = FastMCP("mem0-mcp-server")

# Don't initialize memory client at import time - do it lazily when needed
def get_memory_client_safe():
    """Get memory client with error handling. Returns None if client cannot be initialized."""
    try:
        return get_memory_client()
    except Exception as e:
        logging.warning(f"Failed to get memory client: {e}")
        return None

# Context variables for user_id and client_name
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id")
client_name_var: contextvars.ContextVar[str] = contextvars.ContextVar("client_name")


def get_consistent_user_context() -> tuple[str, str]:
    """Return user_id and client_name with sane defaults and debug logging."""
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)

    if not uid:
        uid = get_default_user_id()
        logging.warning("No user_id found, using default: %s", uid)

    if not client_name:
        client_name = "openmemory"
        logging.warning("No client_name found, using default: %s", client_name)

    logging.info("Using context - user_id: %s, client_name: %s", uid, client_name)
    return uid, client_name

# Create a router for MCP endpoints
mcp_router = APIRouter(prefix="/mcp")

# Initialize SSE transport
sse = SseServerTransport("/mcp/messages/")

@mcp.tool(
    description=
    "Add a new memory. This method is called everytime the user informs anything about themselves, their preferences, or anything that has any relevant information which can be useful in the future conversation. This can also be called when the user asks you to remember something."
)
@with_error_handling("add_memories")
async def add_memories(args: AddMemoriesArgs) -> dict:
    uid, client_name = get_consistent_user_context()
    logging.debug("add_memories called with uid=%s client=%s", uid, client_name)

    memory_client = get_memory_client_safe()
    if not memory_client or not await validate_memory_client(memory_client):
        return {"error": "Memory system unavailable"}

    meta = {"source_app": "openmemory", "mcp_client": client_name}
    if args.metadata:
        meta.update(args.metadata)
    if args.project_id:
        meta["project_id"] = args.project_id
    if args.org_id:
        meta["org_id"] = args.org_id

    added_memories = []
    failed_messages = []

    for i, message in enumerate(args.messages):
        async def _add_one():
            return memory_client.add(
                [{"role": "user", "content": message}],
                user_id=uid,
                metadata=meta.copy(),
            )

        try:
            result = await retry_operation(_add_one)
            if isinstance(result, dict) and "results" in result:
                added_memories.extend(result["results"])
            elif isinstance(result, list):
                added_memories.extend(result)
            elif isinstance(result, dict) and "id" in result:
                added_memories.append(result)

            await asyncio.sleep(0.1)
            verification = memory_client.search(
                query=message[:30], user_id=uid, limit=5
            )
            if not verification.get("results"):
                failed_messages.append(f"Memory {i+1} not found after adding")
        except Exception as e:
            logging.error("Failed to add message %s: %s", i + 1, e)
            failed_messages.append(f"Message {i+1}: {str(e)}")

    return {
        "success": len(added_memories) > 0,
        "results": added_memories,
        "added_count": len(added_memories),
        "attempted_count": len(args.messages),
        "failed_messages": failed_messages,
        "verification_passed": len(failed_messages) == 0,
    }


@mcp.tool(description="Search through stored memories. This method is called EVERYTIME the user asks anything.")
@with_error_handling("search_memory")
async def search_memory(args: SearchMemoryArgs) -> dict:
    # DEBUGGING INFORMATION
    logging.info("\ud83d\udd0d SEARCH_MEMORY DEBUG:")
    logging.info("  Raw query: %r", args.query)
    logging.info("  Query type: %s", type(args.query))
    logging.info("  Query length: %s", len(args.query) if args.query else "None")

    uid, client_name = get_consistent_user_context()
    logging.debug("search_memory called with uid=%s client=%s", uid, client_name)

    memory_client = get_memory_client_safe()
    if not memory_client or not await validate_memory_client(memory_client):
        return {"error": "Memory system unavailable"}

    try:
        # FIX 1: Validate and sanitize query
        query = args.query.strip() if args.query else ""

        # FIX 2: Handle empty queries before embedding
        if not query:
            logging.info("Empty query detected, using database fallback")
            try:
                db = SessionLocal()
                memories = (
                    db.query(Memory)
                    .filter(Memory.user_id == uid, Memory.state == MemoryState.active)
                    .limit(args.top_k or 10)
                    .all()
                )

                results = [
                    {
                        "id": str(memory.id),
                        "memory": memory.content,
                        "created_at": memory.created_at.isoformat(),
                        "score": 1.0,
                    }
                    for memory in memories
                ]

                return {"success": True, "results": results}
            except Exception as e:
                return {"error": f"Database fallback failed: {e}"}

        # FIX 3: Validate embedding generation before search
        try:
            test_embedding = memory_client.embedding_model.embed(query, "search")
            if not test_embedding or len(test_embedding) == 0:
                logging.error("Empty embedding generated for query: '%s'", query)
                db = SessionLocal()
                memories = (
                    db.query(Memory)
                    .filter(
                        Memory.user_id == uid,
                        Memory.state == MemoryState.active,
                        Memory.content.ilike(f"%{query}%"),
                    )
                    .limit(args.top_k or 10)
                    .all()
                )

                results = [
                    {
                        "id": str(memory.id),
                        "memory": memory.content,
                        "created_at": memory.created_at.isoformat(),
                        "score": 0.8,
                    }
                    for memory in memories
                ]

                return {"success": True, "results": results, "method": "text_search_fallback"}

        except Exception as embed_error:
            logging.error("Embedding generation failed: %s", embed_error)
            return {"error": f"Embedding generation failed: {embed_error}"}

        # FIX 4: Original search with better error handling
        search_params = {"query": query, "user_id": uid}
        if args.top_k is not None:
            search_params["limit"] = args.top_k
        if args.threshold is not None:
            search_params["threshold"] = args.threshold

        filters = {}
        if args.filters:
            filters.update(args.filters)
        if args.project_id:
            filters["project_id"] = args.project_id
        if args.org_id:
            filters["org_id"] = args.org_id
        if filters:
            search_params["filters"] = filters

        result = memory_client.search(**search_params)
        return {"success": True, "results": result.get("results", [])}

    except Exception as e:
        logging.exception("Search failed: %s", e)
        return {"error": f"Search operation failed: {e}"}


@mcp.tool(description="List all memories in the user's memory")
@with_error_handling("list_memories")
async def list_memories() -> dict:
    uid, client_name = get_consistent_user_context()
    logging.debug("list_memories called with uid=%s client=%s", uid, client_name)

    memory_client = get_memory_client_safe()
    if not memory_client or not await validate_memory_client(memory_client):
        return {"error": "Memory system unavailable"}

    db = SessionLocal()
    try:
        user, app = get_user_and_app(db, user_id=uid, app_id=client_name)
        try:
            result = memory_client.get_all(user_id=uid)
            if result and "results" in result and result["results"]:
                return {
                    "success": True,
                    "results": result["results"],
                    "count": len(result["results"]),
                    "method": "get_all",
                }
        except Exception as e:
            logging.warning(f"get_all method failed: {e}")

        try:
            result = memory_client.search(query="*", user_id=uid, limit=1000)
            if result and "results" in result:
                return {
                    "success": True,
                    "results": result["results"],
                    "count": len(result["results"]),
                    "method": "search_fallback",
                }
        except Exception as e:
            logging.warning(f"search fallback failed: {e}")

        try:
            memories = db.query(Memory).filter(
                Memory.user_id == user.id,
                Memory.state == MemoryState.active,
            ).all()
            results = [
                {
                    "id": str(m.id),
                    "memory": m.content,
                    "created_at": m.created_at.isoformat(),
                    "metadata": m.metadata_ or {},
                }
                for m in memories
            ]
            return {
                "success": True,
                "results": results,
                "count": len(results),
                "method": "database_direct",
            }
        except Exception as e:
            logging.error(f"Database direct query failed: {e}")

        return {"success": True, "results": [], "count": 0, "method": "empty_fallback"}
    finally:
        db.close()


@mcp.tool(description="Delete all memories in the user's memory")
@with_error_handling("delete_all_memories")
async def delete_all_memories() -> dict:
    uid, client_name = get_consistent_user_context()
    logging.debug("delete_all_memories called with uid=%s client=%s", uid, client_name)

    memory_client = get_memory_client_safe()
    if not memory_client or not await validate_memory_client(memory_client):
        return {"error": "Memory system unavailable"}

    try:
        all_memories = memory_client.get_all(user_id=uid)
        initial_count = len(all_memories.get("results", [])) if all_memories else 0
        if initial_count == 0:
            return {"success": True, "message": "No memories to delete"}
    except Exception:
        initial_count = 0

    db = SessionLocal()
    try:
        user, app = get_user_and_app(db, user_id=uid, app_id=client_name)
        user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
        accessible_memory_ids = [m.id for m in user_memories if check_memory_access_permissions(db, m, app.id)]

        try:
            memory_client.delete_all(user_id=uid)
        except Exception:
            for memory_id in accessible_memory_ids:
                try:
                    memory_client.delete(memory_id)
                except Exception as e:
                    logging.warning(f"Failed to delete memory {memory_id}: {e}")

        remaining = memory_client.get_all(user_id=uid)
        remaining_count = len(remaining.get("results", [])) if remaining else 0
        if remaining_count > 0:
            return {
                "error": f"Deletion incomplete: {remaining_count} memories remain",
                "initial_count": initial_count,
                "remaining_count": remaining_count,
            }

        now = datetime.datetime.now(datetime.UTC)
        for memory_id in accessible_memory_ids:
            memory = db.query(Memory).filter(Memory.id == memory_id).first()
            memory.state = MemoryState.deleted
            memory.deleted_at = now
            history = MemoryStatusHistory(
                memory_id=memory_id,
                changed_by=user.id,
                old_state=MemoryState.active,
                new_state=MemoryState.deleted,
            )
            db.add(history)
            access_log = MemoryAccessLog(
                memory_id=memory_id,
                app_id=app.id,
                access_type="delete_all",
                metadata_={"operation": "bulk_delete"},
            )
            db.add(access_log)
        db.commit()

        return {
            "success": True,
            "deleted_count": initial_count,
            "verified": True,
        }
    finally:
        db.close()


@mcp_router.get("/{client_name}/sse/{user_id}")
async def handle_sse(request: Request):
    """Handle SSE connections for a specific user and client"""
    # Extract user_id and client_name from path parameters
    uid = request.path_params.get("user_id")
    user_token = user_id_var.set(uid or "")
    client_name = request.path_params.get("client_name")
    client_token = client_name_var.set(client_name or "")

    try:
        # Handle SSE connection
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            await mcp._mcp_server.run(
                read_stream,
                write_stream,
                mcp._mcp_server.create_initialization_options(),
            )
    finally:
        # Clean up context variables
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)


@mcp_router.post("/messages/")
async def handle_get_message(request: Request):
    return await _handle_post_message(request)


@mcp_router.post("/{client_name}/sse/{user_id}/messages/")
async def handle_post_message(request: Request):
    return await _handle_post_message(request)

async def _handle_post_message(request: Request):
    """Handle POST messages for SSE"""
    try:
        body = await request.body()

        # Create a simple receive function that returns the body
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        # Create a simple send function that does nothing
        async def send(message):
            return {}

        # Call handle_post_message with the correct arguments
        await sse.handle_post_message(request.scope, receive, send)

        # Return a success response
        return {"status": "ok"}
    finally:
        pass

def setup_mcp_server(app: FastAPI):
    """Setup MCP server with the FastAPI application"""
    mcp._mcp_server.name = "mem0-mcp-server"

    # Include MCP router in the FastAPI app
    app.include_router(mcp_router)
