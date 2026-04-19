from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryUnit(Base):
    __tablename__ = "memory_units"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    namespace_id: Mapped[str] = mapped_column(String(36), ForeignKey("namespaces.id"), index=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id"), nullable=True, index=True)
    primary_space_id: Mapped[str] = mapped_column(String(36), ForeignKey("memory_spaces.id"), index=True)
    kind: Mapped[str] = mapped_column(String(50))
    scope: Mapped[str] = mapped_column(String(50))
    content: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(String(500))
    importance_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    freshness_score: Mapped[float] = mapped_column(Float, default=0.0)
    durability_score: Mapped[float] = mapped_column(Float, default=0.0)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_from_episode_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("episodes.id"), nullable=True)
    supersedes_memory_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("memory_units.id"), nullable=True)
    merge_key: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
