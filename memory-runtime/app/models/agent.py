from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.memory_space import MemorySpace
    from app.models.namespace import Namespace


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Agent(Base):
    __tablename__ = "agents"
    __table_args__ = (
        UniqueConstraint("namespace_id", "name", name="uq_agents_namespace_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    namespace_id: Mapped[str] = mapped_column(String(36), ForeignKey("namespaces.id"), index=True)
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    source_system: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    namespace: Mapped["Namespace"] = relationship(back_populates="agents")
    spaces: Mapped[list["MemorySpace"]] = relationship(back_populates="agent")
