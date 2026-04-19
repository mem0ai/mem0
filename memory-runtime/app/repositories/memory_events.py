from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.memory_event import MemoryEvent


class MemoryEventRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        namespace_id: str,
        agent_id: str | None,
        space_id: str | None,
        session_id: str | None,
        project_id: str | None,
        source_system: str,
        event_type: str,
        payload_json: dict[str, Any],
        event_ts: datetime,
        dedupe_key: str | None,
    ) -> MemoryEvent:
        event = MemoryEvent(
            namespace_id=namespace_id,
            agent_id=agent_id,
            space_id=space_id,
            session_id=session_id,
            project_id=project_id,
            source_system=source_system,
            event_type=event_type,
            payload_json=payload_json,
            event_ts=event_ts,
            dedupe_key=dedupe_key,
        )
        self.session.add(event)
        self.session.flush()
        return event

    def get_by_dedupe_key(
        self,
        *,
        namespace_id: str,
        agent_id: str | None,
        dedupe_key: str,
    ) -> MemoryEvent | None:
        stmt = (
            select(MemoryEvent)
            .where(MemoryEvent.namespace_id == namespace_id)
            .where(MemoryEvent.dedupe_key == dedupe_key)
        )
        if agent_id is None:
            stmt = stmt.where(MemoryEvent.agent_id.is_(None))
        else:
            stmt = stmt.where(MemoryEvent.agent_id == agent_id)
        return self.session.execute(stmt).scalar_one_or_none()
