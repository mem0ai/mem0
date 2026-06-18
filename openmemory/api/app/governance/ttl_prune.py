"""TTL prune governance job (task_08)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Callable, Optional

from app.database import SessionLocal
from app.models import Category, Memory, MemoryAccessLog, MemoryState, memory_categories
from app.utils.governance_policy import resolve_policy
from app.utils.metrics import GOVERNANCE_PRUNED_TOTAL
from app.utils.quarantine import QuarantineEngine
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _last_access(db: Session, memory_id) -> datetime | None:
    row = (
        db.query(func.max(MemoryAccessLog.accessed_at))
        .filter(MemoryAccessLog.memory_id == memory_id)
        .scalar()
    )
    return row


def _protected_category_names(db: Session, memory: Memory, protected: tuple[str, ...]) -> bool:
    if not protected:
        return False
    names = (
        db.query(Category.name)
        .join(memory_categories, Category.id == memory_categories.c.category_id)
        .filter(memory_categories.c.memory_id == memory.id)
        .all()
    )
    cat_names = {n[0] for n in names}
    return bool(cat_names & set(protected))


def run_ttl_prune_job(
    *,
    project: Optional[str],
    job_id: str,
    limit: int = 500,
    session_factory=SessionLocal,
    quarantine_engine: Optional[QuarantineEngine] = None,
    vector_store_provider: Optional[Callable] = None,
) -> int:
    engine = quarantine_engine or QuarantineEngine(
        session_factory=session_factory,
        vector_store_provider=vector_store_provider,
    )
    policy = resolve_policy(project or "", session_factory=session_factory)
    batch_limit = min(limit, policy.batch_limit)
    now = datetime.now(UTC)
    max_age_cutoff = now - timedelta(days=policy.ttl_max_age_days)
    idle_cutoff = now - timedelta(days=policy.ttl_idle_days)

    db: Session = session_factory()
    pruned = 0
    try:
        query = db.query(Memory).filter(Memory.state == MemoryState.active)
        rows = query.all()
        if project:
            rows = [m for m in rows if (m.metadata_ or {}).get("project") == project]

        for mem in rows:
            if pruned >= batch_limit:
                break
            if engine.is_pinned(mem):
                continue
            if _protected_category_names(db, mem, policy.protected_categories):
                continue
            created = mem.created_at
            if created is None or created > max_age_cutoff:
                continue
            last_access = _last_access(db, mem.id) or created
            if last_access > idle_cutoff:
                continue
            if engine.quarantine(mem.id, reason="ttl_prune", job_id=job_id):
                pruned += 1
                GOVERNANCE_PRUNED_TOTAL.inc()
        return pruned
    finally:
        db.close()
