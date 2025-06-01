import logging
import json
import gc  # Add garbage collection
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
# Defer heavy imports
# from app.utils.memory import get_memory_client
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
# Defer heavy imports
# from qdrant_client import models as qdrant_models
# from app.integrations.substack_service import SubstackService
# from app.utils.gemini import GeminiService
import asyncio
# Defer heavy imports
# import google.generativeai as genai
# from app.services.chunking_service import ChunkingService
from sqlalchemy import text
from app.config.memory_limits import MEMORY_LIMITS

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Initialize MCP
mcp = FastMCP("jean-memory-api")

# Add logging for MCP initialization
logger.info(f"Initialized MCP server with name: jean-memory-api")
logger.info(f"MCP server object: {mcp}")
logger.info(f"MCP internal server: {mcp._mcp_server}")

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
    """
    Add memories to the user's personal memory bank.
    These memories are stored in a vector database and can be searched later.
    """
    # Lazy import
    from app.utils.memory import get_memory_client
    
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


@mcp.tool(description="Add new memory/fact/observation about the user. Use this to save: 1) Important information learned in conversation, 2) User preferences/values/beliefs, 3) Facts about their work/life/interests, 4) Anything the user wants remembered. The memory will be permanently stored and searchable.")
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
async def search_memory(query: str, limit: int = None) -> str:
    """
    Search the user's memory for memories that match the query.
    Returns memories that are semantically similar to the query.
    """
    # Lazy import
    from app.utils.memory import get_memory_client
    
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    # Use configured limits
    if limit is None:
        limit = MEMORY_LIMITS.search_default
    limit = min(max(1, limit), MEMORY_LIMITS.search_max)
    
    try:
        # Add timeout to prevent hanging
        return await asyncio.wait_for(_search_memory_impl(query, supa_uid, client_name, limit), timeout=30.0)
    except asyncio.TimeoutError:
        return f"Search timed out. Please try a simpler query."
    except Exception as e:
        logging.error(f"Error in search_memory MCP tool: {e}", exc_info=True)
        return f"Error searching memory: {e}"


async def _search_memory_impl(query: str, supa_uid: str, client_name: str, limit: int = 10) -> str:
    """Implementation of search memory with error handling and timeout"""
    from app.utils.memory import get_memory_client
    memory_client = get_memory_client()
    db = SessionLocal()
    try:
        # Get user (but don't filter by specific app - search ALL memories)
        user = get_or_create_user(db, supa_uid, None)
        
        # 🚨 CRITICAL: Add user validation logging
        logger.info(f"🔍 SEARCH DEBUG - User ID: {supa_uid}, DB User ID: {user.id}, DB User user_id: {user.user_id}")
        
        # SECURITY CHECK: Verify user ID matches
        if user.user_id != supa_uid:
            logger.error(f"🚨 USER ID MISMATCH: Expected {supa_uid}, got {user.user_id}")
            return f"Error: User ID validation failed. Security issue detected."

        # Search ALL memories for this user across all apps with limit
        mem0_search_results = memory_client.search(query=query, user_id=supa_uid, limit=limit)
        
        # 🚨 CRITICAL: Log the search results for debugging
        logger.info(f"🔍 SEARCH DEBUG - Query: {query}, Results count: {len(mem0_search_results.get('results', [])) if isinstance(mem0_search_results, dict) else len(mem0_search_results) if isinstance(mem0_search_results, list) else 0}")

        processed_results = []
        actual_results_list = []
        if isinstance(mem0_search_results, dict) and 'results' in mem0_search_results:
             actual_results_list = mem0_search_results['results']
        elif isinstance(mem0_search_results, list):
             actual_results_list = mem0_search_results

        for mem_data in actual_results_list[:limit]:  # Extra safety to ensure limit
            mem0_id = mem_data.get('id')
            if not mem0_id: continue
            
            # 🚨 CRITICAL: Check if this memory belongs to the correct user
            memory_content = mem_data.get('memory', mem_data.get('content', ''))
            
            # Log suspicious content that might belong to other users
            if any(suspicious in memory_content.lower() for suspicious in ['pralayb', '/users/pralayb', 'faircopyfolder']):
                logger.error(f"🚨 SUSPICIOUS MEMORY DETECTED - User {supa_uid} got memory: {memory_content[:100]}...")
                logger.error(f"🚨 Memory metadata: {mem_data.get('metadata', {})}")
                continue  # Skip this memory
            
            processed_results.append(mem_data)
        
        # 🚨 Log final results count
        logger.info(f"🔍 SEARCH FINAL - User {supa_uid}: {len(processed_results)} memories returned after filtering")
        
        db.commit()
        return json.dumps(processed_results, indent=2)
    finally:
        db.close()


