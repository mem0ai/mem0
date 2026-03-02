import asyncio
import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Dict, List, Optional, Set
from uuid import UUID

from app.database import get_db
from app.models import (
    AccessControl,
    App,
    Category,
    Memory,
    MemoryAccessLog,
    MemoryState,
    MemoryStatusHistory,
    User,
)
from app.models.schemas import (
    TimeRange,
    TemporalEntity,
    CreateMemoryRequest,
    DeleteMemoriesRequest,
    PauseMemoriesRequest,
    UpdateMemoryRequest,
    MoveMemoriesRequest,
    FilterMemoriesRequest,
)
from app.services.temporal_service import (
    build_temporal_extraction_prompt,
    extract_temporal_entity,
    enrich_metadata_with_temporal_data,
    enrich_metadata_with_mycelia_fields,
    format_temporal_log_string,
)
from app.services.memory_service import (
    get_memory_or_404,
    update_memory_state,
    create_history_entry,
)
from app.controllers.permission_controller import (
    get_accessible_memory_ids,
)
from app.schemas import MemoryResponse
from app.utils.memory import get_memory_client, create_memory_async
from app.database import SessionLocal
from app.utils.permissions import check_memory_access_permissions
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate as sqlalchemy_paginate
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

router = APIRouter(prefix="/api/v1/memories", tags=["memories"])


# List all memories with filtering
@router.get("/", response_model=Page[MemoryResponse])
async def list_memories(
    user_id: str,
    app_id: Optional[UUID] = None,
    from_date: Optional[int] = Query(None, description="Filter memories created after this date (timestamp)", examples=[1718505600]),
    to_date: Optional[int] = Query(None, description="Filter memories created before this date (timestamp)", examples=[1718505600]),
    categories: Optional[str] = None,
    params: Params = Depends(),
    search_query: Optional[str] = None,
    sort_column: Optional[str] = Query(None, description="Column to sort by"),
    sort_direction: Optional[str] = Query(None, description="Sort direction (asc or desc)"),
    db: Session = Depends(get_db)
):
    """List memories with filtering and pagination.

    Flow:
    1. Get user
    2. Build base query (user's active memories)
    3. Apply filters (app, dates, search, categories)
    4. Apply joins and sorting
    5. Paginate with permission checking
    """
    from app.controllers import query_controller as qc

    # Step 1: Get user (auto-create if not exists)
    user = qc.get_user_or_create(user_id, db)

    # Step 2: Build base query for user's active memories
    query = qc.build_base_memory_query(user, db)

    # Step 3: Apply search filter
    query = qc.apply_search_filter(query, search_query)

    # Step 4: Apply other filters
    query = qc.apply_app_filter(query, app_id)
    query = qc.apply_date_filters(query, from_date, to_date)

    # Step 5: Add joins for related data
    query = qc.apply_joins(query)

    # Step 6: Apply category filter (after join)
    query = qc.apply_category_filter(query, categories)

    # Step 7: Apply sorting
    query = qc.apply_sorting(query, sort_column, sort_direction)

    # Step 8: Eager load relationships (standard SQLAlchemy optimization)
    query = query.options(
        joinedload(Memory.app),
        joinedload(Memory.categories),
        joinedload(Memory.user)
    ).distinct(Memory.id)

    # Step 9: Paginate and transform with permission checking
    return sqlalchemy_paginate(
        query,
        params,
        transformer=lambda items: qc.transform_to_response(items, app_id, db)
    )


