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
from fastapi.responses import JSONResponse

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
    
    # 🚨 CRITICAL: Add comprehensive logging to detect contamination
    logger.error(f"🔍 ADD_MEMORIES DEBUG - User ID from context: {supa_uid}")
    logger.error(f"🔍 ADD_MEMORIES DEBUG - Client name from context: {client_name}")
    logger.error(f"🔍 ADD_MEMORIES DEBUG - Memory content preview: {text[:100]}...")
    
    # 🚨 CONTAMINATION DETECTION: Check for suspicious Java patterns
    if any(pattern in text.lower() for pattern in [
        'planningcontext', 'java', 'compilation', 'pickgroup', 'defaultgroup',
        'constructor', 'factory', 'junit', '.class', 'import ', 'public class'
    ]):
        logger.error(f"🚨 POTENTIAL CONTAMINATION DETECTED!")
        logger.error(f"🚨 User {supa_uid} trying to add Java content: {text[:150]}...")
        logger.error(f"🚨 This may indicate context variable bleeding!")
        
        # Let's also log current context info
        import contextvars
        logger.error(f"🚨 Current context vars: user_id_var={user_id_var}, client_name_var={client_name_var}")
        
        # 🚨 EMERGENCY: Block suspicious Java content completely to prevent contamination
        return f"❌ BLOCKED: Suspicious Java development content detected. This appears to be contaminated memory from another user. Content blocked for security."
    
    # 🚨 ADDITIONAL SAFETY: Validate user_id format and detect known contaminated user patterns
    if supa_uid and any(suspicious_user in supa_uid.lower() for suspicious_user in ['pralayb', 'test', 'debug']):
        logger.error(f"🚨 SUSPICIOUS USER ID DETECTED: {supa_uid}")
        return f"❌ BLOCKED: Suspicious user ID pattern detected. Operation blocked for security."
    
    memory_client = get_memory_client()

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
                messages=[{"role": "user", "content": text}],
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
async def add_observation(text: str) -> str:
    """
    This is an alias for the add_memories tool with a more descriptive prompt for the agent.
    Functionally, it performs the same action.
    """
    # This function now simply calls the other one to avoid code duplication.
    return await add_memories(text)


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
        # Add timeout to prevent hanging
        return await asyncio.wait_for(_get_memory_details_impl(memory_id, supa_uid, client_name), timeout=10.0)
    except asyncio.TimeoutError:
        return f"Memory lookup timed out. Try again or check if memory ID '{memory_id}' is correct."
    except Exception as e:
        logging.error(f"Error in get_memory_details MCP tool: {e}", exc_info=True)
        return f"Error retrieving memory details: {e}"


async def _get_memory_details_impl(memory_id: str, supa_uid: str, client_name: str) -> str:
    """Optimized implementation of get_memory_details"""
    from app.utils.memory import get_memory_client
    
    db = SessionLocal()
    try:
        # Get user quickly
        user = get_or_create_user(db, supa_uid, None)
        
        # First try SQL database (fastest)
        sql_memory = db.query(Memory).filter(
            Memory.id == memory_id,
            Memory.user_id == user.id,
            Memory.state != MemoryState.deleted
        ).first()
        
        if sql_memory:
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
        
        # Try mem0 with direct search instead of getting all memories
        memory_client = get_memory_client()
        
        # Use search with the exact ID as query - much faster than get_all()
        search_result = memory_client.search(query=memory_id, user_id=supa_uid, limit=20)
        
        memories_list = []
        if isinstance(search_result, dict) and 'results' in search_result:
            memories_list = search_result['results']
        elif isinstance(search_result, list):
            memories_list = search_result
        
        # Look for exact ID match
        for mem in memories_list:
            if isinstance(mem, dict) and mem.get('id') == memory_id:
                return json.dumps({
                    "id": mem.get('id'),
                    "content": mem.get('memory', mem.get('content', 'No content available')),
                    "metadata": mem.get('metadata', {}),
                    "created_at": mem.get('created_at'),
                    "updated_at": mem.get('updated_at'),
                    "score": mem.get('score'),
                    "source": "mem0_vector_store"
                }, indent=2)
        
        return f"Memory with ID '{memory_id}' not found. Possible reasons:\n1. Memory doesn't exist\n2. Belongs to different user\n3. Has been deleted\n4. ID format incorrect"
        
    finally:
        db.close()


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
    This is thorough but slower - use search_memory for simple queries.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
    try:
        # Add timeout to prevent hanging - 45 seconds max
        return await asyncio.wait_for(
            _deep_memory_query_impl(search_query, supa_uid, client_name, memory_limit, chunk_limit, include_full_docs),
            timeout=45.0
        )
    except asyncio.TimeoutError:
        return f"Deep memory search timed out for query '{search_query}'. Try using 'search_memory' for faster results, or simplify your query."
    except Exception as e:
        logger.error(f"Error in deep_memory_query: {e}", exc_info=True)
        return f"Error performing deep search: {str(e)}"


