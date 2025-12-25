"""Memory service for database CRUD operations.

This module handles all database operations for memories:
- Fetching memories
- Updating memory state
- Creating history entries
- Memory lookups
"""

from datetime import UTC, datetime
from uuid import UUID
from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Memory, MemoryState, MemoryStatusHistory


def get_memory_or_404(db: Session, memory_id: UUID) -> Memory:
    """Get a memory by ID or raise 404.

    Args:
        db: Database session
        memory_id: UUID of the memory to fetch

    Returns:
        Memory object

    Raises:
        HTTPException: 404 if memory not found
    """
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


def update_memory_state(
    db: Session,
    memory_id: UUID,
    new_state: MemoryState,
    user_id: UUID
) -> Memory:
    """Update a memory's state and record the change in history.

    Args:
        db: Database session
        memory_id: UUID of the memory to update
        new_state: New state to set
        user_id: UUID of the user making the change

    Returns:
        Updated Memory object
    """
    memory = get_memory_or_404(db, memory_id)
    old_state = memory.state

    # Update memory state
    memory.state = new_state
    if new_state == MemoryState.archived:
        memory.archived_at = datetime.now(UTC)
    elif new_state == MemoryState.deleted:
        memory.deleted_at = datetime.now(UTC)

    # Record state change
    create_history_entry(db, memory_id, user_id, old_state, new_state)

    db.commit()
    return memory


def create_history_entry(
    db: Session,
    memory_id: UUID,
    user_id: UUID,
    old_state: MemoryState,
    new_state: MemoryState
) -> None:
    """Create and persist a memory status history entry.

    Args:
        db: Database session
        memory_id: Memory UUID
        user_id: User UUID making the change
        old_state: Previous memory state
        new_state: New memory state
    """
    history = MemoryStatusHistory(
        memory_id=memory_id,
        changed_by=user_id,
        old_state=old_state,
        new_state=new_state
    )
    db.add(history)
