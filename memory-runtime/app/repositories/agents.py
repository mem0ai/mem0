from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent import Agent


class AgentRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        namespace_id: str,
        name: str,
        source_system: str,
        external_ref: str | None = None,
    ) -> Agent:
        agent = Agent(
            namespace_id=namespace_id,
            name=name,
            source_system=source_system,
            external_ref=external_ref,
        )
        self.session.add(agent)
        self.session.flush()
        return agent

    def get_by_id(self, agent_id: str) -> Agent | None:
        return self.session.get(Agent, agent_id)

    def get_by_name(self, namespace_id: str, name: str) -> Agent | None:
        stmt = select(Agent).where(Agent.namespace_id == namespace_id, Agent.name == name)
        return self.session.execute(stmt).scalar_one_or_none()
