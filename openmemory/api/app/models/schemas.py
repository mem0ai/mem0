"""Pydantic schemas for API requests and responses.

This module contains all the Pydantic models used for:
- Request validation
- Response serialization
- Data transfer objects
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class TimeRange(BaseModel):
    """Represents a time range with start and end timestamps."""
    start: datetime = Field(description="ISO 8601 timestamp when the event/activity starts")
    end: datetime = Field(description="ISO 8601 timestamp when the event/activity ends")
    name: Optional[str] = Field(default=None, description="Optional name/label for this time range")


class TemporalEntity(BaseModel):
    """Structured temporal and entity information extracted from a memory fact."""
    isEvent: bool = Field(description="Whether this memory describes a scheduled event or time-bound activity")
    isPerson: bool = Field(description="Whether this memory is primarily about a person or people")
    isPlace: bool = Field(description="Whether this memory is primarily about a location or place")
    isPromise: bool = Field(description="Whether this memory contains a commitment, promise, or agreement")
    isRelationship: bool = Field(description="Whether this memory describes a relationship between people")
    entities: List[str] = Field(default_factory=list, description="List of people, places, or things mentioned")
    timeRanges: List[TimeRange] = Field(default_factory=list, description="List of time ranges if this is a temporal memory")
    emoji: Optional[str] = Field(default=None, description="Single emoji that best represents this memory")


class CreateMemoryRequest(BaseModel):
    """Request model for creating a new memory."""
    user_id: str
    text: str
    metadata: dict = {}
    infer: bool = True
    app: str = "openmemory"
    timestamp: Optional[int] = None  # Unix timestamp in seconds


class DeleteMemoriesRequest(BaseModel):
    """Request model for deleting memories."""
    memory_ids: List[str]
    user_id: str


class PauseMemoriesRequest(BaseModel):
    """Request model for pausing/unpausing memories."""
    memory_ids: List[str]
    all_for_app: bool = False
    state: str = "paused"
    user_id: str


class UpdateMemoryRequest(BaseModel):
    """Request model for updating a memory."""
    memory_id: str
    memory_content: str
    user_id: str


class MoveMemoriesRequest(BaseModel):
    """Request model for moving memories to another app."""
    memory_ids: List[str]


class FilterMemoriesRequest(BaseModel):
    """Request model for filtering memories."""
    user_id: str
    page: int = 1
    size: int = 10
    search_query: Optional[str] = None
    app_ids: Optional[List[str]] = None
    category_ids: Optional[List[str]] = None
    sort_column: Optional[str] = None
    sort_direction: Optional[str] = None
    from_date: Optional[int] = None
    to_date: Optional[int] = None
    show_archived: Optional[bool] = False
