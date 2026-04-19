from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.schemas.event import ALLOWED_SPACE_HINTS, EventMessage, EventRead
from app.schemas.recall import MemoryBrief, RecallTrace


class AdapterEventCreate(BaseModel):
    namespace_id: str
    agent_id: str | None = None
    session_id: str | None = None
    project_id: str | None = None
    event_type: str = Field(..., min_length=2, max_length=100)
    timestamp: datetime | None = None
    space_hint: str | None = None
    messages: list[EventMessage] = Field(..., min_length=1)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    dedupe_key: str | None = None

    @field_validator("space_hint")
    @classmethod
    def validate_space_hint(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        if normalized not in ALLOWED_SPACE_HINTS:
            raise ValueError(f"Unsupported space_hint '{value}'")
        return normalized


class AdapterEventRead(BaseModel):
    adapter: str
    source_system: str
    event: EventRead


class AdapterRecallRequest(BaseModel):
    namespace_id: str
    agent_id: str | None = None
    session_id: str | None = None
    query: str = Field(..., min_length=3)
    context_budget_tokens: int = Field(..., gt=0)
    space_filter: list[str] | None = None


class AdapterRecallResponse(BaseModel):
    adapter: str
    source_system: str
    brief: MemoryBrief
    trace: RecallTrace
