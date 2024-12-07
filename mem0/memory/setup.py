import os
import uuid
from datetime import datetime
from typing import Optional

from mem0.vector_stores.configs import VectorStoreConfig

# Set up the directory path
home_dir = os.path.expanduser("~")
mem0_dir = os.environ.get("MEM0_DIR") or os.path.join(home_dir, ".mem0")
os.makedirs(mem0_dir, exist_ok=True)
USER_CONFIG_COLLECTION = "mem0_migrations"


def vector_store_setup(vector_store_provider: str, config: VectorStoreConfig):
    if vector_store_provider == "qdrant":
        from mem0.vector_stores.qdrant import Qdrant
        return Qdrant(**config.config.dict())
    elif vector_store_provider == "milvus":
        from mem0.vector_stores.milvus import MilvusDB
        return MilvusDB(**config.config.dict())
    elif vector_store_provider == "chroma":
        from mem0.vector_stores.chroma import ChromaDB
        return ChromaDB(**config.config.dict())
    elif vector_store_provider == "pgvector":
        from mem0.vector_stores.pgvector import PGVector
        return PGVector(**config.config.dict())
    elif vector_store_provider == "azure_ai_search":
        from mem0.vector_stores.azure_ai_search import AzureAISearch
        return AzureAISearch(**config.config.dict())
    else:
        raise ValueError(f"Invalid vector store provider: {vector_store_provider}")


def setup_config(vector_store_provider: str = "qdrant", vector_store_config: Optional[VectorStoreConfig] = None):
    """Set up user configuration using vector store"""
    if vector_store_config is None:
        vector_store_config = VectorStoreConfig(config={"collection_name": USER_CONFIG_COLLECTION})
    else:
        vector_store_config.config.collection_name = USER_CONFIG_COLLECTION

    vector_store = vector_store_setup(vector_store_provider, vector_store_config)

    user_id = str(uuid.uuid4())
    metadata = {"type": "user_config", "user_id": user_id, "created_at": datetime.now().isoformat()}

    # Store empty vector with user metadata
    vectors = [[0.0] * 1536]
    vector_store.insert(vectors=vectors, payloads=[metadata], ids=[user_id])
    return user_id


def get_user_id(vector_store_provider: str = "qdrant", vector_store_config: Optional[VectorStoreConfig] = None):
    """Retrieve user ID from vector store"""
    if vector_store_config is None:
        vector_store_config = VectorStoreConfig(config={"collection_name": USER_CONFIG_COLLECTION})
    else:
        vector_store_config.config.collection_name = USER_CONFIG_COLLECTION

    vector_store = vector_store_setup(vector_store_provider, vector_store_config)
    try:
        # Search for user config entry using empty vector
        query_vector = [0.0] * 1536
        results = vector_store.search(query=query_vector, limit=1, filters={"type": "user_config"})
        if results and len(results) > 0:
            return results[0].payload.get("user_id")

        # If no user found, create new one
        return setup_config(vector_store_provider, vector_store_config)
    except Exception as e:
        print(f"Error retrieving user_id: {e}")
        return "anonymous_user"
