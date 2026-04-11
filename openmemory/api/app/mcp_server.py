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

import asyncio
import contextvars
import datetime
import json
import logging
import uuid

import anyio

from app.database import SessionLocal
from app.models import Memory, MemoryAccessLog, MemoryState, MemoryStatusHistory
from app.utils.db import get_user_and_app
from app.utils.memory import get_memory_client
from app.utils.permissions import check_memory_access_permissions
from dotenv import load_dotenv
import os
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.routing import APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.mcp_oauth import verify_oauth_or_api_key
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from mcp.server.streamable_http import StreamableHTTPServerTransport
from starlette.responses import Response

# Load environment variables
load_dotenv()

security = HTTPBearer()

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

# Synaptic memory (fork-only, kept in mcp_synaptic.py)
from app import mcp_synaptic

# Context variables for user_id and client_name
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id")
client_name_var: contextvars.ContextVar[str] = contextvars.ContextVar("client_name")

# Default user_id from config (single-user server)
from app.config import USER_ID as _DEFAULT_USER_ID

# Create a router for MCP endpoints
mcp_router = APIRouter(prefix="/mcp", dependencies=[Depends(verify_oauth_or_api_key)])

# Initialize SSE transport
sse = SseServerTransport("/mcp/messages/")

@mcp.tool(description="Add a new memory. This method is called everytime the user informs anything about themselves, their preferences, or anything that has any relevant information which can be useful in the future conversation. This can also be called when the user asks you to remember something. Set infer to False to store the memory verbatim without LLM fact extraction.")
async def add_memories(text: str, infer: bool = True) -> str:
    uid = user_id_var.get(None) or _DEFAULT_USER_ID
    client_name = client_name_var.get(None) or "default"

    # Get memory client safely
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        db = SessionLocal()
        try:
            # Get or create user and app
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)

            # Check if app is active
            if not app.is_active:
                return f"Error: App {app.name} is currently paused on OpenMemory. Cannot create new memories."

            response = memory_client.add(text,
                                         user_id=uid,
                                         metadata={
                                            "source_app": "openmemory",
                                            "mcp_client": client_name,
                                         },
                                         infer=infer)

            # Process the response and update database
            if isinstance(response, dict) and 'results' in response:
                for result in response['results']:
                    memory_id = uuid.UUID(result['id'])
                    memory = db.query(Memory).filter(Memory.id == memory_id).first()

                    if result['event'] == 'ADD':
                        if not memory:
                            memory = Memory(
                                id=memory_id,
                                user_id=user.id,
                                app_id=app.id,
                                content=result['memory'],
                                state=MemoryState.active
                            )
                            db.add(memory)
                        else:
                            memory.state = MemoryState.active
                            memory.content = result['memory']

                        # Create history entry
                        history = MemoryStatusHistory(
                            memory_id=memory_id,
                            changed_by=user.id,
                            old_state=MemoryState.deleted if memory else None,
                            new_state=MemoryState.active
                        )
                        db.add(history)

                    elif result['event'] == 'DELETE':
                        if memory:
                            memory.state = MemoryState.deleted
                            memory.deleted_at = datetime.datetime.now(datetime.UTC)
                            # Create history entry
                            history = MemoryStatusHistory(
                                memory_id=memory_id,
                                changed_by=user.id,
                                old_state=MemoryState.active,
                                new_state=MemoryState.deleted
                            )
                            db.add(history)

                db.commit()

            await mcp_synaptic.on_add(response.get("results", []))

            return json.dumps(response)
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error adding to memory: {e}")
        return f"Error adding to memory: {e}"


