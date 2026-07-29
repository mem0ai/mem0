"""Regression test for Qdrant collections created with a different vector size."""

from unittest.mock import MagicMock, patch

import pytest

from mem0 import Memory
from mem0.configs.base import MemoryConfig


def _memory_config(path, embedding_dims):
    return MemoryConfig(
        embedder={"provider": "openai", "config": {"embedding_dims": embedding_dims}},
        vector_store={
            "provider": "qdrant",
            "config": {
                "collection_name": "issue-6318",
                "path": str(path),
                "embedding_model_dims": embedding_dims,
            },
        },
    )


def test_issue_6318(tmp_path):
    """A reused 1536-dimensional collection rejects a 1024-dimensional query."""
    embedder = MagicMock()
    embedder.embed.return_value = [0.0] * 1024

    with (
        patch("mem0.memory.main.EmbedderFactory.create", return_value=embedder),
        patch("mem0.memory.main.LlmFactory.create", return_value=MagicMock()),
        patch("mem0.memory.main.SQLiteManager"),
        patch("mem0.memory.main.capture_event"),
        patch("mem0.memory.main.MEM0_TELEMETRY", False),
    ):
        original_memory = Memory(_memory_config(tmp_path, 1536))
        original_memory.vector_store.client.close()

        memory = Memory(_memory_config(tmp_path, 1024))
        try:
            with pytest.raises(ValueError, match=r"1536.*1024"):
                memory.search("What do I like?", user_id="default_user")
        finally:
            memory.vector_store.client.close()
