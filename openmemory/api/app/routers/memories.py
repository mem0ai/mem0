from datetime import datetime, UTC
from typing import List, Optional, Set
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate as sqlalchemy_paginate
from pydantic import BaseModel
from sqlalchemy import or_, func

from app.database import get_db
from app.auth import get_current_supa_user
from gotrue.types import User as SupabaseUser
from app.utils.memory import get_memory_client
from app.utils.db import get_or_create_user, get_user_and_app
from app.models import (
    Memory, MemoryState, MemoryAccessLog, App,
    MemoryStatusHistory, User, Category, AccessControl
)
from app.schemas import MemoryResponse, PaginatedMemoryResponse
from app.utils.permissions import check_memory_access_permissions

router = APIRouter(prefix="/memories", tags=["memories"])


def get_memory_or_404(db: Session, memory_id: UUID) -> Memory:
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


def update_memory_state(db: Session, memory_id: UUID, new_state: MemoryState, changed_by_supa_user_id: str):
    memory = get_memory_or_404(db, memory_id)
    changed_by_user_record = db.query(User).filter(User.id == UUID(changed_by_supa_user_id)).first()
    if not changed_by_user_record:
        raise HTTPException(status_code=404, detail="User performing action not found in local DB")

    internal_user_pk = changed_by_user_record.id

    old_state = memory.state
    memory.state = new_state
    if new_state == MemoryState.archived:
        memory.archived_at = datetime.now(UTC)
    elif new_state == MemoryState.deleted:
        memory.deleted_at = datetime.now(UTC)

    history = MemoryStatusHistory(
        memory_id=memory_id,
        changed_by=internal_user_pk,
        old_state=old_state,
        new_state=new_state
    )
    db.add(history)


