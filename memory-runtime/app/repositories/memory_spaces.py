from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory_space import MemorySpace


class MemorySpaceRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        namespace_id: str,
        space_type: str,
        name: str,
        agent_id: str | None = None,
        parent_space_id: str | None = None,
    ) -> MemorySpace:
        space = MemorySpace(
            namespace_id=namespace_id,
            space_type=space_type,
            name=name,
            agent_id=agent_id,
            parent_space_id=parent_space_id,
        )
        self.session.add(space)
        self.session.flush()
        return space

    def list_by_agent(self, namespace_id: str, agent_id: str) -> list[MemorySpace]:
        stmt = (
            select(MemorySpace)
            .where(MemorySpace.namespace_id == namespace_id, MemorySpace.agent_id == agent_id)
            .order_by(MemorySpace.space_type.asc())
        )
        return list(self.session.execute(stmt).scalars().all())

    def get_shared_space(self, namespace_id: str) -> MemorySpace | None:
        stmt = select(MemorySpace).where(
            MemorySpace.namespace_id == namespace_id,
            MemorySpace.agent_id.is_(None),
            MemorySpace.space_type == "shared-space",
        )
        return self.session.execute(stmt).scalar_one_or_none()
