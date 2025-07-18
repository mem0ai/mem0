"""
Pydantic schemas for memory operations.
Contains request and response models for memory API endpoints.
"""

from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel

from app.models import MemoryState


class CreateMemoryRequestData(BaseModel):
    text: str
    metadata: dict = {}
    infer: bool = True
    app_name: str


class DeleteMemoriesRequestData(BaseModel):
    memory_ids: List[UUID]


class PauseMemoriesRequestData(BaseModel):
    memory_ids: Optional[List[UUID]] = None
    category_ids: Optional[List[UUID]] = None
    app_id: Optional[UUID] = None
    global_pause_for_user: bool = False
    state: Optional[MemoryState] = MemoryState.paused


class UpdateMemoryRequestData(BaseModel):
    memory_content: str


class FilterMemoriesRequestData(BaseModel):
    search_query: Optional[str] = None
    app_ids: Optional[List[UUID]] = None
    category_ids: Optional[List[UUID]] = None
    sort_column: Optional[str] = None
    sort_direction: Optional[str] = None
    from_date: Optional[int] = None
    to_date: Optional[int] = None
    show_archived: Optional[bool] = False