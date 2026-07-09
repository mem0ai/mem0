"""Regression test for issue #6101.

Verifies that an LLM provider/transport failure during extraction propagates to
the caller instead of being silently collapsed into an empty extraction result.
"""

import importlib.metadata
import sys
from unittest.mock import MagicMock

import pytest

importlib.metadata.version = MagicMock(return_value="0.0.0")
sys.modules.setdefault("posthog", MagicMock(Posthog=MagicMock()))

from mem0 import Memory
from mem0.exceptions import LLMError


def test_issue_6101(monkeypatch):
    class _ProviderError(Exception):
        pass

    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [0.1, 0.2, 0.3]

    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = []

    mock_history_store = MagicMock()

    mock_llm = MagicMock()
    mock_llm.generate_response.side_effect = _ProviderError("429 rate limit")

    monkeypatch.setattr("mem0.utils.factory.EmbedderFactory.create", MagicMock(return_value=mock_embedder))
    monkeypatch.setattr(
        "mem0.utils.factory.VectorStoreFactory.create",
        MagicMock(side_effect=[mock_vector_store, mock_history_store]),
    )
    monkeypatch.setattr("mem0.utils.factory.LlmFactory.create", MagicMock(return_value=mock_llm))
    monkeypatch.setattr("mem0.memory.storage.SQLiteManager", MagicMock())
    monkeypatch.setattr("mem0.memory.main.capture_event", MagicMock())

    memory = Memory()
    memory.db.get_last_messages = MagicMock(return_value=[])
    memory.db.save_messages = MagicMock()

    with pytest.raises(LLMError) as exc_info:
        memory.add([{"role": "user", "content": "hello"}], user_id="u1")

    assert isinstance(exc_info.value.__cause__, _ProviderError)
