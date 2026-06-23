"""Pydantic option models for MemoryClient methods.

These models provide IDE autocompletion, runtime validation, and type safety.
Methods accept both typed options and **kwargs for backward compatibility.

Identity fields (user_id, agent_id, app_id, run_id) must be passed inside
the ``filters`` dict — the v3 API does not accept them at the top level.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class AddMemoryOptions(BaseModel):
    """Options for the add() method.

    Identity fields (user_id, agent_id, app_id, run_id) must be passed inside
    the ``filters`` dict — the v3 API does not accept them at the top level.
    """

    filters: Optional[Dict[str, Any]] = Field(
        default=None, description="Filters containing entity IDs (e.g. {'user_id': '...'})"
    )
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata for the memory")
    infer: Optional[bool] = Field(default=None, description="Whether to infer memories from the input")
    custom_categories: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Custom categories for memory classification"
    )
    custom_instructions: Optional[str] = Field(default=None, description="Custom instructions for fact extraction")
    timestamp: Optional[int] = Field(default=None, description="Unix timestamp for the memory")
    structured_data_schema: Optional[Dict[str, Any]] = Field(
        default=None, description="Schema for structured data extraction"
    )


class SearchMemoryOptions(BaseModel):
    """Options for the search() method.

    Identity fields (user_id, agent_id, etc.) must be passed inside the
    ``filters`` dict — the v2 API does not accept them at the top level.
    """

    filters: Optional[Dict[str, Any]] = Field(
        default=None, description="Filters for the search (e.g. {'user_id': '...'})"
    )
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata for the search")
    top_k: Optional[int] = Field(default=None, description="Number of results to return")
    rerank: Optional[bool] = Field(default=None, description="Whether to rerank results")
    threshold: Optional[float] = Field(default=None, description="Minimum similarity score threshold")
    fields: Optional[List[str]] = Field(default=None, description="Fields to include in the response")
    categories: Optional[List[str]] = Field(default=None, description="Categories to filter by")


class GetAllMemoryOptions(BaseModel):
    """Options for the get_all() method.

    Identity fields (user_id, agent_id, etc.) must be passed inside the
    ``filters`` dict — the v2 API does not accept them at the top level.
    """

    filters: Optional[Dict[str, Any]] = Field(
        default=None, description="Filters for retrieval (e.g. {'user_id': '...'})"
    )
    page: Optional[int] = Field(default=None, description="Page number for pagination")
    page_size: Optional[int] = Field(default=None, description="Number of items per page")
    start_date: Optional[str] = Field(
        default=None, description="Filter memories created on or after this date (ISO 8601)"
    )
    end_date: Optional[str] = Field(
        default=None, description="Filter memories created on or before this date (ISO 8601)"
    )
    categories: Optional[List[str]] = Field(default=None, description="Categories to filter by")


class DeleteAllMemoryOptions(BaseModel):
    """Options for the delete_all() method.

    Identity fields (user_id, agent_id, app_id, run_id) must be passed inside
    the ``filters`` dict — the API does not accept them at the top level.
    """

    filters: Optional[Dict[str, Any]] = Field(
        default=None, description="Filters containing entity IDs (e.g. {'user_id': '...'})"
    )


class UpdateMemoryOptions(BaseModel):
    """Options for the update() method."""

    text: Optional[str] = Field(default=None, description="New text content for the memory")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Updated metadata")
    timestamp: Optional[Union[int, float, str]] = Field(default=None, description="Updated timestamp")


class ProjectUpdateOptions(BaseModel):
    """Options for project update operations."""

    custom_instructions: Optional[str] = Field(default=None, description="Custom instructions for fact extraction")
    custom_categories: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Custom categories for classification"
    )
    memory_depth: Optional[str] = Field(default=None, description="Memory depth configuration")
    usecase_setting: Optional[Any] = Field(default=None, description="Use case specific settings")
    multilingual: Optional[bool] = Field(default=None, description="Whether to enable multilingual support")
    retrieval_criteria: Optional[List[Any]] = Field(default=None, description="Criteria for memory retrieval")
