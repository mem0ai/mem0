import logging
from datetime import datetime, UTC
from typing import List, Optional, Set
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import paginate as sqlalchemy_paginate
from pydantic import BaseModel
from sqlalchemy import or_, func
from qdrant_client import models as qdrant_models

from app.database import get_db
from app.models import (
    Memory, MemoryState, MemoryAccessLog, App,
    MemoryStatusHistory, User, Category, AccessControl
)
from app.schemas import MemoryResponse, PaginatedMemoryResponse
from app.utils.permissions import check_memory_access_permissions
from app.utils.memory import get_memory_client

router = APIRouter(prefix="/api/v1/memories", tags=["memories"])

# Initialize the memory client with Qdrant connection
memory_client = get_memory_client()


def get_memory_or_404(db: Session, memory_id: UUID) -> Memory:
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


def update_memory_state(db: Session, memory_id: UUID, new_state: MemoryState, user_id: UUID):
    memory = get_memory_or_404(db, memory_id)
    old_state = memory.state

    # Update memory state
    memory.state = new_state
    if new_state == MemoryState.archived:
        memory.archived_at = datetime.now(UTC)
    elif new_state == MemoryState.deleted:
        memory.deleted_at = datetime.now(UTC)

    # Record state change
    history = MemoryStatusHistory(
        memory_id=memory_id,
        changed_by=user_id,
        old_state=old_state,
        new_state=new_state
    )
    db.add(history)
    db.commit()
    return memory


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
    user_id: str,
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
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

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
        sort_field = getattr(Memory, sort_column, None)
        if sort_field:
            query = query.order_by(sort_field.desc()) if sort_direction == "desc" else query.order_by(sort_field.asc())


    # Get paginated results
    paginated_results = sqlalchemy_paginate(query, params)

    # Filter results based on permissions
    filtered_items = []
    for item in paginated_results.items:
        if check_memory_access_permissions(db, item, app_id):
            filtered_items.append(item)

    # Update paginated results with filtered items
    paginated_results.items = filtered_items
    paginated_results.total = len(filtered_items)

    return paginated_results


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


class CreateMemoryRequest(BaseModel):
    user_id: str
    text: str
    metadata: dict = {}
    infer: bool = True
    app: str = "openmemory"


# Create new memory
@router.post("/")
async def create_memory(
    request: CreateMemoryRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Get or create app
    app_obj = db.query(App).filter(App.name == request.app).first()
    if not app_obj:
        app_obj = App(name=request.app, owner_id=user.id)
        db.add(app_obj)
        db.commit()
        db.refresh(app_obj)

    # Check if app is active
    if not app_obj.is_active:
        raise HTTPException(status_code=403, detail=f"App {request.app} is currently paused on OpenMemory. Cannot create new memories.")

    # Create memory
    memory = Memory(
        user_id=user.id,
        app_id=app_obj.id,
        content=request.text,
        metadata_=request.metadata
    )
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


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
        "metadata": memory.metadata_
    }


class DeleteMemoriesRequest(BaseModel):
    memory_ids: List[UUID]
    user_id: str