async def _deep_memory_query_impl(search_query: str, supa_uid: str, client_name: str, memory_limit: int = None, chunk_limit: int = None, include_full_docs: bool = True) -> str:
    """Optimized implementation of deep_memory_query"""
    # Lazy imports
    from app.utils.memory import get_memory_client
    from app.utils.gemini import GeminiService
    from app.services.chunking_service import ChunkingService
    import google.generativeai as genai
    
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


@mcp.tool(description="Fast memory search for simple questions - try this first before using heavier tools")
async def ask_memory(question: str) -> str:
    """
    Fast memory search for simple questions about the user.
    This searches stored memories only (not full documents) and returns quick, conversational answers.
    Perfect for everyday questions like "What are my preferences?" or "What do you know about me?"
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)

    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"

    try:
        # Lightweight version for better performance
        return await _lightweight_ask_memory_impl(question, supa_uid, client_name)
    except Exception as e:
        logger.error(f"Error in ask_memory: {e}", exc_info=True)
        return f"I had trouble processing your question: {str(e)}. Try rephrasing or use 'search_memory' for simpler queries."


async def _lightweight_ask_memory_impl(question: str, supa_uid: str, client_name: str) -> str:
    """Lightweight ask_memory implementation for quick answers"""
    from app.utils.memory import get_memory_client
    from mem0.llms.openai import OpenAILLM
    
    import time
    start_time = time.time()
    
    try:
        db = SessionLocal()
        try:
            # Get user quickly
            user = get_or_create_user(db, supa_uid, None)
            
            # SECURITY CHECK: Verify user ID matches
            if user.user_id != supa_uid:
                logger.error(f"🚨 USER ID MISMATCH: Expected {supa_uid}, got {user.user_id}")
                return f"Error: User ID validation failed. Security issue detected."

            # Initialize services
            memory_client = get_memory_client()
            llm = OpenAILLM(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o-mini")
            
            # 1. Quick memory search (limit to 10 for speed)
            search_result = memory_client.search(
                query=question,
                user_id=supa_uid,
                limit=10  # Much smaller for speed
            )
            
            # Process results
            memories = []
            if isinstance(search_result, dict) and 'results' in search_result:
                memories = search_result['results'][:10]
            elif isinstance(search_result, list):
                memories = search_result[:10]
            
            # Filter out contaminated memories and limit token usage
            clean_memories = []
            total_chars = 0
            max_chars = 8000  # Conservative limit to avoid token issues
            
            for idx, mem in enumerate(memories):
                memory_text = mem.get('memory', mem.get('content', ''))
                memory_line = f"Memory {idx+1}: {memory_text}"
                
                # Stop adding memories if we're approaching token limits
                if total_chars + len(memory_line) > max_chars:
                    break
                    
                clean_memories.append(memory_line)
                total_chars += len(memory_line)
            
            # Use LLM for fast, cheap synthesis with safer prompt
            prompt = f"""Based on the user's memories below, please answer their question.
            
            Memories:
            {chr(10).join(clean_memories)}
            
            Question: {question}
            
            Answer concisely based only on the provided memories."""
            
            try:
                response = llm.generate_response(prompt)
                # Access response.text safely
                result = response
                result += f"\\n\\n💡 Quick search: {round(time.time() - start_time, 2)}s | {len(clean_memories)} memories"
                
                return result
            except ValueError as e:
                # Handle cases where the response is blocked or has no content
                if "finish_reason" in str(e):
                    logger.error(f"LLM response for ask_memory was blocked or invalid. Query: '{question}'. Error: {e}")
                    return "The response to your question could not be generated, possibly due to safety filters or an invalid request. Please try rephrasing your question."
                else:
                    logger.error(f"Error processing LLM response in ask_memory: {e}", exc_info=True)
                    return f"An error occurred while generating the response: {e}"
            except Exception as e:
                logger.error(f"Error in lightweight ask_memory: {e}", exc_info=True)
                return f"An unexpected error occurred in ask_memory: {e}"
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in lightweight ask_memory: {e}", exc_info=True)
        return f"An unexpected error occurred in ask_memory: {e}"


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
    """
    Handles a single, stateless JSON-RPC message from the Cloudflare Worker.
    This endpoint runs the requested tool and returns the result immediately.
    """
    user_id_from_header = request.headers.get("x-user-id")
    client_name_from_header = request.headers.get("x-client-name")
    
    if not user_id_from_header or not client_name_from_header:
        return JSONResponse(status_code=400, content={"error": "Missing X-User-Id or X-Client-Name headers"})
            
    # Set context variables for the duration of this request
    user_token = user_id_var.set(user_id_from_header)
    client_token = client_name_var.set(client_name_from_header)
    
    try:
        body = await request.json()
        method_name = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")

        logger.info(f"Handling MCP method '{method_name}' for user '{user_id_from_header}' with params: {params}")

        # Handle MCP protocol methods
        if method_name == "initialize":
            # MCP initialization handshake
            response_payload = {
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "jean-memory-api",
                        "version": "1.0.0"
                    }
                },
                "id": request_id
            }
            return JSONResponse(content=response_payload)
        
        elif method_name == "tools/list":
            # Return list of core memory tools (excluding sync tools that are dashboard-only)
            tools = [
                {
                    "name": "ask_memory",
                    "description": "FAST memory search for simple questions about the user. Use this for quick, everyday questions like 'What are my preferences?', 'What do you know about me?', or 'Tell me about my work'. This tool searches stored memories only (not full documents) and gives conversational answers in under 5 seconds. Perfect for most questions - try this FIRST before using heavier tools.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "Any natural language question about the user's memories, thoughts, documents, or experiences"}
                        },
                        "required": ["question"]
                    }
                },
                {
                    "name": "add_memories",
                    "description": "Store important information, preferences, facts, and observations about the user. Use this tool to remember key details learned during conversation, user preferences, values, beliefs, facts about their work/life/interests, or anything the user wants remembered for future conversations. Think of this as building a comprehensive understanding of who they are. You should consider using this after learning something new about the user, even if not explicitly asked. The memory will be permanently stored and searchable. YOU MUST USE THE TOOLS/CALL TO USE THIS. NOTHING ELSE.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Important information to remember about the user (facts, preferences, insights, observations, etc.)"}
                        },
                        "required": ["text"]
                    }
                },
                {
                    "name": "search_memory", 
                    "description": "Quick keyword-based search through the user's memories. Use this for fast lookups when you need specific information or when ask_memory might be too comprehensive. Perfect for finding specific facts, dates, names, or simple queries. If you need just a quick fact-check or simple lookup, this is faster than ask_memory. Use when you need raw memory data rather than a conversational response.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Keywords or phrases to search for"},
                            "limit": {"type": "integer", "description": "Maximum number of results to return", "default": 10}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "list_memories",
                    "description": "Browse through the user's stored memories to get an overview of what you know about them. Use this when you want to understand the breadth of information available, or when the user asks 'what do you know about me?' or wants to see their stored memories. This gives you raw memory data without analysis - good for getting oriented or checking what's stored.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Maximum number of memories to show", "default": 20}
                        }
                    }
                },
                {
                    "name": "deep_memory_query", 
                    "description": "COMPREHENSIVE search that analyzes ALL user content including full documents and essays. Use this ONLY when ask_memory isn't sufficient and you need to analyze entire documents, find patterns across multiple sources, or do complex research. Takes 30-60 seconds and processes everything. Use sparingly for complex questions like 'Analyze my writing style across all essays' or 'Find patterns in my thinking over time'.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "search_query": {"type": "string", "description": "Complex question or analysis request"},
                            "memory_limit": {"type": "integer", "description": "Number of memories to include", "default": 10},
                            "chunk_limit": {"type": "integer", "description": "Number of document chunks to include", "default": 10},
                            "include_full_docs": {"type": "boolean", "description": "Whether to include complete documents", "default": True}
                        },
                        "required": ["search_query"]
                    }
                }
            ]
            
            response_payload = {
                "jsonrpc": "2.0",
                "result": {"tools": tools},
                "id": request_id
            }
            return JSONResponse(content=response_payload)
        
        elif method_name == "tools/call":
            # Handle tool execution
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            tool_function = tool_registry.get(tool_name)
            if not tool_function:
                return JSONResponse(status_code=404, content={"error": f"Tool '{tool_name}' not found"})
            
            # Execute the tool and await its result
            result = await tool_function(**tool_args)
            
            response_payload = {
                "jsonrpc": "2.0",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result
                        }
                    ]
                },
                "id": request_id
            }
            return JSONResponse(content=response_payload)
        
        elif method_name == "notifications/initialized":
            # Handle MCP initialization notification - no response needed
            logger.info(f"Received initialization notification from client '{client_name_from_header}'")
            return JSONResponse(content={"status": "acknowledged"})
        
        elif method_name == "notifications/cancelled":
            # Handle MCP cancellation notification - no response needed
            logger.info(f"Received cancellation notification for request {params.get('requestId', 'unknown')}")
            return JSONResponse(content={"status": "acknowledged"})
        
        elif method_name == "resources/list":
            # Return empty resources list - we don't have any resources
            response_payload = {
                "jsonrpc": "2.0",
                "result": {
                    "resources": []
                },
                "id": request_id
            }
            return JSONResponse(content=response_payload)
        
        elif method_name == "prompts/list":
            # Return empty prompts list - we don't have any prompts
            response_payload = {
                "jsonrpc": "2.0", 
                "result": {
                    "prompts": []
                },
                "id": request_id
            }
            return JSONResponse(content=response_payload)
        
        else:
            # Handle direct tool calls (legacy support)
            tool_function = tool_registry.get(method_name)
            if not tool_function:
                return JSONResponse(status_code=404, content={"error": f"Method '{method_name}' not found"})
            
            # Execute the tool and await its result  
            result = await tool_function(**params)

            # Format the response as a JSON-RPC result
            response_payload = {
                "jsonrpc": "2.0",
                "result": result,
                "id": request_id
            }
            return JSONResponse(content=response_payload)

    except Exception as e:
        logger.error(f"Error executing tool via stateless endpoint: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        # Clean up context variables
        user_id_var.reset(user_token)
        client_name_var.reset(client_token)

# Core memory tools registry - simplified for better performance
tool_registry = {
    "add_memories": add_memories,
    "search_memory": search_memory,
    "list_memories": list_memories,
    "ask_memory": ask_memory,
    "sync_substack_posts": sync_substack_posts,
    "deep_memory_query": deep_memory_query,
}

# Simple in-memory message queue for SSE connections
sse_message_queues = {}

# Add SSE endpoint for supergateway compatibility
@mcp_router.get("/{client_name}/sse/{user_id}")
async def handle_sse_connection(client_name: str, user_id: str, request: Request):
    """
    SSE endpoint for supergateway compatibility
    This allows npx supergateway to connect to the local development server
    """
    from fastapi.responses import StreamingResponse
    from fastapi import HTTPException
    import asyncio
    import json
    
    # Validate local development user
    if user_id != "local_dev_user" and user_id != "00000000-0000-0000-0000-000000000001":
        raise HTTPException(status_code=404, detail="User not found in local development mode")
    
    logger.info(f"SSE connection from {client_name} for user {user_id}")
    
    # Create a message queue for this connection
    connection_id = f"{client_name}_{user_id}"
    if connection_id not in sse_message_queues:
        sse_message_queues[connection_id] = asyncio.Queue()
    
    async def event_generator():
        try:
            # Send the endpoint event that supergateway expects
            yield f"event: endpoint\ndata: /mcp/{client_name}/messages/{user_id}\n\n"
            
            # Main event loop
            while True:
                try:
                    # Check for messages with timeout
                    message = await asyncio.wait_for(
                        sse_message_queues[connection_id].get(), 
                        timeout=10.0
                    )
                    # Send the message through SSE
                    yield f"data: {json.dumps(message)}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat when no messages
                    yield f"event: heartbeat\ndata: {{'timestamp': '{datetime.datetime.now(datetime.UTC).isoformat()}'}}\n\n"
                    
        except asyncio.CancelledError:
            logger.info(f"SSE connection closed for {client_name}/{user_id}")
            # Clean up the message queue
            if connection_id in sse_message_queues:
                del sse_message_queues[connection_id]
            return
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Cache-Control",
        },
    )

# Add messages endpoint for supergateway compatibility  
@mcp_router.post("/{client_name}/messages/{user_id}")
async def handle_sse_messages(client_name: str, user_id: str, request: Request):
    """
    Messages endpoint for supergateway compatibility
    This handles the actual MCP tool calls from supergateway
    """
    # Validate local development user
    if user_id != "local_dev_user" and user_id != "00000000-0000-0000-0000-000000000001":
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found in local development mode")
    
    # Set context variables for local development
    user_token = user_id_var.set("00000000-0000-0000-0000-000000000001")
    client_token = client_name_var.set(client_name)
    
    try:
        body = await request.json()
        method_name = body.get("method")
        params = body.get("params", {})
        request_id = body.get("id")

        logger.info(f"Handling MCP method '{method_name}' for local user with params: {params}")

        response_payload = None
        
        # Handle MCP protocol methods (same as the existing /messages/ handler)
        if method_name == "initialize":
            response_payload = {
                "jsonrpc": "2.0",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "jean-memory-local",
                        "version": "1.0.0"
                    }
                },
                "id": request_id
            }
        
        elif method_name == "tools/list":
            # Use the same comprehensive tool list as the main endpoint
            tools = [
                {
                    "name": "ask_memory",
                    "description": "FAST memory search for simple questions about the user. Use this for quick, everyday questions like 'What are my preferences?', 'What do you know about me?', or 'Tell me about my work'. This tool searches stored memories only (not full documents) and gives conversational answers in under 5 seconds. Perfect for most questions - try this FIRST before using heavier tools.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "question": {"type": "string", "description": "Any natural language question about the user's memories, thoughts, documents, or experiences"}
                        },
                        "required": ["question"]
                    }
                },
                {
                    "name": "add_memories",
                    "description": "Store important information, preferences, facts, and observations about the user. Use this tool to remember key details learned during conversation, user preferences, values, beliefs, facts about their work/life/interests, or anything the user wants remembered for future conversations. Think of this as building a comprehensive understanding of who they are. You should consider using this after learning something new about the user, even if not explicitly asked. The memory will be permanently stored and searchable. YOU MUST USE THE TOOLS/CALL TO USE THIS. NOTHING ELSE.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "text": {"type": "string", "description": "Important information to remember about the user (facts, preferences, insights, observations, etc.)"}
                        },
                        "required": ["text"]
                    }
                },
                {
                    "name": "search_memory", 
                    "description": "Quick keyword-based search through the user's memories. Use this for fast lookups when you need specific information or when ask_memory might be too comprehensive. Perfect for finding specific facts, dates, names, or simple queries. If you need just a quick fact-check or simple lookup, this is faster than ask_memory. Use when you need raw memory data rather than a conversational response.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Keywords or phrases to search for"},
                            "limit": {"type": "integer", "description": "Maximum number of results to return", "default": 10}
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "list_memories",
                    "description": "Browse through the user's stored memories to get an overview of what you know about them. Use this when you want to understand the breadth of information available, or when the user asks 'what do you know about me?' or wants to see their stored memories. This gives you raw memory data without analysis - good for getting oriented or checking what's stored.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Maximum number of memories to show", "default": 20}
                        }
                    }
                },
                {
                    "name": "deep_memory_query", 
                    "description": "COMPREHENSIVE search that analyzes ALL user content including full documents and essays. Use this ONLY when ask_memory isn't sufficient and you need to analyze entire documents, find patterns across multiple sources, or do complex research. Takes 30-60 seconds and processes everything. Use sparingly for complex questions like 'Analyze my writing style across all essays' or 'Find patterns in my thinking over time'.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "search_query": {"type": "string", "description": "Complex question or analysis request"},
                            "memory_limit": {"type": "integer", "description": "Number of memories to include", "default": 10},
                            "chunk_limit": {"type": "integer", "description": "Number of document chunks to include", "default": 10},
                            "include_full_docs": {"type": "boolean", "description": "Whether to include complete documents", "default": True}
                        },
                        "required": ["search_query"]
                    }
                }
            ]
            
            response_payload = {
                "jsonrpc": "2.0",
                "result": {"tools": tools},
                "id": request_id
            }
        
        elif method_name == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            tool_function = tool_registry.get(tool_name)
            if not tool_function:
                response_payload = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": f"Tool '{tool_name}' not found"
                    },
                    "id": request_id
                }
            else:
                # Execute the tool and await its result
                result = await tool_function(**tool_args)
                
                response_payload = {
                    "jsonrpc": "2.0",
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result
                            }
                        ]
                    },
                    "id": request_id
                }
        
        else:
            # Unknown method
            response_payload = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method_name}"
                },
                "id": request_id
            }
        
        # Send response through SSE queue instead of returning HTTP response
        connection_id = f"{client_name}_{user_id}"
        if connection_id in sse_message_queues:
            await sse_message_queues[connection_id].put(response_payload)
        
        # Return empty response to close HTTP request
        return JSONResponse(content={"status": "sent_via_sse"})
    
    except Exception as e:
        logger.error(f"Error in SSE messages handler: {e}")
        response_payload = {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            },
            "id": request_id if 'request_id' in locals() else None
        }
        
        # Send error through SSE queue
        connection_id = f"{client_name}_{user_id}"
        if connection_id in sse_message_queues:
            await sse_message_queues[connection_id].put(response_payload)
        
        return JSONResponse(content={"status": "error_sent_via_sse"})
    
    finally:
        # Clean up context variables
        try:
            user_id_var.reset(user_token)
            client_name_var.reset(client_token)
        except:
            pass

def setup_mcp_server(app: FastAPI):
    """Setup MCP server with the FastAPI application"""
    # The new stateless /messages endpoint is the primary way to interact.
    # The old SSE endpoints are no longer needed with the Cloudflare Worker architecture.
    app.include_router(mcp_router)
    logger.info("MCP server setup complete - stateless router included.")
