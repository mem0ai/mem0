import logging
from unittest.mock import MagicMock

import pytest

from mem0.memory.main import AsyncMemory, Memory


def _setup_mocks(mocker):
    """Helper to setup common mocks for both sync and async fixtures"""
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store = mocker.MagicMock()
    mock_vector_store.return_value.search.return_value = []
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create", side_effect=[mock_vector_store.return_value, mocker.MagicMock()]
    )

    mock_llm = mocker.MagicMock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)

    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

    return mock_llm, mock_vector_store


class TestAddToVectorStoreErrors:
    @pytest.fixture
    def mock_memory(self, mocker):
        """Fixture that returns a Memory instance with mocker-based mocks"""
        mock_llm, _ = _setup_mocks(mocker)

        memory = Memory()
        memory.config = mocker.MagicMock()
        memory.config.custom_fact_extraction_prompt = None
        memory.config.custom_update_memory_prompt = None
        memory.api_version = "v1.1"

        return memory

    def test_empty_llm_response_fact_extraction(self, mocker, mock_memory, caplog):
        """Test empty response from LLM during fact extraction"""
        # Setup
        mock_memory.llm.generate_response.return_value = "invalid json"  # This will trigger a JSON decode error
        mock_capture_event = mocker.MagicMock()
        mocker.patch("mem0.memory.main.capture_event", mock_capture_event)

        # Execute
        with caplog.at_level(logging.ERROR):
            result = mock_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, filters={}, infer=True
            )

        # Verify
        assert mock_memory.llm.generate_response.call_count == 1
        assert result == []  # Should return empty list when no memories processed
        # Check for error message in any of the log records
        assert any("Error in new_retrieved_facts" in record.msg for record in caplog.records), "Expected error message not found in logs"
        assert mock_capture_event.call_count == 1

    def test_empty_llm_response_memory_actions(self, mock_memory, caplog):
        """Test empty response from LLM during memory actions"""
        # Setup
        # First call returns valid JSON, second call returns empty string
        mock_memory.llm.generate_response.side_effect = ['{"facts": ["test fact"]}', ""]

        # Execute
        with caplog.at_level(logging.WARNING):
            result = mock_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, filters={}, infer=True
            )

        # Verify
        assert mock_memory.llm.generate_response.call_count == 2
        assert result == []  # Should return empty list when no memories processed
        assert "Empty response from LLM, no memories to extract" in caplog.text


