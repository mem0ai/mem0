"""
Memory CRUD operations module.
Contains add, delete, list, and detail operations for memories.
"""

import logging
import asyncio
import datetime
from typing import Optional, List
from sqlalchemy import text

from app.context import user_id_var, client_name_var
from app.database import SessionLocal
from app.models import Memory, MemoryState, MemoryStatusHistory, User
from app.utils.db import get_user_and_app, get_or_create_user
from app.middleware.subscription_middleware import SubscriptionChecker
from app.config.memory_limits import MEMORY_LIMITS
from app.utils.decorators import retry_on_exception
from .utils import (
    safe_json_dumps, track_tool_usage, format_memory_response, 
    format_error_response, validate_memory_limits, truncate_text, sanitize_tags
)

logger = logging.getLogger(__name__)


@retry_on_exception(retries=3, delay=1, backoff=2, exceptions=(ConnectionError,))
async def add_memories(text: str, tags: Optional[List[str]] = None, priority: bool = False) -> str:
    """
    Add new memories to the user's memory collection.
    
    Args:
        text: The content to remember
        tags: Optional list of tags to categorize the memory
        priority: Whether this is a high-priority memory
    
    Returns:
        JSON string confirming successful addition or error details
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid:
        return format_error_response("Supabase user_id not available in context", "add_memories")
    if not client_name:
        return format_error_response("client_name not available in context", "add_memories")
    
    # Validate and sanitize input
    text = text.strip()
    if not text:
        return format_error_response("Memory content cannot be empty", "add_memories")
    
    text = truncate_text(text, 5000)  # Limit memory content length
    tags = sanitize_tags(tags or [])
    
    try:
        # Track usage
        track_tool_usage('add_memories', {
            'text_length': len(text),
            'has_tags': bool(tags),
            'priority': priority
        })
        
        # Add timeout for operation
        return await asyncio.wait_for(
            _add_memories_background_claude(text, tags, supa_uid, client_name, priority),
            timeout=60.0
        )
    except asyncio.TimeoutError:
        return format_error_response("Memory addition timed out", "add_memories")
    except Exception as e:
        logger.error(f"Error in add_memories: {e}", exc_info=True)
        return format_error_response(f"Failed to add memory: {e}", "add_memories")


async def _add_memories_background_claude(text: str, tags: Optional[List[str]], 
                                        supa_uid: str, client_name: str, priority: bool = False):
    """Background implementation for adding memories"""
    from app.utils.memory import get_async_memory_client_v2_optimized
    
    db = SessionLocal()
    try:
        # Get or create user
        user = get_or_create_user(db, supa_uid, f"{supa_uid}@placeholder.com")
        if not user:
            return format_error_response("Failed to get or create user", "add_memories")
        
        # Check subscription limits
        subscription_checker = SubscriptionChecker()
        current_memory_count = db.query(Memory).filter(
            Memory.user_id == user.id,
            Memory.state == MemoryState.active
        ).count()
        
        # Validate memory limits
        can_add, limit_message = validate_memory_limits(
            supa_uid, current_memory_count, MEMORY_LIMITS.__dict__
        )
        if not can_add:
            return format_error_response(limit_message, "add_memories")
        
        # Get app context
        user, app = get_user_and_app(db, supa_uid, client_name)
        
        # Add to memory client
        memory_client = await get_async_memory_client_v2_optimized()
        
        # Prepare metadata
        metadata = {
            'app_name': client_name,
            'user_id': supa_uid,
            'priority': priority,
            'added_at': datetime.datetime.now().isoformat()
        }
        
        if tags:
            metadata['tags'] = tags
        
        # Add to memory system
        result = await memory_client.add(
            text,
            user_id=supa_uid,
            metadata=metadata
        )
        
        # Also save to local database for backup/querying
        memory_record = Memory(
            content=text,
            user_id=user.id,
            app_id=app.id,
            state=MemoryState.active,
            metadata_={'tags': tags, 'priority': priority}
        )
        db.add(memory_record)
        db.commit()
        
        return safe_json_dumps({
            "status": "success",
            "message": "Memory added successfully",
            "memory_id": result.get('id') if result else str(memory_record.id),
            "content_preview": text[:100] + "..." if len(text) > 100 else text,
            "tags": tags,
            "priority": priority
        })
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error adding memory: {e}", exc_info=True)
        return format_error_response(f"Failed to add memory: {str(e)}", "add_memories")
    finally:
        db.close()


async def add_observation(text: str) -> str:
    """
    Add an observation (lightweight memory without heavy processing).
    """
    return await add_memories(text, tags=["observation"], priority=False)


async def list_memories(limit: int = None) -> str:
    """
    List the user's recent memories.
    
    Args:
        limit: Maximum number of memories to return (default: 20, max: 100)
    
    Returns:
        JSON string containing list of memories
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid or not client_name:
        return format_error_response("Missing user context", "list_memories")
    
    if limit is None:
        limit = MEMORY_LIMITS.list_default
    limit = min(max(1, limit), MEMORY_LIMITS.list_max)
    
    try:
        track_tool_usage('list_memories', {'limit': limit})
        
        return await asyncio.wait_for(
            _list_memories_impl(supa_uid, client_name, limit),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        return format_error_response("Memory listing timed out", "list_memories")
    except Exception as e:
        logger.error(f"Error in list_memories: {e}", exc_info=True)
        return format_error_response(f"Failed to list memories: {e}", "list_memories")


async def _list_memories_impl(supa_uid: str, client_name: str, limit: int = 20) -> str:
    """Implementation for listing memories"""
    db = SessionLocal()
    
    try:
        user, app = get_user_and_app(db, supa_uid, client_name)
        
        # Query recent memories
        sql_query = text("""
            SELECT m.id, m.content, m.created_at, m.metadata_,
                   array_agg(DISTINCT c.name) FILTER (WHERE c.name IS NOT NULL) as categories
            FROM memories m
            LEFT JOIN memory_categories mc ON m.id = mc.memory_id
            LEFT JOIN categories c ON mc.category_id = c.id
            WHERE m.user_id = :user_id 
            AND m.state = 'active'
            GROUP BY m.id, m.content, m.created_at, m.metadata_
            ORDER BY m.created_at DESC
            LIMIT :limit
        """)
        
        result = db.execute(sql_query, {'user_id': user.id, 'limit': limit})
        memories = result.fetchall()
        
        # Format response
        formatted_memories = []
        for memory in memories:
            formatted_memories.append({
                'id': str(memory.id),
                'content': memory.content,
                'created_at': memory.created_at.isoformat(),
                'categories': memory.categories or [],
                'metadata': memory.metadata_ or {}
            })
        
        return format_memory_response(formatted_memories, len(formatted_memories))
        
    except Exception as e:
        logger.error(f"Error listing memories: {e}", exc_info=True)
        return format_error_response(f"Failed to list memories: {str(e)}", "list_memories")
    finally:
        db.close()


async def delete_all_memories() -> str:
    """
    Delete all memories for the current user (mark as deleted, don't actually remove).
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid or not client_name:
        return format_error_response("Missing user context", "delete_all_memories")
    
    db = SessionLocal()
    
    try:
        track_tool_usage('delete_all_memories', {})
        
        user, app = get_user_and_app(db, supa_uid, client_name)
        
        # Mark all memories as deleted
        updated_count = db.query(Memory).filter(
            Memory.user_id == user.id,
            Memory.state == MemoryState.active
        ).update({
            Memory.state: MemoryState.deleted,
            Memory.deleted_at: datetime.datetime.now()
        })
        
        db.commit()
        
        return safe_json_dumps({
            "status": "success",
            "message": f"Successfully deleted {updated_count} memories",
            "deleted_count": updated_count
        })
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting all memories: {e}", exc_info=True)
        return format_error_response(f"Failed to delete memories: {str(e)}", "delete_all_memories")
    finally:
        db.close()


async def get_memory_details(memory_id: str) -> str:
    """
    Get detailed information about a specific memory.
    
    Args:
        memory_id: The ID of the memory to retrieve
    
    Returns:
        JSON string containing memory details
    """
    supa_uid = user_id_var.get(None)
    client_name = client_name_var.get(None)
    
    if not supa_uid or not client_name:
        return format_error_response("Missing user context", "get_memory_details")
    
    try:
        track_tool_usage('get_memory_details', {'memory_id': memory_id})
        
        return await asyncio.wait_for(
            _get_memory_details_impl(memory_id, supa_uid, client_name),
            timeout=15.0
        )
    except asyncio.TimeoutError:
        return format_error_response("Memory detail retrieval timed out", "get_memory_details")
    except Exception as e:
        logger.error(f"Error in get_memory_details: {e}", exc_info=True)
        return format_error_response(f"Failed to get memory details: {e}", "get_memory_details")


async def _get_memory_details_impl(memory_id: str, supa_uid: str, client_name: str) -> str:
    """Implementation for getting memory details"""
    db = SessionLocal()
    
    try:
        user, app = get_user_and_app(db, supa_uid, client_name)
        
        # Query specific memory with full details
        sql_query = text("""
            SELECT m.id, m.content, m.created_at, m.updated_at, m.metadata_, m.state,
                   array_agg(DISTINCT c.name) FILTER (WHERE c.name IS NOT NULL) as categories,
                   COUNT(DISTINCT msh.id) as status_changes
            FROM memories m
            LEFT JOIN memory_categories mc ON m.id = mc.memory_id
            LEFT JOIN categories c ON mc.category_id = c.id
            LEFT JOIN memory_status_history msh ON m.id = msh.memory_id
            WHERE m.id = :memory_id 
            AND m.user_id = :user_id
            GROUP BY m.id, m.content, m.created_at, m.updated_at, m.metadata_, m.state
        """)
        
        result = db.execute(sql_query, {'memory_id': memory_id, 'user_id': user.id})
        memory = result.fetchone()
        
        if not memory:
            return format_error_response("Memory not found", "get_memory_details")
        
        memory_details = {
            'id': str(memory.id),
            'content': memory.content,
            'created_at': memory.created_at.isoformat(),
            'updated_at': memory.updated_at.isoformat() if memory.updated_at else None,
            'state': memory.state.value if memory.state else 'unknown',
            'categories': memory.categories or [],
            'metadata': memory.metadata_ or {},
            'status_changes': memory.status_changes or 0
        }
        
        return safe_json_dumps({
            "status": "success",
            "memory": memory_details
        })
        
    except Exception as e:
        logger.error(f"Error getting memory details: {e}", exc_info=True)
        return format_error_response(f"Failed to get memory details: {str(e)}", "get_memory_details")
    finally:
        db.close()