import logging
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

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
        memory.config.custom_instructions = None
        memory.config.custom_update_memory_prompt = None
        memory.custom_instructions = None
        memory.api_version = "v1.1"
        # v3 pipeline needs db.get_last_messages to return a list
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()

        return memory

    def test_empty_llm_response_fact_extraction(self, mocker, mock_memory, caplog):
        """Test invalid JSON response from LLM during extraction"""
        # Setup
        mock_memory.llm.generate_response.return_value = "invalid json"
        mocker.patch("mem0.memory.main.capture_event")

        # Execute
        with caplog.at_level(logging.ERROR):
            result = mock_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, filters={}, infer=True
            )

        # Verify — v3 single-pass pipeline makes 1 LLM call, returns [] on parse error
        assert mock_memory.llm.generate_response.call_count == 1
        assert result == []
        assert any("Error parsing extraction response" in record.message for record in caplog.records), "Expected error message not found in logs"

    def test_empty_llm_response_memory_actions(self, mock_memory, caplog):
        """Test empty response from LLM during memory actions (v3: single-pass, 1 LLM call)"""
        # Setup — v3 pipeline does a single LLM call that returns empty/invalid response
        mock_memory.llm.generate_response.return_value = ""

        # Execute
        with caplog.at_level(logging.WARNING):
            result = mock_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, filters={}, infer=True
            )

        # Verify — v3 only makes 1 LLM call (no separate merge step)
        assert mock_memory.llm.generate_response.call_count == 1
        assert result == []  # Should return empty list when no memories processed


class TestPromptOverridesCustomInstructions:
    @pytest.fixture
    def mock_memory(self, mocker):
        mock_llm, _ = _setup_mocks(mocker)
        mock_llm.return_value.generate_response.return_value = '{"memory": []}'

        memory = Memory()
        memory.custom_instructions = "config-level instructions"
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()
        return memory

    def test_prompt_overrides_custom_instructions(self, mock_memory):
        mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "hello"}],
            metadata={},
            filters={},
            infer=True,
            prompt="per-call override",
        )

        user_prompt = mock_memory.llm.generate_response.call_args[1]["messages"][1]["content"]
        assert "per-call override" in user_prompt
        assert "config-level instructions" not in user_prompt

    def test_falls_back_to_custom_instructions_when_no_prompt(self, mock_memory):
        mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "hello"}],
            metadata={},
            filters={},
            infer=True,
        )

        user_prompt = mock_memory.llm.generate_response.call_args[1]["messages"][1]["content"]
        assert "config-level instructions" in user_prompt


class TestAsyncUpdate:
    @pytest.fixture
    def mock_async_memory(self, mocker):
        """Fixture for AsyncMemory with mocker-based mocks"""
        _setup_mocks(mocker)
        memory = AsyncMemory()
        return memory

    @pytest.mark.asyncio
    async def test_async_update_without_metadata(self, mock_async_memory, mocker):
        """Test async update passes None metadata by default"""
        mock_async_memory.embedding_model = Mock()
        mock_async_memory.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
        mock_async_memory._update_memory = mocker.AsyncMock()

        result = await mock_async_memory.update("test_id", "Updated memory")

        mock_async_memory._update_memory.assert_called_once_with(
            "test_id", "Updated memory", {"Updated memory": [0.1, 0.2, 0.3]}, None
        )
        assert result["message"] == "Memory updated successfully!"

    @pytest.mark.asyncio
    async def test_async_update_with_metadata(self, mock_async_memory, mocker):
        """Test async update correctly forwards metadata"""
        mock_async_memory.embedding_model = Mock()
        mock_async_memory.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
        mock_async_memory._update_memory = mocker.AsyncMock()
        metadata = {"category": "sports", "priority": "high"}

        result = await mock_async_memory.update("test_id", "Updated memory", metadata=metadata)

        mock_async_memory._update_memory.assert_called_once_with(
            "test_id", "Updated memory", {"Updated memory": [0.1, 0.2, 0.3]}, metadata
        )
        assert result["message"] == "Memory updated successfully!"

    @pytest.mark.asyncio
    async def test_async_update_with_empty_metadata(self, mock_async_memory, mocker):
        """Test async update with empty metadata dict"""
        mock_async_memory.embedding_model = Mock()
        mock_async_memory.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
        mock_async_memory._update_memory = mocker.AsyncMock()

        await mock_async_memory.update("test_id", "Updated memory", metadata={})

        mock_async_memory._update_memory.assert_called_once_with(
            "test_id", "Updated memory", {"Updated memory": [0.1, 0.2, 0.3]}, {}
        )

    @pytest.mark.asyncio
    async def test_async_update_can_change_expiration_date_without_changing_text(self, mock_async_memory, mocker):
        mock_async_memory.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
        mock_async_memory.vector_store.get = Mock(
            return_value=Mock(
                payload={
                    "data": "Existing memory",
                    "user_id": "test_user",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "expiration_date": "2026-12-31",
                }
            )
        )
        mock_async_memory.vector_store.update = Mock()
        mock_async_memory.db.add_history = Mock()
        mock_async_memory._remove_memory_from_entity_store = mocker.AsyncMock()
        mock_async_memory._link_entities_for_memory = mocker.AsyncMock()

        result = await mock_async_memory.update("test_id", expiration_date="2999-01-01")

        assert result["message"] == "Memory updated successfully!"
        payload = mock_async_memory.vector_store.update.call_args.kwargs["payload"]
        assert payload["data"] == "Existing memory"
        assert payload["expiration_date"] == "2999-01-01"
        mock_async_memory._remove_memory_from_entity_store.assert_not_called()
        mock_async_memory._link_entities_for_memory.assert_not_called()