class TestCustomPromptJsonInstruction:
    """Test that custom prompts without 'json' get a JSON instruction appended."""

    @pytest.fixture
    def mock_memory_custom_prompt(self, mocker):
        """Fixture that returns a Memory instance with a custom fact extraction prompt."""
        mock_llm, _ = _setup_mocks(mocker)

        memory = Memory()
        memory.config = mocker.MagicMock()
        memory.config.custom_update_memory_prompt = None
        memory.api_version = "v1.1"

        return memory

    def test_custom_prompt_without_json_gets_json_instruction(self, mocker, mock_memory_custom_prompt, caplog):
        """Test that a custom prompt not containing 'json' gets a JSON instruction appended."""
        mock_memory_custom_prompt.config.custom_fact_extraction_prompt = "Extract all important facts from the conversation."
        mock_memory_custom_prompt.llm.generate_response.return_value = '{"facts": ["test fact"]}'
        mock_capture_event = mocker.MagicMock()
        mocker.patch("mem0.memory.main.capture_event", mock_capture_event)

        mock_memory_custom_prompt._add_to_vector_store(
            messages=[{"role": "user", "content": "I like pizza"}], metadata={}, filters={}, infer=True
        )

        # Verify the system prompt passed to generate_response contains the JSON instruction
        call_args = mock_memory_custom_prompt.llm.generate_response.call_args
        system_message = call_args[1]["messages"][0] if "messages" in call_args[1] else call_args[0][0][0]
        assert "json" in system_message["content"].lower()

    def test_custom_prompt_with_json_not_modified(self, mocker, mock_memory_custom_prompt, caplog):
        """Test that a custom prompt already containing 'json' is not modified."""
        original_prompt = "Extract facts and return them in json format."
        mock_memory_custom_prompt.config.custom_fact_extraction_prompt = original_prompt
        mock_memory_custom_prompt.llm.generate_response.return_value = '{"facts": ["test fact"]}'
        mock_capture_event = mocker.MagicMock()
        mocker.patch("mem0.memory.main.capture_event", mock_capture_event)

        mock_memory_custom_prompt._add_to_vector_store(
            messages=[{"role": "user", "content": "I like pizza"}], metadata={}, filters={}, infer=True
        )

        # Verify the system prompt in the first call (fact extraction) is the original (not modified)
        first_call_args = mock_memory_custom_prompt.llm.generate_response.call_args_list[0]
        system_message = first_call_args[1]["messages"][0] if "messages" in first_call_args[1] else first_call_args[0][0][0]
        assert system_message["content"] == original_prompt

    def test_custom_prompt_with_json_uppercase_not_modified(self, mocker, mock_memory_custom_prompt, caplog):
        """Test that a custom prompt containing 'JSON' (uppercase) is not modified."""
        original_prompt = "Extract facts and return in JSON format."
        mock_memory_custom_prompt.config.custom_fact_extraction_prompt = original_prompt
        mock_memory_custom_prompt.llm.generate_response.return_value = '{"facts": ["test fact"]}'
        mock_capture_event = mocker.MagicMock()
        mocker.patch("mem0.memory.main.capture_event", mock_capture_event)

        mock_memory_custom_prompt._add_to_vector_store(
            messages=[{"role": "user", "content": "I like pizza"}], metadata={}, filters={}, infer=True
        )

        # Verify the system prompt in the first call (fact extraction) is the original (not modified)
        first_call_args = mock_memory_custom_prompt.llm.generate_response.call_args_list[0]
        system_message = first_call_args[1]["messages"][0] if "messages" in first_call_args[1] else first_call_args[0][0][0]
        assert system_message["content"] == original_prompt


@pytest.mark.asyncio
class TestAsyncAddToVectorStoreErrors:
    @pytest.fixture
    def mock_async_memory(self, mocker):
        """Fixture for AsyncMemory with mocker-based mocks"""
        mock_llm, _ = _setup_mocks(mocker)

        memory = AsyncMemory()
        memory.config = mocker.MagicMock()
        memory.config.custom_fact_extraction_prompt = None
        memory.config.custom_update_memory_prompt = None
        memory.api_version = "v1.1"

        return memory

    @pytest.mark.asyncio
    async def test_async_empty_llm_response_fact_extraction(self, mock_async_memory, caplog, mocker):
        """Test empty response in AsyncMemory._add_to_vector_store"""
        mocker.patch("mem0.utils.factory.EmbedderFactory.create", return_value=MagicMock())
        mock_async_memory.llm.generate_response.return_value = "invalid json"  # This will trigger a JSON decode error
        mock_capture_event = mocker.MagicMock()
        mocker.patch("mem0.memory.main.capture_event", mock_capture_event)

        with caplog.at_level(logging.ERROR):
            result = await mock_async_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, effective_filters={}, infer=True
            )
        assert mock_async_memory.llm.generate_response.call_count == 1
        assert result == []
        # Check for error message in any of the log records
        assert any("Error in new_retrieved_facts" in record.msg for record in caplog.records), "Expected error message not found in logs"
        assert mock_capture_event.call_count == 1

    @pytest.mark.asyncio
    async def test_async_empty_llm_response_memory_actions(self, mock_async_memory, caplog, mocker):
        """Test empty response in AsyncMemory._add_to_vector_store"""
        mocker.patch("mem0.utils.factory.EmbedderFactory.create", return_value=MagicMock())
        mock_async_memory.llm.generate_response.side_effect = ['{"facts": ["test fact"]}', ""]
        mock_capture_event = mocker.MagicMock()
        mocker.patch("mem0.memory.main.capture_event", mock_capture_event)

        with caplog.at_level(logging.WARNING):
            result = await mock_async_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, effective_filters={}, infer=True
            )

        assert result == []
        assert "Empty response from LLM, no memories to extract" in caplog.text
        assert mock_capture_event.call_count == 1


