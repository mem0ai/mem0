import os
import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from auth import require_auth
from db import get_db
from models import APIKey, RequestLog, User
from server_state import get_current_config

router = APIRouter(prefix="/stats", tags=["stats"])


class OverviewResponse(BaseModel):
    memory_count: int
    active_api_keys: int
    ops_today: int


def _count_current_memories(history_db_path: str) -> int:
    if not history_db_path:
        return 0

    db_path = os.path.expanduser(history_db_path)
    if not os.path.exists(db_path):
        return 0

    try:
        connection = sqlite3.connect(db_path)
    except sqlite3.Error:
        return 0

    try:
        row = connection.execute(
            """
            WITH latest AS (
                SELECT
                    memory_id,
                    COALESCE(is_deleted, 0) AS is_deleted,
                    ROW_NUMBER() OVER (
                        PARTITION BY memory_id
                        ORDER BY COALESCE(updated_at, created_at) DESC, created_at DESC
                    ) AS rn
                FROM history
            )
            SELECT COUNT(*)
            FROM latest
            WHERE rn = 1 AND is_deleted = 0
            """
        ).fetchone()
    except sqlite3.Error:
        return 0
    finally:
        connection.close()

    return int(row[0]) if row and row[0] is not None else 0


@router.get("/overview", response_model=OverviewResponse)
def overview(user: User = Depends(require_auth), db: Session = Depends(get_db)):
    active_keys = db.scalar(select(func.count(APIKey.id)).where(APIKey.revoked_at.is_(None))) or 0
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    ops_today = db.scalar(select(func.count(RequestLog.id)).where(RequestLog.created_at >= today_start)) or 0
    history_db_path = get_current_config().get("history_db_path", "")

    return OverviewResponse(
        memory_count=_count_current_memories(history_db_path),
        active_api_keys=active_keys,
        ops_today=ops_today,
    )