@pytest.mark.asyncio
class TestAsyncAddToVectorStoreErrors:
    @pytest.fixture
    def mock_async_memory(self, mocker):
        """Fixture for AsyncMemory with mocker-based mocks"""
        mock_llm, _ = _setup_mocks(mocker)

        memory = AsyncMemory()
        memory.config = mocker.MagicMock()
        memory.config.custom_instructions = None
        memory.config.custom_update_memory_prompt = None
        memory.custom_instructions = None
        memory.api_version = "v1.1"
        # v3 pipeline needs db.get_last_messages to return a list
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()

        return memory

    @pytest.mark.asyncio
    async def test_async_empty_llm_response_fact_extraction(self, mock_async_memory, caplog, mocker):
        """Test invalid JSON response from LLM during extraction (async)"""
        mocker.patch("mem0.utils.factory.EmbedderFactory.create", return_value=MagicMock())
        mock_async_memory.llm.generate_response.return_value = "invalid json"
        mocker.patch("mem0.memory.main.capture_event")

        with caplog.at_level(logging.ERROR):
            result = await mock_async_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, effective_filters={}, infer=True
            )
        assert mock_async_memory.llm.generate_response.call_count == 1
        assert result == []
        assert any("Error parsing extraction response" in record.message for record in caplog.records), "Expected error message not found in logs"

    @pytest.mark.asyncio
    async def test_async_empty_llm_response_memory_actions(self, mock_async_memory, caplog, mocker):
        """Test empty response in AsyncMemory._add_to_vector_store (v3: single-pass, 1 LLM call)"""
        mocker.patch("mem0.utils.factory.EmbedderFactory.create", return_value=MagicMock())
        mock_async_memory.llm.generate_response.return_value = ""
        mock_capture_event = mocker.MagicMock()
        mocker.patch("mem0.memory.main.capture_event", mock_capture_event)

        with caplog.at_level(logging.WARNING):
            result = await mock_async_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "test"}], metadata={}, effective_filters={}, infer=True
            )

        assert result == []
        assert mock_async_memory.llm.generate_response.call_count == 1


def _build_memory_instance(mocker, memory_cls):
    _setup_mocks(mocker)
    mocker.patch("mem0.memory.main.SQLiteManager", mocker.MagicMock())
    mocker.patch("mem0.memory.main.MEM0_TELEMETRY", False)
    memory = memory_cls()
    memory.config = mocker.MagicMock()
    memory.config.custom_instructions = None
    memory.config.custom_update_memory_prompt = None
    memory.api_version = "v1.1"
    memory.vector_store = mocker.MagicMock()
    memory.db = mocker.MagicMock()
    return memory


def _assert_utc_timestamp(timestamp: str):
    parsed = datetime.fromisoformat(timestamp)
    assert parsed.tzinfo == timezone.utc
    assert parsed.utcoffset().total_seconds() == 0


def test_create_memory_uses_utc_timestamps(mocker):
    memory = _build_memory_instance(mocker, Memory)
    memory._create_memory("new memory", {"new memory": [0.1, 0.2, 0.3]}, metadata={})
    payload = memory.vector_store.insert.call_args.kwargs["payloads"][0]
    _assert_utc_timestamp(payload["created_at"])


def test_create_memory_sets_updated_at(mocker):
    memory = _build_memory_instance(mocker, Memory)
    memory._create_memory("new memory", {"new memory": [0.1, 0.2, 0.3]}, metadata={})
    payload = memory.vector_store.insert.call_args.kwargs["payloads"][0]
    assert "updated_at" in payload
    assert payload["updated_at"] == payload["created_at"]
    _assert_utc_timestamp(payload["updated_at"])

    # History should also receive updated_at
    history_kwargs = memory.db.add_history.call_args
    assert history_kwargs.kwargs["updated_at"] == payload["updated_at"]


def test_create_memory_preserves_existing_created_at(mocker):
    memory = _build_memory_instance(mocker, Memory)
    custom_ts = "2023-05-06T09:19:20+00:00"
    memory._create_memory("new memory", {"new memory": [0.1, 0.2, 0.3]}, metadata={"created_at": custom_ts})
    payload = memory.vector_store.insert.call_args.kwargs["payloads"][0]
    assert payload["created_at"] == custom_ts
    assert payload["updated_at"] == custom_ts


def test_update_memory_uses_utc_timestamps(mocker):
    memory = _build_memory_instance(mocker, Memory)
    memory.vector_store.get.return_value = MagicMock(
        payload={"data": "old memory", "created_at": "2026-03-17T17:00:00-07:00"}
    )
    memory._update_memory("memory-id", "new memory", {"new memory": [0.1, 0.2, 0.3]}, metadata={})
    payload = memory.vector_store.update.call_args.kwargs["payload"]
    assert payload["created_at"] == "2026-03-17T17:00:00-07:00"
    assert payload["updated_at"] is not None