@pytest.mark.asyncio
class TestAsyncCustomPromptJsonInstruction:
    """Test that custom prompts without 'json' get a JSON instruction appended (async)."""

    @pytest.fixture
    def mock_async_memory_custom_prompt(self, mocker):
        """Fixture for AsyncMemory with a custom fact extraction prompt."""
        mock_llm, _ = _setup_mocks(mocker)

        memory = AsyncMemory()
        memory.config = mocker.MagicMock()
        memory.config.custom_update_memory_prompt = None
        memory.api_version = "v1.1"

        return memory

    @pytest.mark.asyncio
    async def test_async_custom_prompt_without_json_gets_json_instruction(self, mocker, mock_async_memory_custom_prompt):
        """Test that a custom prompt not containing 'json' gets a JSON instruction appended (async)."""
        mocker.patch("mem0.utils.factory.EmbedderFactory.create", return_value=MagicMock())
        mock_async_memory_custom_prompt.config.custom_fact_extraction_prompt = "Extract all important facts from the conversation."
        mock_async_memory_custom_prompt.llm.generate_response.return_value = '{"facts": ["test fact"]}'
        mock_capture_event = mocker.MagicMock()
        mocker.patch("mem0.memory.main.capture_event", mock_capture_event)

        await mock_async_memory_custom_prompt._add_to_vector_store(
            messages=[{"role": "user", "content": "I like pizza"}], metadata={}, effective_filters={}, infer=True
        )

        # Verify the system prompt passed to generate_response contains the JSON instruction
        call_args = mock_async_memory_custom_prompt.llm.generate_response.call_args
        system_message = call_args[1]["messages"][0] if "messages" in call_args[1] else call_args[0][0][0]
        assert "json" in system_message["content"].lower()

    @pytest.mark.asyncio
    async def test_async_custom_prompt_with_json_not_modified(self, mocker, mock_async_memory_custom_prompt):
        """Test that a custom prompt already containing 'json' is not modified (async)."""
        mocker.patch("mem0.utils.factory.EmbedderFactory.create", return_value=MagicMock())
        original_prompt = "Extract facts and return them in json format."
        mock_async_memory_custom_prompt.config.custom_fact_extraction_prompt = original_prompt
        mock_async_memory_custom_prompt.llm.generate_response.return_value = '{"facts": ["test fact"]}'
        mock_capture_event = mocker.MagicMock()
        mocker.patch("mem0.memory.main.capture_event", mock_capture_event)

        await mock_async_memory_custom_prompt._add_to_vector_store(
            messages=[{"role": "user", "content": "I like pizza"}], metadata={}, effective_filters={}, infer=True
        )

        # Verify the system prompt in the first call (fact extraction) is the original (not modified)
        first_call_args = mock_async_memory_custom_prompt.llm.generate_response.call_args_list[0]
        system_message = first_call_args[1]["messages"][0] if "messages" in first_call_args[1] else first_call_args[0][0][0]
        assert system_message["content"] == original_prompt

    @pytest.mark.asyncio
    async def test_async_custom_prompt_with_json_uppercase_not_modified(self, mocker, mock_async_memory_custom_prompt):
        """Test that a custom prompt containing 'JSON' (uppercase) is not modified (async)."""
        mocker.patch("mem0.utils.factory.EmbedderFactory.create", return_value=MagicMock())
        original_prompt = "Extract facts and return in JSON format."
        mock_async_memory_custom_prompt.config.custom_fact_extraction_prompt = original_prompt
        mock_async_memory_custom_prompt.llm.generate_response.return_value = '{"facts": ["test fact"]}'
        mock_capture_event = mocker.MagicMock()
        mocker.patch("mem0.memory.main.capture_event", mock_capture_event)

        await mock_async_memory_custom_prompt._add_to_vector_store(
            messages=[{"role": "user", "content": "I like pizza"}], metadata={}, effective_filters={}, infer=True
        )

        # Verify the system prompt in the first call (fact extraction) is the original (not modified)
        first_call_args = mock_async_memory_custom_prompt.llm.generate_response.call_args_list[0]
        system_message = first_call_args[1]["messages"][0] if "messages" in first_call_args[1] else first_call_args[0][0][0]
        assert system_message["content"] == original_prompt
