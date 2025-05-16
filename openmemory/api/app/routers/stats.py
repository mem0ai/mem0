from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, Memory, App, MemoryState
from app.auth import get_current_supa_user
# from supabase.lib.auth.user import User as SupabaseUser # Old incorrect type hint
from gotrue.types import User as SupabaseUser # Correct type hint
from app.utils.db import get_or_create_user


router = APIRouter(prefix="/api/v1/stats", tags=["stats"])

@router.get("/")
async def get_user_stats(
    current_supa_user: SupabaseUser = Depends(get_current_supa_user),
    db: Session = Depends(get_db)
):
    supabase_user_id_str = str(current_supa_user.id)
    user = get_or_create_user(db, supabase_user_id_str, current_supa_user.email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found or could not be processed")
    
    total_memories = db.query(Memory).filter(Memory.user_id == user.id, Memory.state != MemoryState.deleted).count()

    user_apps_query = db.query(App).filter(App.owner_id == user.id)
    total_apps = user_apps_query.count()
    user_apps_list = user_apps_query.all()

    return {
        "user_id": user.id,
        "email": user.email,
        "total_memories": total_memories,
        "total_apps": total_apps,
        "apps": [
            {"id": app.id, "name": app.name, "is_active": app.is_active}
            for app in user_apps_list
        ]
    }

