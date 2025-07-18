"""
Memory search operations module.
Contains all memory search and query functionality.
"""

import logging
import asyncio
from typing import Optional, List
from sqlalchemy import text

from app.context import user_id_var, client_name_var
from app.database import SessionLocal
from app.models import Memory, MemoryState, User
from app.utils.db import get_user_and_app
from app.config.memory_limits import MEMORY_LIMITS
from app.utils.decorators import retry_on_exception
from .utils import safe_json_dumps, track_tool_usage, format_memory_response, format_error_response

logger = logging.getLogger(__name__)


@retry_on_exception(retries=3, delay=1, backoff=2, exceptions=(ConnectionError,))
async def search_memory(query: str, limit: int = None, tags_filter: Optional[List[str]] = None) -> str:
    """
    Search the user's memory for memories that match the query.
    Returns memories that are semantically similar to the query.
    
    Args:
        query: The search term or phrase to look for
        limit: Maximum number of results to return (default: 10, max: 50) 
        tags_filter: Optional list of tags to filter results (e.g., ["work", "project-alpha"])
                    Only memories containing ALL specified tags will be returned.
    
    Returns:
        JSON string containing list of matching memories with their content and metadata
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return format_error_response("Supabase user_id not available in context", "search_memory")
    if not client_name:
        return format_error_response("client_name not available in context", "search_memory")
    
    # Use configured limits
    if limit is None:
        limit = MEMORY_LIMITS.search_default
    limit = min(max(1, limit), MEMORY_LIMITS.search_max)
    
    try:
        # Track search usage (only if private analytics available)
        track_tool_usage('search_memory', {
            'query_length': len(query),
            'limit': limit,
            'has_tags_filter': bool(tags_filter)
        })
        
        # Add timeout to prevent hanging
        return await asyncio.wait_for(
            _search_memory_unified_impl(query, supa_uid, client_name, limit, tags_filter), 
            timeout=30.0
        )
    except asyncio.TimeoutError:
        return format_error_response("Search timed out. Please try a simpler query.", "search_memory")
    except Exception as e:
        logger.error(f"Error in search_memory MCP tool: {e}", exc_info=True)
        return format_error_response(f"Error searching memory: {e}", "search_memory")


async def _search_memory_unified_impl(query: str, supa_uid: str, client_name: str, 
                                    limit: int = 10, tags_filter: Optional[List[str]] = None) -> str:
    """Unified implementation that supports both basic search and tag filtering"""
    from app.utils.memory import get_async_memory_client
    
    memory_client = await get_async_memory_client()
    db = SessionLocal()
    
    try:
        user, app = get_user_and_app(db, supa_uid, client_name)
        
        # Search using the memory client
        search_results = await memory_client.search(query, user_id=supa_uid, limit=limit)
        
        if not search_results:
            return format_memory_response([], 0, query)
        
        # Extract memory IDs from search results
        memory_ids = [result.get('id') for result in search_results if result.get('id')]
        
        if not memory_ids:
            return format_memory_response([], 0, query)
        
        # Build SQL query to get memories with metadata
        placeholders = ','.join([f':id_{i}' for i in range(len(memory_ids))])
        params = {f'id_{i}': memory_id for i, memory_id in enumerate(memory_ids)}
        params['user_id'] = user.id
        
        sql_query = text(f"""
            SELECT m.id, m.content, m.created_at, m.metadata_, 
                   array_agg(DISTINCT c.name) FILTER (WHERE c.name IS NOT NULL) as categories
            FROM memories m
            LEFT JOIN memory_categories mc ON m.id = mc.memory_id
            LEFT JOIN categories c ON mc.category_id = c.id
            WHERE m.id IN ({placeholders}) 
            AND m.user_id = :user_id 
            AND m.state = 'active'
            GROUP BY m.id, m.content, m.created_at, m.metadata_
            ORDER BY m.created_at DESC
        """)
        
        result = db.execute(sql_query, params)
        db_memories = result.fetchall()
        
        # Apply tag filtering if specified
        if tags_filter:
            filtered_memories = []
            for memory in db_memories:
                memory_tags = memory.categories or []
                if all(tag.lower() in [t.lower() for t in memory_tags] for tag in tags_filter):
                    filtered_memories.append(memory)
            db_memories = filtered_memories
        
        # Format response
        formatted_memories = []
        for memory in db_memories:
            formatted_memories.append({
                'id': str(memory.id),
                'content': memory.content,
                'created_at': memory.created_at.isoformat(),
                'categories': memory.categories or [],
                'metadata': memory.metadata_ or {}
            })
        
        return format_memory_response(formatted_memories, len(formatted_memories), query)
        
    except Exception as e:
        logger.error(f"Error in search implementation: {e}", exc_info=True)
        return format_error_response(f"Search failed: {str(e)}", "search_memory")
    finally:
        db.close()


async def search_memory_v2(query: str, limit: int = None, tags_filter: Optional[List[str]] = None) -> str:
    """
    Enhanced memory search with improved ranking and filtering.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid or not client_name:
        return format_error_response("Missing user context", "search_memory_v2")
    
    if limit is None:
        limit = MEMORY_LIMITS.search_default
    limit = min(max(1, limit), MEMORY_LIMITS.search_max)
    
    try:
        track_tool_usage('search_memory_v2', {
            'query_length': len(query),
            'limit': limit,
            'has_tags_filter': bool(tags_filter)
        })
        
        return await asyncio.wait_for(
            _search_memory_v2_impl(query, supa_uid, client_name, limit, tags_filter),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        return format_error_response("Search timed out", "search_memory_v2")
    except Exception as e:
        logger.error(f"Error in search_memory_v2: {e}", exc_info=True)
        return format_error_response(f"Enhanced search failed: {e}", "search_memory_v2")


async def _search_memory_v2_impl(query: str, supa_uid: str, client_name: str,
                               limit: int = 10, tags_filter: Optional[List[str]] = None) -> str:
    """Enhanced search implementation with better ranking"""
    from app.utils.memory import get_async_memory_client_v2_optimized
    
    try:
        # Use the optimized V2 client
        memory_client = await get_async_memory_client_v2_optimized()
        
        # Perform enhanced search
        search_results = await memory_client.search(
            query=query,
            user_id=supa_uid,
            limit=limit,
            filters={"tags": tags_filter} if tags_filter else None
        )
        
        if not search_results:
            return format_memory_response([], 0, query)
        
        # Format and return results
        formatted_results = []
        for result in search_results:
            formatted_results.append({
                'id': result.get('id'),
                'content': result.get('memory', result.get('content', '')),
                'score': result.get('score', 0.0),
                'categories': result.get('categories', []),
                'created_at': result.get('created_at', ''),
                'metadata': result.get('metadata', {})
            })
        
        return format_memory_response(formatted_results, len(formatted_results), query)
        
    except Exception as e:
        logger.error(f"Error in enhanced search: {e}", exc_info=True)
        return format_error_response(f"Enhanced search failed: {str(e)}", "search_memory_v2")


async def ask_memory(question: str) -> str:
    """
    Ask a question about the user's memories and get an AI-generated response.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid or not client_name:
        return format_error_response("Missing user context", "ask_memory")
    
    try:
        track_tool_usage('ask_memory', {'question_length': len(question)})
        
        return await asyncio.wait_for(
            _lightweight_ask_memory_impl(question, supa_uid, client_name),
            timeout=45.0
        )
    except asyncio.TimeoutError:
        return format_error_response("Question processing timed out", "ask_memory")
    except Exception as e:
        logger.error(f"Error in ask_memory: {e}", exc_info=True)
        return format_error_response(f"Failed to process question: {e}", "ask_memory")


async def _lightweight_ask_memory_impl(question: str, supa_uid: str, client_name: str) -> str:
    """Lightweight implementation for asking questions about memories"""
    from app.utils.memory import get_async_memory_client_v2_optimized
    
    try:
        memory_client = await get_async_memory_client_v2_optimized()
        
        # Use the client's ask/chat functionality
        response = await memory_client.chat(
            message=question,
            user_id=supa_uid,
            history=[]  # Could be extended to include conversation history
        )
        
        return safe_json_dumps({
            "status": "success",
            "question": question,
            "answer": response,
            "timestamp": "now"  # Could use actual timestamp
        })
        
    except Exception as e:
        logger.error(f"Error in ask memory implementation: {e}", exc_info=True)
        return format_error_response(f"Failed to generate answer: {str(e)}", "ask_memory")


async def smart_memory_query(search_query: str) -> str:
    """
    Intelligent memory query that combines search and Q&A capabilities.
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid or not client_name:
        return format_error_response("Missing user context", "smart_memory_query")
    
    try:
        track_tool_usage('smart_memory_query', {'query_length': len(search_query)})
        
        # First try semantic search
        search_results = await _search_memory_unified_impl(
            search_query, supa_uid, client_name, limit=5
        )
        
        # If search results are good, return them
        # Otherwise, try ask_memory for more conversational response
        try:
            search_data = safe_json_dumps(search_results)
            if '"memories": []' not in search_data:
                return search_results
        except:
            pass
        
        # Fallback to conversational Q&A
        return await _lightweight_ask_memory_impl(search_query, supa_uid, client_name)
        
    except Exception as e:
        logger.error(f"Error in smart_memory_query: {e}", exc_info=True)
        return format_error_response(f"Smart query failed: {e}", "smart_memory_query")