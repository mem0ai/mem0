"""Pydantic option models for MemoryClient methods.

These models provide IDE autocompletion, runtime validation, and type safety.
Methods accept both typed options and **kwargs for backward compatibility.
"""

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class BaseMemoryOptions(BaseModel):
    """Common options shared across memory operations."""

    user_id: Optional[str] = Field(default=None, description="The user ID to associate with the memory")
    agent_id: Optional[str] = Field(default=None, description="The agent ID to associate with the memory")
    app_id: Optional[str] = Field(default=None, description="The app ID to associate with the memory")
    run_id: Optional[str] = Field(default=None, description="The run ID to associate with the memory")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata for the memory")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Filters to apply to the operation")


class AddMemoryOptions(BaseMemoryOptions):
    """Options for the add() method."""

    infer: Optional[bool] = Field(default=None, description="Whether to infer memories from the input")
    custom_categories: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="Custom categories for memory classification"
    )
    custom_instructions: Optional[str] = Field(default=None, description="Custom instructions for fact extraction")
    timestamp: Optional[int] = Field(default=None, description="Unix timestamp for the memory")
    structured_data_schema: Optional[Dict[str, Any]] = Field(
        default=None, description="Schema for structured data extraction"
    )


class SearchMemoryOptions(BaseMemoryOptions):
    """Options for the search() method."""

    top_k: Optional[int] = Field(default=None, description="Number of results to return")
    rerank: Optional[bool] = Field(default=None, description="Whether to rerank results")
    threshold: Optional[float] = Field(default=None, description="Minimum similarity score threshold")
    fields: Optional[List[str]] = Field(default=None, description="Fields to include in the response")
    categories: Optional[List[str]] = Field(default=None, description="Categories to filter by")
    only_metadata_based_search: Optional[bool] = Field(
        default=None, description="Whether to search only using metadata filters"
    )


class GetAllMemoryOptions(BaseMemoryOptions):
    """Options for the get_all() method."""

    page: Optional[int] = Field(default=None, description="Page number for pagination")
    page_size: Optional[int] = Field(default=None, description="Number of items per page")
    start_date: Optional[str] = Field(default=None, description="Filter memories created on or after this date (ISO 8601)")
    end_date: Optional[str] = Field(default=None, description="Filter memories created on or before this date (ISO 8601)")
    categories: Optional[List[str]] = Field(default=None, description="Categories to filter by")


class DeleteAllMemoryOptions(BaseMemoryOptions):
    """Options for the delete_all() method."""

    pass


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
    inclusion_prompt: Optional[str] = Field(default=None, description="Prompt for memory inclusion criteria")
    exclusion_prompt: Optional[str] = Field(default=None, description="Prompt for memory exclusion criteria")
    memory_depth: Optional[str] = Field(default=None, description="Memory depth configuration")
    usecase_setting: Optional[Any] = Field(default=None, description="Use case specific settings")
    multilingual: Optional[bool] = Field(default=None, description="Whether to enable multilingual support")
    retrieval_criteria: Optional[List[Any]] = Field(default=None, description="Criteria for memory retrieval")
