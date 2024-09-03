from __future__ import annotations

import os
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field
from typing_extensions import Annotated

from mem0.embeddings.configs import EmbedderConfig
from mem0.graphs.configs import GraphStoreConfig
from mem0.llms.configs import LlmConfig
from mem0.memory.setup import mem0_dir
from mem0.memory.storage import SupportedStorageBackends
from mem0.vector_stores.configs import VectorStoreConfig


class MemoryItem(BaseModel):
    id: str = Field(..., description="The unique identifier for the text data")
    memory: str = Field(
        ..., description="The memory deduced from the text data"
    )  # TODO After prompt changes from platform, update this
    hash: Optional[str] = Field(None, description="The hash of the memory")
    # The metadata value can be anything and not just string. Fix it
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata for the text data"
    )
    score: Optional[float] = Field(
        None, description="The score associated with the text data"
    )
    created_at: Optional[str] = Field(
        None, description="The timestamp when the memory was created"
    )
    updated_at: Optional[str] = Field(
        None, description="The timestamp when the memory was updated"
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
        description="Path(Url) to the history database",
        default=os.path.join(mem0_dir, "history.db"),
    )
    history_db_backend: Annotated[SupportedStorageBackends, Field(
        description="Backend for the history database",
        default="sqlite",
    )]
    history_db_initialize: bool = Field(
        description="Skip history storage initialization "
                    "and migrations (if is already initialized its save to turn it off and increase speed)",
        default=True,
    )
    history_db_params: Optional[Dict[str, Any]] = Field(
        description="Additional parameters for the history database as defined by peewee",
        default={},
    )
    graph_store: GraphStoreConfig = Field(
        description="Configuration for the graph",
        default_factory=GraphStoreConfig,
    )
    version: str = Field(
        description="The version of the API",
        default="v1.0",
    )

    db_timezone: Annotated[str, Field(default="US/Pacific", description="The timezone for times stored in database")]


class AzureConfig(BaseModel):
    """
    Configuration settings for Azure.

    Args:
        api_key (str): The API key used for authenticating with the Azure service.
        azure_deployment (str): The name of the Azure deployment.
        azure_endpoint (str): The endpoint URL for the Azure service.
        api_version (str): The version of the Azure API being used.
    """

    api_key: str = Field(description="The API key used for authenticating with the Azure service.", default=None)
    azure_deployment: str = Field(description="The name of the Azure deployment.", default=None)
    azure_endpoint: str = Field(description="The endpoint URL for the Azure service.", default=None)
    api_version: str = Field(description="The version of the Azure API being used.", default=None)
