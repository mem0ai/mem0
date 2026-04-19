from __future__ import annotations

from pydantic import BaseModel, Field


class RecallRequest(BaseModel):
    namespace_id: str
    agent_id: str | None = None
    session_id: str | None = None
    query: str = Field(..., min_length=3)
    context_budget_tokens: int = Field(..., gt=0)
    space_filter: list[str] | None = None


class MemoryBrief(BaseModel):
    critical_facts: list[str] = Field(default_factory=list)
    active_project_context: list[str] = Field(default_factory=list)
    prior_decisions: list[str] = Field(default_factory=list)
    standing_procedures: list[str] = Field(default_factory=list)
    recent_session_carryover: list[str] = Field(default_factory=list)


class RecallTrace(BaseModel):
    candidate_count: int
    selected_count: int
    selected_space_types: list[str]


class RecallResponse(BaseModel):
    brief: MemoryBrief
    trace: RecallTrace