# Delete multiple memories
@router.delete("/")
async def delete_memories(
    request: DeleteMemoriesRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for memory_id in request.memory_ids:
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


class PauseMemoriesRequest(BaseModel):
    memory_ids: Optional[List[UUID]] = None
    category_ids: Optional[List[UUID]] = None
    app_id: Optional[UUID] = None
    all_for_app: bool = False
    global_pause: bool = False
    state: Optional[MemoryState] = None
    user_id: str

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
        return {"message": f"Successfully paused all memories"}

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


class UpdateMemoryRequest(BaseModel):
    memory_content: str
    user_id: str

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
    db.commit()
    db.refresh(memory)
    return memory

class FilterMemoriesRequest(BaseModel):
    user_id: str
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
    request: FilterMemoriesRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # If there's a search query, use Qdrant for semantic search
    if request.search_query:
        try:
            # Use memory_client to get embedding and search
            embeddings = memory_client.embedding_model.embed(request.search_query, "search")
            
            # Create filter conditions
            conditions = [qdrant_models.FieldCondition(key="user_id", match=qdrant_models.MatchValue(value=request.user_id))]
            
            # Add date filters if provided
            if request.from_date:
                from_timestamp = request.from_date
                conditions.append(
                    qdrant_models.FieldCondition(
                        key="created_at",
                        range=qdrant_models.Range(gte=from_timestamp)
                    )
                )
                
            if request.to_date:
                to_timestamp = request.to_date
                conditions.append(
                    qdrant_models.FieldCondition(
                        key="created_at",
                        range=qdrant_models.Range(lte=to_timestamp)
                    )
                )
                
            # Create combined filter
            filters = qdrant_models.Filter(must=conditions)
            
            # Search Qdrant
            hits = memory_client.vector_store.client.query_points(
                collection_name=memory_client.vector_store.collection_name,
                query=embeddings,
                query_filter=filters,
                limit=request.size,
                offset=(request.page - 1) * request.size
            )
            
            # Get memory IDs from search results
            memory_ids = [UUID(hit.id) for hit in hits.points]
            
            # Get full memory objects from database with additional filtering
            memory_items = []
            for memory_id in memory_ids:
                mem = db.query(Memory).filter(
                    Memory.id == memory_id,
                    Memory.user_id == user.id
                ).first()
                
                # Apply additional filters that weren't applied in Qdrant
                if mem and (request.show_archived or mem.state != MemoryState.archived) and mem.state != MemoryState.deleted:
                    # Filter by app_ids if provided
                    if request.app_ids and mem.app_id not in request.app_ids:
                        continue
                        
                    # Filter by category_ids if provided
                    if request.category_ids:
                        category_matches = False
                        for category in mem.categories:
                            if category.id in request.category_ids:
                                category_matches = True
                                break
                        if not category_matches:
                            continue
                    
                    # Log memory access
                    access_log = MemoryAccessLog(
                        memory_id=memory_id,
                        app_id=mem.app_id,
                        access_type="search",
                        metadata_={
                            "query": request.search_query
                        }
                    )
                    db.add(access_log)
                    memory_items.append(mem)
            
            logging.info(f"Memory items: {len(memory_items)}")

            db.commit()
            
            # Convert Memory objects to MemoryResponse
            memory_responses = [
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
                for memory in memory_items
            ]
            
            # Format response
            total = len(memory_responses)
            response = {
                "items": memory_responses,
                "total": total,
                "page": request.page,
                "size": request.size,
                "pages": (total + request.size - 1) // request.size if request.size > 0 else 0
            }
            
            return response
            
        except Exception as e:
            logging.exception(f"Error in Qdrant search: {e}")
            # Fall back to database search if Qdrant fails
            pass
            
    # Standard database filtering (either no search query or Qdrant failed)
    query = db.query(Memory).filter(Memory.user_id == user.id)
    
    # Apply all filters
    if not request.show_archived:
        query = query.filter(Memory.state != MemoryState.archived)
    query = query.filter(Memory.state != MemoryState.deleted)
    
    if request.search_query:
        query = query.filter(Memory.content.ilike(f"%{request.search_query}%"))
        
    if request.app_ids:
        query = query.filter(Memory.app_id.in_(request.app_ids))
        
    if request.from_date:
        from_datetime = datetime.fromtimestamp(request.from_date, tz=UTC)
        query = query.filter(Memory.created_at >= from_datetime)
        
    if request.to_date:
        to_datetime = datetime.fromtimestamp(request.to_date, tz=UTC)
        query = query.filter(Memory.created_at <= to_datetime)
        
    # Add proper eager loading
    query = query.options(joinedload(Memory.app), joinedload(Memory.categories))
    
    # Apply category filter if provided
    if request.category_ids:
        query = query.join(Memory.categories).filter(Category.id.in_(request.category_ids))
        
    # Apply sorting
    if request.sort_column:
        if request.sort_column == "created_at":
            sort_field = Memory.created_at
        elif request.sort_column == "content":
            sort_field = Memory.content
        else:
            sort_field = getattr(Memory, request.sort_column, None)
            
        if sort_field:
            query = query.order_by(sort_field.desc() if request.sort_direction == "desc" else sort_field.asc())
    else:
        # Default sort by created_at descending
        query = query.order_by(Memory.created_at.desc())
    
    # Use this transformer to convert Memory to MemoryResponse
    def transform_to_memory_response(items):
        return [
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
    
    # Paginate results with transformer
    params = Params(page=request.page, size=request.size)
    return sqlalchemy_paginate(query, params, transformer=transform_to_memory_response)


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

    # Get the memory
    memory = get_memory_or_404(db, memory_id)
    
    # Check that memory belongs to the user
    if memory.user_id != user.id:
        raise HTTPException(status_code=403, detail="Access denied to this memory")
        
    try:
        # Use memory_client to get embedding and search for similar memories in Qdrant
        embeddings = memory_client.embedding_model.embed(memory.content, "memory")
        
        # Create filter for user_id
        conditions = [qdrant_models.FieldCondition(key="user_id", match=qdrant_models.MatchValue(value=user_id))]
        
        # Exclude the current memory from results
        conditions.append(
            qdrant_models.FieldCondition(
                key="id", 
                match=qdrant_models.MatchValue(value=str(memory_id)), 
                must_not=True
            )
        )
        
        filters = qdrant_models.Filter(must=conditions)
        
        # Search for related memories in Qdrant
        hits = memory_client.vector_store.client.query_points(
            collection_name=memory_client.vector_store.collection_name,
            query=embeddings,
            query_filter=filters,
            limit=params.size,
            offset=(params.page - 1) * params.size
        )
        
        # Process search results
        memory_ids = [UUID(hit.id) for hit in hits.points]
        
        # Get full memory objects from database
        memory_items = []
        for memory_id in memory_ids:
            mem = db.query(Memory).filter(Memory.id == memory_id).first()
            if mem and mem.state != MemoryState.deleted and mem.state != MemoryState.archived:
                # Create access log
                access_log = MemoryAccessLog(
                    memory_id=memory_id,
                    app_id=memory.app_id,
                    access_type="related_search",
                    metadata_={
                        "original_memory_id": str(memory.id)
                    }
                )
                db.add(access_log)
                memory_items.append(mem)
                
        db.commit()
        
        # Convert Memory objects to MemoryResponse
        memory_responses = [
            MemoryResponse(
                id=mem.id,
                content=mem.content,
                created_at=mem.created_at,
                state=mem.state.value,
                app_id=mem.app_id,
                app_name=mem.app.name if mem.app else None,
                categories=[category.name for category in mem.categories],
                metadata_=mem.metadata_
            )
            for mem in memory_items
        ]
        
        # Format response to match the expected PaginatedMemoryResponse format
        total = len(memory_responses)
        response = {
            "items": memory_responses,
            "total": total,
            "page": params.page,
            "size": params.size,
            "pages": (total + params.size - 1) // params.size if params.size > 0 else 0
        }
        
        return response
        
    except Exception as e:
        logging.exception(f"Error fetching related memories: {e}")
        # Fallback to database if Qdrant search fails
        filtered_query = db.query(Memory).filter(
            Memory.user_id == user.id,
            Memory.id != memory_id,
            Memory.state != MemoryState.deleted,
            Memory.state != MemoryState.archived
        )
        
        # Use transformer to convert Memory to MemoryResponse
        def transform_to_memory_response(items):
            return [
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
        
        return sqlalchemy_paginate(filtered_query, params, transformer=transform_to_memory_response)