@mcp.tool(description="Search through stored memories. This method is called EVERYTIME the user asks anything.")
async def search_memory(query: str) -> str:
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    # Get memory client safely
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        db = SessionLocal()
        try:
            # Get or create user and app
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)

            # Get accessible memory IDs based on ACL
            user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
            accessible_memory_ids = [memory.id for memory in user_memories if check_memory_access_permissions(db, memory, app.id)]

            filters = {
                "user_id": uid
            }

            embeddings = memory_client.embedding_model.embed(query, "search")

            hits = memory_client.vector_store.search(
                query=query, 
                vectors=embeddings, 
                limit=10, 
                filters=filters,
            )

            allowed = set(str(mid) for mid in accessible_memory_ids) if accessible_memory_ids else None

            results = []
            for h in hits:
                # All vector db search functions return OutputData class
                id, score, payload = h.id, h.score, h.payload
                if allowed and (h.id is None or h.id not in allowed):
                    continue
                
                results.append({
                    "id": id, 
                    "memory": payload.get("data"), 
                    "hash": payload.get("hash"),
                    "created_at": payload.get("created_at"), 
                    "updated_at": payload.get("updated_at"), 
                    "score": score,
                })

            for r in results: 
                if r.get("id"): 
                    access_log = MemoryAccessLog(
                        memory_id=uuid.UUID(r["id"]),
                        app_id=app.id,
                        access_type="search",
                        metadata_={
                            "query": query,
                            "score": r.get("score"),
                            "hash": r.get("hash"),
                        },
                    )
                    db.add(access_log)
            db.commit()

            results = await mcp_synaptic.on_search(query, results)

            return json.dumps({"results": results}, indent=2)
        finally:
            db.close()
    except Exception as e:
        logging.exception(e)
        return f"Error searching memory: {e}"


@mcp.tool(description="List all memories in the user's memory")
async def list_memories() -> str:
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    # Get memory client safely
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        db = SessionLocal()
        try:
            # Get or create user and app
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)

            # Get all memories
            memories = memory_client.get_all(user_id=uid)
            filtered_memories = []

            # Filter memories based on permissions
            user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
            accessible_memory_ids = [memory.id for memory in user_memories if check_memory_access_permissions(db, memory, app.id)]
            if isinstance(memories, dict) and 'results' in memories:
                for memory_data in memories['results']:
                    if 'id' in memory_data:
                        memory_id = uuid.UUID(memory_data['id'])
                        if memory_id in accessible_memory_ids:
                            # Create access log entry
                            access_log = MemoryAccessLog(
                                memory_id=memory_id,
                                app_id=app.id,
                                access_type="list",
                                metadata_={
                                    "hash": memory_data.get('hash')
                                }
                            )
                            db.add(access_log)
                            filtered_memories.append(memory_data)
                db.commit()
            else:
                for memory in memories:
                    memory_id = uuid.UUID(memory['id'])
                    memory_obj = db.query(Memory).filter(Memory.id == memory_id).first()
                    if memory_obj and check_memory_access_permissions(db, memory_obj, app.id):
                        # Create access log entry
                        access_log = MemoryAccessLog(
                            memory_id=memory_id,
                            app_id=app.id,
                            access_type="list",
                            metadata_={
                                "hash": memory.get('hash')
                            }
                        )
                        db.add(access_log)
                        filtered_memories.append(memory)
                db.commit()
            return json.dumps(filtered_memories, indent=2)
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error getting memories: {e}")
        return f"Error getting memories: {e}"


@mcp.tool(description="Delete specific memories by their IDs")
async def delete_memories(memory_ids: list[str]) -> str:
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    # Get memory client safely
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        db = SessionLocal()
        try:
            # Get or create user and app
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)

            # Convert string IDs to UUIDs and filter accessible ones
            requested_ids = [uuid.UUID(mid) for mid in memory_ids]
            user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
            accessible_memory_ids = [memory.id for memory in user_memories if check_memory_access_permissions(db, memory, app.id)]

            # Only delete memories that are both requested and accessible
            ids_to_delete = [mid for mid in requested_ids if mid in accessible_memory_ids]

            if not ids_to_delete:
                return "Error: No accessible memories found with provided IDs"

            # Delete from vector store
            for memory_id in ids_to_delete:
                try:
                    memory_client.delete(str(memory_id))
                except Exception as delete_error:
                    logging.warning(f"Failed to delete memory {memory_id} from vector store: {delete_error}")

            # Update each memory's state and create history entries
            now = datetime.datetime.now(datetime.UTC)
            for memory_id in ids_to_delete:
                memory = db.query(Memory).filter(Memory.id == memory_id).first()
                if memory:
                    # Update memory state
                    memory.state = MemoryState.deleted
                    memory.deleted_at = now

                    # Create history entry
                    history = MemoryStatusHistory(
                        memory_id=memory_id,
                        changed_by=user.id,
                        old_state=MemoryState.active,
                        new_state=MemoryState.deleted
                    )
                    db.add(history)

                    # Create access log entry
                    access_log = MemoryAccessLog(
                        memory_id=memory_id,
                        app_id=app.id,
                        access_type="delete",
                        metadata_={"operation": "delete_by_id"}
                    )
                    db.add(access_log)

            db.commit()
            return f"Successfully deleted {len(ids_to_delete)} memories"
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error deleting memories: {e}")
        return f"Error deleting memories: {e}"


