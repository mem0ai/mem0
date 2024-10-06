import os
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator

from mem0.embeddings.configs import EmbedderConfig
from mem0.graphs.configs import GraphStoreConfig
from mem0.llms.configs import LlmConfig
from mem0.memory.setup import mem0_dir
from mem0.vector_stores.configs import VectorStoreConfig


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
    version: str = Field(
        description="The version of the API",
        default="v1.0",
    )
    custom_prompt: Optional[str] = Field(
        description="Custom prompt for the memory",
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
    """

    api_key: str = Field(
        description="The API key used for authenticating with the Azure service.",
        default=None,
    )
    azure_deployment: str = Field(description="The name of the Azure deployment.", default=None)
    azure_endpoint: str = Field(description="The endpoint URL for the Azure service.", default=None)
    api_version: str = Field(description="The version of the Azure API being used.", default=None)


class MemoryContext(BaseModel):
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, str]] = None
    filters: Optional[Dict[str, str]] = None

    @model_validator(mode='before')
    def check_at_least_one_id(cls, values):
        """
        Ensure at least one of 'user_id', 'agent_id', or 'run_id' is provided.
        This validator runs before initializing the model.
        """
        user_id = values.get('user_id')
        agent_id = values.get('agent_id')
        run_id = values.get('run_id')

        if not any([user_id, agent_id, run_id]):
            raise ValueError("At least one of 'user_id', 'agent_id', or 'run_id' must be provided!")

        # Ensure metadata and filters are initialized as empty dicts if None
        if values.get('metadata') is None:
            values['metadata'] = {}
        if values.get('filters') is None:
            values['filters'] = {}

        return values

    def prepare_metadata(self):
        """
        Prepare the metadata and ensure it includes the user, agent, and run IDs.
        """
        metadata = self.metadata or {}
        if self.user_id:
            metadata["user_id"] = self.user_id
        if self.agent_id:
            metadata["agent_id"] = self.agent_id
        if self.run_id:
            metadata["run_id"] = self.run_id

        return metadata
    
    def prepare_filters(self):
        """
        Prepare the filters and ensure it includes the user, agent, and run IDs.
        """
        filters = self.filters or {}
        if self.user_id:
            filters["user_id"] = self.user_id
        if self.agent_id:
            filters["agent_id"] = self.agent_id
        if self.run_id:
            filters["run_id"] = self.run_id

        return filters