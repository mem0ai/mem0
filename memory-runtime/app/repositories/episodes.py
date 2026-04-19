from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.episode import Episode


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
