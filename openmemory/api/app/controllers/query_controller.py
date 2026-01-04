"""Query controller for building and filtering memory queries.

Contains methods for constructing database queries with clear, readable steps.
"""

from datetime import datetime, UTC
from typing import Optional, List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, Query, joinedload
from sqlalchemy import func

from app.models import User, App, Memory, MemoryState, Category
from app.controllers.permission_controller import get_accessible_memory_ids
from app.utils.permissions import check_memory_access_permissions
from app.utils.db import get_or_create_user
from app.schemas import MemoryResponse


def get_user_or_create(user_id: str, db: Session) -> User:
    """Get user by ID or create if not exists.

    Args:
        user_id: User ID string
        db: Database session

    Returns:
        User object (existing or newly created)
    """
    return get_or_create_user(db, user_id)


def build_base_memory_query(user: User, db: Session) -> Query:
    """Build base query for user's active memories.

    Args:
        user: User object
        db: Database session

    Returns:
        Base SQLAlchemy query
    """
    return db.query(Memory).filter(
        Memory.user_id == user.id,
        Memory.state != MemoryState.deleted,
        Memory.state != MemoryState.archived
    )


def apply_app_filter(query: Query, app_id: Optional[UUID]) -> Query:
    """Apply app ID filter to query.

    Args:
        query: Base query
        app_id: Optional app ID to filter by

    Returns:
        Filtered query
    """
    if app_id:
        return query.filter(Memory.app_id == app_id)
    return query


def apply_date_filters(
    query: Query,
    from_date: Optional[int],
    to_date: Optional[int]
) -> Query:
    """Apply date range filters to query.

    Args:
        query: Base query
        from_date: Unix timestamp for start date
        to_date: Unix timestamp for end date

    Returns:
        Filtered query
    """
    if from_date:
        from_datetime = datetime.fromtimestamp(from_date, tz=UTC)
        query = query.filter(Memory.created_at >= from_datetime)

    if to_date:
        to_datetime = datetime.fromtimestamp(to_date, tz=UTC)
        query = query.filter(Memory.created_at <= to_datetime)

    return query


def apply_search_filter(query: Query, search_query: Optional[str]) -> Query:
    """Apply text search filter to query.

    Args:
        query: Base query
        search_query: Search term

    Returns:
        Filtered query
    """
    if search_query:
        return query.filter(Memory.content.ilike(f"%{search_query}%"))
    return query


def apply_category_filter(query: Query, categories: Optional[str]) -> Query:
    """Apply category filter to query.

    Note: This method does the join to categories table ONLY if filtering by category.
    This is more efficient than always joining.

    Args:
        query: Base query
        categories: Comma-separated category names

    Returns:
        Filtered query (with join if needed)
    """
    if categories:
        category_list = [c.strip() for c in categories.split(",")]
        # Join to categories table and filter
        return query.join(Memory.categories).filter(Category.name.in_(category_list))
    return query


def apply_joins(query: Query) -> Query:
    """Add left outer joins for app (for displaying app_name in results).

    Note: Category join is done in apply_category_filter() only if needed.
    This is called for eager loading optimization.

    Args:
        query: Base query

    Returns:
        Query with app join
    """
    return query.outerjoin(App, Memory.app_id == App.id)


def apply_sorting(
    query: Query,
    sort_column: Optional[str],
    sort_direction: Optional[str]
) -> Query:
    """Apply sorting to query.

    Args:
        query: Base query
        sort_column: Column name to sort by
        sort_direction: 'asc' or 'desc'

    Returns:
        Sorted query
    """
    if sort_column:
        sort_field = getattr(Memory, sort_column, None)
        if sort_field:
            if sort_direction == "desc":
                return query.order_by(sort_field.desc())
            else:
                return query.order_by(sort_field.asc())
    return query


def apply_eager_loading(query: Query) -> Query:
    """Add eager loading for relationships.

    Args:
        query: Base query

    Returns:
        Query with eager loading
    """
    return query.options(
        joinedload(Memory.app),
        joinedload(Memory.categories),
        joinedload(Memory.user)
    ).distinct(Memory.id)


def transform_to_response(items: List[Memory], app_id: Optional[UUID], db: Session) -> List[MemoryResponse]:
    """Transform Memory objects to response format with permission checking.

    Args:
        items: List of Memory objects
        app_id: Optional app ID for permission checking
        db: Database session

    Returns:
        List of MemoryResponse objects
    """
    return [
        MemoryResponse(
            id=memory.id,
            content=memory.content,
            created_at=memory.created_at,
            state=memory.state.value,
            app_id=memory.app_id,
            app_name=memory.app.name if memory.app else None,
            categories=[category.name for category in memory.categories],
            metadata_=memory.metadata_,
            user_id=memory.user.user_id if memory.user else None,
            user_email=memory.user.email if memory.user else None
        )
        for memory in items
        if check_memory_access_permissions(db, memory, app_id)
    ]
