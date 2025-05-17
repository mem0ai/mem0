from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc

from app.database import get_db
from app.models import App, Memory, MemoryAccessLog, MemoryState, User
from app.auth import get_current_supa_user
from gotrue.types import User as SupabaseUser
from app.utils.db import get_or_create_user

router = APIRouter(prefix="/apps", tags=["apps"])

# Helper function to get an app owned by the current user, or raise 404/403
def get_user_app_or_40x(db: Session, app_id: UUID, user_id_from_auth: UUID) -> App:
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if app.owner_id != user_id_from_auth:
        raise HTTPException(status_code=403, detail="Not authorized to access this app")
    return app

# List all apps for the authenticated user
@router.get("/")
async def list_apps(
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    name: Optional[str] = None,
    is_active: Optional[bool] = None,
    sort_by: str = 'name',
    sort_direction: str = 'asc',
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)

    # Create a subquery for memory counts, specific to user's apps
    memory_counts_subquery = (
        db.query(
            Memory.app_id,
            func.count(Memory.id).label('memory_count')
        )
        .join(App, Memory.app_id == App.id)
        .filter(
            App.owner_id == user.id,
            Memory.state.in_([MemoryState.active, MemoryState.paused, MemoryState.archived])
        )
        .group_by(Memory.app_id)
        .subquery('memory_counts_sq')
    )

    # Create a subquery for access counts, specific to user's apps
    access_counts_subquery = (
        db.query(
            MemoryAccessLog.app_id,
            func.count(func.distinct(MemoryAccessLog.memory_id)).label('access_count')
        )
        .join(App, MemoryAccessLog.app_id == App.id)
        .filter(App.owner_id == user.id)
        .group_by(MemoryAccessLog.app_id)
        .subquery('access_counts_sq')
    )

    # Base query for Apps owned by the current user
    query = db.query(
        App,
        func.coalesce(memory_counts_subquery.c.memory_count, 0).label('total_memories_created'),
        func.coalesce(access_counts_subquery.c.access_count, 0).label('total_memories_accessed')
    ).filter(App.owner_id == user.id)

    # Join with subqueries
    query = query.outerjoin(
        memory_counts_subquery, # Use named subquery
        App.id == memory_counts_subquery.c.app_id
    ).outerjoin(
        access_counts_subquery, # Use named subquery
        App.id == access_counts_subquery.c.app_id
    )

    if name:
        query = query.filter(App.name.ilike(f"%{name}%"))
    if is_active is not None:
        query = query.filter(App.is_active == is_active)

    # Apply sorting
    sort_field_expression = App.name # Default sort field
    if sort_by == 'name':
        sort_field_expression = App.name
    elif sort_by == 'memories':
        sort_field_expression = func.coalesce(memory_counts_subquery.c.memory_count, 0)
    elif sort_by == 'memories_accessed':
        sort_field_expression = func.coalesce(access_counts_subquery.c.access_count, 0)
    
    if sort_direction == 'desc':
        query = query.order_by(desc(sort_field_expression))
    else:
        query = query.order_by(sort_field_expression)

    # Get total count for pagination (efficiently)
    # Clone the query and remove ordering/limit/offset for counting.
    count_query = query.with_entities(func.count(App.id)).order_by(None)
    total = count_query.scalar()
    
    results = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "apps": [
            {
                "id": app_record.id,
                "name": app_record.name,
                "is_active": app_record.is_active,
                "total_memories_created": created_count,
                "total_memories_accessed": accessed_count
            }
            for app_record, created_count, accessed_count in results
        ]
    }

