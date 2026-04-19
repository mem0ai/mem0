from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Episode(Base):
    __tablename__ = "episodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    namespace_id: Mapped[str] = mapped_column(String(36), ForeignKey("namespaces.id"), index=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id"), nullable=True, index=True)
    space_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("memory_spaces.id"), nullable=True, index=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    start_event_id: Mapped[str] = mapped_column(String(36), ForeignKey("memory_events.id"))
    end_event_id: Mapped[str] = mapped_column(String(36), ForeignKey("memory_events.id"))
    summary: Mapped[str] = mapped_column(String(500))
    raw_text: Mapped[str] = mapped_column(String)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    importance_hint: Mapped[str] = mapped_column(String(50), default="normal")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
