"""Distinct-users endpoint.

Lists every user_id that owns at least one non-deleted memory, with a count
and last-activity timestamp. Used by the Web UI to render a User facet
parallel to the existing App facet, so that operators running multiple
projects against the same OpenMemory instance can switch scope visually
instead of relying on the URL alone.
"""

from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models import Memory, MemoryState, User
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/users", tags=["users"])


class UserStats(BaseModel):
    user_id: str
    memory_count: int
    last_active_at: Optional[datetime]


@router.get("/", response_model=list[UserStats])
async def list_users(
    include_empty: bool = False,
    db: Session = Depends(get_db),
):
    """List users with their memory counts.

    By default returns only users that own at least one non-deleted memory.
    Pass ``include_empty=true`` to also list users that exist in the User
    table but currently have no live memories.
    """
    rows = (
        db.query(
            User.user_id.label("user_id"),
            func.count(Memory.id).label("memory_count"),
            func.max(Memory.updated_at).label("last_active_at"),
        )
        .outerjoin(
            Memory,
            (Memory.user_id == User.id) & (Memory.state != MemoryState.deleted),
        )
        .group_by(User.user_id)
        .all()
    )

    results = [
        UserStats(
            user_id=row.user_id,
            memory_count=int(row.memory_count or 0),
            last_active_at=row.last_active_at,
        )
        for row in rows
    ]

    if not include_empty:
        results = [r for r in results if r.memory_count > 0]

    results.sort(key=lambda r: (-r.memory_count, r.user_id))
    return results
