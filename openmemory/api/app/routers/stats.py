from app.database import get_db
from app.models import App, Memory, MemoryState, User
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger("openmemory.routers.stats")

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])

@router.get("/")
async def get_profile(
    user_id: str,
    db: Session = Depends(get_db)
):
    logger.info(f"[get_profile] Called with params: user_id={user_id}")
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        logger.warning(f"[get_profile] User not found for user_id: {user_id}")
        raise HTTPException(status_code=404, detail="User not found")
    
    logger.info(f"[get_profile] User found: {user.user_id}")

    # Get total number of memories
    total_memories = db.query(Memory).filter(Memory.user_id == user.id, Memory.state != MemoryState.deleted).count()
    logger.info(f"[get_profile] Total memories for user {user.user_id}: {total_memories}")

    # Get total number of apps
    apps = db.query(App).filter(App.owner == user)
    total_apps = apps.count()
    logger.info(f"[get_profile] Total apps for user {user.user_id}: {total_apps}")

    logger.info(f"[get_profile] Returning profile for user {user.user_id}")
    return {
        "total_memories": total_memories,
        "total_apps": total_apps,
        "apps": apps.all()
    }

