"""Dedicated blue-green migration worker (task_06 / ADR-003).

Provisions the target (green) collection — with the tenant index created *before*
any data load (ADR-002) — and copies points from the source (blue) collection in
paginated batches via Qdrant ``scroll`` + ``upsert``, checkpointing the scroll
offset in ``migration_state.scroll_cursor`` so the copy resumes idempotently
after a restart. Runs as its own process, isolated from the write worker, so the
heavy copy does not compete with the write queue SLA.

The copy preserves point ids, so ``upsert`` is idempotent: re-running a batch (or
resuming from a checkpoint) never duplicates points.
"""

import json
import logging
import os
from typing import Callable, Optional

from qdrant_client.models import PointStruct

from app.database import SessionLocal
from app.models import MigrationState, MigrationStatus
from app.utils.metrics import MIGRATION_POINTS_COPIED

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = int(os.getenv("MIGRATION_BATCH_SIZE", "256"))


def _int_env(name: str) -> Optional[int]:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else None


def _bool_env(name: str) -> bool:
    return (os.getenv(name) or "").strip().lower() in ("1", "true", "yes", "on")


class MigrationWorker:
    """Copy points from the source to the target collection with checkpointing."""

    def __init__(
        self,
        session_factory=SessionLocal,
        client=None,
        provisioner: Optional[Callable[[str], None]] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self._session_factory = session_factory
        self._client = client  # raw QdrantClient (scroll/upsert)
        self._provisioner = provisioner  # callable(target_collection) -> None
        self._batch_size = max(1, int(batch_size))

    # ------------------------------------------------------------------ #
    # State helpers
    # ------------------------------------------------------------------ #
    def _load_state(self, db) -> MigrationState:
        state = db.query(MigrationState).order_by(MigrationState.id.desc()).first()
        if state is None:
            raise RuntimeError("no migration_state row; plan a migration first")
        return state

    # ------------------------------------------------------------------ #
    # Steps
    # ------------------------------------------------------------------ #
    def provision_target(self) -> None:
        """Create the target (green) collection with indexes before any load."""
        db = self._session_factory()
        try:
            target = self._load_state(db).target_collection
        finally:
            db.close()
        if self._provisioner is None:
            raise RuntimeError("no provisioner configured")
        logger.info("provisioning target collection %s", target)
        self._provisioner(target)

    def copy_once(self) -> bool:
        """Copy a single batch source -> target. Returns True if more remain."""
        db = self._session_factory()
        try:
            state = self._load_state(db)
            offset = json.loads(state.scroll_cursor) if state.scroll_cursor else None

            records, next_offset = self._client.scroll(
                collection_name=state.source_collection,
                offset=offset,
                limit=self._batch_size,
                with_payload=True,
                with_vectors=True,
            )

            if records:
                points = [
                    PointStruct(id=r.id, vector=r.vector, payload=r.payload)
                    for r in records
                ]
                self._client.upsert(collection_name=state.target_collection, points=points)
                MIGRATION_POINTS_COPIED.inc(len(points))

            if state.status == MigrationStatus.planned:
                state.status = MigrationStatus.copying

            if next_offset is None:
                # Copy complete; awaiting validation + flip (task_07).
                state.status = MigrationStatus.validating
            else:
                state.scroll_cursor = json.dumps(next_offset, default=str)

            db.commit()
            logger.info(
                "copied %s points (next_offset=%s, status=%s)",
                len(records) if records else 0,
                next_offset,
                state.status.value,
            )
            return next_offset is not None
        finally:
            db.close()

    def run_copy(self) -> None:
        """Provision the target and copy all batches until the source is drained."""
        self.provision_target()
        while self.copy_once():
            pass
        logger.info("migration copy complete (status -> validating)")


# --------------------------------------------------------------------------- #
# Default wiring (production)
# --------------------------------------------------------------------------- #
def _default_provisioner_factory(client) -> Callable[[str], None]:
    def _provision(target: str) -> None:
        from mem0.vector_stores.qdrant import Qdrant

        dims = _int_env("EMBEDDER_DIMS") or _int_env("QDRANT_DIMS") or 768
        # Constructing Qdrant creates the collection + indexes (tenant index
        # before load) on the shared client (ADR-002).
        Qdrant(
            collection_name=target,
            embedding_model_dims=dims,
            client=client,
            shard_number=_int_env("QDRANT_SHARD_NUMBER"),
            replication_factor=_int_env("QDRANT_REPLICATION_FACTOR"),
            custom_sharding=_bool_env("QDRANT_CUSTOM_SHARDING"),
        )

    return _provision


def migration_worker_from_env() -> MigrationWorker:
    from app.utils.memory import get_memory_client

    mc = get_memory_client()
    if mc is None:
        raise RuntimeError("memory client unavailable")
    client = mc.vector_store.client
    return MigrationWorker(client=client, provisioner=_default_provisioner_factory(client))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    migration_worker_from_env().run_copy()


if __name__ == "__main__":
    main()
