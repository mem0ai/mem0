"""Blue-green migration control: validation, atomic flip, rollback (task_07 / ADR-003).

Orchestrates the cutover of the partition migration:

- ``start``  — record/refresh the migration_state row (source=blue, target=green,
  active=blue) and enable dual-write so the target stays fresh while the worker
  copies (task_06);
- ``validate`` — compare point counts between source and target (parity gate);
- ``flip``   — atomically repoint ``active_collection`` to the target, disable
  dual-write, mark ``flipped``, and invalidate the resolver cache;
- ``rollback`` — repoint ``active_collection`` back to the source.

Counts come from an injected ``count_fn(collection) -> int`` so this is testable
without a live Qdrant.
"""

import logging
from typing import Callable, Optional

from app.database import SessionLocal
from app.models import MigrationState, MigrationStatus
from app.utils.partitioning import partition_resolver

logger = logging.getLogger(__name__)


class MigrationError(RuntimeError):
    """Raised when a control operation cannot proceed (e.g. flip before parity)."""


class MigrationControl:
    def __init__(self, session_factory=SessionLocal, count_fn: Optional[Callable[[str], int]] = None,
                 resolver=partition_resolver):
        self._session_factory = session_factory
        self._count_fn = count_fn
        self._resolver = resolver

    def _latest(self, db) -> Optional[MigrationState]:
        return db.query(MigrationState).order_by(MigrationState.id.desc()).first()

    # ------------------------------------------------------------------ #
    def start(self, source: str, target: str) -> dict:
        """Plan a migration: source->target, active=source, dual-write ON. Idempotent."""
        if source == target:
            raise MigrationError("source and target collections must differ")
        db = self._session_factory()
        try:
            state = self._latest(db)
            if state is None:
                state = MigrationState(
                    source_collection=source,
                    target_collection=target,
                    active_collection=source,
                )
                db.add(state)
            else:
                state.source_collection = source
                state.target_collection = target
                state.active_collection = source
            state.dual_write_enabled = True
            state.status = MigrationStatus.planned
            state.scroll_cursor = None
            db.commit()
            result = self._to_dict(state)
        finally:
            db.close()
        self._resolver.invalidate()
        return result

    def validate(self) -> dict:
        """Compare source/target counts. ``ok`` when the target has caught up."""
        if self._count_fn is None:
            raise MigrationError("no count function configured")
        db = self._session_factory()
        try:
            state = self._require(db)
            source, target = state.source_collection, state.target_collection
        finally:
            db.close()
        source_count = self._count_fn(source)
        target_count = self._count_fn(target)
        return {
            "ok": target_count >= source_count,
            "source_collection": source,
            "target_collection": target,
            "source_count": source_count,
            "target_count": target_count,
        }

    def flip(self) -> dict:
        """Atomically repoint active->target after a successful parity check."""
        report = self.validate()
        if not report["ok"]:
            raise MigrationError(
                f"parity check failed: target {report['target_count']} < source {report['source_count']}"
            )
        db = self._session_factory()
        try:
            state = self._require(db)
            state.active_collection = state.target_collection
            state.dual_write_enabled = False  # target is now active; no mirror needed
            state.status = MigrationStatus.flipped
            db.commit()
            result = self._to_dict(state)
        finally:
            db.close()
        self._resolver.invalidate()
        return result

    def rollback(self) -> dict:
        """Repoint active back to the source (reversal after/around a flip)."""
        db = self._session_factory()
        try:
            state = self._require(db)
            state.active_collection = state.source_collection
            state.dual_write_enabled = False
            state.status = MigrationStatus.rolled_back
            db.commit()
            result = self._to_dict(state)
        finally:
            db.close()
        self._resolver.invalidate()
        return result

    # ------------------------------------------------------------------ #
    def _require(self, db) -> MigrationState:
        state = self._latest(db)
        if state is None:
            raise MigrationError("no migration planned; call start first")
        return state

    @staticmethod
    def _to_dict(state: MigrationState) -> dict:
        return {
            "source_collection": state.source_collection,
            "target_collection": state.target_collection,
            "active_collection": state.active_collection,
            "dual_write_enabled": state.dual_write_enabled,
            "status": state.status.value,
        }


def default_count_fn() -> Callable[[str], int]:
    """Count points in a collection via the shared Qdrant client."""
    from app.utils.memory import get_memory_client

    def _count(collection: str) -> int:
        client = get_memory_client().vector_store.client
        return client.count(collection_name=collection, exact=True).count

    return _count