@mcp.tool(description="Delete all memories in the user's memory")
async def delete_all_memories() -> str:
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

    # Get memory client safely
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Error: Memory system is currently unavailable. Please try again later."

    try:
        db = SessionLocal()
        try:
            # Get or create user and app
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)

            user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
            accessible_memory_ids = [memory.id for memory in user_memories if check_memory_access_permissions(db, memory, app.id)]

            # delete the accessible memories only
            for memory_id in accessible_memory_ids:
                try:
                    memory_client.delete(str(memory_id))
                except Exception as delete_error:
                    logging.warning(f"Failed to delete memory {memory_id} from vector store: {delete_error}")

            # Update each memory's state and create history entries
            now = datetime.datetime.now(datetime.UTC)
            for memory_id in accessible_memory_ids:
                memory = db.query(Memory).filter(Memory.id == memory_id).first()
                # Update memory state
                memory.state = MemoryState.deleted
                memory.deleted_at = now

                # Create history entry
                history = MemoryStatusHistory(
                    memory_id=memory_id,
                    changed_by=user.id,
                    old_state=MemoryState.active,
                    new_state=MemoryState.deleted
                )
                db.add(history)

                # Create access log entry
                access_log = MemoryAccessLog(
                    memory_id=memory_id,
                    app_id=app.id,
                    access_type="delete_all",
                    metadata_={"operation": "bulk_delete"}
                )
                db.add(access_log)

            db.commit()
            return "Successfully deleted all memories"
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error deleting memories: {e}")
        return f"Error deleting memories: {e}"


# ---------------------------------------------------------------------------
# MCP Resources — discoverable via resources/list, readable via resources/read
# ---------------------------------------------------------------------------

@mcp.resource("mem0://memory-stats", description="Current memory statistics — total memories, categories, and recent activity")
async def memory_stats() -> str:
    """Return a formatted summary of the user's memory store."""
    uid = user_id_var.get(None) or _DEFAULT_USER_ID
    memory_client = get_memory_client_safe()
    if not memory_client:
        return "Memory system is currently unavailable."

    try:
        db = SessionLocal()
        try:
            user, _ = get_user_and_app(db, user_id=uid, app_id="openmemory")

            total_active = db.query(Memory).filter(
                Memory.user_id == user.id,
                Memory.state == MemoryState.active,
            ).count()
            total_deleted = db.query(Memory).filter(
                Memory.user_id == user.id,
                Memory.state == MemoryState.deleted,
            ).count()

            # Recent activity — last 10 access log entries
            recent_logs = (
                db.query(MemoryAccessLog)
                .filter(MemoryAccessLog.app_id == _.id)
                .order_by(MemoryAccessLog.accessed_at.desc())
                .limit(10)
                .all()
            )
            activity_lines = []
            for log in recent_logs:
                activity_lines.append(
                    f"  - [{log.accessed_at.isoformat()}] {log.access_type} (memory {log.memory_id})"
                )

            # Top categories from memory metadata (best-effort)
            recent_memories = (
                db.query(Memory)
                .filter(Memory.user_id == user.id, Memory.state == MemoryState.active)
                .order_by(Memory.created_at.desc())
                .limit(20)
                .all()
            )

            lines = [
                f"Memory Statistics for user '{uid}'",
                f"========================================",
                f"Active memories:   {total_active}",
                f"Deleted memories:  {total_deleted}",
                f"",
                f"Recent activity (last {len(recent_logs)} entries):",
            ]
            if activity_lines:
                lines.extend(activity_lines)
            else:
                lines.append("  (no recent activity)")

            lines.append("")
            lines.append(f"Latest memories (up to 20):")
            for mem in recent_memories:
                preview = mem.content[:100] + ("…" if len(mem.content) > 100 else "")
                lines.append(f"  - [{mem.created_at.isoformat()}] {preview}")

            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error building memory-stats resource: {e}")
        return f"Error retrieving memory stats: {e}"


