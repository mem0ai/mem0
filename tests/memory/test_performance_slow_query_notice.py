from unittest.mock import AsyncMock, MagicMock

import pytest

from mem0.memory import main as memory_main
from mem0.memory.main import AsyncMemory, Memory


def make_sync_memory(search_results=None):
    memory = Memory.__new__(Memory)
    memory.api_version = "v1.1"
    memory.reranker = None
    memory._search_vector_store = MagicMock(return_value=search_results or [])
    return memory


def make_async_memory(search_results=None):
    memory = AsyncMemory.__new__(AsyncMemory)
    memory.api_version = "v1.1"
    memory.reranker = None
    memory._search_vector_store = AsyncMock(return_value=search_results or [])
    return memory


def test_sync_slow_search_triggers_performance_notice_after_success(monkeypatch):
    results = [{"id": "m1"}, {"id": "m2"}]
    memory = make_sync_memory(search_results=results)
    performance_notice = MagicMock()
    temporal_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(side_effect=[100.0, 102.1]))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    result = Memory.search(memory, "favorite drink", filters={"user_id": "u1"}, top_k=3)

    assert result == {"results": results}
    memory._search_vector_store.assert_called_once()
    performance_notice.assert_called_once_with(memory, "sync", "search", pytest.approx(2.1), 3, 2)
    temporal_notice.assert_not_called()
    first_run_notice.assert_not_called()


def test_sync_fast_search_uses_first_run_notice(monkeypatch):
    memory = make_sync_memory()
    performance_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(side_effect=[100.0, 101.0]))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", MagicMock())
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    Memory.search(memory, "favorite drink", filters={"user_id": "u1"})

    performance_notice.assert_not_called()
    first_run_notice.assert_called_once_with(memory, "sync", "search")


def test_sync_failed_search_does_not_trigger_performance_notice(monkeypatch):
    memory = make_sync_memory()
    memory._search_vector_store.side_effect = RuntimeError("search failure")
    performance_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(return_value=100.0))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", MagicMock())
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    with pytest.raises(RuntimeError, match="search failure"):
        Memory.search(memory, "favorite drink", filters={"user_id": "u1"})

    performance_notice.assert_not_called()
    first_run_notice.assert_not_called()


def test_sync_temporal_usage_takes_precedence_over_slow_search(monkeypatch):
    memory = make_sync_memory()
    performance_notice = MagicMock()
    temporal_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(side_effect=[100.0, 102.1]))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    Memory.search(memory, "what happened last week?", filters={"user_id": "u1"})

    temporal_notice.assert_called_once_with(memory, "sync", "search", "query", "relative_phrase")
    performance_notice.assert_not_called()
    first_run_notice.assert_not_called()


@pytest.mark.asyncio
async def test_async_slow_search_triggers_performance_notice_after_success(monkeypatch):
    results = [{"id": "m1"}]
    memory = make_async_memory(search_results=results)
    performance_notice = AsyncMock()
    temporal_notice = AsyncMock()
    first_run_notice = AsyncMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(side_effect=[100.0, 102.1]))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice_async", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice_async", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", first_run_notice)

    result = await AsyncMemory.search(memory, "favorite drink", filters={"user_id": "u1"}, top_k=4)

    assert result == {"results": results}
    memory._search_vector_store.assert_awaited_once()
    performance_notice.assert_awaited_once_with(memory, "async", "search", pytest.approx(2.1), 4, 1)
    temporal_notice.assert_not_awaited()
    first_run_notice.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_fast_search_uses_first_run_notice(monkeypatch):
    memory = make_async_memory()
    performance_notice = AsyncMock()
    first_run_notice = AsyncMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(side_effect=[100.0, 101.0]))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice_async", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice_async", AsyncMock())
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", first_run_notice)

    await AsyncMemory.search(memory, "favorite drink", filters={"user_id": "u1"})

    performance_notice.assert_not_awaited()
    first_run_notice.assert_awaited_once_with(memory, "async", "search")


@pytest.mark.asyncio
async def test_async_failed_search_does_not_trigger_performance_notice(monkeypatch):
    memory = make_async_memory()
    memory._search_vector_store.side_effect = RuntimeError("search failure")
    performance_notice = AsyncMock()
    first_run_notice = AsyncMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(return_value=100.0))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice_async", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice_async", AsyncMock())
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", first_run_notice)

    with pytest.raises(RuntimeError, match="search failure"):
        await AsyncMemory.search(memory, "favorite drink", filters={"user_id": "u1"})

    performance_notice.assert_not_awaited()
    first_run_notice.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_temporal_usage_takes_precedence_over_slow_search(monkeypatch):
    memory = make_async_memory()
    performance_notice = AsyncMock()
    temporal_notice = AsyncMock()
    first_run_notice = AsyncMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main.time, "perf_counter", MagicMock(side_effect=[100.0, 102.1]))
    monkeypatch.setattr(memory_main, "display_performance_slow_query_notice_async", performance_notice)
    monkeypatch.setattr(memory_main, "display_temporal_usage_notice_async", temporal_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", first_run_notice)

    await AsyncMemory.search(memory, "what happened last week?", filters={"user_id": "u1"})

    temporal_notice.assert_awaited_once_with(memory, "async", "search", "query", "relative_phrase")
    performance_notice.assert_not_awaited()
    first_run_notice.assert_not_awaited()
