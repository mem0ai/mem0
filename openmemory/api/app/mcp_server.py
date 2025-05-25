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
from app.models import Memory, MemoryState, MemoryStatusHistory, MemoryAccessLog, Document, DocumentChunk
from app.utils.db import get_user_and_app, get_or_create_user
import uuid
import datetime
from app.utils.permissions import check_memory_access_permissions
from qdrant_client import models as qdrant_models
from app.integrations.substack_service import SubstackService
from app.utils.gemini import GeminiService
import asyncio
import google.generativeai as genai
from app.services.chunking_service import ChunkingService
from sqlalchemy import text

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Initialize MCP
mcp = FastMCP("mem0-mcp-server")

# DO NOT initialize memory_client globally:
# memory_client = get_memory_client()

# Context variables for user_id (Supabase User ID string) and client_name
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("supa_user_id")
client_name_var: contextvars.ContextVar[str] = contextvars.ContextVar("client_name")

# Create a router for MCP endpoints
mcp_router = APIRouter(prefix="/mcp")

# Initialize SSE transport
sse = SseServerTransport("/mcp/messages/")

@mcp.tool(description="Add new memories to the user's memory")
async def add_memories(text: str) -> str:
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    memory_client = get_memory_client() # Initialize client when tool is called

    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"

    try:
        db = SessionLocal()
        try:
            user, app = get_user_and_app(db, supabase_user_id=supa_uid, app_name=client_name, email=None)

            if not app.is_active:
                return f"Error: App {app.name} is currently paused. Cannot create new memories."

            response = memory_client.add(
                messages=text,
                user_id=supa_uid,
                metadata={
                    "source_app": "openmemory_mcp",
                    "mcp_client": client_name,
                    "app_db_id": str(app.id)
                }
            )

            if isinstance(response, dict) and 'results' in response:
                added_count = 0
                updated_count = 0
                for result in response['results']:
                    mem0_memory_id_str = result['id']
                    mem0_content = result.get('memory', text)

                    if result.get('event') == 'ADD':
                        sql_memory_record = Memory(
                            user_id=user.id,
                            app_id=app.id,
                            content=mem0_content,
                            state=MemoryState.active,
                            metadata_={**result.get('metadata', {}), "mem0_id": mem0_memory_id_str}
                        )
                        db.add(sql_memory_record)
                        db.flush()  # Flush to get the memory ID before creating history
                        added_count += 1
                        
                        # Don't create history for initial creation since old_state cannot be NULL
                        # The memory is created with state=active, which is sufficient
                        # History tracking starts from the first state change
                    elif result.get('event') == 'DELETE':
                        # Find the existing SQL memory record by mem0_id
                        sql_memory_record = db.query(Memory).filter(
                            text("metadata_->>'mem0_id' = :mem0_id"),
                            Memory.user_id == user.id
                        ).params(mem0_id=mem0_memory_id_str).first()
                        
                        if sql_memory_record:
                            sql_memory_record.state = MemoryState.deleted
                            sql_memory_record.deleted_at = datetime.datetime.now(datetime.UTC)
                            history = MemoryStatusHistory(
                                memory_id=sql_memory_record.id,
                                changed_by=user.id,
                                old_state=MemoryState.active,
                                new_state=MemoryState.deleted
                            )
                            db.add(history)
                    elif result.get('event') == 'UPDATE':
                        updated_count += 1
                        
                db.commit()
                
                # Return a meaningful string response
                if added_count > 0:
                    return f"Successfully added {added_count} new memory(ies). Content: {text[:100]}{'...' if len(text) > 100 else ''}"
                elif updated_count > 0:
                    return f"Updated {updated_count} existing memory(ies) with new information. Content: {text[:100]}{'...' if len(text) > 100 else ''}"
                else:
                    return f"Memory processed but no changes made (possibly duplicate). Content: {text[:100]}{'...' if len(text) > 100 else ''}"
            else:
                # Handle case where response doesn't have expected format
                return f"Memory processed successfully. Response: {str(response)[:200]}{'...' if len(str(response)) > 200 else ''}"
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error in add_memories MCP tool: {e}", exc_info=True)
        return f"Error adding to memory: {e}"


@mcp.tool(description="Search the user's memory for memories that match the query")
async def search_memory(query: str) -> str:
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    try:
        # Add timeout to prevent hanging
        return await asyncio.wait_for(_search_memory_impl(query, supa_uid, client_name), timeout=30.0)
    except asyncio.TimeoutError:
        return f"Search timed out. Please try a simpler query."
    except Exception as e:
        logging.error(f"Error in search_memory MCP tool: {e}", exc_info=True)
        return f"Error searching memory: {e}"


