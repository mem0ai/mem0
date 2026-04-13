from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth import require_auth
from db import get_db
from models import APIKey, User

router = APIRouter(prefix="/stats", tags=["stats"])


class OverviewResponse(BaseModel):
    memory_count: int
    active_api_keys: int


@router.get("/overview", response_model=OverviewResponse)
def overview(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    active_keys = db.scalar(select(func.count(APIKey.id)).where(APIKey.revoked_at.is_(None))) or 0
    return OverviewResponse(memory_count=0, active_api_keys=active_keys)
