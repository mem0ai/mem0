import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth import require_auth
from db import get_db
from models import APIKey, RequestLog, User
from server_state import get_memory_instance

router = APIRouter(prefix="/stats", tags=["stats"])

MEMORY_COUNT_LIMIT = 10000


class OverviewResponse(BaseModel):
    memory_count: int
    active_api_keys: int
    ops_today: int


def _count_current_memories() -> int:
    try:
        results = get_memory_instance().vector_store.list(limit=MEMORY_COUNT_LIMIT)
    except Exception:
        logging.exception("Failed to count memories from vector store")
        return 0

    if not results:
        return 0
    first = results[0] if isinstance(results, list) else results
    return len(first) if isinstance(first, list) else 0


@router.get("/overview", response_model=OverviewResponse)
def overview(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    active_keys = db.scalar(select(func.count(APIKey.id)).where(APIKey.revoked_at.is_(None))) or 0
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    ops_today = db.scalar(select(func.count(RequestLog.id)).where(RequestLog.created_at >= today_start)) or 0

    return OverviewResponse(
        memory_count=_count_current_memories(),
        active_api_keys=active_keys,
        ops_today=ops_today,
    )
