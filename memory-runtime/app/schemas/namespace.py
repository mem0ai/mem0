from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class MemorySpaceRead(BaseModel):
    id: str
    namespace_id: str
    agent_id: str | None
    space_type: str
    name: str
    parent_space_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NamespaceCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    mode: str = Field(..., pattern="^(isolated|shared)$")
    source_systems: list[str] = Field(default_factory=list)


class NamespaceRead(BaseModel):
    id: str
    name: str
    mode: str
    source_systems: list[str]
    status: str
    created_at: datetime
    updated_at: datetime
    spaces: list[MemorySpaceRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    source_system: str = Field(..., min_length=2, max_length=100)
    external_ref: str | None = Field(default=None, max_length=255)


class AgentRead(BaseModel):
    id: str
    namespace_id: str
    external_ref: str | None
    name: str
    source_system: str
    created_at: datetime
    spaces: list[MemorySpaceRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}
