from __future__ import annotations

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.models.episode import Episode
from app.models.memory_space import MemorySpace


class EpisodeRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        namespace_id: str,
        agent_id: str | None,
        space_id: str | None,
        session_id: str | None,
        start_event_id: str,
        end_event_id: str,
        summary: str,
        raw_text: str,
        token_count: int,
        importance_hint: str,
    ) -> Episode:
        episode = Episode(
            namespace_id=namespace_id,
            agent_id=agent_id,
            space_id=space_id,
            session_id=session_id,
            start_event_id=start_event_id,
            end_event_id=end_event_id,
            summary=summary,
            raw_text=raw_text,
            token_count=token_count,
            importance_hint=importance_hint,
        )
        self.session.add(episode)
        self.session.flush()
        return episode

    def list_for_recall(
        self,
        *,
        namespace_id: str,
        agent_id: str | None,
        session_id: str | None,
        space_types: list[str],
    ) -> list[tuple[Episode, str]]:
        stmt: Select[tuple[Episode, str]] = (
            select(Episode, MemorySpace.space_type)
            .join(MemorySpace, Episode.space_id == MemorySpace.id)
            .where(Episode.namespace_id == namespace_id)
            .where(MemorySpace.space_type.in_(space_types))
        )

        if agent_id is not None:
            stmt = stmt.where((Episode.agent_id == agent_id) | (Episode.agent_id.is_(None)))

        if session_id is not None:
            stmt = stmt.order_by((Episode.session_id == session_id).desc(), Episode.created_at.desc())
        else:
            stmt = stmt.order_by(Episode.created_at.desc())

        return list(self.session.execute(stmt).all())
