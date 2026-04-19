from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.memory_unit import MemoryUnit
from app.models.memory_space import MemorySpace


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
        supersedes_memory_id: str | None = None,
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
            supersedes_memory_id=supersedes_memory_id,
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

    def list_active_in_space(
        self,
        *,
        namespace_id: str,
        primary_space_id: str,
        kind: str,
    ) -> list[MemoryUnit]:
        stmt = select(MemoryUnit).where(
            MemoryUnit.namespace_id == namespace_id,
            MemoryUnit.primary_space_id == primary_space_id,
            MemoryUnit.kind == kind,
            MemoryUnit.status == "active",
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_by_id(self, memory_unit_id: str) -> MemoryUnit | None:
        return self.session.get(MemoryUnit, memory_unit_id)

    def list_active_with_space(
        self,
        *,
        namespace_id: str,
        agent_id: str | None,
        space_types: list[str] | None = None,
    ) -> list[tuple[MemoryUnit, str]]:
        stmt: Select[tuple[MemoryUnit, str]] = (
            select(MemoryUnit, MemorySpace.space_type)
            .join(MemorySpace, MemoryUnit.primary_space_id == MemorySpace.id)
            .where(MemoryUnit.namespace_id == namespace_id)
            .where(MemoryUnit.status == "active")
            .order_by(MemoryUnit.updated_at.desc())
        )
        if agent_id is not None:
            stmt = stmt.where(MemoryUnit.agent_id == agent_id)
        if space_types:
            stmt = stmt.where(MemorySpace.space_type.in_(space_types))
        return list(self.session.execute(stmt).all())

    def get_with_space(self, memory_unit_id: str) -> tuple[MemoryUnit, str] | None:
        stmt: Select[tuple[MemoryUnit, str]] = (
            select(MemoryUnit, MemorySpace.space_type)
            .join(MemorySpace, MemoryUnit.primary_space_id == MemorySpace.id)
            .where(MemoryUnit.id == memory_unit_id)
        )
        return self.session.execute(stmt).one_or_none()

    def delete(self, memory_unit: MemoryUnit) -> None:
        self.session.delete(memory_unit)
        self.session.flush()
