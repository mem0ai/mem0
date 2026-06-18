"""Quarantine / lifecycle engine (Fase 3 task_04 / ADR-003)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Callable, Optional
from uuid import UUID

from app.database import SessionLocal
from app.models import Memory, MemoryState, MemoryStatusHistory
from app.utils.db import get_or_create_user
from app.utils.metrics import (
    GOVERNANCE_PURGED_TOTAL,
    GOVERNANCE_QUARANTINED_CURRENT,
    GOVERNANCE_REVERTED_TOTAL,
)
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
GOVERNANCE_ACTOR = "__governance__"


class QuarantineEngine:
    """Reversible governance transitions in SQL + Qdrant payload."""

    def __init__(
        self,
        session_factory=SessionLocal,
        vector_store_provider: Optional[Callable] = None,
    ):
        self._session_factory = session_factory
        self._vector_store_provider = vector_store_provider

    def _vector_store(self):
        if self._vector_store_provider is not None:
            return self._vector_store_provider()
        from app.utils.memory import get_memory_client_safe

        client = get_memory_client_safe()
        if client is None:
            return None
        return client.vector_store

    def _actor_id(self, db: Session) -> UUID:
        return get_or_create_user(db, GOVERNANCE_ACTOR).id

    @staticmethod
    def is_pinned(memory: Memory) -> bool:
        meta = memory.metadata_ or {}
        return bool(meta.get("pinned"))

    def quarantine(self, memory_id: UUID, *, reason: str, job_id: str) -> bool:
        db = self._session_factory()
        try:
            memory = db.query(Memory).filter(Memory.id == memory_id).first()
            if memory is None:
                return False
            if self.is_pinned(memory):
                return False
            if memory.state == MemoryState.quarantined:
                return True

            old_state = memory.state
            memory.state = MemoryState.quarantined
            memory.quarantined_at = datetime.now(UTC)
            meta = dict(memory.metadata_ or {})
            meta["governance_reason"] = reason
            meta["governance_job_id"] = job_id
            memory.metadata_ = meta

            db.add(
                MemoryStatusHistory(
                    memory_id=memory.id,
                    changed_by=self._actor_id(db),
                    old_state=old_state,
                    new_state=MemoryState.quarantined,
                )
            )
            db.commit()

            vs = self._vector_store()
            if vs is not None:
                try:
                    existing = vs.get(str(memory.id)) or {}
                    payload = dict(existing.get("payload") or {})
                    payload["state"] = "quarantined"
                    vs.update(str(memory.id), payload=payload)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("qdrant payload update failed for %s: %s", memory_id, exc)

            GOVERNANCE_QUARANTINED_CURRENT.inc()
            return True
        finally:
            db.close()

    def revert(self, memory_id: UUID) -> bool:
        db = self._session_factory()
        try:
            memory = db.query(Memory).filter(Memory.id == memory_id).first()
            if memory is None or memory.state != MemoryState.quarantined:
                return False

            old_state = memory.state
            memory.state = MemoryState.active
            memory.quarantined_at = None
            meta = dict(memory.metadata_ or {})
            meta.pop("governance_reason", None)
            meta.pop("governance_job_id", None)
            memory.metadata_ = meta

            db.add(
                MemoryStatusHistory(
                    memory_id=memory.id,
                    changed_by=self._actor_id(db),
                    old_state=old_state,
                    new_state=MemoryState.active,
                )
            )
            db.commit()

            vs = self._vector_store()
            if vs is not None:
                try:
                    existing = vs.get(str(memory.id)) or {}
                    payload = dict(existing.get("payload") or {})
                    payload["state"] = "active"
                    vs.update(str(memory.id), payload=payload)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("qdrant revert payload failed for %s: %s", memory_id, exc)

            GOVERNANCE_REVERTED_TOTAL.inc()
            return True
        finally:
            db.close()

    def purge_expired(self, *, older_than_days: int, limit: int = 500) -> int:
        db = self._session_factory()
        cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
        purged = 0
        try:
            rows = (
                db.query(Memory)
                .filter(
                    Memory.state == MemoryState.quarantined,
                    Memory.quarantined_at.isnot(None),
                    Memory.quarantined_at <= cutoff,
                )
                .order_by(Memory.quarantined_at.asc())
                .limit(limit)
                .all()
            )
            vs = self._vector_store()
            for memory in rows:
                point_id = str(memory.id)
                if vs is not None:
                    try:
                        vs.delete(point_id)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("qdrant delete failed for %s: %s", point_id, exc)
                db.delete(memory)
                purged += 1
            if purged:
                db.commit()
                GOVERNANCE_PURGED_TOTAL.inc(purged)
            return purged
        finally:
            db.close()