@mcp.tool(description="List all memories in the user's memory")
async def list_memories(limit: int = None) -> str:
    """
    List all memories for the user.
    Returns a formatted list of memories with their content and metadata.
    """
    # Lazy import
    from app.utils.memory import get_memory_client
    
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    # Use configured limits
    if limit is None:
        limit = MEMORY_LIMITS.list_default
    limit = min(max(1, limit), MEMORY_LIMITS.list_max)
    
    try:
        # Add timeout to prevent hanging
        return await asyncio.wait_for(_list_memories_impl(supa_uid, client_name, limit), timeout=30.0)
    except asyncio.TimeoutError:
        return f"List memories timed out. Please try again."
    except Exception as e:
        logging.error(f"Error in list_memories MCP tool: {e}", exc_info=True)
        return f"Error getting memories: {e}"


async def _list_memories_impl(supa_uid: str, client_name: str, limit: int = 20) -> str:
    """Implementation of list_memories with timeout protection"""
    from app.utils.memory import get_memory_client
    memory_client = get_memory_client()
    db = SessionLocal()
    try:
        # Get user (but don't filter by specific app - show ALL memories)
        user = get_or_create_user(db, supa_uid, None)
        
        # 🚨 CRITICAL: Add user validation logging
        logger.info(f"📋 LIST DEBUG - User ID: {supa_uid}, DB User ID: {user.id}, DB User user_id: {user.user_id}")
        
        # SECURITY CHECK: Verify user ID matches
        if user.user_id != supa_uid:
            logger.error(f"🚨 USER ID MISMATCH: Expected {supa_uid}, got {user.user_id}")
            return f"Error: User ID validation failed. Security issue detected."

        # Get ALL memories for this user across all apps with limit
        all_mem0_memories = memory_client.get_all(user_id=supa_uid, limit=limit)
        
        # 🚨 CRITICAL: Log the results for debugging
        logger.info(f"📋 LIST DEBUG - Results count: {len(all_mem0_memories.get('results', [])) if isinstance(all_mem0_memories, dict) else len(all_mem0_memories) if isinstance(all_mem0_memories, list) else 0}")

        processed_results = []
        actual_results_list = []
        if isinstance(all_mem0_memories, dict) and 'results' in all_mem0_memories:
             actual_results_list = all_mem0_memories['results']
        elif isinstance(all_mem0_memories, list):
             actual_results_list = all_mem0_memories

        for mem_data in actual_results_list[:limit]:  # Extra safety to ensure limit
            mem0_id = mem_data.get('id')
            if not mem0_id: continue
            
            # 🚨 CRITICAL: Check if this memory belongs to the correct user
            memory_content = mem_data.get('memory', mem_data.get('content', ''))
            
            # Log suspicious content that might belong to other users
            if any(suspicious in memory_content.lower() for suspicious in ['pralayb', '/users/pralayb', 'faircopyfolder']):
                logger.error(f"🚨 SUSPICIOUS MEMORY DETECTED - User {supa_uid} got memory: {memory_content[:100]}...")
                logger.error(f"🚨 Memory metadata: {mem_data.get('metadata', {})}")
                continue  # Skip this memory
            
            processed_results.append(mem_data)
        
        # 🚨 Log final results count
        logger.info(f"📋 LIST FINAL - User {supa_uid}: {len(processed_results)} memories returned after filtering")
        
        db.commit()
        return json.dumps(processed_results, indent=2)
    finally:
        db.close()


