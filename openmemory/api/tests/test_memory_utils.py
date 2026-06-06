"""Regression tests for embedding_dims propagation in get_memory_client().

Ensures that when the embedder config declares an explicit embedding_dims,
that value is forwarded to the vector store config as embedding_model_dims.
Without the fix, QdrantConfig defaults to 1536 regardless of the actual
embedder output size, causing a dimension-mismatch error at insert time.
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import copy
from unittest.mock import MagicMock, patch


def _base_config(embedding_dims=None):
    embedder_cfg = {
        "model": "text-embedding-3-small",
        "api_key": "test-key",
    }
    if embedding_dims is not None:
        embedder_cfg["embedding_dims"] = embedding_dims

    return {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "openmemory",
                "host": "localhost",
                "port": 6333,
            },
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": "gpt-4o-mini",
                "api_key": "test-key",
                "temperature": 0.1,
                "max_tokens": 2000,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": embedder_cfg,
        },
        "version": "v1.1",
    }


class TestEmbeddingDimsPropagation:
    def setup_method(self):
        from app.utils.memory import reset_memory_client
        reset_memory_client()

    def _call_with_config(self, config):
        """Call get_memory_client() and return the config dict passed to Memory.from_config."""
        captured = {}

        def _fake_from_config(config_dict):
            captured.update(copy.deepcopy(config_dict))
            return MagicMock()

        with (
            patch("app.utils.memory.get_default_memory_config", return_value=config),
            patch("app.utils.memory.SessionLocal") as mock_session_cls,
            patch("app.utils.memory.Memory") as mock_mem_cls,
        ):
            mock_db = MagicMock()
            mock_db.query.return_value.filter.return_value.first.return_value = None
            mock_session_cls.return_value = mock_db
            mock_mem_cls.from_config.side_effect = _fake_from_config

            from app.utils.memory import get_memory_client
            get_memory_client()

        return captured

    def test_embedding_dims_propagated_to_vector_store(self):
        """embedding_dims in embedder config must be forwarded to vector_store config."""
        captured = self._call_with_config(_base_config(embedding_dims=768))
        dims = captured.get("vector_store", {}).get("config", {}).get("embedding_model_dims")
        assert dims == 768, f"Expected embedding_model_dims=768, got {dims}"

    def test_no_embedding_dims_leaves_vector_store_config_unchanged(self):
        """When embedder config has no embedding_dims, vector_store config must not gain embedding_model_dims."""
        captured = self._call_with_config(_base_config(embedding_dims=None))
        vs_config = captured.get("vector_store", {}).get("config", {})
        assert "embedding_model_dims" not in vs_config, (
            f"vector_store config should not have embedding_model_dims, got: {vs_config}"
        )

    def test_embedding_dims_1024_propagated(self):
        """Verify non-standard dim sizes (e.g. 1024) are forwarded correctly."""
        captured = self._call_with_config(_base_config(embedding_dims=1024))
        dims = captured.get("vector_store", {}).get("config", {}).get("embedding_model_dims")
        assert dims == 1024, f"Expected embedding_model_dims=1024, got {dims}"
