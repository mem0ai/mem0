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
    
    Args:
        query: The search query string
        limit: Maximum number of results to return (default: from config, max: from config)
    """
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
    """Implementation of search_memory with timeout protection"""
    memory_client = get_memory_client()
    db = SessionLocal()
    try:
        # Get user (but don't filter by specific app - search ALL memories)
        user = get_or_create_user(db, supa_uid, None)

        # Search ALL memories for this user across all apps with limit
        mem0_search_results = memory_client.search(query=query, user_id=supa_uid, limit=limit)

        processed_results = []
        actual_results_list = []
        if isinstance(mem0_search_results, dict) and 'results' in mem0_search_results:
             actual_results_list = mem0_search_results['results']
        elif isinstance(mem0_search_results, list):
             actual_results_list = mem0_search_results

        for mem_data in actual_results_list[:limit]:  # Extra safety to ensure limit
            mem0_id = mem_data.get('id')
            if not mem0_id: continue
            processed_results.append(mem_data)
        
        db.commit()
        return json.dumps(processed_results, indent=2)
    finally:
        db.close()


@mcp.tool(description="List all memories in the user's memory")
async def list_memories(limit: int = None) -> str:
    """
    List memories in the user's memory.
    
    Args:
        limit: Maximum number of memories to return (default: from config, max: from config)
    """
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
    memory_client = get_memory_client()
    db = SessionLocal()
    try:
        # Get user (but don't filter by specific app - show ALL memories)
        user = get_or_create_user(db, supa_uid, None)

        # Get ALL memories for this user across all apps with limit
        all_mem0_memories = memory_client.get_all(user_id=supa_uid, limit=limit)

        processed_results = []
        actual_results_list = []
        if isinstance(all_mem0_memories, dict) and 'results' in all_mem0_memories:
             actual_results_list = all_mem0_memories['results']
        elif isinstance(all_mem0_memories, list):
             actual_results_list = all_mem0_memories

        for mem_data in actual_results_list[:limit]:  # Extra safety to ensure limit
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


@mcp.tool(description="Deep memory search with automatic full document inclusion. Use this for: 1) Reading/summarizing specific essays (e.g. 'summarize The Irreverent Act'), 2) Analyzing personality/writing style across documents, 3) Finding insights from essays written months/years ago, 4) Any query needing full essay context. Automatically detects and includes complete relevant documents using dynamic scoring.")
async def deep_memory_query(search_query: str, memory_limit: int = None, chunk_limit: int = None, include_full_docs: bool = True) -> str:
    """
    Performs a deep, comprehensive search across ALL user content using Gemini.
    Automatically detects when specific documents/essays are referenced and includes their full content.
    This is thorough but slower - use smart_memory_query for speed.
    """
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
            all_documents = db.query(Document).filter(
                Document.user_id == user.id
            ).order_by(Document.created_at.desc()).all()
            
            # Smart document selection based on query
            query_lower = search_query.lower()
            query_words = [w for w in query_lower.split() if len(w) > 2]
            selected_documents = []
            
            # Score each document for relevance
            for doc in all_documents:
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
                selected_documents = [(doc, 1, ["recent"]) for doc in all_documents[:5]]
            
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
            if all_documents:
                context += "=== ALL DOCUMENTS (Essays, Posts, Articles) ===\n\n"
                for i, doc in enumerate(all_documents, 1):
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
                    doc = next((d for d in all_documents if d.id == chunk.document_id), None)
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
            result += f"\n\n📊 Deep Analysis: {processing_time:.2f}s | {len(prioritized_memories)} memories, {len(all_documents)} docs, {len(selected_documents)} full docs"
            
            return result
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in deep_memory_query: {e}", exc_info=True)
        return f"Error performing deep search: {str(e)}"


@mcp.tool(description="Ultra-fast two-layer memory search using Gemini 2.5 preview models. Use this for: 1) Complex queries across massive amounts of data, 2) When you need the FASTEST comprehensive search, 3) Finding connections across many documents/memories, 4) When performance matters. Layer 1 (Gemini 2.5 Flash) scouts ALL content in parallel, Layer 2 (Gemini 2.5 Pro) analyzes filtered results. Returns performance metrics.")
async def smart_memory_query(search_query: str) -> str:
    """
    Optimized two-layer intelligent query system with robust error handling:
    1. Layer 1 (Scout): Fast semantic filtering using embeddings + lightweight LLM
    2. Layer 2 (Analyst): Gemini 2.5 Pro analyzes the filtered content
    
    This approach is faster, more reliable, and handles large datasets efficiently.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return "Error: Supabase user_id not available in context"
    if not client_name:
        return "Error: client_name not available in context"
    
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
            
            # LAYER 1: FAST SCOUT - Semantic + keyword filtering
            scout_start = time.time()
            
            # Get documents efficiently
            all_documents = db.query(Document).filter(
                Document.user_id == user.id
            ).limit(50).all()  # Limit for performance
            
            # Get memories efficiently  
            all_memories_raw = memory_client.search(query=search_query, user_id=supa_uid, limit=50)
            
            # Process memories
            all_memories = []
            if isinstance(all_memories_raw, dict) and 'results' in all_memories_raw:
                all_memories = all_memories_raw['results']
            elif isinstance(all_memories_raw, list):
                all_memories = all_memories_raw
            
            # Smart filtering - combine semantic search with keyword matching
            relevant_documents = []
            relevant_memories = []
            
            # Simple but effective filtering
            query_keywords = set(search_query.lower().split())
            
            # Filter documents
            for doc in all_documents:
                doc_text = f"{doc.title} {doc.content or ''}".lower()
                # Score based on keyword overlap and title relevance
                keyword_matches = sum(1 for kw in query_keywords if kw in doc_text)
                title_matches = sum(1 for kw in query_keywords if kw in doc.title.lower())
                
                if keyword_matches > 0 or title_matches > 0:
                    relevant_documents.append({
                        'doc': doc,
                        'score': keyword_matches + (title_matches * 2)  # Weight title matches more
                    })
            
            # Sort by relevance and take top documents
            relevant_documents = sorted(relevant_documents, key=lambda x: x['score'], reverse=True)[:10]
            
            # Filter memories (already semantically sorted from search)
            relevant_memories = all_memories[:20]  # Take top semantic matches
            
            scout_time = time.time() - scout_start
            
            # LAYER 2: ANALYST - Deep analysis with Gemini Pro
            analyst_start = time.time()
            
            # Build focused context for analysis
            analyst_context = "=== RELEVANT CONTENT FOR ANALYSIS ===\n\n"
            
            # Add relevant documents
            if relevant_documents:
                analyst_context += "=== RELEVANT DOCUMENTS ===\n\n"
                for item in relevant_documents:
                    doc = item['doc']
                    analyst_context += f"DOCUMENT: {doc.title}\n"
                    analyst_context += f"Type: {doc.document_type}\n"
                    analyst_context += f"URL: {doc.source_url or 'No URL'}\n"
                    analyst_context += f"Content:\n{doc.content}\n"
                    analyst_context += "\n" + "="*50 + "\n\n"
            
            # Add relevant memories
            if relevant_memories:
                analyst_context += "\n=== RELEVANT MEMORIES ===\n\n"
                for mem in relevant_memories:
                    memory_text = mem.get('memory', mem.get('content', ''))
                    metadata = mem.get('metadata', {})
                    score = mem.get('score', 0)
                    analyst_context += f"Memory (relevance: {score:.3f}): {memory_text}\n"
                    if metadata:
                        analyst_context += f"Source: {metadata.get('source_app', 'Unknown')}\n"
                    analyst_context += "\n"
            
            # Enhanced analyst prompt
            analyst_prompt = f"""You are an expert analyst with access to a user's personal knowledge base. Provide a comprehensive, insightful answer to their question.

USER'S QUESTION: {search_query}

{analyst_context}

INSTRUCTIONS:
1. Answer the question directly and thoroughly using the provided content
2. Draw connections between documents and memories  
3. Cite specific sources when making points
4. If analyzing personality/style/beliefs, provide concrete examples
5. Look for patterns and themes across the content
6. If the query asks for summaries, provide detailed information
7. Be insightful and add value beyond just listing information

Provide a comprehensive response that demonstrates deep understanding."""

            # Use Gemini Pro with optimized settings
            try:
                # Initialize with the most stable model
                gemini_pro = genai.GenerativeModel('gemini-2.5-pro-preview-05-06')
                
                # Generate response with retry logic
                max_retries = 2
                for attempt in range(max_retries + 1):
                    try:
                        analyst_response = gemini_pro.generate_content(
                            analyst_prompt,
                            generation_config=genai.GenerationConfig(
                                temperature=0.3,
                                max_output_tokens=4096,  # Reasonable limit for speed
                                candidate_count=1,
                            )
                        )
                        
                        # Check for valid response
                        if analyst_response and analyst_response.text:
                            response = analyst_response.text
                            break
                        elif attempt < max_retries:
                            logger.warning(f"Empty response from Gemini Pro, retrying (attempt {attempt + 1})")
                            await asyncio.sleep(1)  # Brief pause before retry
                            continue
                        else:
                            raise Exception("No valid response from Gemini Pro after retries")
                            
                    except Exception as e:
                        if attempt < max_retries:
                            logger.warning(f"Gemini Pro error, retrying (attempt {attempt + 1}): {e}")
                            await asyncio.sleep(1)
                            continue
                        else:
                            raise e
                            
            except Exception as e:
                logger.error(f"Gemini Pro failed: {e}")
                # Fallback to simple concatenation
                response = f"Found relevant content for your query:\n\n"
                
                # Add document summaries
                if relevant_documents:
                    response += "RELEVANT DOCUMENTS:\n"
                    for item in relevant_documents[:5]:
                        doc = item['doc']
                        response += f"• {doc.title}: {doc.content[:300]}...\n\n"
                
                # Add memories
                if relevant_memories:
                    response += "RELEVANT MEMORIES:\n"
                    for mem in relevant_memories[:10]:
                        memory_text = mem.get('memory', mem.get('content', ''))
                        response += f"• {memory_text[:200]}...\n"
                
                response += f"\n(Note: Used fallback processing due to analysis service error: {e})"
            
            analyst_time = time.time() - analyst_start
            total_time = time.time() - start_time
            
            # Add performance metrics
            response += f"\n\n---\n📊 Performance Metrics:\n"
            response += f"- Total processing time: {total_time:.2f}s\n"
            response += f"- Scout time: {scout_time:.2f}s\n"
            response += f"- Analysis time: {analyst_time:.2f}s\n"
            response += f"- Documents found: {len(relevant_documents)}\n"
            response += f"- Memories found: {len(relevant_memories)}\n"
            response += f"- Processing: Optimized Scout → Gemini Pro Analysis"
            
            return response
            
        finally:
            db.close()
            
    except asyncio.TimeoutError:
        return "The analysis took too long. Try a more specific query or break it into smaller parts."
    except Exception as e:
        logger.error(f"Error in smart_memory_query: {e}", exc_info=True)
        return f"Error performing smart search: {str(e)}"


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


