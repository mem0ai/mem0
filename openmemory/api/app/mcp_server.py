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

from app.database import SessionLocal
from app.models import Memory, MemoryAccessLog, MemoryState, MemoryStatusHistory
from app.utils.db import get_user_and_app
from app.utils.memory import get_memory_client
from app.utils.permissions import check_memory_access_permissions
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

# Nastav základní konfiguraci loggeru (pokud není nastavena jinde)
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("openmemory.mcp_server")

# Don't initialize memory client at import time - do it lazily when needed
def get_memory_client_safe():
    """Get memory client with error handling. Returns None if client cannot be initialized."""
    try:
        logger.info("[get_memory_client_safe] Attempting to get memory client...")
        print("🔍 [get_memory_client_safe] Starting safe memory client retrieval...")
        
        memory_client = get_memory_client()
        print(f"🔍 [get_memory_client_safe] get_memory_client() returned: {memory_client}")
        print(f"🔍 [get_memory_client_safe] Type: {type(memory_client)}")
        
        if memory_client is None:
            print("❌ [get_memory_client_safe] Memory client is None!")
            logger.warning("[get_memory_client_safe] Memory client is None")
        else:
            print("✅ [get_memory_client_safe] Memory client retrieved successfully")
            logger.info("[get_memory_client_safe] Memory client retrieved successfully")
        
        return memory_client
    except Exception as e:
        print(f"❌ [get_memory_client_safe] Exception occurred: {e}")
        print(f"❌ [get_memory_client_safe] Exception type: {type(e)}")
        import traceback
        print(f"❌ [get_memory_client_safe] Full traceback:")
        traceback.print_exc()
        
        logger.warning(f"[get_memory_client_safe] Failed to get memory client: {e}")
        return None

# Context variables for user_id and client_name
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id")
client_name_var: contextvars.ContextVar[str] = contextvars.ContextVar("client_name")

# Create a router for MCP endpoints
mcp_router = APIRouter(prefix="/mcp")

# Initialize SSE transport
sse = SseServerTransport("/mcp/messages/")