async def _search_memory_impl(query: str, supa_uid: str, client_name: str) -> str:
    """Implementation of search_memory with timeout protection"""
    memory_client = get_memory_client()
    db = SessionLocal()
    try:
        # Get user (but don't filter by specific app - search ALL memories)
        user = get_or_create_user(db, supa_uid, None)

        # Search ALL memories for this user across all apps
        mem0_search_results = memory_client.search(query=query, user_id=supa_uid)

        processed_results = []
        actual_results_list = []
        if isinstance(mem0_search_results, dict) and 'results' in mem0_search_results:
             actual_results_list = mem0_search_results['results']
        elif isinstance(mem0_search_results, list):
             actual_results_list = mem0_search_results

        for mem_data in actual_results_list:
            mem0_id = mem_data.get('id')
            if not mem0_id: continue
            processed_results.append(mem_data)
        
        db.commit()
        return json.dumps(processed_results, indent=2)
    finally:
        db.close()


@mcp.tool(description="List all memories in the user's memory")
async def list_memories() -> str:
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    try:
        # Add timeout to prevent hanging
        return await asyncio.wait_for(_list_memories_impl(supa_uid, client_name), timeout=30.0)
    except asyncio.TimeoutError:
        return f"List memories timed out. Please try again."
    except Exception as e:
        logging.error(f"Error in list_memories MCP tool: {e}", exc_info=True)
        return f"Error getting memories: {e}"


async def _list_memories_impl(supa_uid: str, client_name: str) -> str:
    """Implementation of list_memories with timeout protection"""
    memory_client = get_memory_client()
    db = SessionLocal()
    try:
        # Get user (but don't filter by specific app - show ALL memories)
        user = get_or_create_user(db, supa_uid, None)

        # Get ALL memories for this user across all apps
        all_mem0_memories = memory_client.get_all(user_id=supa_uid)

        processed_results = []
        actual_results_list = []
        if isinstance(all_mem0_memories, dict) and 'results' in all_mem0_memories:
             actual_results_list = all_mem0_memories['results']
        elif isinstance(all_mem0_memories, list):
             actual_results_list = all_mem0_memories

        for mem_data in actual_results_list:
            mem0_id = mem_data.get('id')
            if not mem0_id: continue
            processed_results.append(mem_data)
        
        db.commit()
        return json.dumps(processed_results, indent=2)
    finally:
        db.close()


@mcp.tool(description="Delete all memories in the user's memory")
async def delete_all_memories() -> str:
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    memory_client = get_memory_client() # Initialize client when tool is called
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    try:
        db = SessionLocal()
        try:
            user, app = get_user_and_app(db, supabase_user_id=supa_uid, app_name=client_name, email=None)

            memory_client.delete_all(user_id=supa_uid)

            sql_memories_to_delete = db.query(Memory).filter(Memory.user_id == user.id).all()
            now = datetime.datetime.now(datetime.UTC)
            for mem_record in sql_memories_to_delete:
                if mem_record.state != MemoryState.deleted:
                    history = MemoryStatusHistory(
                        memory_id=mem_record.id,
                        changed_by=user.id,
                        old_state=mem_record.state,
                        new_state=MemoryState.deleted
                    )
                    db.add(history)
                    mem_record.state = MemoryState.deleted
                    mem_record.deleted_at = now
                    
                    access_log = MemoryAccessLog(
                        memory_id=mem_record.id,
                        app_id=app.id,
                        access_type="delete_all_mcp",
                        metadata_={
                            "operation": "bulk_delete_mcp_tool",
                            "mem0_user_id_cleared": supa_uid
                        }
                    )
                    db.add(access_log)
            
            db.commit()
            return f"Successfully initiated deletion of all memories for user {supa_uid} via mem0 and updated SQL records."
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error in delete_all_memories MCP tool: {e}", exc_info=True)
        return f"Error deleting memories: {e}"


