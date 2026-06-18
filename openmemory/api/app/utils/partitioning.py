"""Partition routing for the Fase 2 Qdrant partitioning (task_03 / ADR-002 / ADR-003).

The ``PartitionResolver`` is the single place that answers two questions for the
read/write paths:

- which collection is currently served (the blue-green flip pointer,
  ``migration_state.active_collection``); and
- which custom shard key, if any, a project routes to (set only for projects
  promoted to ``partition_tier=dedicated``).

State is read from PostgreSQL and cached in memory; the cache is invalidated
explicitly on flip and on promotion (it is NOT reloaded on every call). When no
``migration_state`` row exists yet (pre-migration), it falls back to the
collection configured by the environment, so the resolver is safe to adopt
before any migration is planned.
"""

import logging
import threading
from dataclasses import dataclass
from typing import Optional

from app.database import SessionLocal
from app.models import MigrationState, PartitionTier, Project

logger = logging.getLogger(__name__)


def _default_collection() -> str:
    """Collection configured by the environment (pre-migration fallback)."""
    try:
        from app.utils.memory import get_default_memory_config

        return get_default_memory_config().get("collection_name", "openmemory")
    except Exception:  # noqa: BLE001 - never let config discovery break routing
        return "openmemory"


@dataclass(frozen=True)
class CollectionRoute:
    """Resolved routing for a project: the active collection and optional shard key."""
    collection: str
    shard_key: Optional[str] = None


@dataclass(frozen=True)
class _Snapshot:
    active_collection: str
    # Only promoted (dedicated) projects appear here: project -> shard_key.
    dedicated: dict


class PartitionResolver:
    """Resolve the active collection and per-project shard key from DB state."""

    def __init__(self, session_factory=SessionLocal, default_collection: Optional[str] = None):
        self._session_factory = session_factory
        self._default_collection = default_collection
        self._snapshot: Optional[_Snapshot] = None
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def route_for(self, project: str) -> CollectionRoute:
        snap = self._get_snapshot()
        return CollectionRoute(
            collection=snap.active_collection,
            shard_key=snap.dedicated.get(project),
        )

    def active_collection(self) -> str:
        return self._get_snapshot().active_collection

    def invalidate(self) -> None:
        """Drop the cached snapshot; the next call reloads from the database.

        Called on collection flip (task_07) and on tenant promotion (task_08).
        """
        with self._lock:
            self._snapshot = None

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _get_snapshot(self) -> _Snapshot:
        snap = self._snapshot
        if snap is not None:
            return snap
        with self._lock:
            if self._snapshot is None:
                self._snapshot = self._load()
            return self._snapshot

    def _load(self) -> _Snapshot:
        fallback = self._default_collection or _default_collection()
        db = self._session_factory()
        try:
            state = (
                db.query(MigrationState)
                .order_by(MigrationState.id.desc())
                .first()
            )
            active = state.active_collection if state else fallback

            dedicated = {
                p.name: p.shard_key
                for p in db.query(Project)
                .filter(Project.partition_tier == PartitionTier.dedicated)
                .all()
                if p.shard_key
            }
            return _Snapshot(active_collection=active, dedicated=dedicated)
        finally:
            db.close()


# Module-level singleton used by the read/write paths (task_04).
partition_resolver = PartitionResolver()
