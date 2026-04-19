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
            stmt = stmt.where(
                (Episode.agent_id == agent_id)
                | (Episode.agent_id.is_(None))
                | (MemorySpace.space_type == "shared-space")
            )

        if session_id is not None:
            stmt = stmt.order_by((Episode.session_id == session_id).desc(), Episode.created_at.desc())
        else:
            stmt = stmt.order_by(Episode.created_at.desc())

        return list(self.session.execute(stmt).all())

    def list_by_session(
        self,
        *,
        namespace_id: str,
        agent_id: str | None,
        session_id: str,
    ) -> list[tuple[Episode, str]]:
        stmt: Select[tuple[Episode, str]] = (
            select(Episode, MemorySpace.space_type)
            .join(MemorySpace, Episode.space_id == MemorySpace.id)
            .where(Episode.namespace_id == namespace_id)
            .where(Episode.session_id == session_id)
            .order_by(Episode.created_at.desc())
        )
        if agent_id is not None:
            stmt = stmt.where(Episode.agent_id == agent_id)
        return list(self.session.execute(stmt).all())

    def get_by_id(self, episode_id: str) -> Episode | None:
        return self.session.get(Episode, episode_id)

    def get_by_event_id(self, event_id: str) -> Episode | None:
        stmt = (
            select(Episode)
            .where(Episode.start_event_id == event_id)
            .where(Episode.end_event_id == event_id)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def delete(self, episode: Episode) -> None:
        self.session.delete(episode)
        self.session.flush()
