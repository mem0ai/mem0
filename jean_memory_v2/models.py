"""
Jean Memory V2 API Models
========================

Pydantic models for the Jean Memory V2 API to ensure type safety,
validation, and consistency across all interfaces.
"""

from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum


class MemoryType(str, Enum):
    """Types of memory storage backends"""
    VECTOR = "vector"
    GRAPH = "graph"
    HYBRID = "hybrid"


class SearchStrategy(str, Enum):
    """Search strategies for memory retrieval"""
    VECTOR_ONLY = "vector_only"
    GRAPH_ONLY = "graph_only"
    HYBRID = "hybrid"
    VECTOR_GRAPH_FUSION = "vector_graph_fusion"


# Request Models
class AddMemoryRequest(BaseModel):
    """Request model for adding a single memory"""
    memory_text: str = Field(..., description="The memory text to store", min_length=1, max_length=10000)
    user_id: str = Field(..., description="User ID for memory isolation", min_length=1, max_length=100)
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata for the memory")
    source_description: Optional[str] = Field(default="user_input", description="Description of the memory source")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        """Validate user_id format"""
        if not v or not v.strip():
            raise ValueError("user_id cannot be empty")
        return v.strip()
    
    @validator('memory_text')
    def validate_memory_text(cls, v):
        """Validate memory text"""
        if not v or not v.strip():
            raise ValueError("memory_text cannot be empty")
        return v.strip()


class AddMemoriesBulkRequest(BaseModel):
    """Request model for adding multiple memories in bulk"""
    memories: List[str] = Field(..., description="List of memory texts to store", min_items=1, max_items=1000)
    user_id: str = Field(..., description="User ID for memory isolation", min_length=1, max_length=100)
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional metadata applied to all memories")
    source_description: Optional[str] = Field(default="bulk_import", description="Description of the memory source")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        """Validate user_id format"""
        if not v or not v.strip():
            raise ValueError("user_id cannot be empty")
        return v.strip()
    
    @validator('memories')
    def validate_memories(cls, v):
        """Validate memories list"""
        if not v:
            raise ValueError("memories list cannot be empty")
        
        # Filter out empty strings and validate
        valid_memories = []
        for i, memory in enumerate(v):
            if not memory or not memory.strip():
                continue  # Skip empty memories
            if len(memory.strip()) > 10000:
                raise ValueError(f"Memory {i} exceeds maximum length of 10000 characters")
            valid_memories.append(memory.strip())
        
        if not valid_memories:
            raise ValueError("No valid memories found in the list")
        
        return valid_memories


class SearchMemoriesRequest(BaseModel):
    """Request model for searching memories"""
    query: str = Field(..., description="Search query", min_length=1, max_length=1000)
    user_id: str = Field(..., description="User ID for memory isolation", min_length=1, max_length=100)
    limit: Optional[int] = Field(default=20, description="Maximum number of results", ge=1, le=100)
    strategy: Optional[SearchStrategy] = Field(default=SearchStrategy.HYBRID, description="Search strategy to use")
    include_metadata: Optional[bool] = Field(default=True, description="Include metadata in results")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        """Validate user_id format"""
        if not v or not v.strip():
            raise ValueError("user_id cannot be empty")
        return v.strip()
    
    @validator('query')
    def validate_query(cls, v):
        """Validate search query"""
        if not v or not v.strip():
            raise ValueError("query cannot be empty")
        # Allow wildcard queries for get_all operations
        if v.strip() == "*":
            return v.strip()
        # Require at least 1 character for regular queries
        if len(v.strip()) < 1:
            raise ValueError("query must have at least 1 character (or use '*' for all)")
        return v.strip()


class ClearMemoriesRequest(BaseModel):
    """Request model for clearing user memories"""
    user_id: str = Field(..., description="User ID for memory isolation", min_length=1, max_length=100)
    confirm: bool = Field(..., description="Confirmation flag to prevent accidental deletion")
    
    @validator('user_id')
    def validate_user_id(cls, v):
        """Validate user_id format"""
        if not v or not v.strip():
            raise ValueError("user_id cannot be empty")
        return v.strip()
    
    @validator('confirm')
    def validate_confirm(cls, v):
        """Ensure confirmation is explicit"""
        if not v:
            raise ValueError("confirm must be True to proceed with deletion")
        return v


# Response Models
class MemoryItem(BaseModel):
    """Individual memory item"""
    id: str = Field(..., description="Unique memory identifier")
    text: str = Field(..., description="Memory text content")
    score: Optional[float] = Field(default=None, description="Relevance score (for search results)")
    source: Optional[MemoryType] = Field(default=None, description="Source backend (vector/graph)")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Memory metadata")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")


