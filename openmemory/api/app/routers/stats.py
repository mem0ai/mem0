from app.database import get_db
from app.models import App, Memory, MemoryState, User
from app.utils.db import get_or_create_user
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])

@router.get("/")
async def get_profile(
    user_id: str,
    db: Session = Depends(get_db)
):
    user = get_or_create_user(db, user_id)
    
    # Get total number of memories
    total_memories = db.query(Memory).filter(Memory.user_id == user.id, Memory.state != MemoryState.deleted).count()

    # Get total number of apps
    apps = db.query(App).filter(App.owner == user)
    total_apps = apps.count()

    return {
        "total_memories": total_memories,
        "total_apps": total_apps,
        "apps": apps.all()
    }

