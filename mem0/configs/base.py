import os
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from mem0.configs.rerankers.config import RerankerConfig
from mem0.embeddings.configs import EmbedderConfig
from mem0.llms.configs import LlmConfig
from mem0.vector_stores.configs import VectorStoreConfig

# Set up the directory path
home_dir = os.path.expanduser("~")
mem0_dir = os.environ.get("MEM0_DIR") or os.path.join(home_dir, ".mem0")


class MemoryItem(BaseModel):
    id: str = Field(..., description="The unique identifier for the text data")
    memory: str = Field(
        ..., description="The memory deduced from the text data"
    )  # TODO After prompt changes from platform, update this
    hash: Optional[str] = Field(None, description="The hash of the memory")
    # The metadata value can be anything and not just string. Fix it
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata for the text data")
    score: Optional[float] = Field(None, description="The score associated with the text data")
    created_at: Optional[str] = Field(None, description="The timestamp when the memory was created")
    updated_at: Optional[str] = Field(None, description="The timestamp when the memory was updated")
    
    # Cognitive-inspired memory fields for Phase 1: Memory Compression & Forgetting Mechanism
    importance_score: Optional[float] = Field(
        default=0.5, 
        ge=0.0, 
        le=1.0,
        description="Importance score based on cognitive psychology (0.0=trivial, 1.0=critical)"
    )
    access_count: Optional[int] = Field(
        default=0, 
        ge=0,
        description="Number of times this memory has been accessed/recalled"
    )
    last_accessed_at: Optional[str] = Field(
        None, 
        description="ISO timestamp of the last access time for decay calculation"
    )
    decay_factor: Optional[float] = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Ebbinghaus forgetting curve decay factor (1.0=fresh, 0.0=forgotten)"
    )
    emotion_intensity: Optional[float] = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Emotional intensity associated with the memory (affects retention)"
    )
    compression_status: Optional[str] = Field(
        default="raw",
        description="Compression status: 'raw' (original), 'compressed' (summarized), 'archived' (low priority)"
    )
    consolidation_level: Optional[str] = Field(
        default="short_term",
        description="Consolidation level: 'short_term' (hippocampal), 'long_term' (cortical)"
    )


class MemoryConfig(BaseModel):
    vector_store: VectorStoreConfig = Field(
        description="Configuration for the vector store",
        default_factory=VectorStoreConfig,
    )
    llm: LlmConfig = Field(
        description="Configuration for the language model",
        default_factory=LlmConfig,
    )
    embedder: EmbedderConfig = Field(
        description="Configuration for the embedding model",
        default_factory=EmbedderConfig,
    )
    history_db_path: str = Field(
        description="Path to the history database",
        default=os.path.join(mem0_dir, "history.db"),
    )
    reranker: Optional[RerankerConfig] = Field(
        description="Configuration for the reranker",
        default=None,
    )
    version: str = Field(
        description="The version of the API",
        default="v1.1",
    )
    custom_instructions: Optional[str] = Field(
        description="Custom instructions for fact extraction",
        default=None,
    )


class AzureConfig(BaseModel):
    """
    Configuration settings for Azure.

    Args:
        api_key (str): The API key used for authenticating with the Azure service.
        azure_deployment (str): The name of the Azure deployment.
        azure_endpoint (str): The endpoint URL for the Azure service.
        api_version (str): The version of the Azure API being used.
        default_headers (Dict[str, str]): Headers to include in requests to the Azure API.
    """

    api_key: str = Field(
        description="The API key used for authenticating with the Azure service.",
        default=None,
    )
    azure_deployment: str = Field(description="The name of the Azure deployment.", default=None)
    azure_endpoint: str = Field(description="The endpoint URL for the Azure service.", default=None)
    api_version: str = Field(description="The version of the Azure API being used.", default=None)
    default_headers: Optional[Dict[str, str]] = Field(
        description="Headers to include in requests to the Azure API.", default=None
    )
