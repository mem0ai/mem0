from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.namespace import Namespace


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemorySpace(Base):
    __tablename__ = "memory_spaces"
    __table_args__ = (
        UniqueConstraint("namespace_id", "agent_id", "space_type", name="uq_memory_spaces_scope"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    namespace_id: Mapped[str] = mapped_column(String(36), ForeignKey("namespaces.id"), index=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agents.id"), nullable=True, index=True)
    space_type: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    parent_space_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("memory_spaces.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    namespace: Mapped["Namespace"] = relationship(back_populates="spaces")
    agent: Mapped["Agent | None"] = relationship(back_populates="spaces")