@pytest.mark.asyncio
async def test_async_create_memory_uses_utc_timestamps(mocker):
    memory = _build_memory_instance(mocker, AsyncMemory)
    await memory._create_memory("new memory", {"new memory": [0.1, 0.2, 0.3]}, metadata={})
    payload = memory.vector_store.insert.call_args.kwargs["payloads"][0]
    _assert_utc_timestamp(payload["created_at"])


@pytest.mark.asyncio
async def test_async_create_memory_sets_updated_at(mocker):
    memory = _build_memory_instance(mocker, AsyncMemory)
    await memory._create_memory("new memory", {"new memory": [0.1, 0.2, 0.3]}, metadata={})
    payload = memory.vector_store.insert.call_args.kwargs["payloads"][0]
    assert "updated_at" in payload
    assert payload["updated_at"] == payload["created_at"]
    _assert_utc_timestamp(payload["updated_at"])

    # History should also receive updated_at
    history_kwargs = memory.db.add_history.call_args
    assert history_kwargs.kwargs["updated_at"] == payload["updated_at"]


@pytest.mark.asyncio
async def test_async_create_memory_preserves_existing_created_at(mocker):
    memory = _build_memory_instance(mocker, AsyncMemory)
    custom_ts = "2023-05-06T09:19:20+00:00"
    await memory._create_memory("new memory", {"new memory": [0.1, 0.2, 0.3]}, metadata={"created_at": custom_ts})
    payload = memory.vector_store.insert.call_args.kwargs["payloads"][0]
    assert payload["created_at"] == custom_ts
    assert payload["updated_at"] == custom_ts


@pytest.mark.asyncio
async def test_async_update_memory_uses_utc_timestamps(mocker):
    memory = _build_memory_instance(mocker, AsyncMemory)
    memory.vector_store.get.return_value = MagicMock(
        payload={"data": "old memory", "created_at": "2026-03-17T17:00:00-07:00"}
    )
    await memory._update_memory("memory-id", "new memory", {"new memory": [0.1, 0.2, 0.3]}, metadata={})
    payload = memory.vector_store.update.call_args.kwargs["payload"]
    assert payload["created_at"] == "2026-03-17T17:00:00-07:00"
    assert payload["updated_at"] is not None


def test_create_then_search_and_get_all_return_same_timestamps(mocker):
    """Reproduces issue #3720: created_at must be identical in search() and get_all()."""
    memory = _build_memory_instance(mocker, Memory)

    # Step 1: Create a memory — capture the payload stored in the vector store
    memory._create_memory("Likes pizza", {"Likes pizza": [0.1, 0.2, 0.3]}, metadata={"user_id": "alice"})
    stored_payload = memory.vector_store.insert.call_args.kwargs["payloads"][0]
    stored_id = memory.vector_store.insert.call_args.kwargs["ids"][0]

    # Verify both timestamps were stored
    assert stored_payload["created_at"] is not None
    assert stored_payload["updated_at"] is not None
    assert stored_payload["updated_at"] == stored_payload["created_at"]

    # Step 2: Simulate the vector store returning this memory for both search and get_all
    mem_result = MagicMock()
    mem_result.id = stored_id
    mem_result.payload = stored_payload
    mem_result.score = 0.95

    memory.vector_store.search.return_value = [mem_result]
    memory.vector_store.list.return_value = [[mem_result]]

    # Step 3: Call search and get_all, compare timestamps
    search_results = memory._search_vector_store("pizza", filters={"user_id": "alice"}, limit=10)
    get_all_results = memory._get_all_from_vector_store(filters={"user_id": "alice"}, limit=100)

    search_item = search_results[0]
    get_all_item = get_all_results[0]

    # The core assertion from issue #3720: created_at must be the same
    assert search_item["created_at"] == get_all_item["created_at"], (
        f"created_at mismatch: search={search_item['created_at']}, get_all={get_all_item['created_at']}"
    )
    assert search_item["updated_at"] == get_all_item["updated_at"], (
        f"updated_at mismatch: search={search_item['updated_at']}, get_all={get_all_item['updated_at']}"
    )

    # Neither should be None
    assert search_item["created_at"] is not None
    assert search_item["updated_at"] is not None
    assert get_all_item["created_at"] is not None
    assert get_all_item["updated_at"] is not None


def test_update_preserves_created_at_and_updates_updated_at(mocker):
    """After an update, created_at must stay the same and updated_at must change."""
    memory = _build_memory_instance(mocker, Memory)

    # Create a memory
    memory._create_memory("Likes pizza", {"Likes pizza": [0.1, 0.2, 0.3]}, metadata={"user_id": "alice"})
    created_payload = memory.vector_store.insert.call_args.kwargs["payloads"][0]
    created_id = memory.vector_store.insert.call_args.kwargs["ids"][0]
    original_created_at = created_payload["created_at"]

    # Update the memory — simulate existing memory in vector store
    memory.vector_store.get.return_value = MagicMock(
        id=created_id,
        payload=created_payload,
    )
    memory._update_memory(created_id, "Loves pizza", {"Loves pizza": [0.2, 0.3, 0.4]}, metadata={})
    updated_payload = memory.vector_store.update.call_args.kwargs["payload"]

    # created_at must be preserved
    assert updated_payload["created_at"] == original_created_at
    # updated_at must be set and different from creation time (or at least present)
    assert updated_payload["updated_at"] is not None
    _assert_utc_timestamp(updated_payload["updated_at"])