def get_accessible_memory_ids(db: Session, app_id: UUID) -> Set[UUID]:
    """
    Get the set of memory IDs that the app has access to based on app-level ACL rules.
    Returns all memory IDs if no specific restrictions are found.
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


# List all memories with filtering
@router.get("/", response_model=Page[MemoryResponse])
async def list_memories(
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    app_id: Optional[UUID] = None,
    from_date: Optional[int] = Query(
        None,
        description="Filter memories created after this date (timestamp)",
        examples=[1718505600]
    ),
    to_date: Optional[int] = Query(
        None,
        description="Filter memories created before this date (timestamp)",
        examples=[1718505600]
    ),
    categories: Optional[str] = None,
    params: Params = Depends(),
    search_query: Optional[str] = None,
    sort_column: Optional[str] = Query(None, description="Column to sort by (memory, categories, app_name, created_at)"),
    sort_direction: Optional[str] = Query(None, description="Sort direction (asc or desc)"),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found or could not be created")

    # Build base query
    query = db.query(Memory).filter(
        Memory.user_id == user.id,
        Memory.state != MemoryState.deleted,
        Memory.state != MemoryState.archived,
        Memory.content.ilike(f"%{search_query}%") if search_query else True
    )

    # Apply filters
    if app_id:
        query = query.filter(Memory.app_id == app_id)

    if from_date:
        from_datetime = datetime.fromtimestamp(from_date, tz=UTC)
        query = query.filter(Memory.created_at >= from_datetime)

    if to_date:
        to_datetime = datetime.fromtimestamp(to_date, tz=UTC)
        query = query.filter(Memory.created_at <= to_datetime)

    # Add joins for app and categories after filtering
    query = query.outerjoin(App, Memory.app_id == App.id)
    query = query.outerjoin(Memory.categories)

    # Apply category filter if provided
    if categories:
        category_list = [c.strip() for c in categories.split(",")]
        query = query.filter(Category.name.in_(category_list))

    # Apply sorting if specified
    if sort_column:
        sort_field = None
        if sort_column == "memory": sort_field = Memory.content
        elif sort_column == "categories": sort_field = Category.name
        elif sort_column == "app_name": sort_field = App.name
        elif sort_column == "created_at": sort_field = Memory.created_at
        
        if sort_field is not None:
            if sort_column == "categories" and not categories:
                query = query.join(Memory.categories)
            if sort_column == "app_name" and not app_id:
                query = query.outerjoin(App, Memory.app_id == App.id)
                
            query = query.order_by(sort_field.desc() if sort_direction == "desc" else sort_field.asc())
        else:
            query = query.order_by(Memory.created_at.desc())
    else:
        query = query.order_by(Memory.created_at.desc())

    # Get paginated results - items are SQLAlchemy Memory objects
    paginated_sqla_results = sqlalchemy_paginate(
        query.options(joinedload(Memory.app), joinedload(Memory.categories)).distinct(), 
        params
    )

    # Filter results based on permissions
    permitted_sqla_items = []
    for item in paginated_sqla_results.items: # item is app.models.Memory
        if check_memory_access_permissions(db, item, app_id): # app_id is the one from query params for filtering
            permitted_sqla_items.append(item)

    # Now, transform the permitted SQLAlchemy items into MemoryResponse Pydantic models
    response_items = [
        MemoryResponse(
            id=mem.id,
            content=mem.content,
            created_at=mem.created_at, 
            state=mem.state.value if mem.state else None,
            app_id=mem.app_id,
            app_name=mem.app.name if mem.app else None, 
            categories=[cat.name for cat in mem.categories], 
            metadata_=mem.metadata_
        )
        for mem in permitted_sqla_items
    ]

    # Create a new Page object with the transformed items and correct total
    return Page.create(
        items=response_items,
        total=len(response_items), 
        params=params 
    )


# Get all categories
@router.get("/categories")
async def get_categories(
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    memories = db.query(Memory).filter(Memory.user_id == user.id, Memory.state != MemoryState.deleted, Memory.state != MemoryState.archived).all()
    categories_set = set()
    for memory_item in memories:
        for category_item in memory_item.categories:
            categories_set.add(category_item.name)
    
    return {
        "categories": list(categories_set),
        "total": len(categories_set)
    }


class CreateMemoryRequestData(BaseModel):
    text: str
    metadata: dict = {}
    infer: bool = True
    app_name: str


# Create new memory
@router.post("/", response_model=MemoryResponse)
async def create_memory(
    request: CreateMemoryRequestData,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    
    user, app_obj = get_user_and_app(db, supabase_user_id_str, request.app_name, current_supa_user.email)

    if not app_obj.is_active:
        raise HTTPException(status_code=403, detail=f"App {request.app_name} is currently paused. Cannot create new memories.")

    sql_memory = Memory(
        user_id=user.id,
        app_id=app_obj.id,
        content=request.text,
        metadata_=request.metadata
    )
    db.add(sql_memory)
    try:
        db.commit()
        db.refresh(sql_memory)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return MemoryResponse(
        id=sql_memory.id,
        content=sql_memory.content,
        created_at=sql_memory.created_at,
        state=sql_memory.state.value if sql_memory.state else None,
        app_id=sql_memory.app_id,
        app_name=app_obj.name,
        categories=[cat.name for cat in sql_memory.categories],
        metadata_=sql_memory.metadata_
    )


# Get memory by ID
@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: UUID,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)

    memory = get_memory_or_404(db, memory_id)
    
    if memory.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access this memory")

    return MemoryResponse(
        id=memory.id,
        content=memory.content,
        created_at=memory.created_at,
        state=memory.state.value if memory.state else None,
        app_id=memory.app_id,
        app_name=memory.app.name if memory.app else None,
        categories=[category.name for category in memory.categories],
        metadata_=memory.metadata_
    )


class DeleteMemoriesRequestData(BaseModel):
    memory_ids: List[UUID]


# Delete multiple memories
@router.delete("/", status_code=200)
async def delete_memories(
    request: DeleteMemoriesRequestData,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)

    deleted_count = 0
    not_found_count = 0
    not_authorized_count = 0

    user_internal_id = UUID(supabase_user_id_str)

    for memory_id_to_delete in request.memory_ids:
        memory_to_delete = db.query(Memory).filter(Memory.id == memory_id_to_delete).first()
        if not memory_to_delete:
            not_found_count += 1
            continue
        if memory_to_delete.user_id != user_internal_id:
            not_authorized_count += 1
            continue
        
        update_memory_state(db, memory_id_to_delete, MemoryState.deleted, supabase_user_id_str)
        deleted_count += 1
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error committing deletions: {e}")

    return {"message": f"Successfully deleted {deleted_count} memories. Not found: {not_found_count}. Not authorized: {not_authorized_count}."}


# Archive memories
@router.post("/actions/archive", status_code=200)
async def archive_memories(
    memory_ids: List[UUID],
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    archived_count = 0
    not_found_count = 0
    not_authorized_count = 0
    user_internal_id = UUID(supabase_user_id_str)

    for memory_id_to_archive in memory_ids:
        memory_to_archive = db.query(Memory).filter(Memory.id == memory_id_to_archive).first()
        if not memory_to_archive:
            not_found_count += 1
            continue
        if memory_to_archive.user_id != user_internal_id:
            not_authorized_count += 1
            continue
        update_memory_state(db, memory_id_to_archive, MemoryState.archived, supabase_user_id_str)
        archived_count += 1

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error committing archival: {e}")
    
    return {"message": f"Successfully archived {archived_count} memories. Not found: {not_found_count}. Not authorized: {not_authorized_count}."}


class PauseMemoriesRequestData(BaseModel):
    memory_ids: Optional[List[UUID]] = None
    category_ids: Optional[List[UUID]] = None
    app_id: Optional[UUID] = None
    global_pause_for_user: bool = False
    state: Optional[MemoryState] = MemoryState.paused


# Pause access to memories
@router.post("/actions/pause", status_code=200)
async def pause_memories(
    request: PauseMemoriesRequestData,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)

    state_to_set = request.state or MemoryState.paused

    count = 0
    if request.global_pause_for_user:
        memories_to_update = db.query(Memory).filter(
            Memory.user_id == user.id,
        ).all()
        for memory_item in memories_to_update:
            update_memory_state(db, memory_item.id, state_to_set, supabase_user_id_str)
            count += 1
        message = f"Successfully set state for all {count} accessible memories for user."

    elif request.app_id:
        memories_to_update = db.query(Memory).filter(
            Memory.app_id == request.app_id,
            Memory.user_id == user.id,
        ).all()
        for memory_item in memories_to_update:
            update_memory_state(db, memory_item.id, state_to_set, supabase_user_id_str)
            count += 1
        message = f"Successfully set state for {count} memories for app {request.app_id}."
    
    elif request.memory_ids:
        for mem_id in request.memory_ids:
            memory_to_update = db.query(Memory).filter(Memory.id == mem_id, Memory.user_id == user.id).first()
            if memory_to_update:
                 update_memory_state(db, mem_id, state_to_set, supabase_user_id_str)
                 count += 1
        message = f"Successfully set state for {count} specified memories."

    elif request.category_ids:
        memories_to_update = db.query(Memory).join(Memory.categories).filter(
            Memory.user_id == user.id,
            Category.id.in_(request.category_ids),
            Memory.state != MemoryState.deleted,
        ).distinct().all()
        for memory_item in memories_to_update:
            update_memory_state(db, memory_item.id, state_to_set, supabase_user_id_str)
            count += 1
        message = f"Successfully set state for {count} memories in {len(request.category_ids)} categories."
    else:
        db.rollback()
        raise HTTPException(status_code=400, detail="Invalid pause request parameters. Specify memories, app, categories, or global_pause_for_user.")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error committing state changes: {e}")
        
    return {"message": message}


# Get memory access logs
@router.get("/{memory_id}/access-log")
async def get_memory_access_log(
    memory_id: UUID,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)

    memory_owner_check = get_memory_or_404(db, memory_id)
    if memory_owner_check.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access logs for this memory")

    query = db.query(MemoryAccessLog).filter(MemoryAccessLog.memory_id == memory_id)
    total = query.count()
    logs = query.order_by(MemoryAccessLog.accessed_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    for log_item in logs:
        app = db.query(App).filter(App.id == log_item.app_id).first()
        log_item.app_name = app.name if app else None

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "logs": logs
    }


class UpdateMemoryRequestData(BaseModel):
    memory_content: str


# Update a memory
@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: UUID,
    request: UpdateMemoryRequestData,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    
    memory_to_update = get_memory_or_404(db, memory_id)

    if memory_to_update.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this memory")

    memory_to_update.content = request.memory_content
    try:
        db.commit()
        db.refresh(memory_to_update)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
        
    return MemoryResponse(
        id=memory_to_update.id,
        content=memory_to_update.content,
        created_at=memory_to_update.created_at,
        state=memory_to_update.state.value if memory_to_update.state else None,
        app_id=memory_to_update.app_id,
        app_name=memory_to_update.app.name if memory_to_update.app else None,
        categories=[cat.name for cat in memory_to_update.categories],
        metadata_=memory_to_update.metadata_
    )


class FilterMemoriesRequestData(BaseModel):
    page: int = 1
    size: int = 10
    search_query: Optional[str] = None
    app_ids: Optional[List[UUID]] = None
    category_ids: Optional[List[UUID]] = None
    sort_column: Optional[str] = None
    sort_direction: Optional[str] = None
    from_date: Optional[int] = None
    to_date: Optional[int] = None
    show_archived: Optional[bool] = False


@router.post("/filter", response_model=Page[MemoryResponse])
async def filter_memories(
    request: FilterMemoriesRequestData,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)

    query = db.query(Memory).filter(
        Memory.user_id == user.id,
        Memory.state != MemoryState.deleted,
    )

    if not request.show_archived:
        query = query.filter(Memory.state != MemoryState.archived)

    if request.search_query:
        query = query.filter(Memory.content.ilike(f"%{request.search_query}%"))

    if request.app_ids:
        query = query.filter(Memory.app_id.in_(request.app_ids))

    query = query.outerjoin(App, Memory.app_id == App.id)

    if request.category_ids:
        query = query.join(Memory.categories).filter(Category.id.in_(request.category_ids))
    else:
        query = query.outerjoin(Memory.categories)

    if request.from_date:
        from_datetime = datetime.fromtimestamp(request.from_date, tz=UTC)
        query = query.filter(Memory.created_at >= from_datetime)

    if request.to_date:
        to_datetime = datetime.fromtimestamp(request.to_date, tz=UTC)
        query = query.filter(Memory.created_at <= to_datetime)

    if request.sort_column and request.sort_direction:
        sort_direction = request.sort_direction.lower()
        if sort_direction not in ['asc', 'desc']:
            raise HTTPException(status_code=400, detail="Invalid sort direction")

        sort_mapping = {
            'memory': Memory.content,
            'app_name': App.name,
            'created_at': Memory.created_at,
        }
        
        if request.sort_column == 'categories':
            query = query.order_by(Memory.created_at.desc())
        elif request.sort_column in sort_mapping:
            sort_field = sort_mapping[request.sort_column]
            if sort_direction == 'desc':
                query = query.order_by(sort_field.desc())
            else:
                query = query.order_by(sort_field.asc())
        else:
            query = query.order_by(Memory.created_at.desc())
    else:
        query = query.order_by(Memory.created_at.desc())

    query = query.options(
        joinedload(Memory.categories),
        joinedload(Memory.app)
    ).distinct()

    return sqlalchemy_paginate(
        query,
        Params(page=request.page, size=request.size),
        transformer=lambda items: [
            MemoryResponse(
                id=mem.id,
                content=mem.content,
                created_at=mem.created_at,
                state=mem.state.value if mem.state else None,
                app_id=mem.app_id,
                app_name=mem.app.name if mem.app else None,
                categories=[cat.name for cat in mem.categories],
                metadata_=mem.metadata_
            )
            for mem in items
        ]
    )


@router.get("/{memory_id}/related", response_model=Page[MemoryResponse])
async def get_related_memories(
    memory_id: UUID,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    params: Params = Depends(),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    
    source_memory = get_memory_or_404(db, memory_id)
    if source_memory.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to access related memories for this item.")
        
    category_ids = [category.id for category in source_memory.categories]
    
    if not category_ids:
        return Page[MemoryResponse].create([], total=0, params=params)
    
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
    
    page_num = params.page if params and params.page is not None else 1
    forced_params = Params(page=page_num, size=5)

    paginated_results = sqlalchemy_paginate(
        query,
        forced_params,
    )
    transformed_items = [
            MemoryResponse(
                id=item.id,
                content=item.content,
                created_at=item.created_at,
                state=item.state.value if item.state else None,
                app_id=item.app_id,
                app_name=item.app.name if item.app else None,
                categories=[cat.name for cat in item.categories],
                metadata_=item.metadata_
            )
            for item in paginated_results.items
        ]
    return Page[MemoryResponse](items=transformed_items, total=paginated_results.total, page=paginated_results.page, size=paginated_results.size, pages=paginated_results.pages)