# Get app details (for an app owned by the current user)
@router.get("/{app_id}")
async def get_app_details(
    app_id: UUID,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    app = get_user_app_or_40x(db, app_id, user.id) # user.id is the UUID PK

    access_stats = db.query(
        func.count(MemoryAccessLog.id).label("total_memories_accessed"),
        func.min(MemoryAccessLog.accessed_at).label("first_accessed"),
        func.max(MemoryAccessLog.accessed_at).label("last_accessed")
    ).filter(MemoryAccessLog.app_id == app.id).first()

    return {
        "id": app.id,
        "name": app.name,
        "is_active": app.is_active,
        "total_memories_created": db.query(func.count(Memory.id))
            .filter(Memory.app_id == app.id)
            .scalar(),
        "total_memories_accessed": access_stats.total_memories_accessed or 0,
        "first_accessed": access_stats.first_accessed,
        "last_accessed": access_stats.last_accessed
    }

# List memories created by a specific app (owned by the current user)
@router.get("/{app_id}/memories")
async def list_app_memories(
    app_id: UUID,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    app = get_user_app_or_40x(db, app_id, user.id)

    query = db.query(Memory).filter(
        Memory.app_id == app.id,
        # Memory.user_id == user.id, # App ownership implies user ownership of memories within that app context
        Memory.state.in_([MemoryState.active, MemoryState.paused, MemoryState.archived])
    ).options(joinedload(Memory.categories))
    
    total_query = query.with_entities(func.count(Memory.id)).order_by(None)
    total = total_query.scalar()
    memories_results = query.order_by(Memory.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "memories": [
            {
                "id": mem.id,
                "content": mem.content,
                "created_at": mem.created_at,
                "state": mem.state.value,
                "app_id": mem.app_id,
                "categories": [category.name for category in mem.categories],
                "metadata_": mem.metadata_
            }
            for mem in memories_results
        ]
    }

# List memories accessed by app (owned by current user)
@router.get("/{app_id}/accessed")
async def list_app_accessed_memories(
    app_id: UUID,
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    app = get_user_app_or_40x(db, app_id, user.id)
    
    query = db.query(
        Memory,
        func.count(MemoryAccessLog.id).label("access_count")
    ).join(
        MemoryAccessLog,
        Memory.id == MemoryAccessLog.memory_id
    ).filter(
        MemoryAccessLog.app_id == app.id,
        Memory.user_id == user.id # Ensure memory is user's (important for accessed memories)
    ).group_by(
        Memory.id
    ).order_by(
        desc("access_count")
    ).options(joinedload(Memory.categories), joinedload(Memory.app))

    # Efficiently count distinct memories that were accessed
    # This counts groups after group_by, which is equivalent to distinct memories here.
    count_query = db.query(func.count(Memory.id.distinct()))\
        .join(MemoryAccessLog, Memory.id == MemoryAccessLog.memory_id)\
        .filter(MemoryAccessLog.app_id == app.id, Memory.user_id == user.id)
    total = count_query.scalar_one_or_none() or 0

    results = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "memories": [
            {
                "memory": {
                    "id": mem.id,
                    "content": mem.content,
                    "created_at": mem.created_at,
                    "state": mem.state.value,
                    "app_id": mem.app_id,
                    "app_name": mem.app.name if mem.app else None,
                    "categories": [cat.name for cat in mem.categories],
                    "metadata_": mem.metadata_
                },
                "access_count": access_cnt
            }
            for mem, access_cnt in results
        ]
    }

# Update app details (for an app owned by current user)
@router.put("/{app_id}")
async def update_app_details(
    app_id: UUID,
    is_active: bool, # Assuming request body is just this boolean, or use Pydantic model
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    app = get_user_app_or_40x(db, app_id, user.id)
    
    app.is_active = is_active
    try:
        db.commit()
        db.refresh(app)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
        
    return {"status": "success", "message": "Updated app details successfully", "app_id": app.id, "is_active": app.is_active}

# Note: App creation endpoint is currently missing from this router.
# It seems to be handled implicitly in memories_router.create_memory.
# If a dedicated app creation endpoint is needed, it should also use:
# current_supa_user: SupabaseUser = Depends(get_current_supa_user)
# user = get_or_create_user(db, str(current_supa_user.id), current_supa_user.email)
# new_app = App(owner_id=user.id, name=request.name, ...)