@mcp.tool(description="Add a new memory. This method is called everytime the user informs anything about themselves, their preferences, or anything that has any relevant information which can be useful in the future conversation. This can also be called when the user asks you to remember something.")
async def add_memories(text: str) -> str:
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)

    logger.info(f"[add_memories] Called with user_id={uid}, client_name={client_name}, text={text}")
    print(f"🔍 [add_memories] Called with user_id={uid}, client_name={client_name}, text={text}")

    if not uid:
        logger.error("[add_memories] user_id not provided")
        print("❌ [add_memories] user_id not provided")
        return "Error: user_id not provided"
    if not client_name:
        logger.error("[add_memories] client_name not provided")
        print("❌ [add_memories] client_name not provided")
        return "Error: client_name not provided"

    print("🔍 [add_memories] Getting memory client safely...")
    memory_client = get_memory_client_safe()
    print(f"🔍 [add_memories] Memory client result: {memory_client}")
    
    if not memory_client:
        logger.error("[add_memories] Memory system is currently unavailable.")
        print("❌ [add_memories] Memory system is currently unavailable.")
        return "Error: Memory system is currently unavailable. Please try again later."

    print("✅ [add_memories] Memory client obtained successfully, proceeding with database operations...")
    
    try:
        db = SessionLocal()
        print("🗄️ [add_memories] Database session created")
        
        try:
            logger.info(f"[add_memories] Getting/creating user and app for user_id={uid}, app_id={client_name}")
            print(f"🗄️ [add_memories] Getting/creating user and app for user_id={uid}, app_id={client_name}")
            
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)
            print(f"✅ [add_memories] User and app obtained: user={user}, app={app}")

            if not app.is_active:
                logger.warning(f"[add_memories] App {app.name} is paused. Cannot create new memories.")
                print(f"⚠️ [add_memories] App {app.name} is paused. Cannot create new memories.")
                return f"Error: App {app.name} is currently paused on OpenMemory. Cannot create new memories."

            logger.info(f"[add_memories] Calling memory_client.add() for user_id={uid}")
            print(f"🚀 [add_memories] Calling memory_client.add() for user_id={uid}")
            print(f"🚀 [add_memories] Memory client type: {type(memory_client)}")
            print(f"🚀 [add_memories] Memory client methods: {[m for m in dir(memory_client) if not m.startswith('_')]}")
            
            # Detailní logování parametrů
            print(f"🚀 [add_memories] === DETAILNÍ PARAMETRY ===")
            print(f"🚀 [add_memories] text: '{text}'")
            print(f"🚀 [add_memories] user_id: '{uid}'")
            print(f"🚀 [add_memories] metadata: {{'source_app': 'openmemory', 'mcp_client': '{client_name}'}}")
            print(f"🚀 [add_memories] memory_client.config: {memory_client.config}")
            print(f"🚀 [add_memories] memory_client.config.vector_store: {memory_client.config.vector_store}")
            print(f"🚀 [add_memories] memory_client.config.vector_store.config: {memory_client.config.vector_store.config}")
            print(f"🚀 [add_memories] memory_client.config.vector_store.config.collection_name: {memory_client.config.vector_store.config.collection_name}")
            print(f"🚀 [add_memories] memory_client.vector_store: {memory_client.vector_store}")
            print(f"🚀 [add_memories] memory_client.vector_store.collection_name: {memory_client.vector_store.collection_name}")
            print(f"🚀 [add_memories] === KONEC PARAMETRŮ ===")
            
            print(f"🚀 [add_memories] Volám memory_client.add() s text={text}, user_id={uid}, metadata={{'source_app': 'openmemory', 'mcp_client': {client_name}}}")
            response = memory_client.add(text,
                                         user_id=uid,
                                         metadata={
                                            "source_app": "openmemory",
                                            "mcp_client": client_name,
                                        })
            print(f"✅ [add_memories] Odpověď memory_client.add(): {response}")
            if isinstance(response, dict) and 'results' in response and not response['results']:
                print(f"⚠️ [add_memories] memory_client.add() vrátil prázdné results!")
                print(f"⚠️ [add_memories] Celá odpověď: {json.dumps(response, indent=2)}")
            
            logger.info(f"[add_memories] memory_client.add() response: {response}")
            print(f"✅ [add_memories] memory_client.add() response: {response}")

            if isinstance(response, dict) and 'results' in response:
                print(f"📊 [add_memories] Processing {len(response['results'])} results...")
                for result in response['results']:
                    memory_id = uuid.UUID(result['id'])
                    memory = db.query(Memory).filter(Memory.id == memory_id).first()
                    logger.info(f"[add_memories] Processing result: {result}")
                    print(f"📊 [add_memories] Processing result: {result}")

                    if result['event'] == 'ADD':
                        if not memory:
                            logger.info(f"[add_memories] Creating new Memory record for id={memory_id}")
                            print(f"📝 [add_memories] Creating new Memory record for id={memory_id}")
                            memory = Memory(
                                id=memory_id,
                                user_id=user.id,
                                app_id=app.id,
                                content=result['memory'],
                                state=MemoryState.active
                            )
                            db.add(memory)
                        else:
                            logger.info(f"[add_memories] Updating existing Memory record for id={memory_id}")
                            print(f"📝 [add_memories] Updating existing Memory record for id={memory_id}")
                            memory.state = MemoryState.active
                            memory.content = result['memory']

                        history = MemoryStatusHistory(
                            memory_id=memory_id,
                            changed_by=user.id,
                            old_state=MemoryState.deleted if memory else None,
                            new_state=MemoryState.active
                        )
                        db.add(history)

                    elif result['event'] == 'DELETE':
                        if memory:
                            logger.info(f"[add_memories] Marking Memory id={memory_id} as deleted")
                            print(f"🗑️ [add_memories] Marking Memory id={memory_id} as deleted")
                            memory.state = MemoryState.deleted
                            memory.deleted_at = datetime.datetime.now(datetime.UTC)
                            history = MemoryStatusHistory(
                                memory_id=memory_id,
                                changed_by=user.id,
                                old_state=MemoryState.active,
                                new_state=MemoryState.deleted
                            )
                            db.add(history)

                db.commit()
                logger.info(f"[add_memories] DB commit successful for user_id={uid}")
                print(f"✅ [add_memories] DB commit successful for user_id={uid}")

            logger.info(f"[add_memories] Returning response: {response}")
            print(f"✅ [add_memories] Returning response: {response}")
            
            # Convert response to string for MCP tool
            if isinstance(response, dict):
                return json.dumps(response, indent=2)
            else:
                return str(response)
        finally:
            db.close()
            logger.info(f"[add_memories] DB session closed for user_id={uid}")
            print(f"🗄️ [add_memories] DB session closed for user_id={uid}")
    except Exception as e:
        logger.exception(f"[add_memories] Error adding to memory: {e}")
        print(f"❌ [add_memories] Error adding to memory: {e}")
        print(f"❌ [add_memories] Error type: {type(e)}")
        import traceback
        print(f"❌ [add_memories] Full traceback:")
        traceback.print_exc()
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
            
            conditions = [qdrant_models.FieldCondition(key="user_id", match=qdrant_models.MatchValue(value=uid))]
            
            if accessible_memory_ids:
                # Convert UUIDs to strings for Qdrant
                accessible_memory_ids_str = [str(memory_id) for memory_id in accessible_memory_ids]
                conditions.append(qdrant_models.HasIdCondition(has_id=accessible_memory_ids_str))

            filters = qdrant_models.Filter(must=conditions)
            embeddings = memory_client.embedding_model.embed(query, "search")
            
            hits = memory_client.vector_store.client.query_points(
                collection_name=memory_client.vector_store.collection_name,
                query=embeddings,
                query_filter=filters,
                limit=10,
            )

            # Process search results
            memories = hits.points
            memories = [
                {
                    "id": memory.id,
                    "memory": memory.payload["data"],
                    "hash": memory.payload.get("hash"),
                    "created_at": memory.payload.get("created_at"),
                    "updated_at": memory.payload.get("updated_at"),
                    "score": memory.score,
                }
                for memory in memories
            ]

            # Log memory access for each memory found
            if isinstance(memories, dict) and 'results' in memories:
                print(f"Memories: {memories}")
                for memory_data in memories['results']:
                    if 'id' in memory_data:
                        memory_id = uuid.UUID(memory_data['id'])
                        # Create access log entry
                        access_log = MemoryAccessLog(
                            memory_id=memory_id,
                            app_id=app.id,
                            access_type="search",
                            metadata_={
                                "query": query,
                                "score": memory_data.get('score'),
                                "hash": memory_data.get('hash')
                            }
                        )
                        db.add(access_log)
                db.commit()
            else:
                for memory in memories:
                    memory_id = uuid.UUID(memory['id'])
                    # Create access log entry
                    access_log = MemoryAccessLog(
                        memory_id=memory_id,
                        app_id=app.id,
                        access_type="search",
                        metadata_={
                            "query": query,
                            "score": memory.get('score'),
                            "hash": memory.get('hash')
                        }
                    )
                    db.add(access_log)
                db.commit()
            return json.dumps(memories, indent=2)
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
                    memory_client.delete(memory_id)
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


