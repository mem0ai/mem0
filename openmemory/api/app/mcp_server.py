import logging
import json
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from app.utils.memory import get_memory_client
from fastapi import FastAPI, Request
from fastapi.routing import APIRouter
import contextvars
import os
from dotenv import load_dotenv
from app.database import SessionLocal
from app.models import Memory, MemoryState, MemoryStatusHistory, MemoryAccessLog
from app.utils.db import get_user_and_app
import uuid
import datetime
from app.utils.permissions import check_memory_access_permissions
from qdrant_client import models as qdrant_models

# Load environment variables
load_dotenv()

# Initialize MCP and memory client
mcp = FastMCP("mem0-mcp-server")

# Check if OpenAI API key is set
if not os.getenv("OPENAI_API_KEY"):
    raise Exception("OPENAI_API_KEY is not set in .env file")

memory_client = get_memory_client()

# Context variables for user_id and client_name
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("user_id")
client_name_var: contextvars.ContextVar[str] = contextvars.ContextVar("client_name")

# Create a router for MCP endpoints
mcp_router = APIRouter(prefix="/mcp")

# Initialize SSE transport
sse = SseServerTransport("/mcp/messages/")

@mcp.tool(description="Add new memories to the user's memory")
async def add_memories(text: str) -> str:
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)

    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"

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
                                        })

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

            return response
        finally:
            db.close()
    except Exception as e:
        return f"Error adding to memory: {e}"


@mcp.tool(description="Search the user's memory for memories that match the query")
async def search_memory(query: str) -> str:
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"
    try:
        db = SessionLocal()
        try:
            # Get or create user and app
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)

            # Get accessible memory IDs based on ACL
            user_memories = db.query(Memory).filter(
                Memory.user_id == user.id,
                Memory.state != MemoryState.deleted,
                Memory.state != MemoryState.archived
            ).all()
            
            accessible_memory_ids = [memory.id for memory in user_memories if check_memory_access_permissions(db, memory, app.id)]
            
            # Initialize result collections
            all_memories = []
            found_memory_ids = set()
            
            # PART 1: VECTOR SEARCH WITH QDRANT
            try:
                # Set up conditions for Qdrant search
                conditions = [qdrant_models.FieldCondition(key="user_id", match=qdrant_models.MatchValue(value=uid))]
                
                if accessible_memory_ids:
                    # Convert UUIDs to strings for Qdrant
                    accessible_memory_ids_str = [str(memory_id) for memory_id in accessible_memory_ids]
                    conditions.append(qdrant_models.HasIdCondition(has_id=accessible_memory_ids_str))
                
                filters = qdrant_models.Filter(must=conditions)
                
                # Perform vector search
                embeddings = memory_client.embedding_model.embed(query, "search")
                hits = memory_client.vector_store.client.query_points(
                    collection_name=memory_client.vector_store.collection_name,
                    query=embeddings,
                    query_filter=filters,
                    limit=10,
                )

                # Process vector search results
                vector_memories = []
                for memory in hits.points:
                    memory_id = memory.id
                    memory_data = {
                        "id": memory_id,
                        "memory": memory.payload["data"],
                        "hash": memory.payload.get("hash"),
                        "created_at": memory.payload.get("created_at"),
                        "updated_at": memory.payload.get("updated_at"),
                        "score": memory.score,
                        "source": "vector_search"
                    }
                    vector_memories.append(memory_data)
                    found_memory_ids.add(memory_id)
                    
                    # Create access log entry
                    access_log = MemoryAccessLog(
                        memory_id=uuid.UUID(memory_id),
                        app_id=app.id,
                        access_type="search",
                        metadata_={
                            "query": query,
                            "score": memory.score,
                            "hash": memory.payload.get("hash")
                        }
                    )
                    db.add(access_log)
                
                all_memories.extend(vector_memories)
            except Exception as e:
                logging.exception(f"Error in vector search: {e}")
                # Vector search failed, continue with SQL search
            
            # PART 2: TEXT SEARCH WITH SQL
            # Perform text search on the database memories
            sql_memories = []
            for memory in user_memories:
                # Skip memories already found in vector search
                if str(memory.id) in found_memory_ids:
                    continue
                    
                # Simple text search: check if query appears in memory content
                if query.lower() in memory.content.lower():
                    memory_data = {
                        "id": str(memory.id),
                        "memory": memory.content,
                        "created_at": int(memory.created_at.timestamp()) if memory.created_at else None,
                        "updated_at": int(memory.updated_at.timestamp()) if memory.updated_at else None,
                        "score": 0.5,  # Default score for text matches
                        "source": "text_search"
                    }
                    sql_memories.append(memory_data)
                    
                    # Create access log entry
                    access_log = MemoryAccessLog(
                        memory_id=memory.id,
                        app_id=app.id,
                        access_type="search",
                        metadata_={
                            "query": query,
                            "score": 0.5,
                            "source": "text_search"
                        }
                    )
                    db.add(access_log)

            logging.info(f"SQL memories: {len(sql_memories)}")
            logging.info(f"Vector memories: {len(vector_memories)}")
            
            # Add SQL search results to the final list
            all_memories.extend(sql_memories)
            
            # Sort combined results by score (highest first)
            all_memories.sort(key=lambda x: x.get("score", 0), reverse=True)
            
            # Commit the access logs
            db.commit()
            
            # Return all results as JSON
            return json.dumps(all_memories, indent=2)
            
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
        return f"Error getting memories: {e}"


@mcp.tool(description="Delete all memories in the user's memory")
async def delete_all_memories() -> str:
    uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    if not uid:
        return "Error: user_id not provided"
    if not client_name:
        return "Error: client_name not provided"
    try:
        db = SessionLocal()
        try:
            # Get or create user and app
            user, app = get_user_and_app(db, user_id=uid, app_id=client_name)

            user_memories = db.query(Memory).filter(Memory.user_id == user.id).all()
            accessible_memory_ids = [memory.id for memory in user_memories if check_memory_access_permissions(db, memory, app.id)]

            # delete the accessible memories only
            for memory_id in accessible_memory_ids:
                memory_client.delete(memory_id)

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
        return f"Error deleting memories: {e}"


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
async def handle_post_message_sse(request: Request):
    return await handle_post_message(request)

@mcp_router.post("/{client_name}/sse/{user_id}/messages/")
async def handle_post_message_sse(request: Request):
    return await handle_post_message(request)


async def handle_post_message(request: Request):
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
        # Clean up context variable
        # client_name_var.reset(client_token)

def setup_mcp_server(app: FastAPI):
    """Setup MCP server with the FastAPI application"""
    mcp._mcp_server.name = f"mem0-mcp-server"

    # Include MCP router in the FastAPI app
    app.include_router(mcp_router)
