"""Batch exact dedup governance job (task_07)."""

from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from typing import Callable, Optional

from app.database import SessionLocal
from app.models import Memory, MemoryState
from app.utils.governance_policy import resolve_policy
from app.utils.metrics import GOVERNANCE_DEDUPED_TOTAL
from app.utils.quarantine import QuarantineEngine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _content_hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def run_dedup_job(
    *,
    project: Optional[str],
    job_id: str,
    limit: int = 500,
    session_factory=SessionLocal,
    quarantine_engine: Optional[QuarantineEngine] = None,
    vector_store_provider: Optional[Callable] = None,
) -> int:
    """Quarantine exact duplicate memories within a project scope."""
    engine = quarantine_engine or QuarantineEngine(
        session_factory=session_factory,
        vector_store_provider=vector_store_provider,
    )
    policy = resolve_policy(project or "", session_factory=session_factory)
    batch_limit = min(limit, policy.batch_limit)

    db: Session = session_factory()
    deduped = 0
    try:
        query = db.query(Memory).filter(Memory.state == MemoryState.active)
        if project:
            # Filter via metadata project tag when present.
            rows = query.all()
            rows = [
                m
                for m in rows
                if (m.metadata_ or {}).get("project") == project or project is None
            ]
        else:
            rows = query.limit(batch_limit * 4).all()

        groups: dict[str, list[Memory]] = defaultdict(list)
        for mem in rows:
            h = (mem.metadata_ or {}).get("hash") or _content_hash(mem.content)
            groups[h].append(mem)

        for _hash, mems in groups.items():
            if len(mems) < 2:
                continue
            mems.sort(key=lambda m: m.created_at or m.id)
            # mems[0] is the canonical record (oldest); mems[1:] are duplicates.
            for dup in mems[1:]:
                if deduped >= batch_limit:
                    return deduped
                if engine.is_pinned(dup):
                    continue
                if engine.quarantine(dup.id, reason="dedup", job_id=job_id):
                    deduped += 1
                    GOVERNANCE_DEDUPED_TOTAL.inc()
        return deduped
    finally:
        db.close()
