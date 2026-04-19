from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.repositories.agents import AgentRepository
from app.repositories.episodes import EpisodeRepository
from app.repositories.jobs import JobRepository
from app.repositories.memory_events import MemoryEventRepository
from app.repositories.memory_spaces import MemorySpaceRepository
from app.repositories.namespaces import NamespaceRepository
from app.schemas.event import EventCreate, EventMessage, EventRead


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IngestionService:
    def __init__(self, session: Session):
        self.session = session
        self.namespaces = NamespaceRepository(session)
        self.agents = AgentRepository(session)
        self.spaces = MemorySpaceRepository(session)
        self.events = MemoryEventRepository(session)
        self.episodes = EpisodeRepository(session)
        self.jobs = JobRepository(session)

    def ingest_event(self, payload: EventCreate) -> EventRead:
        namespace = self.namespaces.get_by_id(payload.namespace_id)
        if namespace is None:
            raise LookupError(f"Namespace '{payload.namespace_id}' not found")

        agent = None
        if payload.agent_id is not None:
            agent = self.agents.get_by_id(payload.agent_id)
            if agent is None or agent.namespace_id != payload.namespace_id:
                raise LookupError(f"Agent '{payload.agent_id}' not found in namespace")

        normalized_messages = self.normalize_messages(payload.messages)
        event_ts = payload.timestamp or _utcnow()
        project_id = payload.project_id or self._metadata_project_id(payload.metadata)
        space = self.resolve_target_space(
            namespace_mode=namespace.mode,
            namespace_id=payload.namespace_id,
            agent_id=payload.agent_id,
            space_hint=payload.space_hint,
        )

        normalized_payload = {
            "messages": [message.model_dump() for message in normalized_messages],
            "metadata": payload.metadata,
        }
        dedupe_key = payload.dedupe_key or self.compute_dedupe_key(
            namespace_id=payload.namespace_id,
            agent_id=payload.agent_id,
            session_id=payload.session_id,
            source_system=payload.source_system,
            event_type=payload.event_type,
            normalized_payload=normalized_payload,
        )

        event = self.events.create(
            namespace_id=payload.namespace_id,
            agent_id=payload.agent_id,
            space_id=space.id if space else None,
            session_id=payload.session_id,
            project_id=project_id,
            source_system=payload.source_system.strip().lower(),
            event_type=payload.event_type.strip().lower(),
            payload_json=normalized_payload,
            event_ts=event_ts,
            dedupe_key=dedupe_key,
        )

        raw_text = self.build_raw_text(normalized_messages)
        episode = self.episodes.create(
            namespace_id=payload.namespace_id,
            agent_id=payload.agent_id,
            space_id=space.id if space else None,
            session_id=payload.session_id,
            start_event_id=event.id,
            end_event_id=event.id,
            summary=self.summarize_event(payload.event_type, normalized_messages),
            raw_text=raw_text,
            token_count=self.estimate_token_count(raw_text),
            importance_hint=self.estimate_importance_hint(payload.event_type, normalized_messages),
        )
        self.jobs.create(
            job_type="memory_consolidation",
            payload_json={
                "episode_id": episode.id,
                "space_type": space.space_type if space else "session-space",
            },
        )

        self.session.commit()
        self.session.refresh(event)

        return EventRead(
            id=event.id,
            episode_id=episode.id,
            namespace_id=event.namespace_id,
            agent_id=event.agent_id,
            space_id=event.space_id,
            session_id=event.session_id,
            project_id=event.project_id,
            source_system=event.source_system,
            event_type=event.event_type,
            dedupe_key=event.dedupe_key,
            event_ts=event.event_ts,
            ingested_at=event.ingested_at,
            payload_json=event.payload_json,
        )

    @staticmethod
    def normalize_messages(messages: list[EventMessage]) -> list[EventMessage]:
        normalized: list[EventMessage] = []
        for message in messages:
            content = " ".join(message.content.split())
            normalized.append(EventMessage(role=message.role, content=content))
        if not normalized:
            raise ValueError("At least one valid message is required")
        return normalized

    @staticmethod
    def build_raw_text(messages: list[EventMessage]) -> str:
        return "\n".join(f"{message.role}: {message.content}" for message in messages)

    @staticmethod
    def estimate_token_count(raw_text: str) -> int:
        return len(raw_text.split())

    @staticmethod
    def summarize_event(event_type: str, messages: list[EventMessage]) -> str:
        first_content = messages[0].content
        truncated = first_content[:120]
        if len(first_content) > 120:
            truncated += "..."
        return f"{event_type.strip().lower()}: {truncated}"

    @staticmethod
    def estimate_importance_hint(event_type: str, messages: list[EventMessage]) -> str:
        if event_type.strip().lower() in {"decision", "architecture_decision"}:
            return "high"
        if any(message.role == "tool" for message in messages):
            return "medium"
        return "normal"

    @staticmethod
    def compute_dedupe_key(
        *,
        namespace_id: str,
        agent_id: str | None,
        session_id: str | None,
        source_system: str,
        event_type: str,
        normalized_payload: dict,
    ) -> str:
        raw = json.dumps(
            {
                "namespace_id": namespace_id,
                "agent_id": agent_id,
                "session_id": session_id,
                "source_system": source_system.strip().lower(),
                "event_type": event_type.strip().lower(),
                "payload": normalized_payload,
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _metadata_project_id(metadata: dict[str, str | int | float | bool | None]) -> str | None:
        project_id = metadata.get("project_id")
        return str(project_id) if project_id is not None else None

    def resolve_target_space(
        self,
        *,
        namespace_mode: str,
        namespace_id: str,
        agent_id: str | None,
        space_hint: str | None,
    ):
        if space_hint == "shared-space":
            space = self.spaces.get_shared_space(namespace_id)
            if space is None:
                raise LookupError("Shared space not found for namespace")
            return space

        if agent_id is None:
            if namespace_mode == "shared":
                space = self.spaces.get_shared_space(namespace_id)
                if space is not None:
                    return space
            return None

        effective_hint = space_hint or "session-space"
        space = self.spaces.get_by_type(namespace_id=namespace_id, agent_id=agent_id, space_type=effective_hint)
        if space is None:
            raise LookupError(f"Space '{effective_hint}' not found for agent")
        return space