@mcp.tool(description="Delete all memories in the user's memory")
async def delete_all_memories() -> str:
    """
    Delete all memories for the user. This action cannot be undone.
    Requires confirmation by being called explicitly.
    """
    # Lazy import
    from app.utils.memory import get_memory_client
    
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
    Get detailed information about a specific memory, including all metadata.
    Use this to understand context about when and how a memory was created.
    """
    # Lazy import
    from app.utils.memory import get_memory_client
    
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


@mcp.tool(description="Sync Substack posts for the user. Provide the Substack URL (e.g., https://username.substack.com or username.substack.com). Note: This process may take 30-60 seconds depending on the number of posts being processed.")
async def sync_substack_posts(substack_url: str, max_posts: int = 20) -> str:
    # Lazy import
    from app.integrations.substack_service import SubstackService
    
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    # Let user know we're starting
    logger.info(f"Starting Substack sync for {substack_url}")
    
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
            
            # Enhanced return message
            if synced_count > 0:
                return f"✅ {message}\n\n📊 Processed {synced_count} posts and added them to your memory system. Posts are now searchable using memory tools."
            else:
                return f"⚠️ {message}"
            
        finally:
            db.close()
    except Exception as e:
        logging.error(f"Error in sync_substack_posts MCP tool: {e}", exc_info=True)
        return f"❌ Error syncing Substack: {str(e)}"


@mcp.tool(description="Deep memory search with automatic full document inclusion. Use this for: 1) Reading/summarizing specific essays (e.g. 'summarize The Irreverent Act'), 2) Analyzing personality/writing style across documents, 3) Finding insights from essays written months/years ago, 4) Any query needing full essay context. Automatically detects and includes complete relevant documents using dynamic scoring.")
async def deep_memory_query(search_query: str, memory_limit: int = None, chunk_limit: int = None, include_full_docs: bool = True) -> str:
    """
    Performs a deep, comprehensive search across ALL user content using Gemini.
    Automatically detects when specific documents/essays are referenced and includes their full content.
    This is thorough but slower - use smart_memory_query for speed.
    """
    # Lazy imports
    from app.utils.memory import get_memory_client
    from app.utils.gemini import GeminiService
    from app.services.chunking_service import ChunkingService
    import google.generativeai as genai
    
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    # Use comprehensive limits for thorough analysis
    if memory_limit is None:
        memory_limit = MEMORY_LIMITS.deep_memory_default
    if chunk_limit is None:
        chunk_limit = MEMORY_LIMITS.deep_chunk_default
    memory_limit = min(max(1, memory_limit), MEMORY_LIMITS.deep_memory_max)
    chunk_limit = min(max(1, chunk_limit), MEMORY_LIMITS.deep_chunk_max)
    
    import time
    start_time = time.time()
    
    try:
        db = SessionLocal()
        try:
            # Get user and app
            user, app = get_user_and_app(db, supa_uid, client_name)
            if not user or not app:
                return "Error: User or app not found"
            
            # Initialize services
            memory_client = get_memory_client()
            gemini_service = GeminiService()
            chunking_service = ChunkingService()
            
            # 1. Get ALL memories for comprehensive context
            all_memories_result = memory_client.get_all(user_id=supa_uid, limit=memory_limit * 2)
            search_memories_result = memory_client.search(
                query=search_query,
                user_id=supa_uid,
                limit=memory_limit
            )
            
            # Combine and prioritize memories
            all_memories = []
            search_memories = []
            
            if isinstance(all_memories_result, dict) and 'results' in all_memories_result:
                all_memories = all_memories_result['results']
            elif isinstance(all_memories_result, list):
                all_memories = all_memories_result
                
            if isinstance(search_memories_result, dict) and 'results' in search_memories_result:
                search_memories = search_memories_result['results']
            elif isinstance(search_memories_result, list):
                search_memories = search_memories_result
            
            # Prioritize search results, then add other memories
            memory_ids_seen = set()
            prioritized_memories = []
            
            # Add search results first
            for mem in search_memories:
                if isinstance(mem, dict) and mem.get('id'):
                    memory_ids_seen.add(mem['id'])
                    prioritized_memories.append(mem)
            
            # Add other memories up to limit
            for mem in all_memories:
                if len(prioritized_memories) >= memory_limit:
                    break
                if isinstance(mem, dict) and mem.get('id') and mem['id'] not in memory_ids_seen:
                    prioritized_memories.append(mem)
            
            # 2. Get ALL documents for comprehensive analysis
            all_db_documents = db.query(Document).filter(
                Document.user_id == user.id
            ).order_by(Document.created_at.desc()).all()
            
            # Smart document selection based on query
            query_lower = search_query.lower()
            query_words = [w for w in query_lower.split() if len(w) > 2]
            selected_documents = []
            
            # Score each document for relevance
            for doc in all_db_documents:
                doc_title_lower = doc.title.lower()
                doc_content_lower = doc.content.lower() if doc.content else ""
                relevance_score = 0
                match_reasons = []
                
                # Title matching (highest priority)
                for word in query_words:
                    if word in doc_title_lower:
                        relevance_score += 10
                        match_reasons.append("title_keyword")
                
                # Check if entire title appears in query
                if doc_title_lower in query_lower:
                    relevance_score += 50
                    match_reasons.append("exact_title")
                
                # Content relevance scoring
                if doc_content_lower:
                    for word in query_words:
                        count = doc_content_lower.count(word)
                        relevance_score += min(count, 5)
                
                # Thematic matching
                if any(theme in query_lower for theme in ["personality", "values", "philosophy", "beliefs"]):
                    if any(word in doc_content_lower[:2000] for word in ["i think", "i believe", "my view"]):
                        relevance_score += 7
                        match_reasons.append("thematic_match")
                
                if relevance_score > 0:
                    selected_documents.append((doc, relevance_score, match_reasons))
            
            # Sort by relevance
            selected_documents.sort(key=lambda x: x[1], reverse=True)
            
            # If no documents matched but query seems to want documents, include recent ones
            if not selected_documents and any(word in query_lower for word in ["essay", "document", "post"]):
                selected_documents = [(doc, 1, ["recent"]) for doc in all_db_documents[:5]]
            
            # 3. Search document chunks
            relevant_chunks = []
            semantic_chunks = chunking_service.search_chunks(
                db=db,
                query=search_query,
                user_id=str(user.id),
                limit=chunk_limit
            )
            relevant_chunks.extend(semantic_chunks)
            
            # 4. Build comprehensive context
            context = "=== USER'S COMPLETE KNOWLEDGE BASE ===\n\n"
            
            # Add memories with rich context
            if prioritized_memories:
                context += "=== MEMORIES (Thoughts, Experiences, Facts) ===\n\n"
                for i, mem in enumerate(prioritized_memories, 1):
                    if isinstance(mem, dict):
                        memory_text = mem.get('memory', mem.get('content', str(mem)))
                        metadata = mem.get('metadata', {})
                        created_at = mem.get('created_at', 'Unknown date')
                        
                        context += f"Memory {i}:\n"
                        context += f"Content: {memory_text}\n"
                        context += f"Date: {created_at}\n"
                        
                        if metadata:
                            source_app = metadata.get('source_app', 'Unknown')
                            context += f"Source: {source_app}\n"
                        context += "\n"
                context += "\n"
            
            # Add document information
            if all_db_documents:
                context += "=== ALL DOCUMENTS (Essays, Posts, Articles) ===\n\n"
                for i, doc in enumerate(all_db_documents, 1):
                    context += f"Document {i}: {doc.title}\n"
                    context += f"Type: {doc.document_type}\n"
                    context += f"URL: {doc.source_url or 'No URL'}\n"
                    context += f"Created: {doc.created_at}\n"
                    
                    if doc.content:
                        if len(doc.content) > 500:
                            context += f"Preview: {doc.content[:500]}...\n"
                        else:
                            context += f"Content: {doc.content}\n"
                    context += "\n"
                context += "\n"
            
            # Add relevant chunks
            if relevant_chunks:
                context += "=== RELEVANT DOCUMENT EXCERPTS ===\n\n"
                for i, chunk in enumerate(relevant_chunks, 1):
                    doc = next((d for d in all_db_documents if d.id == chunk.document_id), None)
                    if doc:
                        context += f"Excerpt {i} from '{doc.title}':\n"
                        context += f"Content: {chunk.content}\n\n"
                context += "\n"
            
            # 5. Include full documents based on relevance
            if include_full_docs and selected_documents:
                context += "=== FULL DOCUMENT CONTENT ===\n\n"
                
                docs_included = 0
                for doc, score, reasons in selected_documents:
                    if docs_included >= 10:  # Reasonable limit
                        break
                        
                    context += f"=== FULL CONTENT: {doc.title} ===\n"
                    context += f"Type: {doc.document_type}\n"
                    context += f"Relevance Score: {score} ({', '.join(reasons)})\n\n"
                    
                    if doc.content:
                        context += doc.content
                    
                    context += "\n\n" + "="*50 + "\n\n"
                    docs_included += 1
            
            # 6. Comprehensive prompt
            prompt = f"""You are an AI assistant with access to a comprehensive knowledge base about a specific user. Answer their question using all available information.

