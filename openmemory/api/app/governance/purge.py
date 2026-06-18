"""Purge governance job (task_09)."""

from __future__ import annotations

import logging
from typing import Callable, Optional

from app.utils.governance_policy import resolve_policy
from app.utils.quarantine import QuarantineEngine

logger = logging.getLogger(__name__)


def run_purge_job(
    *,
    project: Optional[str],
    job_id: str,
    limit: int = 500,
    session_factory=None,
    quarantine_engine: Optional[QuarantineEngine] = None,
    vector_store_provider: Optional[Callable] = None,
) -> int:
    from app.database import SessionLocal

    factory = session_factory or SessionLocal
    engine = quarantine_engine or QuarantineEngine(
        session_factory=factory,
        vector_store_provider=vector_store_provider,
    )
    policy = resolve_policy(project or "", session_factory=factory)
    return engine.purge_expired(
        older_than_days=policy.quarantine_window_days,
        limit=min(limit, policy.batch_limit),
    )
