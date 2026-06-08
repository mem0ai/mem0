import pytest
from mem0.configs.vector_stores.qdrant import QdrantConfig


def test_qdrant_config_https_default_is_none():
    """https defaults to None, preserving backward compatibility."""
    config = QdrantConfig(
        collection_name="memories",
        embedding_model_dims=1536,
        host="localhost",
        port=6333,
    )
    assert config.https is None


def test_qdrant_config_https_true():
    """Explicit https=True forces HTTPS, e.g. for Qdrant Cloud."""
    config = QdrantConfig(
        collection_name="memories",
        embedding_model_dims=1536,
        host="cloud.qdrant.io",
        port=6333,
        https=True,
    )
    assert config.https is True


def test_qdrant_config_https_false():
    """Explicit https=False forces HTTP for self-hosted instances with API key."""
    config = QdrantConfig(
        collection_name="memories",
        embedding_model_dims=1536,
        host="localhost",
        port=6333,
        api_key="my-key",
        https=False,
    )
    assert config.https is False


def test_qdrant_config_https_none_with_api_key():
    """When https is None, QdrantClient auto-detects based on api_key presence."""
    config = QdrantConfig(
        collection_name="memories",
        embedding_model_dims=1536,
        host="localhost",
        port=6333,
        api_key="my-key",
    )
    assert config.https is None