# Get all categories
@router.get("/categories")
async def get_categories(
    user_id: str,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get unique categories associated with the user's memories
    # Get all memories
    memories = db.query(Memory).filter(Memory.user_id == user.id, Memory.state != MemoryState.deleted, Memory.state != MemoryState.archived).all()
    # Get all categories from memories
    categories = [category for memory in memories for category in memory.categories]
    # Get unique categories
    unique_categories = list(set(categories))

    return {
        "categories": unique_categories,
        "total": len(unique_categories)
    }


# Create new memory
@router.post("/")
async def create_memory(
    request: CreateMemoryRequest,
    db: Session = Depends(get_db)
):
    """Create a new memory.

    Flow:
    1. Get/create user and app
    2. Validate app is active
    3. Add timestamp and user info to metadata
    4. Create placeholder (instant response)
    5. Process with mem0 (controller handles client lifecycle)
    """
    from app.controllers import memory_controller as controller

    # Step 1: Get or create user and app
    user, app = await controller.get_or_create_user_and_app(request, db)

    # Step 2: Validate app is active
    controller.validate_app_active(app)

    # Step 3: Add timestamp and user info to metadata
    metadata = controller.add_timestamp_and_user_to_metadata(request, user)

    # Step 4: Create placeholder for instant response
    placeholder = controller.create_placeholder(user, app, request, metadata, db)

    # Step 5: Process with mem0 (controller handles mem0 client internally)
    await controller.process_memory_with_mem0(placeholder, request, metadata)

    return placeholder





# Get memory by ID
@router.get("/{memory_id}")
async def get_memory(
    memory_id: UUID,
    db: Session = Depends(get_db)
):
    memory = get_memory_or_404(db, memory_id)
    return {
        "id": memory.id,
        "text": memory.content,
        "created_at": int(memory.created_at.timestamp()),
        "state": memory.state.value,
        "app_id": memory.app_id,
        "app_name": memory.app.name if memory.app else None,
        "categories": [category.name for category in memory.categories],
        "metadata_": memory.metadata_
    }


# Delete multiple memories
@router.delete("/")
async def delete_memories(
    request: DeleteMemoriesRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Get memory client to delete from vector store
    try:
        memory_client = await get_memory_client()
        if not memory_client:
            raise HTTPException(
                status_code=503,
                detail="Memory client is not available"
            )
    except HTTPException:
        raise
    except Exception as client_error:
        logging.error(f"Memory client initialization failed: {client_error}")
        raise HTTPException(
            status_code=503,
            detail=f"Memory service unavailable: {str(client_error)}"
        )

    # Delete from vector store then mark as deleted in database
    for memory_id in request.memory_ids:
        try:
            await memory_client.delete(str(memory_id))
        except Exception as delete_error:
            logging.warning(f"Failed to delete memory {memory_id} from vector store: {delete_error}")

        update_memory_state(db, memory_id, MemoryState.deleted, user.id)

    return {"message": f"Successfully deleted {len(request.memory_ids)} memories"}


# Archive memories
@router.post("/actions/archive")
async def archive_memories(
    memory_ids: List[UUID],
    user_id: UUID,
    db: Session = Depends(get_db)
):
    for memory_id in memory_ids:
        update_memory_state(db, memory_id, MemoryState.archived, user_id)
    return {"message": f"Successfully archived {len(memory_ids)} memories"}


# Pause access to memories
@router.post("/actions/pause")
async def pause_memories(
    request: PauseMemoriesRequest,
    db: Session = Depends(get_db)
):
    
    global_pause = request.global_pause
    all_for_app = request.all_for_app
    app_id = request.app_id
    memory_ids = request.memory_ids
    category_ids = request.category_ids
    state = request.state or MemoryState.paused

    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_id = user.id
    
    if global_pause:
        # Pause all memories
        memories = db.query(Memory).filter(
            Memory.state != MemoryState.deleted,
            Memory.state != MemoryState.archived
        ).all()
        for memory in memories:
            update_memory_state(db, memory.id, state, user_id)
        return {"message": "Successfully paused all memories"}

    if app_id:
        # Pause all memories for an app
        memories = db.query(Memory).filter(
            Memory.app_id == app_id,
            Memory.user_id == user.id,
            Memory.state != MemoryState.deleted,
            Memory.state != MemoryState.archived
        ).all()
        for memory in memories:
            update_memory_state(db, memory.id, state, user_id)
        return {"message": f"Successfully paused all memories for app {app_id}"}
    
    if all_for_app and memory_ids:
        # Pause all memories for an app
        memories = db.query(Memory).filter(
            Memory.user_id == user.id,
            Memory.state != MemoryState.deleted,
            Memory.id.in_(memory_ids)
        ).all()
        for memory in memories:
            update_memory_state(db, memory.id, state, user_id)
        return {"message": "Successfully paused all memories"}

    if memory_ids:
        # Pause specific memories
        for memory_id in memory_ids:
            update_memory_state(db, memory_id, state, user_id)
        return {"message": f"Successfully paused {len(memory_ids)} memories"}

    if category_ids:
        # Pause memories by category
        memories = db.query(Memory).join(Memory.categories).filter(
            Category.id.in_(category_ids),
            Memory.state != MemoryState.deleted,
            Memory.state != MemoryState.archived
        ).all()
        for memory in memories:
            update_memory_state(db, memory.id, state, user_id)
        return {"message": f"Successfully paused memories in {len(category_ids)} categories"}

    raise HTTPException(status_code=400, detail="Invalid pause request parameters")


# Get memory access logs
@router.get("/{memory_id}/access-log")
async def get_memory_access_log(
    memory_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(MemoryAccessLog).filter(MemoryAccessLog.memory_id == memory_id)
    total = query.count()
    logs = query.order_by(MemoryAccessLog.accessed_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # Get app name
    for log in logs:
        app = db.query(App).filter(App.id == log.app_id).first()
        log.app_name = app.name if app else None

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "logs": logs
    }


# Update a memory
@router.put("/{memory_id}")
async def update_memory(
    memory_id: UUID,
    request: UpdateMemoryRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    memory = get_memory_or_404(db, memory_id)
    memory.content = request.memory_content
    if request.target_app_id:
        memory.app_id = request.target_app_id
    db.commit()
    db.refresh(memory)
    return memory

@router.post("/{app_id}/memories/move/")
async def move_memories_to_app(
    app_id: UUID,
    request: UpdateMemoryRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")    
    # Get memories to move
    memories = db.query(Memory).filter(
        Memory.id.in_(request.memory_ids),
        Memory.app_id == app_id,
        # Memory.user_id == user.id,
        # Memory.state != MemoryState.deleted
    ).all()
    
    if not memories:
        raise HTTPException(status_code=404, detail="No memories found to move")
    
    # Move memories to target app
    moved_count = 0
    for memory in memories:
        try:
            await update_memory(memory.id, request, db)
            moved_count += 1
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to move memory {memory.id}: {str(e)}")
    
    return {
        "status": "success",
        "message": f"Successfully moved {moved_count} memories to {request.target_app_id}",
        "moved_count": moved_count
    }



@router.post("/filter", response_model=Page[MemoryResponse])
async def filter_memories(
    request: FilterMemoriesRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Build base query
    # Superusers can see all memories, regular users only see their own
    if user.is_superuser:
        query = db.query(Memory).filter(
            Memory.state != MemoryState.deleted,
        )
    else:
        query = db.query(Memory).filter(
            Memory.user_id == user.id,
            Memory.state != MemoryState.deleted,
        )

    # Filter archived memories based on show_archived parameter
    if not request.show_archived:
        query = query.filter(Memory.state != MemoryState.archived)

    # Apply search filter
    if request.search_query:
        query = query.filter(Memory.content.ilike(f"%{request.search_query}%"))

    # Apply app filter
    if request.app_ids:
        query = query.filter(Memory.app_id.in_(request.app_ids))

    # Add joins for app and categories
    query = query.outerjoin(App, Memory.app_id == App.id)

    # Apply category filter
    if request.category_ids:
        query = query.join(Memory.categories).filter(Category.id.in_(request.category_ids))
    else:
        query = query.outerjoin(Memory.categories)

    # Apply date filters
    if request.from_date:
        from_datetime = datetime.fromtimestamp(request.from_date, tz=UTC)
        query = query.filter(Memory.created_at >= from_datetime)

    if request.to_date:
        to_datetime = datetime.fromtimestamp(request.to_date, tz=UTC)
        query = query.filter(Memory.created_at <= to_datetime)

    # Apply sorting
    if request.sort_column and request.sort_direction:
        sort_direction = request.sort_direction.lower()
        if sort_direction not in ['asc', 'desc']:
            raise HTTPException(status_code=400, detail="Invalid sort direction")

        sort_mapping = {
            'memory': Memory.content,
            'app_name': App.name,
            'created_at': Memory.created_at
        }

        if request.sort_column not in sort_mapping:
            raise HTTPException(status_code=400, detail="Invalid sort column")

        sort_field = sort_mapping[request.sort_column]
        if sort_direction == 'desc':
            query = query.order_by(sort_field.desc())
        else:
            query = query.order_by(sort_field.asc())
    else:
        # Default sorting
        query = query.order_by(Memory.created_at.desc())

    # Add eager loading for categories and make the query distinct
    query = query.options(
        joinedload(Memory.categories)
    ).distinct(Memory.id)

    # Use fastapi-pagination's paginate function
    return sqlalchemy_paginate(
        query,
        Params(page=request.page, size=request.size),
        transformer=lambda items: [
            MemoryResponse(
                id=memory.id,
                content=memory.content,
                created_at=memory.created_at,
                state=memory.state.value,
                app_id=memory.app_id,
                app_name=memory.app.name if memory.app else None,
                categories=[category.name for category in memory.categories],
                metadata_=memory.metadata_
            )
            for memory in items
        ]
    )


@router.post("/actions/recover-stuck")
async def recover_stuck_memories(
    db: Session = Depends(get_db)
):
    """Manual endpoint to check for and recover stuck processing memories"""
    stuck_memories = db.query(Memory).filter(Memory.state == MemoryState.processing).all()
    
    if not stuck_memories:
        return {"message": "No stuck processing memories found", "count": 0}
    
    return {
        "message": f"Found {len(stuck_memories)} stuck processing memories",
        "count": len(stuck_memories),
        "memories": [
            {
                "id": str(memory.id),
                "content": memory.content[:100] + "..." if len(memory.content) > 100 else memory.content,
                "created_at": memory.created_at.isoformat(),
                "user_id": memory.user_id,
                "app_id": memory.app_id
            }
            for memory in stuck_memories
        ]
    }


@router.get("/{memory_id}/related", response_model=Page[MemoryResponse])
async def get_related_memories(
    memory_id: UUID,
    user_id: str,
    params: Params = Depends(),
    db: Session = Depends(get_db)
):
    # Validate user
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get the source memory
    memory = get_memory_or_404(db, memory_id)
    
    # Extract category IDs from the source memory
    category_ids = [category.id for category in memory.categories]
    
    if not category_ids:
        return Page.create([], total=0, params=params)
    
    # Build query for related memories
    query = db.query(Memory).distinct(Memory.id).filter(
        Memory.user_id == user.id,
        Memory.id != memory_id,
        Memory.state != MemoryState.deleted
    ).join(Memory.categories).filter(
        Category.id.in_(category_ids)
    ).options(
        joinedload(Memory.categories),
        joinedload(Memory.app)
    ).order_by(
        func.count(Category.id).desc(),
        Memory.created_at.desc()
    ).group_by(Memory.id)
    
    # ⚡ Force page size to be 5
    params = Params(page=params.page, size=5)
    
    return sqlalchemy_paginate(
        query,
        params,
        transformer=lambda items: [
            MemoryResponse(
                id=memory.id,
                content=memory.content,
                created_at=memory.created_at,
                state=memory.state.value,
                app_id=memory.app_id,
                app_name=memory.app.name if memory.app else None,
                categories=[category.name for category in memory.categories],
                metadata_=memory.metadata_
            )
            for memory in items
        ]
    )

    