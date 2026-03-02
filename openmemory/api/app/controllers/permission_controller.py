"""Permission controller for access control logic."""

from typing import Set, Optional
from uuid import UUID
from sqlalchemy.orm import Session

from app.models import AccessControl


def get_accessible_memory_ids(db: Session, app_id: UUID) -> Optional[Set[UUID]]:
    """Get the set of memory IDs that the app has access to based on app-level ACL rules.

    Args:
        db: Database session
        app_id: App ID to check permissions for

    Returns:
        Set of accessible memory IDs, or None if all memories are accessible
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
