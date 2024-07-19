import os
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from mem0.memory.setup import mem0_dir
from mem0.vector_stores.configs import VectorStoreConfig
from mem0.llms.configs import LlmConfig
from mem0.embeddings.configs import EmbedderConfig

class MemoryItem(BaseModel):
    id: str = Field(..., description="The unique identifier for the text data")
    text: str = Field(..., description="The text content")
    # The metadata value can be anything and not just string. Fix it
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the text data"
    )
    score: Optional[float] = Field(
        None, description="The score associated with the text data"
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
    collection_name: str = Field(default="mem0", description="Name of the collection")
    embedding_model_dims: int = Field(
        default=1536, description="Dimensions of the embedding model"
    )