@mcp_router.get("/{client_name}/sse/{user_id}")
async def handle_sse(request: Request):
    """Handle SSE connections for a specific user and client"""
    # Extract user_id and client_name from path parameters
    uid = request.path_params.get("user_id")
    user_token = user_id_var.set(uid or "")
    client_name = request.path_params.get("client_name")
    client_token = client_name_var.set(client_name or "")

    class LoggingWriteStream:
        def __init__(self, original_write_stream):
            self._original = original_write_stream

        async def send(self, data):
            logger.info(f"[SSE] Sending data: {data!r}")
            print(f"[SSE] Sending data: {data!r}")
            await self._original.send(data)

        def __getattr__(self, name):
            return getattr(self._original, name)

        async def __aenter__(self):
            return await self._original.__aenter__()

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return await self._original.__aexit__(exc_type, exc_val, exc_tb)

    try:
        # Handle SSE connection
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            logging_write_stream = LoggingWriteStream(write_stream)
            await mcp._mcp_server.run(
                read_stream,
                logging_write_stream,
                mcp._mcp_server.create_initialization_options(),
            )
    finally:
        # Clean up context variables
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)


@mcp_router.post("/messages/")
async def handle_get_message(request: Request):
    return await handle_post_message(request)

@mcp_router.get("/messages/")
async def handle_get_message_get(request: Request):
    session_id = request.query_params.get("session_id", "")
    try:
        body = await request.body()
    except Exception:
        body = b""
    headers = dict(request.headers)
    logger.info(f"[handle_get_message_get] GET /mcp/messages/ session_id={session_id} HEADERS: {headers} QUERY: {dict(request.query_params)} BODY: {body.decode('utf-8', errors='replace')}")
    print(f"[handle_get_message_get] GET /mcp/messages/ session_id={session_id} HEADERS: {headers} QUERY: {dict(request.query_params)} BODY: {body.decode('utf-8', errors='replace')}")
    response = {"status": "ok", "message": "GET /mcp/messages/ není implementováno, pouze logování."}
    logger.info(f"[handle_get_message_get] RESPONSE: {response}")
    print(f"[handle_get_message_get] RESPONSE: {response}")
    return response


async def handle_post_message(request: Request):
    """Handle POST messages for SSE"""
    try:
        body = await request.body()
        session_id = request.query_params.get("session_id", "")
        headers = dict(request.headers)
        logger.info(f"[handle_post_message] POST /mcp/messages/ session_id={session_id} HEADERS: {headers} BODY: {body.decode('utf-8', errors='replace')}")
        print(f"[handle_post_message] POST /mcp/messages/ session_id={session_id} HEADERS: {headers} BODY: {body.decode('utf-8', errors='replace')}")

        # Create a simple receive function that returns the body
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        # Create a simple send function that does nothing
        async def send(message):
            return {}

        # Call handle_post_message with the correct arguments
        await sse.handle_post_message(request.scope, receive, send)

        # Return a success response
        response = {"status": "ok"}
        logger.info(f"[handle_post_message] RESPONSE: {response}")
        print(f"[handle_post_message] RESPONSE: {response}")
        return response
    finally:
        pass


def setup_mcp_server(app: FastAPI):
    """Setup MCP server with the FastAPI application"""
    mcp._mcp_server.name = "mem0-mcp-server"

    # Include MCP router in the FastAPI app
    app.include_router(mcp_router)
