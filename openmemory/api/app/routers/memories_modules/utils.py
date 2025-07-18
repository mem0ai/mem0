"""
Memory utility functions extracted from memories.py
Contains helper functions for memory operations, state management, and access control.
"""

import datetime
import logging
from typing import List, Set, Optional
from uuid import UUID

# Python 3.10 compatibility for datetime.UTC
try:
    from datetime import UTC
except ImportError:
    from datetime import timezone
    UTC = timezone.utc

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import (
    Memory, MemoryState, MemoryAccessLog, App,
    MemoryStatusHistory, User, Category, AccessControl
)
from app.schemas import MemoryResponse

logger = logging.getLogger(__name__)


def get_memory_or_404(db: Session, memory_id: UUID, user_id: UUID) -> Memory:
    """Get memory by ID with permission check, raise 404 if not found."""
    memory = db.query(Memory).filter(Memory.id == memory_id, Memory.user_id == user_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found or you do not have permission")
    return memory


def update_memory_state(db: Session, memory_id: UUID, new_state: MemoryState, changed_by_user_id: UUID):
    """Update memory state with history tracking."""
    memory = get_memory_or_404(db, memory_id, changed_by_user_id)
    
    old_state = memory.state
    memory.state = new_state
    if new_state == MemoryState.archived:
        memory.archived_at = datetime.datetime.now(UTC)
    elif new_state == MemoryState.deleted:
        memory.deleted_at = datetime.datetime.now(UTC)

    history = MemoryStatusHistory(
        memory_id=memory_id,
        changed_by=changed_by_user_id,
        old_state=old_state,
        new_state=new_state
    )
    db.add(history)


def get_accessible_memory_ids(db: Session, app_id: UUID) -> Optional[Set[UUID]]:
    """
    Get the set of memory IDs that the app has access to based on app-level ACL rules.
    Returns None if all memories are accessible, empty set if none are accessible.
    """
    # Get app-level access controls
    app_access = db.query(AccessControl).filter(
        AccessControl.subject_type == "app",
        AccessControl.subject_id == app_id,
        AccessControl.object_type == "memory"
    ).all()

    # If no app-level rules exist, return None to indicate all memories are accessible
    if not app_access:
        return None

    # Initialize sets for allowed and denied memory IDs
    allowed_memory_ids = set()
    denied_memory_ids = set()

    # Process app-level rules
    for rule in app_access:
        if rule.effect == "allow":
            if rule.object_id:  # Specific memory access
                allowed_memory_ids.add(rule.object_id)
            else:  # All memories access
                return None  # All memories allowed
        elif rule.effect == "deny":
            if rule.object_id:  # Specific memory denied
                denied_memory_ids.add(rule.object_id)
            else:  # All memories denied
                return set()  # No memories accessible

    # Remove denied memories from allowed set
    if allowed_memory_ids:
        allowed_memory_ids -= denied_memory_ids

    return allowed_memory_ids


def group_memories_into_threads(memories: List[MemoryResponse]) -> List[MemoryResponse]:
    """
    Group related memories into threads using mem0_id linking.
    
    SQL memories with mem0_id will be grouped with their corresponding 
    Jean Memory V2 enhanced memories. Returns primary memories with
    related memories appended as a special 'thread_memories' field.
    """
    try:
        if not memories:
            return memories
        
        # Separate SQL and Jean Memory V2 memories
        sql_memories = []
        jean_memories = []
        
        for memory in memories:
            # Check if it's a Jean Memory V2 memory (has the dummy app_id or specific app_name pattern)
            if (hasattr(memory, 'app_name') and 
                ('Jean Memory V2' in memory.app_name or 'jean memory' in memory.app_name.lower())):
                jean_memories.append(memory)
            else:
                sql_memories.append(memory)
        
        # Create a lookup of Jean Memory V2 memories by their original mem0 ID
        jean_memory_lookup = {}
        logger.debug(f"Processing {len(jean_memories)} Jean Memory V2 memories for lookup")
        
        for memory in jean_memories:
            # Store both the generated UUID and try to get original ID from metadata
            jean_memory_lookup[str(memory.id)] = memory
            # Also try to find the original Jean Memory V2 ID if stored in metadata
            if hasattr(memory, 'metadata_') and memory.metadata_:
                original_id = memory.metadata_.get('original_mem0_id') or memory.metadata_.get('mem0_id')
                if original_id:
                    jean_memory_lookup[str(original_id)] = memory
        
        # Group SQL memories with their Jean Memory V2 counterparts
        result_memories = []
        processed_jean_ids = set()
        
        for sql_memory in sql_memories:
            # Create the result memory (copy of SQL memory)
            result_memory = sql_memory
            thread_memories = []
            
            # Look for related Jean Memory V2 memories
            if hasattr(sql_memory, 'mem0_id') and sql_memory.mem0_id:
                jean_match = jean_memory_lookup.get(str(sql_memory.mem0_id))
                if jean_match:
                    thread_memories.append(jean_match)
                    processed_jean_ids.add(str(jean_match.id))
            
            # Add thread memories if any found
            if thread_memories:
                result_memory.thread_memories = thread_memories
                logger.debug(f"Grouped SQL memory {sql_memory.id} with {len(thread_memories)} Jean Memory V2 memories")
            
            result_memories.append(result_memory)
        
        # Add any unprocessed Jean Memory V2 memories as standalone
        for jean_memory in jean_memories:
            if str(jean_memory.id) not in processed_jean_ids:
                result_memories.append(jean_memory)
        
        logger.debug(f"Threading complete: {len(memories)} → {len(result_memories)} memories with threading")
        return result_memories
        
    except Exception as e:
        logger.warning(f"Memory threading failed: {e}")
        # Return original memories if threading fails
        return memories