from __future__ import annotations

from sqlalchemy.orm import Session

from app.repositories.agents import AgentRepository
from app.repositories.namespaces import NamespaceRepository
from app.schemas.adapters import (
    AdapterEventCreate,
    AdapterEventRead,
    AdapterRecallRequest,
    AdapterRecallResponse,
)
from app.schemas.event import EventCreate
from app.schemas.recall import RecallRequest
from app.services.ingestion import IngestionService
from app.services.retrieval import RetrievalService


class AdapterService:
    def __init__(self, session: Session):
        self.session = session
        self.namespaces = NamespaceRepository(session)
        self.agents = AgentRepository(session)
        self.ingestion = IngestionService(session)
        self.retrieval = RetrievalService(session)

    def ingest_event(self, adapter_name: str, payload: AdapterEventCreate) -> AdapterEventRead:
        self._validate_adapter_context(
            adapter_name=adapter_name,
            namespace_id=payload.namespace_id,
            agent_id=payload.agent_id,
        )
        event = self.ingestion.ingest_event(
            EventCreate(
                namespace_id=payload.namespace_id,
                agent_id=payload.agent_id,
                session_id=payload.session_id,
                project_id=payload.project_id,
                source_system=adapter_name,
                event_type=payload.event_type,
                timestamp=payload.timestamp,
                space_hint=payload.space_hint,
                messages=payload.messages,
                metadata=payload.metadata,
                dedupe_key=payload.dedupe_key,
            )
        )
        return AdapterEventRead(adapter=adapter_name, source_system=adapter_name, event=event)

    def recall(self, adapter_name: str, payload: AdapterRecallRequest) -> AdapterRecallResponse:
        self._validate_adapter_context(
            adapter_name=adapter_name,
            namespace_id=payload.namespace_id,
            agent_id=payload.agent_id,
        )
        recall_response = self.retrieval.recall(
            RecallRequest(
                namespace_id=payload.namespace_id,
                agent_id=payload.agent_id,
                session_id=payload.session_id,
                query=payload.query,
                context_budget_tokens=payload.context_budget_tokens,
                space_filter=payload.space_filter,
            )
        )
        return AdapterRecallResponse(
            adapter=adapter_name,
            source_system=adapter_name,
            brief=recall_response.brief,
            trace=recall_response.trace,
        )

    def _validate_adapter_context(self, *, adapter_name: str, namespace_id: str, agent_id: str | None) -> None:
        namespace = self.namespaces.get_by_id(namespace_id)
        if namespace is None:
            raise LookupError(f"Namespace '{namespace_id}' not found")

        if namespace.source_systems and adapter_name not in namespace.source_systems:
            raise ValueError(f"Adapter '{adapter_name}' is not enabled for namespace '{namespace_id}'")

        if agent_id is None:
            return

        agent = self.agents.get_by_id(agent_id)
        if agent is None or agent.namespace_id != namespace_id:
            raise LookupError(f"Agent '{agent_id}' not found in namespace")
        if agent.source_system.strip().lower() != adapter_name:
            raise ValueError(f"Agent '{agent_id}' does not belong to adapter '{adapter_name}'")
