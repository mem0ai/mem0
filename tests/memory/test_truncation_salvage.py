import logging
from unittest.mock import MagicMock
import pytest

from mem0.memory.main import AsyncMemory, Memory
from mem0.memory.utils import salvage_memory_objects


class TestSalvageMemoryObjects:
    """Unit tests for salvage_memory_objects utility function."""

    def test_clean_json_array(self):
        text = '{"memory": [{"id": "0", "text": "Likes coffee", "attributed_to": "user"}]}'
        result = salvage_memory_objects(text)
        assert len(result) == 1
        assert result[0]["text"] == "Likes coffee"
        assert result[0]["attributed_to"] == "user"

    def test_truncated_mid_second_object(self):
        text = (
            '{"memory": ['
            '{"id": "0", "text": "Likes coffee", "attributed_to": "user"}, '
            '{"id": "1", "text": "Works at Google", "attributed_to": "us'
        )
        result = salvage_memory_objects(text)
        assert len(result) == 1
        assert result[0]["text"] == "Likes coffee"

    def test_truncated_at_comma_after_objects(self):
        text = '{"memory": [{"id": "0", "text": "Fact 1"}, {"id": "1", "text": "Fact 2"}, '
        result = salvage_memory_objects(text)
        assert len(result) == 2
        assert result[0]["text"] == "Fact 1"
        assert result[1]["text"] == "Fact 2"

    def test_truncated_at_opening_brace_of_third_object(self):
        text = '{"memory": [{"id": "0", "text": "Fact 1"}, {"id": "1", "text": "Fact 2"}, {"id": "2", '
        result = salvage_memory_objects(text)
        assert len(result) == 2
        assert result[0]["text"] == "Fact 1"
        assert result[1]["text"] == "Fact 2"

    def test_truncated_inside_markdown_and_think_block(self):
        text = """<think>Extracting facts from the conversation...</think>
```json
{
  "memory": [
    {
      "id": "0",
      "text": "User lives in Seattle",
      "attributed_to": "user"
    },
    {
      "id": "1",
      "text": "User drives an electric car",
      "attributed_to": "user"
    },
    {
      "id": "2",
      "text": "User visited Vancouver in
"""
        result = salvage_memory_objects(text)
        assert len(result) == 2
        assert result[0]["text"] == "User lives in Seattle"
        assert result[1]["text"] == "User drives an electric car"

    def test_facts_key_salvage(self):
        text = '{"facts": [{"text": "Alpha"}, {"text": "Beta"}, {"text": "Trun'
        result = salvage_memory_objects(text)
        assert len(result) == 2
        assert result[0]["text"] == "Alpha"
        assert result[1]["text"] == "Beta"

    def test_string_facts_salvage(self):
        text = '{"facts": ["User is an engineer", "User likes tea", "User plans to tr'
        result = salvage_memory_objects(text)
        assert len(result) == 2
        assert result[0]["text"] == "User is an engineer"
        assert result[1]["text"] == "User likes tea"

    def test_top_level_array_salvage(self):
        text = '[{"text": "Fact A"}, {"text": "Fact B"}, {"text": "Fact C trun'
        result = salvage_memory_objects(text)
        assert len(result) == 2
        assert result[0]["text"] == "Fact A"
        assert result[1]["text"] == "Fact B"

    def test_alternative_fact_keys_normalized(self):
        text = '{"memory": [{"fact": "Loves hiking"}, {"statement": "Reads sci-fi"}]}'
        result = salvage_memory_objects(text)
        assert len(result) == 2
        assert result[0]["text"] == "Loves hiking"
        assert result[1]["text"] == "Reads sci-fi"

    def test_empty_and_whitespace_input(self):
        assert salvage_memory_objects("") == []
        assert salvage_memory_objects("   \n\t ") == []
        assert salvage_memory_objects(None) == []

    def test_completely_invalid_json(self):
        assert salvage_memory_objects("This is a conversational reply with no JSON.") == []


def _setup_mocks_for_salvage(mocker):
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder.return_value.embed_batch.return_value = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store = mocker.MagicMock()
    mock_vector_store.return_value.search.return_value = []
    mock_vector_store.return_value.insert = mocker.MagicMock()
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create", side_effect=[mock_vector_store.return_value, mocker.MagicMock()]
    )

    mock_llm = mocker.MagicMock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())
    mocker.patch("mem0.memory.main.capture_event")

    return mock_llm, mock_vector_store


class TestTruncationEndToEnd:
    """End-to-end tests for sync and async memory extraction with truncation."""

    def test_sync_add_to_vector_store_salvages_truncated_output(self, mocker, caplog):
        mock_llm, _ = _setup_mocks_for_salvage(mocker)

        memory = Memory()
        memory.config = mocker.MagicMock()
        memory.config.custom_instructions = None
        memory.config.custom_update_memory_prompt = None
        memory.custom_instructions = None
        memory.api_version = "v1.1"
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()

        # Simulate max_tokens cutoff mid-generation on the 2nd item
        truncated_response = (
            '{"memory": ['
            '{"id": "0", "text": "User is named Alice", "attributed_to": "user"}, '
            '{"id": "1", "text": "Alice is a software dev'
        )
        memory.llm.generate_response.return_value = truncated_response

        with caplog.at_level(logging.WARNING):
            result = memory._add_to_vector_store(
                messages=[{"role": "user", "content": "I am Alice and work as a software dev"}],
                metadata={},
                filters={},
                infer=True,
            )

        # Confirm salvaged memory was persisted rather than silently dropped
        assert len(result) == 1
        assert result[0]["memory"] == "User is named Alice"
        assert any(
            "Extraction response was truncated; salvaged 1 memory objects" in record.message
            for record in caplog.records
        )

    @pytest.mark.asyncio
    async def test_async_add_to_vector_store_salvages_truncated_output(self, mocker, caplog):
        mock_llm, _ = _setup_mocks_for_salvage(mocker)

        async_memory = AsyncMemory()
        async_memory.config = mocker.MagicMock()
        async_memory.config.custom_instructions = None
        async_memory.config.custom_update_memory_prompt = None
        async_memory.custom_instructions = None
        async_memory.api_version = "v1.1"
        async_memory.db.get_last_messages = MagicMock(return_value=[])
        async_memory.db.save_messages = MagicMock()

        truncated_response = (
            '{"memory": ['
            '{"id": "0", "text": "User is named Bob", "attributed_to": "user"}, '
            '{"id": "1", "text": "Bob has two dogs", "attributed_to": "user"}, '
            '{"id": "2", "text": "One dog is named Ch'
        )
        async_memory.llm.generate_response.return_value = truncated_response

        with caplog.at_level(logging.WARNING):
            result = await async_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "I am Bob and have two dogs"}],
                metadata={},
                effective_filters={},
                infer=True,
            )

        assert len(result) == 2
        assert result[0]["memory"] == "User is named Bob"
        assert result[1]["memory"] == "Bob has two dogs"
        assert any(
            "Extraction response was truncated; salvaged 2 memory objects (async)" in record.message
            for record in caplog.records
        )
