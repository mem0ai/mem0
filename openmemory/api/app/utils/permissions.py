from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from app.models import Memory, App, MemoryState


def check_memory_access_permissions(
    db: Session,
    memory: Memory,
    app_id: Optional[UUID] = None
) -> bool:
    """
    Check if the given app has permission to access a memory based on:
    1. Memory state (must be active)
    2. App state (must not be paused)
    3. App-specific access controls

    Args:
        db: Database session
        memory: Memory object to check access for
        app_id: Optional app ID to check permissions for

    Returns:
        bool: True if access is allowed, False otherwise
    """
    # Check if memory is active
    if memory.state != MemoryState.active:
        return False

    # If no app_id provided, only check memory state
    if not app_id:
        return True

    # Check if app exists and is active
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        return False

    # Check if app is paused/inactive
    if not app.is_active:
        return False

    # Check app-specific access controls
    from app.routers.memories import get_accessible_memory_ids
    accessible_memory_ids = get_accessible_memory_ids(db, app_id)

    # If accessible_memory_ids is None, all memories are accessible
    if accessible_memory_ids is None:
        return True

    # Check if memory is in the accessible set
    return memory.id in accessible_memory_ids
