"""Regression tests for _propagate_embedding_dims.

Verifies that the embedder's resolved dimension is propagated to the vector
store config only when the user did not set it explicitly, covering both the
sync ``Memory`` and async ``AsyncMemory`` paths.
"""

from unittest.mock import Mock, patch

import pytest

from mem0.configs.base import MemoryConfig
from mem0.memory.main import AsyncMemory, Memory, _propagate_embedding_dims


@pytest.fixture(autouse=True)
def mock_openai():
    import os

    os.environ["OPENAI_API_KEY"] = "123"
    with patch("openai.OpenAI") as mock:
        mock.return_value = Mock()
        yield mock


def _make_config(embedder_dims=None, vs_dims=1536, vs_class="pgvector"):
    """Build a minimal MemoryConfig with controllable dims."""
    from mem0.configs.vector_stores.pgvector import PGVectorConfig

    config = MemoryConfig()
    config.vector_store.provider = "pgvector"
    config.vector_store.config = PGVectorConfig()
    config.vector_store.config.embedding_model_dims = vs_dims
    return config


class TestPropagateEmbeddingDimsHelper:
    """Unit tests for the _propagate_embedding_dims function."""

    def test_propagates_when_default_dims(self):
        """Should propagate when the store still has the default 1536."""
        embedder = Mock()
        embedder.config.embedding_dims = 768
        vs_config = Mock()
        vs_config.embedding_model_dims = 1536

        _propagate_embedding_dims(embedder, vs_config)

        assert vs_config.embedding_model_dims == 768

    def test_does_not_overwrite_user_set_dims(self):
        """Should NOT overwrite when the user set a non-default value."""
        embedder = Mock()
        embedder.config.embedding_dims = 768
        vs_config = Mock()
        vs_config.embedding_model_dims = 1024  # user-set, non-default

        _propagate_embedding_dims(embedder, vs_config)

        assert vs_config.embedding_model_dims == 1024

    def test_skips_when_embedder_dims_none(self):
        """Should be a no-op when the embedder has no embedding_dims."""
        embedder = Mock()
        embedder.config.embedding_dims = None
        vs_config = Mock()
        vs_config.embedding_model_dims = 1536

        _propagate_embedding_dims(embedder, vs_config)

        assert vs_config.embedding_model_dims == 1536

    def test_handles_databricks_embedding_dimension(self):
        """Should propagate to databricks' embedding_dimension field."""
        embedder = Mock()
        embedder.config.embedding_dims = 512
        vs_config = Mock(spec=[])  # no embedding_model_dims attr
        vs_config.embedding_dimension = 1536

        _propagate_embedding_dims(embedder, vs_config)

        assert vs_config.embedding_dimension == 512

    def test_skips_stores_without_dims_field(self):
        """Should be a no-op for stores that have no dims attribute (chroma, etc.)."""
        embedder = Mock()
        embedder.config.embedding_dims = 768
        vs_config = Mock(spec=[])  # no dims attrs at all

        _propagate_embedding_dims(embedder, vs_config)

        # Should not raise, should not set any attribute
        assert not hasattr(vs_config, "embedding_model_dims")

    def test_does_not_overwrite_explicit_default_equal_dims(self):
        """Should NOT overwrite when the user explicitly set 1536 (== class default)."""
        embedder = Mock()
        embedder.config.embedding_dims = 768
        vs_config = Mock()
        vs_config.embedding_model_dims = 1536
        # Simulate a user-supplied value: the field is in model_fields_set.
        vs_config.model_fields_set = {"embedding_model_dims"}

        _propagate_embedding_dims(embedder, vs_config)

        assert vs_config.embedding_model_dims == 1536

    def test_non_pydantic_config_without_fields_set_still_propagates(self):
        """Plain (non-pydantic) configs fall back to the value heuristic."""
        embedder = Mock()
        embedder.config.embedding_dims = 768
        vs_config = Mock()  # no model_fields_set attribute
        vs_config.embedding_model_dims = 1536

        _propagate_embedding_dims(embedder, vs_config)

        assert vs_config.embedding_model_dims == 768

    def test_non_pydantic_config_with_user_set_value_not_overwritten(self):
        """Plain configs: a non-default value is treated as user-set."""
        embedder = Mock()
        embedder.config.embedding_dims = 768
        vs_config = Mock()  # no model_fields_set attribute
        vs_config.embedding_model_dims = 1024

        _propagate_embedding_dims(embedder, vs_config)

        assert vs_config.embedding_model_dims == 1024


