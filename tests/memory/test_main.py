import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from mem0.memory.main import AsyncMemory, Memory, _normalize_iso_timestamp_to_utc


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


def _build_memory_instance(mocker, memory_cls):
    _setup_mocks(mocker)
    mocker.patch("mem0.memory.main.SQLiteManager", mocker.MagicMock())
    mocker.patch("mem0.memory.main.MEM0_TELEMETRY", False)
    memory = memory_cls()
    memory.config = mocker.MagicMock()
    memory.config.custom_fact_extraction_prompt = None
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
    assert payload["created_at"] == "2026-03-18T00:00:00+00:00"
    _assert_utc_timestamp(payload["updated_at"])


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
    assert payload["created_at"] == "2026-03-18T00:00:00+00:00"
    _assert_utc_timestamp(payload["updated_at"])


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
    search_results = memory._search_vector_store("pizza", filters={"user_id": "alice"}, limit=10, threshold=None)
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

    search_results = memory._search_vector_store("pizza", filters={"user_id": "alice"}, limit=10, threshold=None)
    get_all_results = memory._get_all_from_vector_store(filters={"user_id": "alice"}, limit=100)

    assert search_results[0]["created_at"] == get_all_results[0]["created_at"]
    assert search_results[0]["updated_at"] == get_all_results[0]["updated_at"]
    # created_at should be the original, not the updated time
    assert search_results[0]["created_at"] == "2023-05-06T09:19:20+00:00"
    assert search_results[0]["updated_at"] == "2026-03-23T10:00:00+00:00"


def test_normalize_iso_timestamp_to_utc_preserves_naive_values():
    assert _normalize_iso_timestamp_to_utc("2026-03-18T00:00:00") == "2026-03-18T00:00:00"


def test_normalize_iso_timestamp_to_utc_converts_pacific():
    result = _normalize_iso_timestamp_to_utc("2026-03-17T17:00:00-07:00")
    assert result == "2026-03-18T00:00:00+00:00"


def test_normalize_iso_timestamp_to_utc_handles_none():
    assert _normalize_iso_timestamp_to_utc(None) is None


def test_normalize_iso_timestamp_to_utc_handles_empty():
    assert _normalize_iso_timestamp_to_utc("") == ""
