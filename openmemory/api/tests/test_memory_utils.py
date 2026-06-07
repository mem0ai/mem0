"""Regression tests for embedding_dims propagation in get_memory_client() (#5405).

When the embedder config declares an explicit embedding_dims, that value must be
forwarded to the vector store config as embedding_model_dims. Vector store
configs commonly default to 1536 (OpenAI size), so a non-OpenAI embedder with a
different output size would otherwise hit a dimension-mismatch error at insert.
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

import copy
from unittest.mock import MagicMock, patch


def _config(embedding_dims=None, with_vector_store=True):
    embedder_config = {"model": "nomic-embed-text", "api_key": "test-key"}
    if embedding_dims is not None:
        embedder_config["embedding_dims"] = embedding_dims

    config = {
        "llm": {"provider": "openai", "config": {"model": "gpt-4o-mini", "api_key": "test-key"}},
        "embedder": {"provider": "openai", "config": embedder_config},
        "version": "v1.1",
    }
    if with_vector_store:
        config["vector_store"] = {
            "provider": "qdrant",
            "config": {"collection_name": "openmemory", "host": "localhost", "port": 6333},
        }
    return config


def _captured_config(config):
    """Run get_memory_client() with the given default config and return the
    config dict that was handed to Memory.from_config()."""
    from app.utils.memory import reset_memory_client

    reset_memory_client()
    captured = {}

    def _fake_from_config(config_dict):
        captured.update(copy.deepcopy(config_dict))
        return MagicMock()

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with (
        patch("app.utils.memory.get_default_memory_config", return_value=config),
        patch("app.utils.memory.SessionLocal", return_value=mock_db),
        patch("app.utils.memory.Memory") as mock_memory_cls,
    ):
        mock_memory_cls.from_config.side_effect = _fake_from_config
        from app.utils.memory import get_memory_client

        get_memory_client()

    return captured


class TestEmbeddingDimsPropagation:
    def test_embedding_dims_propagated_to_vector_store(self):
        captured = _captured_config(_config(embedding_dims=768))
        assert captured["vector_store"]["config"]["embedding_model_dims"] == 768

    def test_non_standard_dims_propagated(self):
        captured = _captured_config(_config(embedding_dims=1024))
        assert captured["vector_store"]["config"]["embedding_model_dims"] == 1024

    def test_no_embedding_dims_leaves_vector_store_untouched(self):
        captured = _captured_config(_config(embedding_dims=None))
        assert "embedding_model_dims" not in captured["vector_store"]["config"]

    def test_missing_vector_store_config_does_not_raise(self):
        # The guard must tolerate a config without a vector_store section rather
        # than raising KeyError while trying to propagate the dims.
        captured = _captured_config(_config(embedding_dims=768, with_vector_store=False))
        assert "vector_store" not in captured