@mcp.tool(description="Get detailed information about a specific memory by its ID")
async def get_memory_details(memory_id: str) -> str:
    """
    Retrieve detailed information about a specific memory using its ID.
    This is useful when you want to examine a particular memory in detail.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    try:
        db = SessionLocal()
        try:
            # Get user
            user = get_or_create_user(db, supa_uid, None)
            
            # First try to find the memory in our SQL database
            sql_memory = db.query(Memory).filter(
                Memory.id == memory_id,
                Memory.user_id == user.id,
                Memory.state != MemoryState.deleted
            ).first()
            
            if sql_memory:
                # Found in SQL database
                memory_details = {
                    "id": str(sql_memory.id),
                    "content": sql_memory.content,
                    "created_at": sql_memory.created_at.isoformat() if sql_memory.created_at else None,
                    "updated_at": sql_memory.updated_at.isoformat() if sql_memory.updated_at else None,
                    "state": sql_memory.state.value if sql_memory.state else None,
                    "metadata": sql_memory.metadata_ or {},
                    "app_name": sql_memory.app.name if sql_memory.app else None,
                    "categories": [cat.name for cat in sql_memory.categories] if sql_memory.categories else [],
                    "source": "sql_database"
                }
                
                return json.dumps(memory_details, indent=2)
            
            # If not found in SQL, try searching mem0 by ID
            memory_client = get_memory_client()
            all_memories = memory_client.get_all(user_id=supa_uid)
            
            # Handle different response formats
            memories_list = []
            if isinstance(all_memories, dict) and 'results' in all_memories:
                memories_list = all_memories['results']
            elif isinstance(all_memories, list):
                memories_list = all_memories
            
            # Look for the specific memory ID
            for mem in memories_list:
                if isinstance(mem, dict) and mem.get('id') == memory_id:
                    return json.dumps({
                        "id": mem.get('id'),
                        "content": mem.get('memory', mem.get('content', 'No content available')),
                        "metadata": mem.get('metadata', {}),
                        "created_at": mem.get('created_at'),
                        "updated_at": mem.get('updated_at'),
                        "source": "mem0_vector_store"
                    }, indent=2)
            
            # Memory not found
            return f"Memory with ID '{memory_id}' not found. This could mean:\n1. The memory doesn't exist\n2. It belongs to a different user\n3. It has been deleted\n4. The ID format is incorrect"
            
        finally:
            db.close()
            
    except Exception as e:
        logging.error(f"Error in get_memory_details MCP tool: {e}", exc_info=True)
        return f"Error retrieving memory details: {e}"


@mcp.tool(description="Sync Substack posts for the user. Provide the Substack URL (e.g., https://username.substack.com)")
async def sync_substack_posts(substack_url: str, max_posts: int = 20) -> str:
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    try:
        db = SessionLocal()
        try:
            # Use the SubstackService to handle the sync
            service = SubstackService()
            synced_count, message = await service.sync_substack_posts(
                db=db,
                supabase_user_id=supa_uid,
                substack_url=substack_url,
                max_posts=max_posts,
                use_mem0=True  # Try to use mem0, but it will gracefully degrade if not available
            )
            
            return message
            
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error in sync_substack_posts MCP tool: {e}", exc_info=True)
        return f"Error syncing Substack: {str(e)}"


@mcp.tool(description="Deep query across all user's memories and documents using Gemini's long-context capabilities. This searches through everything - regular memories, documents, essays, etc.")
async def deep_memory_query(search_query: str) -> str:
    """
    Performs a deep, comprehensive search across all user content using Gemini.
    Uses chunked search for efficiency, then retrieves full context.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    try:
        db = SessionLocal()
        try:
            # Get user and app
            user, app = get_user_and_app(db, supa_uid, client_name)
            if not user or not app:
                return "Error: User or app not found"
            
            # Initialize services
            gemini_service = GeminiService()
            chunking_service = ChunkingService()
            
            # 1. Search regular memories (quick)
            memory_client = get_memory_client()
            memories_result = memory_client.search(
                query=search_query,
                user_id=supa_uid,  # Use Supabase user ID for mem0 search
                limit=20
            )
            
            # Handle different memory result formats
            memories = []
            if isinstance(memories_result, dict) and 'results' in memories_result:
                memories = memories_result['results']
            elif isinstance(memories_result, list):
                memories = memories_result
            
            # 2. Search document chunks (efficient)
            relevant_chunks = chunking_service.search_chunks(
                db=db,
                query=search_query,
                user_id=str(user.id),  # Use SQL user ID for document search
                limit=10
            )
            
            # 3. Get unique documents from relevant chunks
            document_ids = list(set(chunk.document_id for chunk in relevant_chunks))
            relevant_documents = []
            if document_ids:
                relevant_documents = db.query(Document).filter(
                    Document.id.in_(document_ids)
                ).all()
            
            # 4. If no chunks found, search documents directly by content
            if not relevant_documents:
                relevant_documents = db.query(Document).filter(
                    Document.user_id == user.id,
                    Document.content.ilike(f"%{search_query}%")
                ).limit(5).all()
            
            # 5. Build context for Gemini
            context = "=== SEARCH RESULTS ===\n\n"
            
            # Add memories with proper type checking
            if memories:
                context += "--- RELEVANT MEMORIES ---\n\n"
                for i, mem in enumerate(memories, 1):
                    # Handle both string and dict formats
                    if isinstance(mem, dict):
                        memory_text = mem.get('memory', mem.get('content', str(mem)))
                    else:
                        memory_text = str(mem)
                    context += f"Memory {i}: {memory_text}\n"
                context += "\n"
            
            # Add relevant chunks with document context
            if relevant_chunks:
                context += "--- RELEVANT DOCUMENT EXCERPTS ---\n\n"
                for chunk in relevant_chunks:
                    doc = next((d for d in relevant_documents if d.id == chunk.document_id), None)
                    if doc:
                        context += f"From '{doc.title}' ({doc.document_type}):\n"
                        context += f"{chunk.content}\n\n"
            
            # 6. If we have relevant documents, include their full context
            if relevant_documents and len(context) < 50000:  # Limit context size
                context += "\n--- FULL DOCUMENTS (Most Relevant) ---\n\n"
                for doc in relevant_documents[:2]:  # Limit to 2 full documents
                    context += f"=== {doc.title} ===\n"
                    context += f"Type: {doc.document_type}\n"
                    context += f"URL: {doc.source_url}\n\n"
                    # Include first 10k chars of document
                    context += doc.content[:10000]
                    if len(doc.content) > 10000:
                        context += "\n... (truncated)\n"
                    context += "\n\n"
            
            # 7. Generate response with Gemini
            prompt = f"""You are analyzing a user's knowledge base to answer their query.

Query: {search_query}

{context}

Please provide a comprehensive answer based on the search results above. If you found relevant information, cite which memories or documents it came from. If the query wasn't found, explain what you did find that might be related."""
            
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    gemini_service.model.generate_content,
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.7,
                        max_output_tokens=2048
                    )
                ),
                timeout=30.0  # 30 second timeout
            )
            
            return response.text
            
        finally:
            db.close()
            
    except asyncio.TimeoutError:
        return "The search took too long. Try a more specific query or use the regular search_memory tool for faster results."
    except Exception as e:
        logger.error(f"Error in deep_memory_query: {e}")
        return f"Error performing deep search: {str(e)}"


