from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory_unit import MemoryUnit


class MemoryUnitRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        namespace_id: str,
        agent_id: str | None,
        primary_space_id: str,
        kind: str,
        scope: str,
        content: str,
        summary: str,
        merge_key: str,
        created_from_episode_id: str | None,
        importance_score: float = 0.0,
        confidence_score: float = 0.8,
        freshness_score: float = 1.0,
        durability_score: float = 0.8,
    ) -> MemoryUnit:
        memory = MemoryUnit(
            namespace_id=namespace_id,
            agent_id=agent_id,
            primary_space_id=primary_space_id,
            kind=kind,
            scope=scope,
            content=content,
            summary=summary,
            merge_key=merge_key,
            created_from_episode_id=created_from_episode_id,
            importance_score=importance_score,
            confidence_score=confidence_score,
            freshness_score=freshness_score,
            durability_score=durability_score,
        )
        self.session.add(memory)
        self.session.flush()
        return memory

    def find_by_merge_key(
        self,
        *,
        namespace_id: str,
        primary_space_id: str,
        merge_key: str,
    ) -> MemoryUnit | None:
        stmt = select(MemoryUnit).where(
            MemoryUnit.namespace_id == namespace_id,
            MemoryUnit.primary_space_id == primary_space_id,
            MemoryUnit.merge_key == merge_key,
            MemoryUnit.status == "active",
        )
        return self.session.execute(stmt).scalar_one_or_none()
