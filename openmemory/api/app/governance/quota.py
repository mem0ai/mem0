"""Quota enforcement governance job (task_06 / ADR-005).

Aplica o teto ``max_memories`` por project. Com ação ``alert`` apenas contabiliza
projects acima do teto; com ação ``enforce`` quarentena os candidatos menos
relevantes (mais antigos / menos acessados) até o ``memory_count`` voltar ao teto,
respeitando memórias pinned e ``protected_categories``. O enforcement é
assíncrono (roda no governance-worker), nunca no caminho de escrita.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from app.database import SessionLocal
from app.governance.ttl_prune import _last_access, _protected_category_names
from app.models import Memory, MemoryState
from app.utils.governance_policy import resolve_policy
from app.utils.metrics import (
    GOVERNANCE_QUOTA_ENFORCED_TOTAL,
    GOVERNANCE_QUOTA_OVER_LIMIT_PROJECTS,
)
from app.utils.quarantine import QuarantineEngine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def run_enforce_quota_job(
    *,
    project: Optional[str],
    job_id: str,
    limit: int = 500,
    session_factory=SessionLocal,
    quarantine_engine: Optional[QuarantineEngine] = None,
    vector_store_provider: Optional[Callable] = None,
) -> int:
    """Enforce ``max_memories`` for ``project``.

    Returns the number of memories quarantined (always 0 in ``alert`` mode or when
    no project/teto applies).
    """
    if not project:
        # Quota é por project; o escopo global não tem teto.
        return 0

    policy = resolve_policy(project, session_factory=session_factory)
    if policy.max_memories is None:
        return 0

    engine = quarantine_engine or QuarantineEngine(
        session_factory=session_factory,
        vector_store_provider=vector_store_provider,
    )
    batch_limit = min(limit, policy.batch_limit)

    db: Session = session_factory()
    enforced = 0
    try:
        rows = [
            m
            for m in db.query(Memory).filter(Memory.state == MemoryState.active).all()
            if (m.metadata_ or {}).get("project") == project
        ]
        excess = len(rows) - policy.max_memories
        if excess <= 0:
            GOVERNANCE_QUOTA_OVER_LIMIT_PROJECTS.set(0)
            return 0

        # Project acima do teto.
        GOVERNANCE_QUOTA_OVER_LIMIT_PROJECTS.set(1)
        if policy.max_memories_action != "enforce":
            logger.info(
                "project %s over max_memories by %s (action=alert)", project, excess
            )
            return 0

        # Candidatos menos relevantes primeiro: mais antigos / menos acessados.
        def _sort_key(mem: Memory):
            return _last_access(db, mem.id) or mem.created_at

        rows.sort(key=_sort_key)
        for mem in rows:
            if excess <= 0 or enforced >= batch_limit:
                break
            if engine.is_pinned(mem):
                continue
            if _protected_category_names(db, mem, policy.protected_categories):
                continue
            if engine.quarantine(mem.id, reason="enforce_quota", job_id=job_id):
                enforced += 1
                excess -= 1
                GOVERNANCE_QUOTA_ENFORCED_TOTAL.inc()
        GOVERNANCE_QUOTA_OVER_LIMIT_PROJECTS.set(0 if excess <= 0 else 1)
        return enforced
    finally:
        db.close()
