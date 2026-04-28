from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from auth import require_auth
from db import get_db
from models import RequestLog, User

router = APIRouter(prefix="/requests", tags=["requests"])


class RequestLogItem(BaseModel):
    id: uuid.UUID
    method: str
    path: str
    status_code: int
    latency_ms: float
    auth_type: str
    created_at: datetime

    model_config = {"from_attributes": True}


API_KEY_AUTH_TYPES = ("api_key", "admin_api_key")


@router.get("", response_model=list[RequestLogItem])
def list_requests(
    user: User = Depends(require_auth),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
):
    logs = (
        db.execute(
            select(RequestLog)
            .where(RequestLog.auth_type.in_(API_KEY_AUTH_TYPES))
            .order_by(RequestLog.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return logs