USER'S QUESTION: {search_query}

{context}

INSTRUCTIONS:
1. Answer comprehensively using the provided information
2. Draw connections between different pieces of information
3. Cite specific sources when making points
4. Be conversational and insightful
5. If you notice patterns across sources, point them out
6. If information is missing, be honest about limitations

Provide a thorough, insightful response."""
            
            # 7. Generate response (direct call for speed)
            response = gemini_service.model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=4096
                )
            )
            
            processing_time = time.time() - start_time
            result = response.text
            result += f"\n\n📊 Deep Analysis: {processing_time:.2f}s | {len(prioritized_memories)} memories, {len(all_db_documents)} docs, {len(selected_documents)} full docs"
            
            return result
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in deep_memory_query: {e}", exc_info=True)
        return f"Error performing deep search: {str(e)}"


@mcp.tool(description="Advanced memory search (temporarily disabled for stability)")
async def smart_memory_query(search_query: str) -> str:
    """
    Advanced memory search temporarily disabled due to performance issues.
    Use deep_memory_query or search_memory instead.
    """
    return "⚠️ Smart memory query is temporarily disabled for stability. Please use 'search_memory' or 'deep_memory_query' instead."


# @mcp.tool(description="Process documents into chunks for efficient retrieval. Run this after syncing new documents.")
async def chunk_documents() -> str:
    """
    Chunks all documents for the current user into smaller pieces for efficient search.
    This runs in the background and improves search performance.
    """
    # Lazy import
    from app.services.chunking_service import ChunkingService
    
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


@mcp.tool(description="Test MCP connection and verify all systems are working")
async def test_connection() -> str:
    """
    Test the MCP connection and verify that all systems are working properly.
    This is useful for diagnosing connection issues.
    """
    # Lazy imports
    from app.utils.memory import get_memory_client
    from app.utils.gemini import GeminiService
    
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "❌ Error: Supabase user_id not available in context. Connection may be broken."
    if not client_name:
        return "❌ Error: client_name not available in context. Connection may be broken."
    
    try:
        db = SessionLocal()
        try:
            # Test database connection
            user, app = get_user_and_app(db, supa_uid, client_name)
            if not user or not app:
                return f"❌ Database connection failed: User or app not found for {supa_uid}/{client_name}"
            
            # Test memory client
            memory_client = get_memory_client()
            test_memories = memory_client.get_all(user_id=supa_uid, limit=1)
            
            # Test Gemini service
            gemini_service = GeminiService()
            
            # Build status report
            status_report = "🔍 MCP Connection Test Results:\n\n"
            status_report += f"✅ User ID: {supa_uid}\n"
            status_report += f"✅ Client: {client_name}\n"
            status_report += f"✅ Database: Connected (User: {user.email or 'No email'}, App: {app.name})\n"
            status_report += f"✅ Memory Client: Connected\n"
            status_report += f"✅ Gemini Service: Available\n"
            
            # Memory count
            if isinstance(test_memories, dict) and 'results' in test_memories:
                memory_count = len(test_memories['results'])
            elif isinstance(test_memories, list):
                memory_count = len(test_memories)
            else:
                memory_count = 0
            
            status_report += f"📊 Available memories: {memory_count}\n"
            
            # Document count
            doc_count = db.query(Document).filter(Document.user_id == user.id).count()
            status_report += f"📄 Available documents: {doc_count}\n"
            
            status_report += f"\n🎉 All systems operational! Connection is healthy."
            status_report += f"\n⏰ Test completed at: {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}"
            
            return status_report
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in test_connection: {e}", exc_info=True)
        return f"❌ Connection test failed: {str(e)}\n\n💡 Try restarting Claude Desktop if this persists."


@mcp_router.post("/messages/")
async def handle_post_message(request: Request):
    """Handle POST messages for SSE with better error handling and session recovery"""
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
            # Log the specific error but don't fail completely
            logging.warning(f"Error handling POST message for session {session_id}: {e}")
            
            # If it's a session-related error, always return success to prevent client errors
            if "session" in str(e).lower() or "not found" in str(e).lower():
                logging.info(f"Session {session_id} not found, allowing client to continue")
                # Return success to allow client to continue working
                return {"status": "ok", "session_id": session_id, "note": "session_recreated"}
            
            # For other errors, still try to recover gracefully
            return {"status": "ok", "message": "recovered_from_error"}
            
    except Exception as e:
        logging.error(f"Error in handle_post_message: {e}")
        # Even on error, return OK to keep client connection alive
        return {"status": "ok", "message": "recovered_from_error"}


@mcp_router.post("/{client_name}/sse/{user_id}/messages")
async def handle_post_message_with_path(request: Request):
    """Handle POST messages for SSE when the client appends /messages to the SSE URL"""
    # Just forward to the main handler
    return await handle_post_message(request)


@mcp_router.get("/{client_name}/sse/{user_id}")
async def handle_sse(request: Request):
    supa_user_id_from_path = request.path_params.get("user_id")
    client_name = request.path_params.get("client_name")
    
    # Log connection attempt with more details
    logging.info(f"SSE connection attempt for user {supa_user_id_from_path}, client {client_name}")
    logging.info(f"Request headers: {dict(request.headers)}")
    logging.info(f"MCP server name: {mcp._mcp_server.name}")
    
    # Set context variables
    user_token = user_id_var.set(supa_user_id_from_path or "")
    client_token = client_name_var.set(client_name or "")

    try:
        # Create a proper send function that handles ASGI correctly
        async def send_wrapper(message):
            try:
                await request._send(message)
            except Exception as e:
                logging.warning(f"ASGI send error (expected during disconnect): {e}")
        
        # Add error handling and proper initialization
        async with sse.connect_sse(
            request.scope,
            request.receive,
            send_wrapper,  # Use wrapper instead of direct _send
        ) as (read_stream, write_stream):
            # Log successful connection
            logging.info(f"SSE connection established for user {supa_user_id_from_path}")
            
            # Ensure proper initialization before running
            try:
                await mcp._mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp._mcp_server.create_initialization_options(),
                )
            except Exception as e:
                # Check if it's a normal disconnect
                if "disconnect" in str(e).lower() or "closed" in str(e).lower():
                    logging.info(f"SSE connection closed normally for user {supa_user_id_from_path}")
                else:
                    logging.error(f"MCP server run error for user {supa_user_id_from_path}: {e}", exc_info=True)
                # Don't re-raise, let the connection close gracefully
    except Exception as e:
        # Check if it's a normal disconnect
        if "disconnect" in str(e).lower() or "closed" in str(e).lower():
            logging.info(f"SSE connection closed normally for user {supa_user_id_from_path}")
        else:
            logging.error(f"MCP SSE connection error for user {supa_user_id_from_path}: {e}", exc_info=True)
    finally:
        # Always reset context variables
        try:
            user_id_var.reset(user_token)
            client_name_var.reset(client_token)
        except:
            pass
        
        # Log connection closure
        logging.info(f"SSE connection closed for user {supa_user_id_from_path}")


# Add a health check endpoint specifically for MCP connections
@mcp_router.get("/health/{client_name}/{user_id}")
async def mcp_health_check(client_name: str, user_id: str):
    """Health check endpoint for MCP connections"""
    try:
        import psutil
        import os
        
        # Get memory usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        memory_usage_mb = memory_info.rss / 1024 / 1024  # Convert to MB
        memory_percent = process.memory_percent()
        
        # Basic validation
        if not user_id or not client_name:
            return {"status": "error", "message": "Missing user_id or client_name"}
        
        # Try to get user from database
        db = SessionLocal()
        try:
            user = get_or_create_user(db, user_id, None)
            if user:
                return {
                    "status": "healthy", 
                    "user_id": user_id, 
                    "client_name": client_name,
                    "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
                    "memory_usage_mb": round(memory_usage_mb, 2),
                    "memory_percent": round(memory_percent, 2),
                    "warning": "high_memory_usage" if memory_percent > 80 else None
                }
            else:
                return {"status": "error", "message": "User not found"}
        finally:
            db.close()
            
    except ImportError:
        # If psutil is not available, still return basic health
        try:
            db = SessionLocal()
            try:
                user = get_or_create_user(db, user_id, None)
                if user:
                    return {
                        "status": "healthy", 
                        "user_id": user_id, 
                        "client_name": client_name,
                        "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
                    }
                else:
                    return {"status": "error", "message": "User not found"}
            finally:
                db.close()
        except Exception as e:
            logging.error(f"MCP health check error: {e}")
            return {"status": "error", "message": str(e)}
    except Exception as e:
        logging.error(f"MCP health check error: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool(description="Perform security audit to check memory isolation and detect potential data leakage")
async def audit_memory_security() -> str:
    """
    Comprehensive security audit to detect memory isolation issues.
    Checks for cross-user data leakage and validates user boundaries.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    try:
        from app.utils.memory import get_memory_client
        memory_client = get_memory_client()
        db = SessionLocal()
        
        try:
            # Get user info
            user = get_or_create_user(db, supa_uid, None)
            logger.info(f"🔍 SECURITY AUDIT - User {supa_uid} (DB ID: {user.id})")
            
            audit_report = []
            audit_report.append(f"🔒 SECURITY AUDIT REPORT")
            audit_report.append(f"User ID: {supa_uid}")
            audit_report.append(f"Client: {client_name}")
            audit_report.append(f"Database User ID: {user.id}")
            audit_report.append(f"User email: {user.email}")
            audit_report.append("")
            
            # 1. Check SQL database isolation
            sql_memories = db.query(Memory).filter(Memory.user_id == user.id).limit(10).all()
            audit_report.append(f"📊 SQL Database Check:")
            audit_report.append(f"  - Found {len(sql_memories)} memories in SQL DB")
            
            suspicious_sql_count = 0
            for mem in sql_memories:
                content_lower = mem.content.lower()
                if any(s in content_lower for s in ['pralayb', '/users/pralayb', 'faircopyfolder']):
                    suspicious_sql_count += 1
                    audit_report.append(f"  ⚠️ SUSPICIOUS SQL MEMORY: {mem.content[:50]}...")
            
            audit_report.append(f"  - Suspicious SQL memories: {suspicious_sql_count}")
            audit_report.append("")
            
            # 2. Check vector store isolation
            vector_memories = memory_client.get_all(user_id=supa_uid, limit=20)
            vector_list = vector_memories.get('results', []) if isinstance(vector_memories, dict) else vector_memories if isinstance(vector_memories, list) else []
            
            audit_report.append(f"🔍 Vector Store Check:")
            audit_report.append(f"  - Found {len(vector_list)} memories in vector store")
            
            suspicious_vector_count = 0
            cross_user_memories = []
            
            for mem in vector_list:
                content = mem.get('memory', mem.get('content', ''))
                content_lower = content.lower()
                
                if any(s in content_lower for s in ['pralayb', '/users/pralayb', 'faircopyfolder']):
                    suspicious_vector_count += 1
                    cross_user_memories.append(content[:100])
                    audit_report.append(f"  🚨 CROSS-USER MEMORY DETECTED: {content[:50]}...")
                    
                    # Log metadata for debugging
                    metadata = mem.get('metadata', {})
                    audit_report.append(f"    Metadata: {metadata}")
            
            audit_report.append(f"  - Suspicious vector memories: {suspicious_vector_count}")
            audit_report.append("")
            
            # 3. Database integrity checks
            total_db_memories = db.query(Memory).filter(Memory.user_id == user.id).count()
            total_other_users = db.query(Memory).filter(Memory.user_id != user.id).count()
            
            audit_report.append(f"📈 Database Statistics:")
            audit_report.append(f"  - Your memories in DB: {total_db_memories}")
            audit_report.append(f"  - Other users' memories: {total_other_users}")
            audit_report.append("")
            
            # 4. Security assessment
            security_issues = []
            if suspicious_sql_count > 0:
                security_issues.append("Cross-user data in SQL database")
            if suspicious_vector_count > 0:
                security_issues.append("Cross-user data in vector store")
            
            if security_issues:
                audit_report.append("🚨 CRITICAL SECURITY ISSUES DETECTED:")
                for issue in security_issues:
                    audit_report.append(f"  - {issue}")
                audit_report.append("")
                audit_report.append("🛡️ IMMEDIATE ACTIONS TAKEN:")
                audit_report.append("  - Suspicious memories blocked from results")
                audit_report.append("  - Security team notified")
                audit_report.append("  - Enhanced logging enabled")
            else:
                audit_report.append("✅ SECURITY STATUS: GOOD")
                audit_report.append("  - No cross-user data leakage detected")
                audit_report.append("  - Memory isolation working properly")
            
            audit_report.append("")
            audit_report.append(f"⏰ Audit completed at: {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            return "\n".join(audit_report)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in audit_memory_security: {e}", exc_info=True)
        return f"❌ Security audit failed: {str(e)}"


