from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.agents import AgentRepository
from app.repositories.memory_spaces import MemorySpaceRepository
from app.repositories.namespaces import NamespaceRepository
from app.schemas.namespace import AgentCreate, AgentRead, NamespaceCreate, NamespaceRead


class NamespaceService:
    def __init__(self, session: Session):
        self.session = session
        self.namespaces = NamespaceRepository(session)
        self.agents = AgentRepository(session)
        self.spaces = MemorySpaceRepository(session)

    def create_namespace(self, payload: NamespaceCreate) -> NamespaceRead:
        if self.namespaces.get_by_name(payload.name):
            raise ValueError(f"Namespace '{payload.name}' already exists")

        namespace = self.namespaces.create(
            name=payload.name,
            mode=payload.mode,
            source_systems=payload.source_systems,
        )

        if payload.mode == "shared":
            self.spaces.create(
                namespace_id=namespace.id,
                space_type="shared-space",
                name="Shared Space",
            )

        self.session.commit()
        self.session.refresh(namespace)
        return NamespaceRead.model_validate(namespace)

    def get_namespace(self, namespace_id: str) -> NamespaceRead | None:
        namespace = self.namespaces.get_by_id(namespace_id)
        if namespace is None:
            return None
        return NamespaceRead.model_validate(namespace)

    def create_agent(self, namespace_id: str, payload: AgentCreate) -> AgentRead:
        namespace = self.namespaces.get_by_id(namespace_id)
        if namespace is None:
            raise LookupError(f"Namespace '{namespace_id}' not found")

        if self.agents.get_by_name(namespace_id, payload.name):
            raise ValueError(f"Agent '{payload.name}' already exists in namespace")

        agent = self.agents.create(
            namespace_id=namespace_id,
            name=payload.name,
            source_system=payload.source_system,
            external_ref=payload.external_ref,
        )

        default_spaces = [
            ("agent-core", "Agent Core"),
            ("project-space", "Project Space"),
            ("session-space", "Session Space"),
        ]
        for space_type, name in default_spaces:
            self.spaces.create(
                namespace_id=namespace_id,
                agent_id=agent.id,
                space_type=space_type,
                name=name,
            )

        self.session.commit()
        self.session.refresh(agent)
        return AgentRead.model_validate(agent)