class AddMemoryResponse(BaseModel):
    """Response model for adding a single memory"""
    success: bool = Field(..., description="Whether the operation succeeded")
    memory_id: Optional[str] = Field(default=None, description="ID of the created memory")
    vector_stored: bool = Field(default=False, description="Whether memory was stored in vector database")
    graph_stored: bool = Field(default=False, description="Whether memory was stored in graph database")
    message: str = Field(..., description="Operation result message")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional response metadata")


class AddMemoriesBulkResponse(BaseModel):
    """Response model for bulk memory addition"""
    success: bool = Field(..., description="Whether the operation succeeded")
    total_memories: int = Field(..., description="Total number of memories processed")
    successful_memories: int = Field(..., description="Number of successfully stored memories")
    failed_memories: int = Field(default=0, description="Number of failed memory additions")
    vector_stored_count: int = Field(default=0, description="Number stored in vector database")
    graph_stored_count: int = Field(default=0, description="Number stored in graph database")
    memory_ids: List[str] = Field(default_factory=list, description="IDs of created memories")
    message: str = Field(..., description="Operation result message")
    errors: Optional[List[str]] = Field(default=None, description="List of errors encountered")


class SearchMemoriesResponse(BaseModel):
    """Response model for memory search"""
    success: bool = Field(..., description="Whether the search succeeded")
    query: str = Field(..., description="Original search query")
    total_results: int = Field(..., description="Total number of results found")
    memories: List[MemoryItem] = Field(default_factory=list, description="Retrieved memory items")
    strategy_used: SearchStrategy = Field(..., description="Search strategy that was used")
    collection_name: Optional[str] = Field(default=None, description="Collection name used for search")
    vector_results_count: int = Field(default=0, description="Number of results from vector search")
    graph_results_count: int = Field(default=0, description="Number of results from graph search")
    search_time_ms: Optional[float] = Field(default=None, description="Search execution time in milliseconds")
    message: str = Field(..., description="Search result message")
    errors: Optional[List[str]] = Field(default=None, description="List of errors encountered")
    unexpected_error: Optional[bool] = Field(default=False, description="Whether an unexpected error occurred")


class ClearMemoriesResponse(BaseModel):
    """Response model for clearing memories"""
    success: bool = Field(..., description="Whether the operation succeeded")
    user_id: str = Field(..., description="User ID whose memories were cleared")
    vector_deleted_count: int = Field(default=0, description="Number of memories deleted from vector database")
    graph_deleted_count: int = Field(default=0, description="Number of memories deleted from graph database")
    total_deleted: int = Field(..., description="Total number of memories deleted")
    message: str = Field(..., description="Operation result message")


# System Status Models
class DatabaseStatus(BaseModel):
    """Status of a database connection"""
    name: str = Field(..., description="Database name")
    connected: bool = Field(..., description="Connection status")
    collections_count: Optional[int] = Field(default=None, description="Number of collections/tables")
    error: Optional[str] = Field(default=None, description="Error message if connection failed")


class SystemStatus(BaseModel):
    """Overall system status"""
    healthy: bool = Field(..., description="Overall system health")
    version: str = Field(..., description="Jean Memory V2 version")
    databases: List[DatabaseStatus] = Field(default_factory=list, description="Database status list")
    dynamic_indexing_enabled: bool = Field(..., description="Whether dynamic indexing is enabled")
    last_check: datetime = Field(default_factory=datetime.now, description="Last health check timestamp")


# Error Models
class APIError(BaseModel):
    """Standard error response"""
    error: bool = Field(default=True, description="Error flag")
    error_type: str = Field(..., description="Type of error")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(default=None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")


# Configuration Models  
class APIConfig(BaseModel):
    """Configuration for the Jean Memory V2 API"""
    enable_vector_storage: bool = Field(default=True, description="Enable Mem0 vector storage")
    enable_graph_storage: bool = Field(default=True, description="Enable Graphiti graph storage")
    default_search_strategy: SearchStrategy = Field(default=SearchStrategy.HYBRID, description="Default search strategy")
    auto_create_indexes: bool = Field(default=True, description="Automatically create Qdrant indexes")
    index_wait_time: int = Field(default=5, description="Seconds to wait after index creation")
    max_memory_length: int = Field(default=10000, description="Maximum length for single memory")
    max_bulk_size: int = Field(default=1000, description="Maximum number of memories in bulk operation")
    search_timeout_seconds: int = Field(default=30, description="Search operation timeout")
    
    class Config:
        """Pydantic config"""
        use_enum_values = True 