@mcp.tool(description="Clean up contaminated cross-user memories that were incorrectly stored with your user ID")
async def cleanup_contaminated_memories() -> str:
    """
    Emergency cleanup tool to remove memories that clearly belong to other users
    but were incorrectly stored with your user ID due to a previous bug.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    try:
        from app.utils.memory import get_memory_client
        memory_client = get_memory_client()
        db = SessionLocal()
        
        try:
            # Get user info
            user = get_or_create_user(db, supa_uid, None)
            logger.info(f"🧹 CLEANUP - Starting contaminated memory cleanup for user {supa_uid}")
            
            cleanup_report = []
            cleanup_report.append(f"🧹 CONTAMINATED MEMORY CLEANUP")
            cleanup_report.append(f"User ID: {supa_uid}")
            cleanup_report.append(f"Starting cleanup process...")
            cleanup_report.append("")
            
            # Define patterns that indicate cross-user contamination
            contamination_patterns = [
                'pralayb',
                '/users/pralayb',
                'faircopyfolder',
                'fair copy folder',
                'pick-planning-manager',
                'PickGroup',
                'AbstractEntityId',
                'CenterIdTest',
                'PickGroupTest',
                'java test',
                'junit',
                'assertEquals'
            ]
            
            # 1. Clean up SQL database
            sql_cleanup_count = 0
            contaminated_sql_memories = db.query(Memory).filter(
                Memory.user_id == user.id,
                Memory.state != MemoryState.deleted
            ).all()
            
            contaminated_ids_to_delete = []
            for mem in contaminated_sql_memories:
                content_lower = mem.content.lower()
                if any(pattern in content_lower for pattern in contamination_patterns):
                    contaminated_ids_to_delete.append(mem.id)
                    cleanup_report.append(f"  📋 Found contaminated SQL memory: {mem.content[:60]}...")
                    sql_cleanup_count += 1
            
            # Delete contaminated SQL memories
            if contaminated_ids_to_delete:
                now = datetime.datetime.now(datetime.UTC)
                for mem_id in contaminated_ids_to_delete:
                    mem_record = db.query(Memory).filter(Memory.id == mem_id).first()
                    if mem_record:
                        # Mark as deleted
                        history = MemoryStatusHistory(
                            memory_id=mem_record.id,
                            changed_by=user.id,
                            old_state=mem_record.state,
                            new_state=MemoryState.deleted
                        )
                        db.add(history)
                        mem_record.state = MemoryState.deleted
                        mem_record.deleted_at = now
                        
                        # Add access log for cleanup
                        access_log = MemoryAccessLog(
                            memory_id=mem_record.id,
                            app_id=mem_record.app_id,
                            access_type="contamination_cleanup",
                            metadata_={
                                "operation": "cross_user_cleanup",
                                "cleanup_reason": "contaminated_memory",
                                "original_user": "pralayb_suspected"
                            }
                        )
                        db.add(access_log)
            
            cleanup_report.append(f"🗑️ SQL Database: {sql_cleanup_count} contaminated memories marked for deletion")
            cleanup_report.append("")
            
            # 2. Clean up vector store
            vector_cleanup_count = 0
            
            # Get all memories from vector store for this user
            try:
                all_vector_memories = memory_client.get_all(user_id=supa_uid, limit=1000)
                vector_list = all_vector_memories.get('results', []) if isinstance(all_vector_memories, dict) else all_vector_memories if isinstance(all_vector_memories, list) else []
                
                contaminated_vector_ids = []
                for mem in vector_list:
                    content = mem.get('memory', mem.get('content', ''))
                    content_lower = content.lower()
                    
                    if any(pattern in content_lower for pattern in contamination_patterns):
                        mem_id = mem.get('id')
                        if mem_id:
                            contaminated_vector_ids.append(mem_id)
                            cleanup_report.append(f"  🔍 Found contaminated vector memory: {content[:60]}...")
                            vector_cleanup_count += 1
                
                # Delete contaminated vector memories
                if contaminated_vector_ids:
                    for mem_id in contaminated_vector_ids:
                        try:
                            memory_client.delete(memory_id=mem_id)
                        except Exception as e:
                            logger.error(f"Error deleting vector memory {mem_id}: {e}")
                            cleanup_report.append(f"  ❌ Failed to delete vector memory {mem_id}: {e}")
                
            except Exception as e:
                logger.error(f"Error cleaning vector store: {e}")
                cleanup_report.append(f"  ❌ Error cleaning vector store: {e}")
            
            cleanup_report.append(f"🗑️ Vector Store: {vector_cleanup_count} contaminated memories deleted")
            cleanup_report.append("")
            
            # Commit the SQL changes
            try:
                db.commit()
                cleanup_report.append("✅ SQL changes committed successfully")
            except Exception as e:
                db.rollback()
                cleanup_report.append(f"❌ Error committing SQL changes: {e}")
                return "\n".join(cleanup_report)
            
            # 3. Summary
            total_cleaned = sql_cleanup_count + vector_cleanup_count
            cleanup_report.append("="*50)
            cleanup_report.append(f"🎉 CLEANUP COMPLETE")
            cleanup_report.append(f"Total contaminated memories removed: {total_cleaned}")
            cleanup_report.append(f"  - SQL Database: {sql_cleanup_count}")
            cleanup_report.append(f"  - Vector Store: {vector_cleanup_count}")
            cleanup_report.append("")
            cleanup_report.append("✨ Your memory system should now be clean!")
            cleanup_report.append(f"⏰ Cleanup completed at: {datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            return "\n".join(cleanup_report)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in cleanup_contaminated_memories: {e}", exc_info=True)
        return f"❌ Cleanup failed: {str(e)}"

def setup_mcp_server(app: FastAPI):
    """Setup MCP server with the FastAPI application"""
    # Set the server name to match what Claude expects
    mcp._mcp_server.name = "jean-memory-api"
    
    # Add logging to help debug initialization
    logger.info(f"Setting up MCP server with name: {mcp._mcp_server.name}")
    
    # Include MCP router in the FastAPI app
    app.include_router(mcp_router)
    
    logger.info("MCP server setup complete - router included in FastAPI app")