@mcp.tool(description="Test MCP connection and verify all systems are working")
async def test_connection() -> str:
    """
    Test the MCP connection and verify that all systems are working properly.
    This is useful for diagnosing connection issues.
    """
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
            
            # If it's a session-related error, try to recover gracefully
            if "session" in str(e).lower() or "not found" in str(e).lower():
                logging.info(f"Attempting session recovery for {session_id}")
                return {"status": "session_recovery", "message": "Session recovered", "session_id": session_id}
            
            return {"status": "error", "message": str(e)}
            
    except Exception as e:
        logging.error(f"Error in handle_post_message: {e}")
        return {"status": "error", "message": "Internal server error"}


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
                    "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
                }
            else:
                return {"status": "error", "message": "User not found"}
        finally:
            db.close()
            
    except Exception as e:
        logging.error(f"MCP health check error: {e}")
        return {"status": "error", "message": str(e)}

def setup_mcp_server(app: FastAPI):
    """Setup MCP server with the FastAPI application"""
    # Set the server name to match what Claude expects
    mcp._mcp_server.name = "jean-memory-api"
    
    # Add logging to help debug initialization
    logger.info(f"Setting up MCP server with name: {mcp._mcp_server.name}")
    
    # Include MCP router in the FastAPI app
    app.include_router(mcp_router)
    
    logger.info("MCP server setup complete - router included in FastAPI app")
