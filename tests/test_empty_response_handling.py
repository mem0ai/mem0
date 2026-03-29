"""Tests for empty/invalid LLM response handling in fact extraction.

When LLMs like Groq compound models return non-JSON or empty responses
for the fact extraction call, _add_to_vector_store should handle it
gracefully instead of crashing.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from mem0 import Memory


@pytest.fixture
def memory_instance():
    with patch("mem0.memory.main.MemoryBase.__init__", return_value=None), \
         patch("mem0.memory.main.capture_event"):
        m = Memory.__new__(Memory)
        m.config = MagicMock()
        m.config.custom_fact_extraction_prompt = None
        m.config.custom_update_memory_prompt = None
        m.config.version = "v1.0"
        m.api_version = "v1.0"
        m.llm = MagicMock()
        m.embedding_model = MagicMock()
        m.vector_store = MagicMock()
        m.db = MagicMock()
        m.enable_graph = False
        yield m


class TestFactExtractionErrorHandling:
    """Verify _add_to_vector_store handles bad LLM responses for fact extraction."""

    def test_none_response_returns_empty(self, memory_instance):
        """None from generate_response should not crash."""
        memory_instance.llm.generate_response.return_value = None
        memory_instance._should_use_agent_memory_extraction = Mock(return_value=False)

        result = memory_instance._add_to_vector_store(
            messages=[{"role": "user", "content": "Hello"}],
            metadata={"user_id": "test"},
            filters={"user_id": "test"},
            infer=True,
        )
        assert result == []

    def test_empty_string_response_returns_empty(self, memory_instance):
        """Empty string from generate_response should not crash."""
        memory_instance.llm.generate_response.return_value = ""
        memory_instance._should_use_agent_memory_extraction = Mock(return_value=False)

        result = memory_instance._add_to_vector_store(
            messages=[{"role": "user", "content": "Hello"}],
            metadata={"user_id": "test"},
            filters={"user_id": "test"},
            infer=True,
        )
        assert result == []

    def test_non_json_response_returns_empty(self, memory_instance):
        """Plain text (non-JSON) response should not crash."""
        memory_instance.llm.generate_response.return_value = "I cannot help with that request."
        memory_instance._should_use_agent_memory_extraction = Mock(return_value=False)

        result = memory_instance._add_to_vector_store(
            messages=[{"role": "user", "content": "Hello"}],
            metadata={"user_id": "test"},
            filters={"user_id": "test"},
            infer=True,
        )
        assert result == []

    def test_generate_response_exception_returns_empty(self, memory_instance):
        """If generate_response raises, should not crash."""
        memory_instance.llm.generate_response.side_effect = Exception("API error: unsupported parameter")
        memory_instance._should_use_agent_memory_extraction = Mock(return_value=False)

        result = memory_instance._add_to_vector_store(
            messages=[{"role": "user", "content": "Hello"}],
            metadata={"user_id": "test"},
            filters={"user_id": "test"},
            infer=True,
        )
        assert result == []
