"""Tests for embedding dimension detection and propagation to vector stores."""

from pydantic import BaseModel, Field

from mem0.memory.main import _sync_embedding_dims_to_vector_store


class FakeEmbedderConfig:
    def __init__(self, embedding_dims):
        self.embedding_dims = embedding_dims


class FakeEmbedder:
    """Embedder that returns vectors of a given actual dimension."""

    def __init__(self, actual_dims, config_dims=None):
        self.config = FakeEmbedderConfig(config_dims)
        self._actual_dims = actual_dims

    def embed(self, text, memory_action=None):
        return [0.0] * self._actual_dims


class FailingEmbedder:
    """Embedder whose embed() raises, simulating an unreachable API."""

    def __init__(self, config_dims):
        self.config = FakeEmbedderConfig(config_dims)

    def embed(self, text, memory_action=None):
        raise ConnectionError("server unreachable")


class FakeVectorStoreConfig(BaseModel):
    """Mimics a real vector store config (Pydantic BaseModel with default dims)."""

    collection_name: str = "mem0"
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")


class FakeDatabricksConfig(BaseModel):
    """Mimics Databricks config which uses 'embedding_dimension' instead."""

    collection_name: str = "mem0"
    embedding_dimension: int = Field(1536, description="Vector embedding dimensions")


class FakeChromaConfig(BaseModel):
    """Mimics a vector store config without any dimension field."""

    collection_name: str = "mem0"


class TestSyncEmbeddingDims:
    def test_propagates_known_dims(self):
        """When embedder already knows its dims, propagate directly (no probe)."""
        embedder = FakeEmbedder(actual_dims=768, config_dims=768)
        vs_config = FakeVectorStoreConfig()

        assert vs_config.embedding_model_dims == 1536
        _sync_embedding_dims_to_vector_store(embedder, vs_config)
        assert vs_config.embedding_model_dims == 768

    def test_probes_when_dims_are_none(self):
        """When embedder has None dims (Azure/Bedrock/FastEmbed), probe to detect."""
        embedder = FakeEmbedder(actual_dims=1024, config_dims=None)
        vs_config = FakeVectorStoreConfig()

        _sync_embedding_dims_to_vector_store(embedder, vs_config)
        assert vs_config.embedding_model_dims == 1024
        assert embedder.config.embedding_dims == 1024

    def test_probe_failure_preserves_default(self):
        """When probe fails and config is None, vector store keeps its default."""
        embedder = FailingEmbedder(config_dims=None)
        vs_config = FakeVectorStoreConfig()

        _sync_embedding_dims_to_vector_store(embedder, vs_config)
        assert vs_config.embedding_model_dims == 1536

    def test_non_int_dims_ignored(self):
        """Non-integer embedding_dims (e.g. MagicMock from tests) are safely ignored."""
        embedder = FakeEmbedder(actual_dims=768, config_dims="not_an_int")
        vs_config = FakeVectorStoreConfig()

        _sync_embedding_dims_to_vector_store(embedder, vs_config)
        assert vs_config.embedding_model_dims == 1536

    def test_user_explicit_vector_store_dims_not_overridden(self):
        """User-provided embedding_model_dims should NOT be overridden."""
        embedder = FakeEmbedder(actual_dims=768, config_dims=768)
        vs_config = FakeVectorStoreConfig(embedding_model_dims=2048)

        _sync_embedding_dims_to_vector_store(embedder, vs_config)
        assert vs_config.embedding_model_dims == 2048

    def test_databricks_embedding_dimension_field(self):
        """Should handle Databricks' 'embedding_dimension' field name."""
        embedder = FakeEmbedder(actual_dims=768, config_dims=768)
        vs_config = FakeDatabricksConfig()

        assert vs_config.embedding_dimension == 1536
        _sync_embedding_dims_to_vector_store(embedder, vs_config)
        assert vs_config.embedding_dimension == 768

    def test_config_without_dim_field_is_skipped(self):
        """Vector stores without a dimension field (e.g., Chroma) should be skipped."""
        embedder = FakeEmbedder(actual_dims=768, config_dims=768)
        vs_config = FakeChromaConfig()

        _sync_embedding_dims_to_vector_store(embedder, vs_config)
        assert not hasattr(vs_config, "embedding_model_dims")
        assert not hasattr(vs_config, "embedding_dimension")
