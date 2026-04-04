import os
import uuid
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, Field

from mem0.embeddings.configs import EmbedderConfig
from mem0.graphs.configs import GraphStoreConfig
from mem0.llms.configs import LlmConfig
from mem0.vector_stores.configs import VectorStoreConfig
from mem0.configs.rerankers.config import RerankerConfig

# Set up the directory path
home_dir = os.path.expanduser("~")
mem0_dir = os.environ.get("MEM0_DIR") or os.path.join(home_dir, ".mem0")


class ConflictDetectionConfig(BaseModel):
    similarity_threshold: float = Field(
        description="Cosine similarity score above which a pair is sent to secondary classification",
        default_factory=lambda: float(os.environ.get("MEM0_CONFLICT_SIMILARITY_THRESHOLD", "0.85")),
    )
    top_k: int = Field(
        description="Maximum number of existing memories to retrieve per new fact",
        default_factory=lambda: int(os.environ.get("MEM0_CONFLICT_TOP_K", "20")),
    )
    auto_resolve_strategy: Literal["keep-higher-confidence", "keep-newer", "merge"] = Field(
        description="Strategy for auto-resolving CONTRADICTION pairs",
        default_factory=lambda: os.environ.get("MEM0_CONFLICT_AUTO_RESOLVE_STRATEGY", "keep-higher-confidence"),
    )
    hitl_enabled: bool = Field(
        description="Whether to prompt a human for CONTRADICTION resolution",
        default_factory=lambda: os.environ.get("MEM0_CONFLICT_HITL_ENABLED", "false").lower() == "true",
    )


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
    graph_store: GraphStoreConfig = Field(
        description="Configuration for the graph",
        default_factory=GraphStoreConfig,
    )
    reranker: Optional[RerankerConfig] = Field(
        description="Configuration for the reranker",
        default=None,
    )
    version: str = Field(
        description="The version of the API",
        default="v1.1",
    )
    custom_fact_extraction_prompt: Optional[str] = Field(
        description="Custom prompt for the fact extraction",
        default=None,
    )
    custom_update_memory_prompt: Optional[str] = Field(
        description="Custom prompt for the update memory",
        default=None,
    )
    conflict_detection: ConflictDetectionConfig = Field(
        description="Configuration for conflict detection and resolution",
        default_factory=ConflictDetectionConfig,
    )
    session_id: str = Field(
        description="Unique session identifier for HITL override scoping",
        default_factory=lambda: str(uuid.uuid4()),
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
