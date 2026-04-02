import logging
import os
import shutil
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


def _migrate_legacy_data(provider: str, new_path: str):
    """Auto-migrate data from legacy /tmp/{provider} to the new persistent path.

    Skips migration if:
    - Legacy path doesn't exist, is empty, or is a symlink (security)
    - New path already contains data (no clobbering)
    - A .migration_complete sentinel exists at the new path (already migrated)

    Falls back to a warning with manual instructions if the copy fails.
    Note: On Windows /tmp doesn't exist, so this is effectively a no-op.
    """
    legacy_path = Path(f"/tmp/{provider}")
    if not legacy_path.exists() or legacy_path.is_symlink() or not any(legacy_path.iterdir()):
        return

    new_path_obj = Path(new_path)

    # Skip if already migrated in a previous run
    sentinel = new_path_obj / ".migration_complete"
    if sentinel.exists():
        return

    if new_path_obj.exists() and any(new_path_obj.iterdir()):
        logger.info(
            "Both legacy path '%s' and new path '%s' contain data. "
            "Using new path. Legacy data at '%s' is untouched.",
            legacy_path, new_path, legacy_path,
        )
        return

    try:
        shutil.copytree(str(legacy_path), new_path, dirs_exist_ok=True)
        # Write sentinel to prevent repeated migration attempts on future startups
        sentinel.touch()
        logger.info(
            "Migrated vector store data from '%s' to '%s'. "
            "You may remove the old directory once verified.",
            legacy_path, new_path,
        )
    except Exception as e:
        logger.warning(
            "Could not auto-migrate data from '%s' to '%s': %s. "
            "Please manually copy/move the data, or set path='/tmp/%s' in your config "
            "to keep using the old location.",
            legacy_path, new_path, e, provider,
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
            config["path"] = get_default_vector_store_path(provider)
            _migrate_legacy_data(provider, config["path"])

        self.config = config_class(**config)
        return self