class TestMemoryPropagateDims:
    """Integration tests through Memory.__init__ (sync path)."""

    def test_sync_propagates_embedder_dims_to_vector_store(self):
        """Memory.__init__ should propagate embedder dims to the vector store config."""
        with (
            patch("mem0.memory.main.EmbedderFactory") as mock_embedder,
            patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
            patch("mem0.memory.main.LlmFactory") as mock_llm,
            patch("mem0.memory.telemetry.capture_event"),
        ):
            mock_embedder.create.return_value = Mock()
            mock_embedder.create.return_value.config.embedding_dims = 768
            mock_vector_store.create.return_value = Mock()
            mock_vector_store.create.return_value.search.return_value = []
            mock_llm.create.return_value = Mock()

            config = MemoryConfig(version="v1.1")
            # The vector store config keeps its class default 1536 and was
            # never assigned by the user — propagation should fill it in.
            Memory(config)

            # The vector store config should now have 768
            assert config.vector_store.config.embedding_model_dims == 768

    def test_sync_does_not_overwrite_user_set_dims(self):
        """Memory.__init__ should NOT overwrite when user set a non-default dim."""
        with (
            patch("mem0.memory.main.EmbedderFactory") as mock_embedder,
            patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
            patch("mem0.memory.main.LlmFactory") as mock_llm,
            patch("mem0.memory.telemetry.capture_event"),
        ):
            mock_embedder.create.return_value = Mock()
            mock_embedder.create.return_value.config.embedding_dims = 768
            mock_vector_store.create.return_value = Mock()
            mock_vector_store.create.return_value.search.return_value = []
            mock_llm.create.return_value = Mock()

            config = MemoryConfig(version="v1.1")
            # User explicitly set 1024 — should NOT be overwritten
            config.vector_store.config.embedding_model_dims = 1024

            Memory(config)

            assert config.vector_store.config.embedding_model_dims == 1024

    def test_sync_does_not_overwrite_user_set_dims_equal_to_default(self):
        """Memory.__init__ should NOT overwrite user-set 1536 (== class default)."""
        with (
            patch("mem0.memory.main.EmbedderFactory") as mock_embedder,
            patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
            patch("mem0.memory.main.LlmFactory") as mock_llm,
            patch("mem0.memory.telemetry.capture_event"),
        ):
            mock_embedder.create.return_value = Mock()
            mock_embedder.create.return_value.config.embedding_dims = 768
            mock_vector_store.create.return_value = Mock()
            mock_vector_store.create.return_value.search.return_value = []
            mock_llm.create.return_value = Mock()

            config = MemoryConfig(version="v1.1")
            # User explicitly set 1536 (== class default) — must NOT be overwritten
            config.vector_store.config.embedding_model_dims = 1536

            Memory(config)

            assert config.vector_store.config.embedding_model_dims == 1536


class TestAsyncMemoryPropagateDims:
    """Integration tests through AsyncMemory.__init__ (async path)."""

    def test_async_propagates_embedder_dims_to_vector_store(self):
        """AsyncMemory.__init__ should propagate embedder dims to the vector store config."""
        with (
            patch("mem0.memory.main.EmbedderFactory") as mock_embedder,
            patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
            patch("mem0.memory.main.LlmFactory") as mock_llm,
            patch("mem0.memory.telemetry.capture_event"),
        ):
            mock_embedder.create.return_value = Mock()
            mock_embedder.create.return_value.config.embedding_dims = 768
            mock_vector_store.create.return_value = Mock()
            mock_vector_store.create.return_value.search.return_value = []
            mock_llm.create.return_value = Mock()

            config = MemoryConfig(version="v1.1")
            # Vector store keeps its class default — not user-set.
            AsyncMemory(config)

            assert config.vector_store.config.embedding_model_dims == 768

    def test_async_does_not_overwrite_user_set_dims(self):
        """AsyncMemory.__init__ should NOT overwrite when user set a non-default dim."""
        with (
            patch("mem0.memory.main.EmbedderFactory") as mock_embedder,
            patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
            patch("mem0.memory.main.LlmFactory") as mock_llm,
            patch("mem0.memory.telemetry.capture_event"),
        ):
            mock_embedder.create.return_value = Mock()
            mock_embedder.create.return_value.config.embedding_dims = 768
            mock_vector_store.create.return_value = Mock()
            mock_vector_store.create.return_value.search.return_value = []
            mock_llm.create.return_value = Mock()

            config = MemoryConfig(version="v1.1")
            config.vector_store.config.embedding_model_dims = 1024

            AsyncMemory(config)

            assert config.vector_store.config.embedding_model_dims == 1024

    def test_async_does_not_overwrite_user_set_dims_equal_to_default(self):
        """AsyncMemory.__init__ should NOT overwrite user-set 1536 (== class default)."""
        with (
            patch("mem0.memory.main.EmbedderFactory") as mock_embedder,
            patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
            patch("mem0.memory.main.LlmFactory") as mock_llm,
            patch("mem0.memory.telemetry.capture_event"),
        ):
            mock_embedder.create.return_value = Mock()
            mock_embedder.create.return_value.config.embedding_dims = 768
            mock_vector_store.create.return_value = Mock()
            mock_vector_store.create.return_value.search.return_value = []
            mock_llm.create.return_value = Mock()

            config = MemoryConfig(version="v1.1")
            config.vector_store.config.embedding_model_dims = 1536

            AsyncMemory(config)

            assert config.vector_store.config.embedding_model_dims == 1536
