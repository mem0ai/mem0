"""Tests for memory client configuration building (app.utils.memory)."""

import os

# Set dummy keys before importing modules that may initialize clients
os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.utils.memory import get_default_memory_config


class TestEmbeddingDimsPropagation:
    """The embedder's vector dimension must reach the vector store config.

    Without propagation, the vector store keeps its 1536 default (OpenAI size)
    and any embedder producing a different dimension fails on insert with a
    dimension mismatch.
    """

    def test_embedding_dims_propagated_to_vector_store(self, monkeypatch):
        monkeypatch.setenv("EMBEDDER_PROVIDER", "ollama")
        monkeypatch.setenv("EMBEDDER_MODEL", "nomic-embed-text-v2-moe")
        monkeypatch.setenv("EMBEDDER_EMBEDDING_DIMS", "768")

        config = get_default_memory_config()

        assert config["embedder"]["config"]["embedding_dims"] == 768
        assert config["vector_store"]["config"]["embedding_model_dims"] == 768

    def test_no_dims_env_leaves_vector_store_default(self, monkeypatch):
        """When EMBEDDER_EMBEDDING_DIMS is unset, no dims are forced (backward compatible)."""
        monkeypatch.delenv("EMBEDDER_EMBEDDING_DIMS", raising=False)
        monkeypatch.setenv("EMBEDDER_PROVIDER", "openai")
        monkeypatch.setenv("EMBEDDER_MODEL", "text-embedding-3-small")

        config = get_default_memory_config()

        assert "embedding_model_dims" not in config["vector_store"]["config"]
        assert "embedding_dims" not in config["embedder"]["config"]
