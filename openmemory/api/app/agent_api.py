from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import cast, String
from threading import Lock
from . import models, schemas
from .database import get_db
from .auth import get_current_supa_user, SupabaseUser
from .utils.db import get_user_and_app
from typing import Optional

router = APIRouter()
db_lock = Lock()

@router.post("/v1/memory/add_tagged", status_code=201)
def add_tagged_memory(
    memory_in: schemas.AgentMemoryCreate,
    db: Session = Depends(get_db),
    supa_user: SupabaseUser = Depends(get_current_supa_user),
    x_client_name: Optional[str] = Header("default_agent_app", alias="X-Client-Name"),
):
    """
    Adds a new memory with specified text and metadata tags.
    This endpoint is thread-safe for use with SQLite in local testing.
    """
    with db_lock:
        user, app = get_user_and_app(db, supa_user.id, x_client_name)

        if not app.is_active:
            raise HTTPException(
                status_code=403,
                detail=f"The application '{x_client_name}' is not active.",
            )

        db_memory = models.Memory(
            user_id=user.id,
            app_id=app.id,
            content=memory_in.text,
            metadata_=memory_in.metadata,
        )
        db.add(db_memory)
        db.commit()
        db.refresh(db_memory)

        return {"status": "success", "memory_id": db_memory.id}


@router.post("/v1/memory/search_by_tags")
def search_by_tags(
    search_in: schemas.AgentMemorySearch,
    db: Session = Depends(get_db),
    supa_user: SupabaseUser = Depends(get_current_supa_user),
    x_client_name: Optional[str] = Header(None, alias="X-Client-Name"),
):
    """
    Searches for memories based on metadata tags.
    This query is cross-database compatible (PostgreSQL & SQLite).
    """
    query = db.query(models.Memory).filter(models.Memory.user.has(user_id=supa_user.id))

    if x_client_name:
        query = query.filter(models.Memory.app.has(name=x_client_name))

    if search_in.filter:
        for key, value in search_in.filter.items():
            json_snippet = f'"{key}": "{value}"'
            query = query.filter(cast(models.Memory.metadata_, String).like(f"%{json_snippet}%"))

    results = query.all()
    
    return results 