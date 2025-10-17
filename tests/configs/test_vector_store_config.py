import pytest

from mem0.vector_stores.configs import VectorStoreConfig


class TestVectorStoreConfig:
    def test_default_config(self):
        """Test VectorStoreConfig with default values."""
        config = VectorStoreConfig()
        assert config.provider == "qdrant"
        assert config.collection_name == "mem0"
        assert config.embedding_model_dims == 1536
        assert config.api_key is None
        assert config.host is None
        assert config.port is None
        assert config.url is None

    def test_qdrant_config_properties(self):
        """Test VectorStoreConfig properties with Qdrant provider."""
        config = VectorStoreConfig(
            provider="qdrant",
            config={
                "collection_name": "test_collection",
                "embedding_model_dims": 768,
                "host": "localhost",
                "port": 6333,
                "path": "/custom/path",
            },
        )
        assert config.provider == "qdrant"
        assert config.collection_name == "test_collection"
        assert config.embedding_model_dims == 768
        assert config.host == "localhost"
        assert config.port == 6333
        assert config.path == "/custom/path"

    def test_chroma_config_properties(self):
        """Test VectorStoreConfig properties with Chroma provider - skip if chromadb not installed."""
        try:
            config = VectorStoreConfig(
                provider="chroma", config={"collection_name": "chroma_test", "path": "/tmp/chroma_test"}
            )
            assert config.provider == "chroma"
            assert config.collection_name == "chroma_test"
            assert config.path == "/tmp/chroma_test"
        except ImportError:
            pytest.skip("chromadb not installed")

    def test_to_dict_method(self):
        """Test to_dict method for serialization."""
        config = VectorStoreConfig(
            provider="qdrant",
            config={"collection_name": "test", "embedding_model_dims": 512, "host": "localhost", "port": 6333},
        )
        result = config.to_dict()
        assert result["provider"] == "qdrant"
        assert result["collection_name"] == "test"
        assert result["embedding_model_dims"] == 512
        assert result["host"] == "localhost"
        assert result["port"] == 6333
        assert "config" in result

    def test_get_migration_config(self):
        """Test get_migration_config method."""
        config = VectorStoreConfig(
            provider="qdrant",
            config={"collection_name": "migrate_test", "embedding_model_dims": 1024, "host": "localhost", "port": 6333},
        )
        migration_config = config.get_migration_config()
        assert migration_config["provider"] == "qdrant"
        assert migration_config["source_collection"] == "migrate_test"
        assert migration_config["embedding_dims"] == 1024
        assert migration_config["connection_params"]["host"] == "localhost"
        assert migration_config["connection_params"]["port"] == 6333

    def test_rebuild_config(self):
        """Test rebuild_config method."""
        original_config = VectorStoreConfig(
            provider="qdrant", config={"collection_name": "original", "embedding_model_dims": 768}
        )
        new_config = original_config.rebuild_config(new_collection_name="rebuilt")
        assert new_config.provider == "qdrant"
        assert new_config.collection_name == "rebuilt"

    def test_invalid_provider(self):
        """Test VectorStoreConfig with invalid provider."""
        with pytest.raises(ValueError, match="Unsupported vector store provider"):
            VectorStoreConfig(provider="invalid_provider")

    def test_pinecone_config_with_api_key(self):
        """Test VectorStoreConfig with Pinecone provider and API key."""
        config = VectorStoreConfig(
            provider="pinecone", config={"api_key": "test-api-key", "collection_name": "test-index"}
        )
        assert config.provider == "pinecone"
        assert config.api_key == "test-api-key"
        assert config.collection_name == "test-index"

    def test_config_with_none_values(self):
        """Test that None values are handled correctly."""
        config = VectorStoreConfig(provider="qdrant", config={})
        assert config.collection_name == "mem0"  # Should return default
        assert config.api_key is None
        assert config.host is None
        assert config.port is None
