import os
import sys
from pathlib import Path
from typing import Dict, Optional

from pydantic import BaseModel, Field, model_validator


def _default_data_dir(provider: str) -> str:
    """Return an OS-appropriate data directory for the given vector store provider.

    Respects MEM0_DATA_DIR environment variable if set. Otherwise:
    - Linux: $XDG_DATA_HOME/mem0/{provider} or ~/.local/share/mem0/{provider}
    - macOS: ~/Library/Application Support/mem0/{provider}
    - Windows: %LOCALAPPDATA%/mem0/{provider} or %APPDATA%/mem0/{provider}
    """
    env_dir = os.environ.get("MEM0_DATA_DIR")
    if env_dir:
        return str(Path(env_dir) / provider)

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA", "")
        if base:
            return str(Path(base) / "mem0" / provider)
        return str(Path.home() / "mem0" / provider)
    elif sys.platform == "darwin":
        return str(Path.home() / "Library" / "Application Support" / "mem0" / provider)
    else:
        xdg = os.environ.get("XDG_DATA_HOME", "")
        if xdg:
            return str(Path(xdg) / "mem0" / provider)
        return str(Path.home() / ".local" / "share" / "mem0" / provider)


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
            config["path"] = _default_data_dir(provider)

        self.config = config_class(**config)
        return self
