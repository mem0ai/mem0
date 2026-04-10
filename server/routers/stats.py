from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth import verify_auth
from db import get_db
from models import APIKey, User

router = APIRouter(prefix="/stats", tags=["stats"])


class OverviewResponse(BaseModel):
    memory_count: int
    team_size: int
    active_api_keys: int


@router.get("/overview/", response_model=OverviewResponse)
def overview(user: User = Depends(verify_auth), db: Session = Depends(get_db)):
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required.")

    team_size = db.scalar(select(func.count(User.id))) or 0
    active_keys = db.scalar(select(func.count(APIKey.id)).where(APIKey.revoked_at.is_(None))) or 0

    return OverviewResponse(memory_count=0, team_size=team_size, active_api_keys=active_keys)
