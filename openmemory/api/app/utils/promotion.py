"""Promote a giant project to a dedicated custom shard key (task_08 / ADR-002).

Promotion keeps the same collection (so cross-project search stays cheap) but
moves a project's points onto a dedicated shard key, localizing its requests.
Steps, all idempotent so the operation is safely re-runnable/resumable:

1. create the shard key (no-op if it already exists);
2. rewrite the project's points into that shard key (upsert preserves ids);
3. mark the project ``dedicated`` with its shard key and invalidate the resolver
   so subsequent reads pass ``shard_key_selector`` (task_04).

The vector store is injected so this is testable without a live Qdrant.
"""

import logging
import os
from typing import Callable, Optional

from qdrant_client.models import PointStruct

from app.database import SessionLocal
from app.models import PartitionTier, Project
from app.utils.partitioning import partition_resolver

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = int(os.getenv("PROMOTION_BATCH_SIZE", "256"))


class PromotionService:
    def __init__(
        self,
        session_factory=SessionLocal,
        vector_store_provider: Optional[Callable] = None,
        resolver=partition_resolver,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ):
        self._session_factory = session_factory
        self._vs_provider = vector_store_provider
        self._resolver = resolver
        self._batch_size = max(1, int(batch_size))

    def promote(self, project: str) -> dict:
        shard_key = project
        vs = self._vs_provider()

        # 1. Create the dedicated shard key (idempotent).
        try:
            vs.create_shard_key(shard_key)
        except Exception as e:  # noqa: BLE001 - already exists / transient
            logger.debug("create_shard_key(%s) ignored: %s", shard_key, e)

        # 2. Rewrite the project's points into the shard key.
        filt = vs._create_filter({"project": project})
        offset = None
        moved = 0
        while True:
            records, offset = vs.client.scroll(
                collection_name=vs.collection_name,
                scroll_filter=filt,
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
                vs.client.upsert(
                    collection_name=vs.collection_name,
                    points=points,
                    shard_key_selector=shard_key,
                )
                moved += len(points)
            if offset is None:
                break

        # 3. Mark the project dedicated and refresh routing.
        db = self._session_factory()
        try:
            proj = db.query(Project).filter(Project.name == project).first()
            if proj is None:
                proj = Project(name=project)
                db.add(proj)
            proj.partition_tier = PartitionTier.dedicated
            proj.shard_key = shard_key
            db.commit()
        finally:
            db.close()
        self._resolver.invalidate()

        logger.info("promoted project %s to shard_key %s (%s points)", project, shard_key, moved)
        return {"project": project, "shard_key": shard_key, "moved": moved}


def default_promotion_service() -> PromotionService:
    from app.utils.memory import get_memory_client

    def _vs():
        return get_memory_client().vector_store

    return PromotionService(vector_store_provider=_vs)