def test_search_and_get_all_consistent_after_update(mocker):
    """After update, search and get_all must still return the same timestamps."""
    memory = _build_memory_instance(mocker, Memory)

    # Simulate a memory that was created then updated
    updated_payload = {
        "data": "Loves pizza",
        "hash": "abc123",
        "user_id": "alice",
        "created_at": "2023-05-06T09:19:20+00:00",
        "updated_at": "2026-03-23T10:00:00+00:00",
    }

    mem_result = MagicMock()
    mem_result.id = "mem-1"
    mem_result.payload = updated_payload
    mem_result.score = 0.9

    memory.vector_store.search.return_value = [mem_result]
    memory.vector_store.list.return_value = [[mem_result]]

    search_results = memory._search_vector_store("pizza", filters={"user_id": "alice"}, limit=10)
    get_all_results = memory._get_all_from_vector_store(filters={"user_id": "alice"}, limit=100)

    assert search_results[0]["created_at"] == get_all_results[0]["created_at"]
    assert search_results[0]["updated_at"] == get_all_results[0]["updated_at"]
    # created_at should be the original, not the updated time
    assert search_results[0]["created_at"] == "2023-05-06T09:19:20+00:00"
    assert search_results[0]["updated_at"] == "2026-03-23T10:00:00+00:00"


