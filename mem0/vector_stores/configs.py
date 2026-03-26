import logging
import os
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)


def get_default_vector_store_path(provider: str) -> str:
    """Return a platform-appropriate default path for a vector store provider.

    Preference order: MEM0_DATA_DIR → XDG_DATA_HOME (Linux) → APPDATA (Windows) → ~/.local/share
    """
    mem0_data_dir = os.environ.get("MEM0_DATA_DIR")
    if mem0_data_dir:
        base = Path(mem0_data_dir)
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        app_data = os.environ.get("APPDATA")
        if xdg:
            base = Path(xdg)
        elif app_data:
            base = Path(app_data)
        else:
            base = Path.home() / ".local" / "share"
        base = base / "mem0"
    return str(base / provider)


class VectorStoreConfig(BaseModel):
    provider: str = Field(
        description="Provider of the vector store (e.g., 'qdrant', 'chroma', 'upstash_vector')",
        default="qdrant",
    )
    config: Optional[Dict] = Field(description="Configuration for the specific vector store", default=None)

    _provider_configs: Dict[str, str] = {
        "qdrant": "QdrantConfig",
        "chroma": "ChromaDbConfig",
        "pgvector": "PGVectorConfig",
        "pinecone": "PineconeConfig",
        "mongodb": "MongoDBConfig",
        "milvus": "MilvusDBConfig",
        "baidu": "BaiduDBConfig",
        "cassandra": "CassandraConfig",
        "neptune": "NeptuneAnalyticsConfig",
        "upstash_vector": "UpstashVectorConfig",
        "azure_ai_search": "AzureAISearchConfig",
        "azure_mysql": "AzureMySQLConfig",
        "redis": "RedisDBConfig",
        "valkey": "ValkeyConfig",
        "databricks": "DatabricksConfig",
        "elasticsearch": "ElasticsearchConfig",
        "vertex_ai_vector_search": "GoogleMatchingEngineConfig",
        "opensearch": "OpenSearchConfig",
        "supabase": "SupabaseConfig",
        "weaviate": "WeaviateConfig",
        "faiss": "FAISSConfig",
        "langchain": "LangchainConfig",
        "s3_vectors": "S3VectorsConfig",
        "turbopuffer": "TurbopufferConfig",
    }

    @model_validator(mode="after")
    def validate_and_create_config(self) -> "VectorStoreConfig":
        provider = self.provider
        config = self.config

        if provider not in self._provider_configs:
            raise ValueError(f"Unsupported vector store provider: {provider}")

        module = __import__(
            f"mem0.configs.vector_stores.{provider}",
            fromlist=[self._provider_configs[provider]],
        )
        config_class = getattr(module, self._provider_configs[provider])

        if config is None:
            config = {}

        if not isinstance(config, dict):
            if not isinstance(config, config_class):
                raise ValueError(f"Invalid config type for provider {provider}")
            return self

        # also check if path in allowed kays for pydantic model, and whether config extra fields are allowed
        if "path" not in config and "path" in config_class.__annotations__:
            config["path"] = get_default_vector_store_path(provider)

            legacy_path = Path(f"/tmp/{provider}")
            if legacy_path.exists() and any(legacy_path.iterdir()):
                logger.warning(
                    f"Found existing data at legacy path '{legacy_path}'. "
                    f"mem0 now defaults to '{config['path']}'. "
                    f"To keep using the old location, set path='/tmp/{provider}' in your config, "
                    f"or move the data to the new path."
                )

        self.config = config_class(**config)
        return self
