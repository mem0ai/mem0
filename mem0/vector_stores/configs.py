from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class VectorStoreConfig(BaseModel):
    provider: str = Field(
        description="Provider of the vector store (e.g., 'qdrant', 'chroma', 'upstash_vector')",
        default="qdrant",
    )
    config: Optional[Dict[str, Any]] = Field(description="Configuration for the specific vector store", default=None)

    _provider_configs: Dict[str, str] = {
        "qdrant": "QdrantConfig",
        "chroma": "ChromaDbConfig",
        "pgvector": "PGVectorConfig",
        "pinecone": "PineconeConfig",
        "mongodb": "MongoDBConfig",
        "milvus": "MilvusDBConfig",
        "baidu": "BaiduDBConfig",
        "neptune": "NeptuneAnalyticsConfig",
        "upstash_vector": "UpstashVectorConfig",
        "azure_ai_search": "AzureAISearchConfig",
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

        # also check if path in allowed keys for pydantic model, and whether config extra fields are allowed
        if "path" not in config and "path" in config_class.__annotations__:
            config["path"] = f"/tmp/{provider}"

        self.config = config_class(**config)
        return self

    @property
    def collection_name(self) -> str:
        """Get the collection/index name from the provider config."""
        if self.config and hasattr(self.config, "collection_name"):
            return self.config.collection_name
        return "mem0"

    @property
    def embedding_model_dims(self) -> int:
        """Get the embedding dimensions."""
        if self.config and hasattr(self.config, "embedding_model_dims"):
            return self.config.embedding_model_dims
        return 1536

    @property
    def api_key(self) -> Optional[str]:
        """Get the API key if the provider requires one."""
        if self.config and hasattr(self.config, "api_key"):
            return self.config.api_key
        return None

    @property
    def host(self) -> Optional[str]:
        """Get the host for self-hosted vector stores."""
        if self.config and hasattr(self.config, "host"):
            return self.config.host
        return None

    @property
    def port(self) -> Optional[int]:
        """Get the port for self-hosted vector stores."""
        if self.config and hasattr(self.config, "port"):
            return self.config.port
        return None

    @property
    def url(self) -> Optional[str]:
        """Get the URL for cloud-based vector stores."""
        if self.config and hasattr(self.config, "url"):
            return self.config.url
        return None

    @property
    def path(self) -> Optional[str]:
        """Get the path for local vector stores."""
        if self.config and hasattr(self.config, "path"):
            return self.config.path
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for serialization."""
        result = {
            "provider": self.provider,
            "collection_name": self.collection_name,
            "embedding_model_dims": self.embedding_model_dims,
        }

        # Add optional fields if they exist
        if self.api_key:
            result["api_key"] = self.api_key
        if self.host:
            result["host"] = self.host
        if self.port:
            result["port"] = self.port
        if self.url:
            result["url"] = self.url
        if self.path:
            result["path"] = self.path

        # Include full config if needed
        if self.config:
            result["config"] = self.config.model_dump() if hasattr(self.config, "model_dump") else vars(self.config)

        return result

    def get_migration_config(self) -> Dict[str, Any]:
        """Get configuration for migration operations."""
        return {
            "provider": self.provider,
            "source_collection": self.collection_name,
            "embedding_dims": self.embedding_model_dims,
            "connection_params": self._get_connection_params(),
        }

    def _get_connection_params(self) -> Dict[str, Any]:
        """Extract connection parameters for migration."""
        params = {}
        if self.config:
            for key in ["host", "port", "url", "api_key", "path"]:
                if hasattr(self.config, key):
                    value = getattr(self.config, key)
                    if value is not None:
                        params[key] = value
        return params

    def rebuild_config(self, new_collection_name: Optional[str] = None) -> "VectorStoreConfig":
        """Create a new config for rebuilding the vector database."""
        config_dict = self.model_dump()
        if new_collection_name and self.config:
            if "config" not in config_dict:
                config_dict["config"] = {}
            config_dict["config"]["collection_name"] = new_collection_name
        return VectorStoreConfig(**config_dict)
