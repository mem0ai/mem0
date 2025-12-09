import logging
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel

from app.database import get_db
from app.models import App, Memory, MemoryAccessLog, MemoryState, User
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, func
from sqlalchemy.orm import Session, joinedload
from app.routers.memories import update_memory_state

router = APIRouter(prefix="/api/v1/apps", tags=["apps"])

# Helper functions
def get_app_or_404(db: Session, app_id: UUID) -> App:
    app = db.query(App).filter(App.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    return app

# List all users
@router.get("/users")
async def list_users(db: Session = Depends(get_db)):
    """List all users in the system"""
    users = db.query(User).all()
    return {
        "total": len(users),
        "users": [
            {
                "id": str(user.id),
                "user_id": user.user_id,
                "name": user.name,
                "email": user.email,
                "created_at": user.created_at
            }
            for user in users
        ]
    }

class CreateAppRequest(BaseModel):
    name: str
    user_id: str
    description: Optional[str] = None


# Create a new app
@router.post("/")
async def create_app(
    request: CreateAppRequest,
    db: Session = Depends(get_db)
):
    """Create a new app"""
    # Get or create the user
    user = db.query(User).filter(User.user_id == request.user_id).first()
    if not user:
        # Create the user if they don't exist
        user = User(
            user_id=request.user_id,
            name=request.user_id.replace("_", " ").title()
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # Check if app name already exists
    existing_app = db.query(App).filter(App.name == request.name).first()
    if existing_app:
        raise HTTPException(status_code=400, detail=f"App with name '{request.name}' already exists")

    # Create the new app
    new_app = App(
        name=request.name,
        description=request.description,
        owner_id=user.id,
        is_active=True
    )

    db.add(new_app)
    db.commit()
    db.refresh(new_app)

    return {
        "status": "success",
        "message": f"App '{request.name}' created successfully",
        "app": {
            "id": str(new_app.id),
            "name": new_app.name,
            "description": new_app.description,
            "is_active": new_app.is_active,
            "created_at": new_app.created_at,
            "owner_id": str(new_app.owner_id)
        }
    }


# List all apps with filtering
@router.get("/")
async def list_apps(
    name: Optional[str] = None,
    is_active: Optional[bool] = None,
    sort_by: str = 'name',
    sort_direction: str = 'asc',
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    # Create a subquery for memory counts
    memory_counts = db.query(
        Memory.app_id,
        func.count(Memory.id).label('memory_count')
    ).filter(
        Memory.state.in_([MemoryState.active, MemoryState.paused, MemoryState.archived])
    ).group_by(Memory.app_id).subquery()

    # Create a subquery for access counts
    access_counts = db.query(
        MemoryAccessLog.app_id,
        func.count(func.distinct(MemoryAccessLog.memory_id)).label('access_count')
    ).group_by(MemoryAccessLog.app_id).subquery()

    # Base query
    query = db.query(
        App,
        func.coalesce(memory_counts.c.memory_count, 0).label('total_memories_created'),
        func.coalesce(access_counts.c.access_count, 0).label('total_memories_accessed')
    )

    # Join with subqueries
    query = query.outerjoin(
        memory_counts,
        App.id == memory_counts.c.app_id
    ).outerjoin(
        access_counts,
        App.id == access_counts.c.app_id
    )

    if name:
        query = query.filter(App.name.ilike(f"%{name}%"))

    if is_active is not None:
        query = query.filter(App.is_active == is_active)

    # Apply sorting
    if sort_by == 'name':
        sort_field = App.name
    elif sort_by == 'memories':
        sort_field = func.coalesce(memory_counts.c.memory_count, 0)
    elif sort_by == 'memories_accessed':
        sort_field = func.coalesce(access_counts.c.access_count, 0)
    else:
        sort_field = App.name  # default sort

    if sort_direction == 'desc':
        query = query.order_by(desc(sort_field))
    else:
        query = query.order_by(sort_field)

    total = query.count()
    apps = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "apps": [
            {
                "id": app[0].id,
                "name": app[0].name,
                "is_active": app[0].is_active,
                "total_memories_created": app[1],
                "total_memories_accessed": app[2]
            }
            for app in apps
        ]
    }

# Get app details
@router.get("/{app_id}")
async def get_app_details(
    app_id: UUID,
    db: Session = Depends(get_db)
):
    app = get_app_or_404(db, app_id)

    # Get memory access statistics
    access_stats = db.query(
        func.count(MemoryAccessLog.id).label("total_memories_accessed"),
        func.min(MemoryAccessLog.accessed_at).label("first_accessed"),
        func.max(MemoryAccessLog.accessed_at).label("last_accessed")
    ).filter(MemoryAccessLog.app_id == app_id).first()

    # Get owner information
    owner = db.query(User).filter(User.id == app.owner_id).first()

    return {
        "is_active": app.is_active,
        "created_by": owner.user_id if owner else None,
        "created_by_name": owner.name if owner else None,
        "created_at": app.created_at,
        "total_memories_created": db.query(Memory)
            .filter(Memory.app_id == app_id)
            .count(),
        "total_memories_accessed": access_stats.total_memories_accessed or 0,
        "first_accessed": access_stats.first_accessed,
        "last_accessed": access_stats.last_accessed
    }

# List memories created by app
@router.get("/{app_id}/memories")
async def list_app_memories(
    app_id: UUID,
    user_id: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    get_app_or_404(db, app_id)
    query = db.query(Memory).filter(
        Memory.app_id == app_id,
        Memory.state.in_([MemoryState.active, MemoryState.paused, MemoryState.archived, MemoryState.processing])
    )

    # Filter by user_id if provided
    if user_id:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user:
            query = query.filter(Memory.user_id == user.id)
    # Add eager loading for categories, app, and user
    query = query.options(
        joinedload(Memory.categories),
        joinedload(Memory.app),
        joinedload(Memory.user)
    )
    total = query.count()
    memories = query.order_by(Memory.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "memories": [
            {
                "id": memory.id,
                "content": memory.content,
                "created_at": int(memory.created_at.timestamp()) if memory.created_at else None,
                "state": memory.state.value,
                "app_id": memory.app_id,
                "app_name": memory.app.name if memory.app else None,
                "categories": [category.name for category in memory.categories],
                "metadata_": memory.metadata_,
                "user_id": memory.user.user_id if memory.user else None,
                "user_email": memory.user.email if memory.user else None
            }
            for memory in memories
        ]
    }

# List memories accessed by app
@router.get("/{app_id}/accessed")
async def list_app_accessed_memories(
    app_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    
    # Get memories with access counts
    query = db.query(
        Memory,
        func.count(MemoryAccessLog.id).label("access_count")
    ).join(
        MemoryAccessLog,
        Memory.id == MemoryAccessLog.memory_id
    ).filter(
        MemoryAccessLog.app_id == app_id
    ).group_by(
        Memory.id
    ).order_by(
        desc("access_count")
    )

    # Add eager loading for categories
    query = query.options(joinedload(Memory.categories))

    total = query.count()
    results = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "memories": [
            {
                "memory": {
                    "id": memory.id,
                    "content": memory.content,
                    "created_at": memory.created_at,
                    "state": memory.state.value,
                    "app_id": memory.app_id,
                    "app_name": memory.app.name if memory.app else None,
                    "categories": [category.name for category in memory.categories],
                    "metadata_": memory.metadata_
                },
                "access_count": count
            }
            for memory, count in results
        ]
    }


@router.put("/{app_id}")
async def update_app_details(
    app_id: UUID,
    is_active: bool,
    db: Session = Depends(get_db)
):
    app = get_app_or_404(db, app_id)
    app.is_active = is_active
    db.commit()
    return {"status": "success", "message": "Updated app details successfully"}


class TransferAppOwnershipRequest(BaseModel):
    new_owner_user_id: str


@router.post("/{app_id}/transfer-ownership")
async def transfer_app_ownership(
    app_id: UUID,
    request: TransferAppOwnershipRequest,
    db: Session = Depends(get_db)
):
    """Transfer app ownership to another user"""
    # Get the app
    app = get_app_or_404(db, app_id)

    # Get or create the new owner
    new_owner = db.query(User).filter(User.user_id == request.new_owner_user_id).first()
    if not new_owner:
        # Create the user if they don't exist
        new_owner = User(
            user_id=request.new_owner_user_id,
            name=request.new_owner_user_id.replace("_", " ").title()
        )
        db.add(new_owner)
        db.commit()
        db.refresh(new_owner)

    # Get old owner for response
    old_owner = db.query(User).filter(User.id == app.owner_id).first()
    old_owner_user_id = old_owner.user_id if old_owner else "Unknown"

    # Transfer ownership
    app.owner_id = new_owner.id
    db.commit()

    return {
        "status": "success",
        "message": f"App ownership transferred from {old_owner_user_id} to {request.new_owner_user_id}",
        "app_id": str(app_id),
        "old_owner": old_owner_user_id,
        "new_owner": request.new_owner_user_id
    }


class DeleteAppRequest(BaseModel):
    user_id: str
    action: str  # "delete_memories" or "move_memories"
    target_app_id: Optional[str] = None  # Changed to str to handle UUID strings from frontend


@router.delete("/{app_id}")
async def delete_app(
    app_id: UUID,
    request: DeleteAppRequest,
    db: Session = Depends(get_db)
):
    """Delete an app and handle its memories"""
    try:
        # Validate user
        user = db.query(User).filter(User.user_id == request.user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get app (no ownership check since there's no UI authentication)
        app = db.query(App).filter(App.id == app_id).first()
        if not app:
            raise HTTPException(status_code=404, detail="App not found")
        
        message = ""
        memory_count = 0

        if request.action == "delete_memories":
             # Get all memories for this app
            memories = db.query(Memory).filter(
                Memory.app_id == app_id,
                Memory.state != MemoryState.deleted
            ).all()

            memory_count = len(memories)
            # Delete all memories
            for memory in memories:
                update_memory_state(db, memory.id, MemoryState.deleted, user.id)

            message = f"Successfully deleted app '{app.name}' and {memory_count} memories"

        elif request.action == "move_memories":
            if not request.target_app_id:
                raise HTTPException(status_code=400, detail="target_app_id is required for move_memories action")

            # Convert target_app_id string to UUID
            try:
                target_app_uuid = UUID(request.target_app_id)
            except (ValueError, AttributeError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid target_app_id format: {str(e)}")

            # Validate target app exists
            target_app = db.query(App).filter(App.id == target_app_uuid).first()
            if not target_app:
                raise HTTPException(status_code=404, detail="Target app not found")

            # Get all memories for this app
            memories = db.query(Memory).filter(
                Memory.app_id == app_id,
            ).all()

            memory_count = len(memories)
            # Move all memories to target app
            for memory in memories:
                memory.app_id = target_app_uuid

            db.commit()
            message = f"Successfully moved {memory_count} memories to '{target_app.name}'"
        else:
            logging.error(f"Invalid action: {request.action}")
            raise HTTPException(status_code=400, detail="Invalid action. Must be 'delete_memories' or 'move_memories'")

        # Actually delete the app from the database
        try:
            db.delete(app)
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to delete app: {str(e)}")

        return {
            "status": "success",
            "message": message,
            "affected_memories": memory_count,
            "target_app_id": str(request.target_app_id) if request.target_app_id else None
        }
        
        
    except Exception as e:
        logging.error(f"Unexpected error in delete_app: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
