from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from mem0.memory import main as memory_main
from mem0.memory.main import AsyncMemory, Memory


def make_sync_memory():
    memory = Memory.__new__(Memory)
    memory.config = SimpleNamespace(llm=SimpleNamespace(config={}))
    memory.api_version = "v1.1"
    memory.reranker = None
    memory._add_to_vector_store = MagicMock(return_value=[])
    memory._search_vector_store = MagicMock(return_value=[])
    return memory


def make_async_memory():
    memory = AsyncMemory.__new__(AsyncMemory)
    memory.config = SimpleNamespace(llm=SimpleNamespace(config={}))
    memory.api_version = "v1.1"
    memory.reranker = None
    memory._add_to_vector_store = AsyncMock(return_value=[])
    memory._search_vector_store = AsyncMock(return_value=[])
    return memory


def test_sync_add_temporal_metadata_triggers_notice_after_success(monkeypatch):
    memory = make_sync_memory()
    temporal_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    result = Memory.add(
        memory,
        "The user visited Paris.",
        user_id="u1",
        metadata={"event_date": "2025-04-09"},
        infer=False,
    )

    assert result == {"results": [], "failed": []}
    memory._add_to_vector_store.assert_called_once()
    temporal_notice.assert_called_once_with(memory, "sync", "add", "metadata", "date_like_metadata")
    first_run_notice.assert_not_called()


def test_sync_add_non_temporal_metadata_uses_first_run_notice(monkeypatch):
    memory = make_sync_memory()
    temporal_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    Memory.add(memory, "The user likes tea.", user_id="u1", metadata={"topic": "drink"}, infer=False)

    temporal_notice.assert_not_called()
    first_run_notice.assert_called_once_with(memory, "sync", "add")


def test_sync_add_failure_does_not_trigger_temporal_usage_notice(monkeypatch):
    memory = make_sync_memory()
    memory._add_to_vector_store.side_effect = RuntimeError("vector failure")
    temporal_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    with pytest.raises(RuntimeError, match="vector failure"):
        Memory.add(
            memory,
            "The user visited Paris.",
            user_id="u1",
            metadata={"event_date": "2025-04-09"},
            infer=False,
        )

    temporal_notice.assert_not_called()
    first_run_notice.assert_not_called()


def test_sync_search_temporal_query_triggers_notice_after_success(monkeypatch):
    memory = make_sync_memory()
    temporal_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    result = Memory.search(memory, "what happened last week?", filters={"user_id": "u1"})

    assert result == {"results": []}
    memory._search_vector_store.assert_called_once()
    temporal_notice.assert_called_once_with(memory, "sync", "search", "query", "relative_phrase")
    first_run_notice.assert_not_called()


def test_sync_search_temporal_filter_triggers_notice_after_success(monkeypatch):
    memory = make_sync_memory()
    temporal_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", MagicMock())

    Memory.search(
        memory,
        "favorite drink",
        filters={"user_id": "u1", "created_at": {"gte": "2025-04-01"}},
    )

    temporal_notice.assert_called_once_with(memory, "sync", "search", "filter", "date_range_filter")


def test_sync_search_failure_does_not_trigger_temporal_usage_notice(monkeypatch):
    memory = make_sync_memory()
    memory._search_vector_store.side_effect = RuntimeError("search failure")
    temporal_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", MagicMock())

    with pytest.raises(RuntimeError, match="search failure"):
        Memory.search(memory, "what happened last week?", filters={"user_id": "u1"})

    temporal_notice.assert_not_called()


@pytest.mark.asyncio
async def test_async_add_temporal_metadata_triggers_notice_after_success(monkeypatch):
    memory = make_async_memory()
    temporal_notice = AsyncMock()
    first_run_notice = AsyncMock()
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice_async", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", first_run_notice)

    result = await AsyncMemory.add(
        memory,
        "The user visited Paris.",
        user_id="u1",
        metadata={"event_date": "2025-04-09"},
        infer=False,
    )

    assert result == {"results": [], "failed": []}
    memory._add_to_vector_store.assert_awaited_once()
    temporal_notice.assert_awaited_once_with(memory, "async", "add", "metadata", "date_like_metadata")
    first_run_notice.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_add_runs_scale_detection_in_thread(monkeypatch):
    memory = make_async_memory()
    scale_detector = MagicMock(return_value=("memory_count", "memory_count_threshold", None, 2000, 2000))
    scale_notice = AsyncMock()
    first_run_notice = AsyncMock()
    to_thread_calls = []

    async def to_thread(fn, *args, **kwargs):
        to_thread_calls.append((fn, args, kwargs))
        return fn(*args, **kwargs)

    monkeypatch.setattr(memory_main, "detect_scale_threshold_from_add_result", scale_detector)
    monkeypatch.setattr(memory_main.asyncio, "to_thread", to_thread)
    monkeypatch.setattr(memory_main, "display_scale_threshold_notice_async", scale_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", first_run_notice)

    result = await AsyncMemory.add(memory, "The user likes tea.", user_id="u1", infer=False)

    assert result == {"results": [], "failed": []}
    assert to_thread_calls == [(scale_detector, (memory, []), {})]
    scale_detector.assert_called_once_with(memory, [])
    scale_notice.assert_awaited_once_with(
        memory,
        "async",
        "add",
        "memory_count",
        "memory_count_threshold",
        None,
        2000,
        2000,
    )
    first_run_notice.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_search_temporal_query_triggers_notice_after_success(monkeypatch):
    memory = make_async_memory()
    temporal_notice = AsyncMock()
    first_run_notice = AsyncMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice_async", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", first_run_notice)

    result = await AsyncMemory.search(memory, "what happened last week?", filters={"user_id": "u1"})

    assert result == {"results": []}
    memory._search_vector_store.assert_awaited_once()
    temporal_notice.assert_awaited_once_with(memory, "async", "search", "query", "relative_phrase")
    first_run_notice.assert_not_awaited()