@mcp.resource("mem0://user-context", description="Stored user context and preferences for the current user")
async def user_context() -> str:
    """Retrieve stored user context, preferences, and key facts from the database."""
    uid = user_id_var.get(None) or _DEFAULT_USER_ID

    try:
        db = SessionLocal()
        try:
            user, _ = get_user_and_app(db, user_id=uid, app_id="openmemory")

            # Fetch all active memories for this user
            memories = (
                db.query(Memory)
                .filter(Memory.user_id == user.id, Memory.state == MemoryState.active)
                .order_by(Memory.updated_at.desc())
                .all()
            )

            lines = [
                f"User Context for '{uid}'",
                f"========================================",
                f"Total active memories: {len(memories)}",
                "",
            ]

            if not memories:
                lines.append("No stored context found. Memories will accumulate as you use the system.")
            else:
                # Simple keyword-based categorisation
                categories = {
                    "preferences": [],
                    "projects/tools": [],
                    "personal facts": [],
                    "other": [],
                }
                pref_kw = {"prefer", "like", "dislike", "favourite", "favorite", "always", "never", "uses", "uses "}
                proj_kw = {"project", "repo", "build", "deploy", "server", "docker", "vps", "rust", "python", "mcp", "android", "kernel"}
                for mem in memories:
                    lower = mem.content.lower()
                    if any(kw in lower for kw in pref_kw):
                        categories["preferences"].append(mem)
                    elif any(kw in lower for kw in proj_kw):
                        categories["projects/tools"].append(mem)
                    elif any(kw in lower for kw in ["name is", "lives", "age", "work", "job", "clinical", "nhs"]):
                        categories["personal facts"].append(mem)
                    else:
                        categories["other"].append(mem)

                for cat_name, cat_mems in categories.items():
                    if not cat_mems:
                        continue
                    lines.append(f"--- {cat_name.title()} ({len(cat_mems)}) ---")
                    for mem in cat_mems[:10]:
                        preview = mem.content[:120] + ("…" if len(mem.content) > 120 else "")
                        lines.append(f"  • {preview}")
                    if len(cat_mems) > 10:
                        lines.append(f"  ... and {len(cat_mems) - 10} more")
                    lines.append("")

            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        logging.exception(f"Error building user-context resource: {e}")
        return f"Error retrieving user context: {e}"


@mcp.resource("mem0://available-tools", description="Available Mem0 tools and their capabilities")
async def available_tools() -> str:
    """Static reference listing all Mem0 MCP tools."""
    return """\
Mem0 OpenMemory — Available MCP Tools
========================================

1. add_memories(text, infer=True)
   Add a new memory. Called whenever the user shares personal information,
   preferences, or anything useful for future conversations. Also used when
   the user explicitly asks to remember something.
   - text (str): The content to store.
   - infer (bool): If True, the server extracts structured facts via LLM.
     Set to False to store verbatim.

2. search_memory(query)
   Search through stored memories. Called EVERY time the user asks a
   question to provide relevant context from past interactions.
   - query (str): Natural-language search query.

3. list_memories()
   List all memories accessible to the current user/client. Returns full
   memory objects with IDs, content, hashes, and timestamps.

4. delete_memories(memory_ids)
   Delete specific memories by their IDs.
   - memory_ids (list[str]): UUIDs of memories to delete.

5. delete_all_memories()
   Delete all memories for the current user. Use with caution.

Usage Notes:
- All tools are scoped to the authenticated user (user_id from path).
- Per-app access control (ACL) determines which memories are visible.
- The memory client initialises lazily; tools return errors if unavailable.
"""


# Register synaptic MCP tools (fork-only, no-op if SYNAPTIC_ENABLED is unset)
mcp_synaptic.register_tools(mcp)