@mcp.tool(description="Process documents into chunks for efficient retrieval. Run this after syncing new documents.")
async def chunk_documents() -> str:
    """
    Chunks all documents for the current user into smaller pieces for efficient search.
    This runs in the background and improves search performance.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    try:
        db = SessionLocal()
        try:
            # Get user
            user, app = get_user_and_app(db, supa_uid, client_name)
            if not user or not app:
                return "Error: User or app not found"
            
            # Run chunking
            chunking_service = ChunkingService()
            processed = chunking_service.chunk_all_documents(db, str(user.id))
            
            return f"Successfully chunked {processed} documents. Your searches will now be faster and more accurate."
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in chunk_documents: {e}")
        return f"Error chunking documents: {str(e)}"


@mcp_router.get("/{client_name}/sse/{user_id}")
async def handle_sse(request: Request):
    supa_user_id_from_path = request.path_params.get("user_id")
    client_name = request.path_params.get("client_name")
    
    # Set context variables
    user_token = user_id_var.set(supa_user_id_from_path or "")
    client_token = client_name_var.set(client_name or "")

    try:
        # Add error handling and proper initialization
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,
        ) as (read_stream, write_stream):
            # Ensure proper initialization before running
            try:
                await mcp._mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp._mcp_server.create_initialization_options(),
                )
            except Exception as e:
                logging.error(f"MCP server run error: {e}")
                # Don't re-raise, let the connection close gracefully
    except Exception as e:
        logging.error(f"MCP SSE connection error: {e}")
    finally:
        # Always reset context variables
        try:
            user_id_var.reset(user_token)
            client_name_var.reset(client_token)
        except:
            pass


@mcp_router.post("/messages/")
async def handle_post_message(request: Request):
    """Handle POST messages for SSE with better error handling"""
    try:
        # Get session_id from query params
        session_id = request.query_params.get("session_id")
        if not session_id:
            return {"status": "error", "message": "Missing session_id"}
        
        body = await request.body()
        if not body:
            return {"status": "error", "message": "Empty request body"}

        # Create proper receive function
        async def receive():
            return {"type": "http.request", "body": body, "more_body": False}

        # Create proper send function that captures responses
        responses = []
        async def send(message):
            responses.append(message)

        try:
            # Handle the message with proper error catching
            await sse.handle_post_message(request.scope, receive, send)
            return {"status": "ok", "session_id": session_id}
        except Exception as e:
            logging.error(f"Error handling POST message: {e}")
            return {"status": "error", "message": str(e)}
            
    except Exception as e:
        logging.error(f"Error in handle_post_message: {e}")
        return {"status": "error", "message": "Internal server error"}

def setup_mcp_server(app: FastAPI):
    """Setup MCP server with the FastAPI application"""
    mcp._mcp_server.name = f"mem0-mcp-server"

    # Include MCP router in the FastAPI app
    app.include_router(mcp_router)
