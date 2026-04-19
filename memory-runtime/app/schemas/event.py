from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


ALLOWED_ROLES = {"system", "user", "assistant", "tool"}
ALLOWED_SPACE_HINTS = {"session-space", "project-space", "agent-core", "shared-space"}


class EventMessage(BaseModel):
    role: str = Field(..., min_length=2, max_length=20)
    content: str = Field(..., min_length=1)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in ALLOWED_ROLES:
            raise ValueError(f"Unsupported role '{value}'")
        return normalized

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Message content cannot be empty")
        return normalized


class EventCreate(BaseModel):
    namespace_id: str
    agent_id: str | None = None
    session_id: str | None = None
    project_id: str | None = None
    source_system: str = Field(..., min_length=2, max_length=100)
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


class EventRead(BaseModel):
    id: str
    episode_id: str
    namespace_id: str
    agent_id: str | None
    space_id: str | None
    session_id: str | None
    project_id: str | None
    source_system: str
    event_type: str
    dedupe_key: str | None
    event_ts: datetime
    ingested_at: datetime
    payload_json: dict

    model_config = {"from_attributes": True}
