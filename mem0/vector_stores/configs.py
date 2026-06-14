import os
import sys
from typing import Dict, Optional

from pydantic import BaseModel, Field, model_validator


def _default_data_dir() -> str:
    """Return a writable user-data directory suitable for embedded vector stores.

    Resolution order:
      1. ``MEM0_DATA_DIR`` environment variable (explicit override).
      2. Platform convention:
         - macOS: ``~/Library/Application Support/mem0``
         - Windows: ``%LOCALAPPDATA%/mem0``
         - Linux/BSD: ``$XDG_DATA_HOME/mem0`` or ``~/.local/share/mem0``

    The previous default of ``/tmp/{provider}`` broke macOS LaunchAgents, systemd
    services with ``noexec`` ``/tmp``, Windows (no ``/tmp``), and Docker (ephemeral
    ``/tmp``). See #4279.
    """
    env_dir = os.environ.get("MEM0_DATA_DIR")
    if env_dir:
        return env_dir
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/mem0")
    if sys.platform == "win32":
        return os.path.join(
            os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/AppData/Local"),
            "mem0",
        )
    return os.path.join(
        os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
        "mem0",
    )


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
            config["path"] = os.path.join(_default_data_dir(), provider)

        self.config = config_class(**config)
        return self