class TestMetadataNotMutated:
    """Tests that metadata dicts passed to memory methods are not mutated in-place (issue #2648)."""

    def test_create_memory_does_not_mutate_metadata(self, mocker):
        memory = _build_memory_instance(mocker, Memory)
        original_metadata = {"user_id": "test_user", "category": "sports"}
        metadata_copy = original_metadata.copy()

        memory._create_memory("test data", {"test data": [0.1, 0.2, 0.3]}, metadata=original_metadata)

        assert original_metadata == metadata_copy, (
            f"_create_memory mutated the caller's metadata dict: {original_metadata} != {metadata_copy}"
        )

    def test_create_memory_stores_correct_payload(self, mocker):
        memory = _build_memory_instance(mocker, Memory)
        metadata = {"user_id": "test_user", "category": "sports"}

        memory._create_memory("test data", {"test data": [0.1, 0.2, 0.3]}, metadata=metadata)

        payload = memory.vector_store.insert.call_args.kwargs["payloads"][0]
        assert payload["data"] == "test data"
        assert payload["user_id"] == "test_user"
        assert payload["category"] == "sports"
        assert "hash" in payload
        assert "created_at" in payload

    def test_create_memory_with_none_metadata(self, mocker):
        memory = _build_memory_instance(mocker, Memory)

        memory._create_memory("test data", {"test data": [0.1, 0.2, 0.3]}, metadata=None)

        payload = memory.vector_store.insert.call_args.kwargs["payloads"][0]
        assert payload["data"] == "test data"
        assert "hash" in payload

    def test_create_memory_shared_metadata_across_calls(self, mocker):
        """Verify that sharing a metadata dict between multiple _create_memory calls is safe."""
        memory = _build_memory_instance(mocker, Memory)
        shared_metadata = {"user_id": "test_user"}

        memory._create_memory("first memory", {"first memory": [0.1, 0.2, 0.3]}, metadata=shared_metadata)
        memory._create_memory("second memory", {"second memory": [0.4, 0.5, 0.6]}, metadata=shared_metadata)

        assert shared_metadata == {"user_id": "test_user"}, "shared metadata was mutated across calls"

        # Verify each call got the correct data
        first_payload = memory.vector_store.insert.call_args_list[0].kwargs["payloads"][0]
        second_payload = memory.vector_store.insert.call_args_list[1].kwargs["payloads"][0]
        assert first_payload["data"] == "first memory"
        assert second_payload["data"] == "second memory"

    def test_create_memory_preserves_role_and_actor_id_in_history(self, mocker):
        """Verify that role and actor_id from metadata flow through to add_history after deepcopy."""
        memory = _build_memory_instance(mocker, Memory)
        metadata = {"user_id": "test_user", "role": "assistant", "actor_id": "bot-1"}

        memory._create_memory("test data", {"test data": [0.1, 0.2, 0.3]}, metadata=metadata)

        # Verify the payload stored in vector store has all fields
        payload = memory.vector_store.insert.call_args.kwargs["payloads"][0]
        assert payload["role"] == "assistant"
        assert payload["actor_id"] == "bot-1"
        assert payload["user_id"] == "test_user"
        assert payload["data"] == "test data"

        # Verify add_history received the correct role and actor_id
        history_call = memory.db.add_history.call_args
        assert history_call.kwargs["role"] == "assistant"
        assert history_call.kwargs["actor_id"] == "bot-1"

        # And the original metadata is still untouched
        assert metadata == {"user_id": "test_user", "role": "assistant", "actor_id": "bot-1"}

    def test_create_memory_with_nested_metadata_not_mutated(self, mocker):
        """Verify deepcopy protects nested structures in metadata."""
        memory = _build_memory_instance(mocker, Memory)
        metadata = {"user_id": "test_user", "tags": ["important", "urgent"], "config": {"key": "val"}}
        import copy
        metadata_snapshot = copy.deepcopy(metadata)

        memory._create_memory("test data", {"test data": [0.1, 0.2, 0.3]}, metadata=metadata)

        assert metadata == metadata_snapshot, "Nested metadata structures were mutated"

    def test_update_memory_does_not_mutate_metadata(self, mocker):
        memory = _build_memory_instance(mocker, Memory)
        memory.vector_store.get.return_value = MagicMock(
            payload={"data": "old data", "user_id": "test_user", "created_at": "2026-01-01T00:00:00+00:00"}
        )
        original_metadata = {"category": "updated"}
        metadata_copy = original_metadata.copy()

        memory._update_memory("mem-id", "new data", {"new data": [0.1, 0.2, 0.3]}, metadata=original_metadata)

        assert original_metadata == metadata_copy, (
            f"_update_memory mutated the caller's metadata dict: {original_metadata} != {metadata_copy}"
        )

    def test_add_to_vector_store_no_infer_does_not_mutate_metadata(self, mocker):
        """Verify _add_to_vector_store with infer=False doesn't leak metadata between messages."""
        memory = _build_memory_instance(mocker, Memory)
        memory.embedding_model.embed.return_value = [0.1, 0.2, 0.3]

        original_metadata = {"user_id": "test_user"}
        metadata_copy = original_metadata.copy()

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there", "name": "bot-1"},
        ]

        result = memory._add_to_vector_store(messages, original_metadata, filters={}, infer=False)

        # Metadata should not be mutated
        assert original_metadata == metadata_copy, (
            f"_add_to_vector_store mutated the caller's metadata: {original_metadata}"
        )

        # Should have created 2 memories
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"
        assert result[1]["actor_id"] == "bot-1"

        # Verify each insert got distinct payloads with correct roles
        insert_calls = memory.vector_store.insert.call_args_list
        first_payload = insert_calls[0].kwargs["payloads"][0]
        second_payload = insert_calls[1].kwargs["payloads"][0]
        assert first_payload["role"] == "user"
        assert "actor_id" not in first_payload  # user message has no name
        assert second_payload["role"] == "assistant"
        assert second_payload["actor_id"] == "bot-1"

    @pytest.mark.asyncio
    async def test_async_create_memory_does_not_mutate_metadata(self, mocker):
        memory = _build_memory_instance(mocker, AsyncMemory)
        original_metadata = {"user_id": "test_user", "category": "sports"}
        metadata_copy = original_metadata.copy()

        await memory._create_memory("test data", {"test data": [0.1, 0.2, 0.3]}, metadata=original_metadata)

        assert original_metadata == metadata_copy, (
            f"async _create_memory mutated the caller's metadata dict: {original_metadata} != {metadata_copy}"
        )

    @pytest.mark.asyncio
    async def test_async_create_memory_shared_metadata_across_calls(self, mocker):
        memory = _build_memory_instance(mocker, AsyncMemory)
        shared_metadata = {"user_id": "test_user"}

        await memory._create_memory("first memory", {"first memory": [0.1, 0.2, 0.3]}, metadata=shared_metadata)
        await memory._create_memory("second memory", {"second memory": [0.4, 0.5, 0.6]}, metadata=shared_metadata)

        assert shared_metadata == {"user_id": "test_user"}, "shared metadata was mutated across async calls"

    @pytest.mark.asyncio
    async def test_async_add_to_vector_store_no_infer_does_not_mutate_metadata(self, mocker):
        """Verify async _add_to_vector_store with infer=False doesn't leak metadata between messages."""
        memory = _build_memory_instance(mocker, AsyncMemory)
        memory.embedding_model.embed.return_value = [0.1, 0.2, 0.3]

        original_metadata = {"user_id": "test_user"}
        metadata_copy = original_metadata.copy()

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there", "name": "bot-1"},
        ]

        result = await memory._add_to_vector_store(messages, original_metadata, effective_filters={}, infer=False)

        assert original_metadata == metadata_copy, (
            f"async _add_to_vector_store mutated the caller's metadata: {original_metadata}"
        )
        assert len(result) == 2
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_async_update_memory_does_not_mutate_metadata(self, mocker):
        memory = _build_memory_instance(mocker, AsyncMemory)
        memory.vector_store.get.return_value = MagicMock(
            payload={"data": "old data", "user_id": "test_user", "created_at": "2026-01-01T00:00:00+00:00"}
        )
        original_metadata = {"category": "updated"}
        metadata_copy = original_metadata.copy()

        await memory._update_memory("mem-id", "new data", {"new data": [0.1, 0.2, 0.3]}, metadata=original_metadata)

        assert original_metadata == metadata_copy, (
            f"async _update_memory mutated the caller's metadata dict: {original_metadata} != {metadata_copy}"
        )