@mcp_router.get("")
@mcp_router.get("/")
async def root_sse(request: Request):
    logging.error(f"SSE ENDPOINT HIT - METHOD: {request.method} PATH: {request.url.path}")

    # Default to claude and configured user for the base /mcp endpoint
    request.scope['path_params'] = {'client_name': 'claude', 'user_id': _DEFAULT_USER_ID}
    user_id_var.set(_DEFAULT_USER_ID)
    client_name_var.set("claude")

    # We must return an EventSourceResponse so FastAPI properly flushes the stream!
    # Instead of using connect_sse context manager which breaks FastAPI, we use it properly:
    from sse_starlette.sse import EventSourceResponse
    import anyio

    # Initialize streams manually to match how connect_sse does it
    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)

    session_id = uuid.uuid4()
    sse._read_stream_writers[session_id] = read_stream_writer

    root_path = request.scope.get("root_path", "")
    full_message_path_for_client = root_path.rstrip("/") + sse._endpoint
    base_url = str(request.base_url).rstrip("/")
    # DO NOT QUOTE THE SLASHES! Claude hates it.
    client_post_uri_data = f"{base_url}{full_message_path_for_client}?session_id={session_id.hex}"

    sse_stream_writer, sse_stream_reader = anyio.create_memory_object_stream(0)

    async def sse_writer():
        async with sse_stream_writer, write_stream_reader:
            await sse_stream_writer.send({"event": "endpoint", "data": client_post_uri_data})
            async for session_message in write_stream_reader:
                await sse_stream_writer.send({
                    "event": "message",
                    "data": session_message.message.model_dump_json(by_alias=True, exclude_none=True),
                })

    async def run_server():
        try:
            await mcp._mcp_server.run(read_stream, write_stream, mcp._mcp_server.create_initialization_options())
        finally:
            await read_stream_writer.aclose()
            await write_stream_reader.aclose()

    # Start the server loop in a background task
    asyncio.create_task(run_server())

    return EventSourceResponse(content=sse_stream_reader, data_sender_callable=sse_writer, ping=30)

@mcp_router.get("/{client_name}/sse/{user_id}")

async def handle_sse(request: Request):
    """Handle SSE connections for a specific user and client"""
    # Extract user_id and client_name from path parameters
    uid = request.path_params.get("user_id")
    user_token = user_id_var.set(uid or "")
    client_name = request.path_params.get("client_name")
    client_token = client_name_var.set(client_name or "")

    try:
        # NOTE: request._send is the raw ASGI `send` callable. Starlette does not
        # expose it publicly, but the MCP SDK transports require the raw ASGI
        # interface (scope, receive, send). This is the standard pattern from the
        # MCP Python SDK examples.
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
async def handle_messages(request: Request):
    return await _handle_post_message(request)


@mcp_router.post("/{client_name}/sse/{user_id}/messages/")
async def handle_post_message_with_client(request: Request):
    return await _handle_post_message(request)

async def _handle_post_message(request: Request):
    """Handle POST messages for SSE"""
    try:
        body = await request.body()
        logging.error(f"POST MESSAGE RECEIVED ON {request.url.path}: {body}")

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


@mcp_router.api_route("/{client_name}/http/{user_id}", methods=["POST", "GET", "DELETE"])
async def handle_streamable_http(request: Request):
    """Handle Streamable HTTP connections for a specific user and client.

    Uses the Streamable HTTP transport (MCP spec 2025-03-26+) which replaces
    the deprecated SSE transport. Runs in stateless mode — each request is
    handled independently with no persistent session.

    The transport writes its response directly to the ASGI ``send`` callable.
    We intercept it via ``capture_send`` so we can return a proper ``Response``
    to FastAPI — otherwise FastAPI would also try to send its own response,
    causing a "double-response" bug.
    """
    uid = request.path_params.get("user_id")
    user_token = user_id_var.set(uid or "")
    client_name = request.path_params.get("client_name")
    client_token = client_name_var.set(client_name or "")

    # Intercept the ASGI messages the transport sends so we can return them
    # as a single Response to FastAPI.  Without this, FastAPI would attempt to
    # write its own response after the transport already wrote one.
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
            await transport._terminate_session()
            tg.cancel_scope.cancel()
    finally:
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)

    if not response_started:
        return Response(status_code=500, content=b"Transport did not produce a response")

    # Header dict conversion is safe here: the MCP transport in stateless JSON
    # mode only emits single-valued headers (Content-Type, Content-Length).
    return Response(
        content=bytes(response_body),
        status_code=response_status,
        headers={k.decode(): v.decode() for k, v in response_headers},
    )


def setup_mcp_server(app: FastAPI):
    """Setup MCP server with the FastAPI application"""
    mcp._mcp_server.name = "mem0-mcp-server"

    # Include MCP router in the FastAPI app
    app.include_router(mcp_router)
