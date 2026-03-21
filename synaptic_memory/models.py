"""Data models for the synaptic memory system."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class CitationType(Enum):
    RETRIEVAL = "retrieval"
    EXPLICIT = "explicit"
    DECISION = "decision"
    CO_RETRIEVAL = "co_retrieval"
    MANUAL = "manual"
    TEMPORAL = "temporal"


@dataclass
class Synapse:
    id: str
    source_id: str
    target_id: str

    strength: float = 0.1
    base_strength: float = 0.1

    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    last_strength_update: datetime = field(default_factory=datetime.now)

    access_count: int = 0
    co_citation_count: int = 0

    decay_rate: float = 0.01
    citation_type: CitationType = CitationType.RETRIEVAL

    temporal_bias: float = 0.0

    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())


@dataclass
class MemoryAugmented:
    memory_id: str

    incoming_strength: float = 0.0
    outgoing_strength: float = 0.0
    total_strength: float = 0.0

    page_rank: float = 0.0
    hub_score: float = 0.0

    total_access_count: int = 0
    last_accessed: Optional[datetime] = None

    decay_rate: float = 0.01
    importance_score: float = 0.5

    in_replay_buffer: bool = False
    replay_count: int = 0
    replay_effectiveness: float = 0.0

    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ReplayItem:
    id: str
    memory_id: str
    synapse_id: Optional[str] = None
    priority: float = 0.0
    reason: str = "weakening"
    created_at: datetime = field(default_factory=datetime.now)
    due_at: datetime = field(default_factory=datetime.now)
    presented_count: int = 0
    effectiveness_boost: float = 0.0

    @staticmethod
    def new_id() -> str:
        return str(uuid.uuid4())