def test_update_preserves_actor_id_when_different_actor_updates(mocker):
    """actor_id must be preserved from the original memory even when the
    updating caller passes a different actor_id in metadata (issue #4490)."""
    memory = _build_memory_instance(mocker, Memory)
    memory.vector_store.get.return_value = MagicMock(
        payload={
            "data": "I am player #1",
            "user_id": "team",
            "actor_id": "Alice",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )

    memory._update_memory(
        "mem-id", "Player #1 is a good person",
        {"Player #1 is a good person": [0.1, 0.2, 0.3]},
        metadata={"user_id": "team", "actor_id": "Bob"},
    )

    stored = memory.vector_store.update.call_args.kwargs["payload"]
    assert stored["actor_id"] == "Alice"


@pytest.mark.asyncio
async def test_async_update_preserves_actor_id_when_different_actor_updates(mocker):
    """Async variant: actor_id must be preserved from the original memory (issue #4490)."""
    memory = _build_memory_instance(mocker, AsyncMemory)
    memory.vector_store.get.return_value = MagicMock(
        payload={
            "data": "I am player #1",
            "user_id": "team",
            "actor_id": "Alice",
            "created_at": "2026-01-01T00:00:00+00:00",
        }
    )

    await memory._update_memory(
        "mem-id", "Player #1 is a good person",
        {"Player #1 is a good person": [0.1, 0.2, 0.3]},
        metadata={"user_id": "team", "actor_id": "Bob"},
    )

    stored = memory.vector_store.update.call_args.kwargs["payload"]
    assert stored["actor_id"] == "Alice"


def _make_match(score, linked_memory_ids):
    return SimpleNamespace(score=score, payload={"linked_memory_ids": linked_memory_ids})


class TestEntityBoostParallelism:
    """Tests for parallelized entity boost searches (#5214)."""

    @pytest.fixture
    def mock_memory(self, mocker):
        _setup_mocks(mocker)
        return Memory()

    @pytest.fixture
    def mock_async_memory(self, mocker):
        _setup_mocks(mocker)
        return AsyncMemory()

    def test_sync_boosts_preserve_scoring(self, mock_memory):
        from mem0.utils.scoring import ENTITY_BOOST_WEIGHT

        mock_memory.embedding_model = Mock()
        mock_memory.embedding_model.embed_batch = Mock(return_value=[[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]])

        results_by_query = {
            "alice": [_make_match(0.9, ["mem-1"])],
            "bob": [_make_match(0.6, ["mem-1", "mem-2"])],
        }

        def fake_search(query, vectors, top_k, filters):
            return results_by_query[query]

        mock_memory._entity_store = Mock()
        mock_memory._entity_store.search = Mock(side_effect=fake_search)

        boosts = mock_memory._compute_entity_boosts(
            [("person", "alice"), ("person", "bob")],
            {"user_id": "u1"},
        )

        boost_alice = 0.9 * ENTITY_BOOST_WEIGHT * (1.0 / (1.0 + 0.001 * (0**2)))
        boost_bob = 0.6 * ENTITY_BOOST_WEIGHT * (1.0 / (1.0 + 0.001 * (1**2)))
        assert boosts["mem-1"] == pytest.approx(max(boost_alice, boost_bob))
        assert boosts["mem-2"] == pytest.approx(boost_bob)

    def test_sync_embed_batch_called_once(self, mock_memory):
        mock_memory.embedding_model = Mock()
        mock_memory.embedding_model.embed_batch = Mock(return_value=[[0.1], [0.1], [0.1]])
        mock_memory._entity_store = Mock()
        mock_memory._entity_store.search = Mock(return_value=[_make_match(0.7, ["mem-1"])])

        mock_memory._compute_entity_boosts(
            [("person", "alice"), ("person", "bob"), ("person", "carol")],
            {"user_id": "u1"},
        )

        mock_memory.embedding_model.embed_batch.assert_called_once_with(["alice", "bob", "carol"], "search")

    @pytest.mark.asyncio
    async def test_async_boosts_preserve_scoring(self, mock_async_memory):
        from mem0.utils.scoring import ENTITY_BOOST_WEIGHT

        mock_async_memory.embedding_model = Mock()
        mock_async_memory.embedding_model.embed_batch = Mock(return_value=[[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]])

        results_by_query = {
            "alice": [_make_match(0.9, ["mem-1"])],
            "bob": [_make_match(0.6, ["mem-1", "mem-2"])],
        }

        def fake_search(query, vectors, top_k, filters):
            return results_by_query[query]

        mock_async_memory._entity_store = Mock()
        mock_async_memory._entity_store.search = Mock(side_effect=fake_search)

        boosts = await mock_async_memory._compute_entity_boosts_async(
            [("person", "alice"), ("person", "bob")],
            {"user_id": "u1"},
        )

        boost_alice = 0.9 * ENTITY_BOOST_WEIGHT * (1.0 / (1.0 + 0.001 * (0**2)))
        boost_bob = 0.6 * ENTITY_BOOST_WEIGHT * (1.0 / (1.0 + 0.001 * (1**2)))
        assert boosts["mem-1"] == pytest.approx(max(boost_alice, boost_bob))
        assert boosts["mem-2"] == pytest.approx(boost_bob)

    @pytest.mark.asyncio
    async def test_async_embed_batch_called_once(self, mock_async_memory):
        mock_async_memory.embedding_model = Mock()
        mock_async_memory.embedding_model.embed_batch = Mock(return_value=[[0.1], [0.1], [0.1]])
        mock_async_memory._entity_store = Mock()
        mock_async_memory._entity_store.search = Mock(return_value=[_make_match(0.7, ["mem-1"])])

        await mock_async_memory._compute_entity_boosts_async(
            [("person", "alice"), ("person", "bob"), ("person", "carol")],
            {"user_id": "u1"},
        )

        mock_async_memory.embedding_model.embed_batch.assert_called_once_with(["alice", "bob", "carol"], "search")

    def test_sync_one_entity_failure_does_not_abort_others(self, mock_memory, caplog):
        mock_memory.embedding_model = Mock()
        mock_memory.embedding_model.embed_batch = Mock(return_value=[[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]])

        def fake_search(query, vectors, top_k, filters):
            if query == "boom":
                raise RuntimeError("provider timeout")
            return [_make_match(0.8, ["mem-9"])]

        mock_memory._entity_store = Mock()
        mock_memory._entity_store.search = Mock(side_effect=fake_search)

        with caplog.at_level(logging.WARNING):
            boosts = mock_memory._compute_entity_boosts(
                [("person", "boom"), ("person", "ok")],
                {"user_id": "u1"},
            )

        assert "mem-9" in boosts
        assert any("Entity boost search failed" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_async_one_entity_failure_does_not_abort_others(self, mock_async_memory, caplog):
        mock_async_memory.embedding_model = Mock()
        mock_async_memory.embedding_model.embed_batch = Mock(return_value=[[0.1, 0.2, 0.3], [0.1, 0.2, 0.3]])

        def fake_search(query, vectors, top_k, filters):
            if query == "boom":
                raise RuntimeError("provider timeout")
            return [_make_match(0.8, ["mem-9"])]

        mock_async_memory._entity_store = Mock()
        mock_async_memory._entity_store.search = Mock(side_effect=fake_search)

        with caplog.at_level(logging.WARNING):
            boosts = await mock_async_memory._compute_entity_boosts_async(
                [("person", "boom"), ("person", "ok")],
                {"user_id": "u1"},
            )

        assert "mem-9" in boosts
        assert any("Entity boost search failed" in r.message for r in caplog.records)

    def test_sync_searches_run_concurrently(self, mock_memory):
        mock_memory.embedding_model = Mock()
        mock_memory.embedding_model.embed_batch = Mock(return_value=[[0.1]] * 4)

        concurrent_count = {"current": 0, "peak": 0}

        def blocking_search(query, vectors, top_k, filters):
            concurrent_count["current"] += 1
            concurrent_count["peak"] = max(concurrent_count["peak"], concurrent_count["current"])
            time.sleep(0.2)
            concurrent_count["current"] -= 1
            return [_make_match(0.7, [f"mem-{query}"])]

        mock_memory._entity_store = Mock()
        mock_memory._entity_store.search = Mock(side_effect=blocking_search)

        entities = [("person", f"e{i}") for i in range(4)]
        start = time.perf_counter()
        boosts = mock_memory._compute_entity_boosts(entities, {"user_id": "u1"})
        elapsed = time.perf_counter() - start

        assert elapsed < 0.75, f"searches did not run concurrently (took {elapsed:.2f}s)"
        assert concurrent_count["peak"] >= 2, "no overlap observed between entity searches"
        assert len(boosts) == 4

    @pytest.mark.asyncio
    async def test_async_searches_run_concurrently(self, mock_async_memory):
        mock_async_memory.embedding_model = Mock()
        mock_async_memory.embedding_model.embed_batch = Mock(return_value=[[0.1]] * 4)

        concurrent_count = {"current": 0, "peak": 0}

        def blocking_search(query, vectors, top_k, filters):
            concurrent_count["current"] += 1
            concurrent_count["peak"] = max(concurrent_count["peak"], concurrent_count["current"])
            time.sleep(0.2)
            concurrent_count["current"] -= 1
            return [_make_match(0.7, [f"mem-{query}"])]

        mock_async_memory._entity_store = Mock()
        mock_async_memory._entity_store.search = Mock(side_effect=blocking_search)

        entities = [("person", f"e{i}") for i in range(4)]
        start = time.perf_counter()
        boosts = await mock_async_memory._compute_entity_boosts_async(entities, {"user_id": "u1"})
        elapsed = time.perf_counter() - start

        assert elapsed < 0.75, f"searches did not run concurrently (took {elapsed:.2f}s)"
        assert concurrent_count["peak"] >= 2, "no overlap observed between entity searches"
        assert len(boosts) == 4


class TestAddPipelineEntityEmbeddingCountGuard:
    """A misbehaving embedder returning fewer (or more) vectors than entity
    texts must not silently drop ALL entity links via a swallowed IndexError.

    Before the fix, `entity_embeddings[i]` (indexed by ordered_keys length) raised
    IndexError on a short return; the outer `except Exception` in the Phase 7
    entity-linking block swallowed it, so no entity was ever searched/inserted and
    no error surfaced. The search path (_compute_entity_boosts) already guarded
    this; the add path did not.
    """

    @pytest.fixture
    def mock_memory(self, mocker):
        mock_llm, _ = _setup_mocks(mocker)
        memory = Memory()
        memory.config = mocker.MagicMock()
        memory.config.custom_instructions = None
        memory.config.custom_update_memory_prompt = None
        memory.custom_instructions = None
        memory.api_version = "v1.1"
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()
        memory.db.batch_add_history = MagicMock()
        return memory

    @pytest.fixture
    def mock_async_memory(self, mocker):
        mock_llm, _ = _setup_mocks(mocker)
        memory = AsyncMemory()
        memory.config = mocker.MagicMock()
        memory.config.custom_instructions = None
        memory.config.custom_update_memory_prompt = None
        memory.custom_instructions = None
        memory.api_version = "v1.1"
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()
        memory.db.batch_add_history = MagicMock()
        return memory

    @staticmethod
    def _short_entity_embed_batch(texts, memory_action="add"):
        # Memory-text embeddings are well-behaved; entity embeddings come back short.
        if memory_action == "add" and any(t in ("Alice", "Bob") for t in texts):
            return [[0.1] * 10]  # 1 vector for 2 entity texts
        return [[0.1] * 10 for _ in texts]

    def test_sync_short_entity_embeddings_still_link_valid_entity(self, mock_memory, mocker, caplog):
        mock_memory.llm.generate_response.return_value = (
            '{"memory": [{"text": "Alice met Bob"}, {"text": "Bob called Alice"}]}'
        )
        mock_memory.embedding_model = Mock()
        mock_memory.embedding_model.embed_batch = Mock(side_effect=self._short_entity_embed_batch)
        mock_memory.embedding_model.embed = Mock(return_value=[0.1] * 10)

        mock_memory._entity_store = Mock()
        mock_memory._entity_store.search_batch = Mock(return_value=[[]])
        mock_memory._entity_store.insert = Mock()
        mock_memory._entity_store.update = Mock()

        mocker.patch(
            "mem0.memory.main.extract_entities_batch",
            return_value=[
                [("person", "Alice"), ("person", "Bob")],
                [("person", "Bob"), ("person", "Alice")],
            ],
        )
        mocker.patch("mem0.memory.main.capture_event")

        with caplog.at_level(logging.WARNING):
            result = mock_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "Alice met Bob; Bob called Alice"}],
                metadata={},
                filters={"user_id": "u1"},
                infer=True,
            )

        # Both memories persist regardless.
        assert len(result) == 2
        # The entity block did NOT abort: it searched + inserted the one valid entity
        # instead of swallowing an IndexError and linking nothing.
        assert mock_memory._entity_store.search_batch.call_count == 1
        assert mock_memory._entity_store.insert.call_count == 1
        assert not any("Batch entity linking failed" in r.message for r in caplog.records), (
            "entity linking aborted on a swallowed IndexError"
        )
        assert any("padding/truncating" in r.message for r in caplog.records), (
            "expected count-mismatch warning was not emitted"
        )

    @pytest.mark.asyncio
    async def test_async_short_entity_embeddings_still_link_valid_entity(self, mock_async_memory, mocker, caplog):
        mock_async_memory.llm.generate_response.return_value = (
            '{"memory": [{"text": "Alice met Bob"}, {"text": "Bob called Alice"}]}'
        )
        mock_async_memory.embedding_model = Mock()
        mock_async_memory.embedding_model.embed_batch = Mock(side_effect=self._short_entity_embed_batch)
        mock_async_memory.embedding_model.embed = Mock(return_value=[0.1] * 10)

        mock_async_memory._entity_store = Mock()
        mock_async_memory._entity_store.search_batch = Mock(return_value=[[]])
        mock_async_memory._entity_store.insert = Mock()
        mock_async_memory._entity_store.update = Mock()

        mocker.patch(
            "mem0.memory.main.extract_entities_batch",
            return_value=[
                [("person", "Alice"), ("person", "Bob")],
                [("person", "Bob"), ("person", "Alice")],
            ],
        )
        mocker.patch("mem0.memory.main.capture_event")

        with caplog.at_level(logging.WARNING):
            result = await mock_async_memory._add_to_vector_store(
                messages=[{"role": "user", "content": "Alice met Bob; Bob called Alice"}],
                metadata={},
                effective_filters={"user_id": "u1"},
                infer=True,
            )

        assert len(result) == 2
        assert mock_async_memory._entity_store.search_batch.call_count == 1
        assert mock_async_memory._entity_store.insert.call_count == 1
        assert not any("Batch entity linking failed" in r.message for r in caplog.records), (
            "async entity linking aborted on a swallowed IndexError"
        )
        assert any("padding/truncating" in r.message for r in caplog.records), (
            "expected count-mismatch warning was not emitted"
        )
