from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from mem0.memory import main as memory_main
from mem0.memory.main import AsyncMemory, Memory


def make_sync_memory():
    memory = Memory.__new__(Memory)
    memory.vector_store = MagicMock()
    memory._delete_memory = MagicMock()
    return memory


def make_async_memory():
    memory = AsyncMemory.__new__(AsyncMemory)
    memory.vector_store = MagicMock()
    memory._delete_memory = AsyncMock()
    memory._entity_store = None
    return memory


def test_sync_delete_decay_usage_runs_after_success(monkeypatch):
    memory = make_sync_memory()
    existing_memory = SimpleNamespace(id="memory-1")
    memory.vector_store.get.return_value = existing_memory
    decay_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(
        memory_main,
        "detect_decay_usage_from_delete",
        MagicMock(return_value=("delete_count", "repeated_deletes", 5, None)),
    )
    monkeypatch.setattr(memory_main, "display_decay_usage_notice", decay_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    result = Memory.delete(memory, "memory-1")

    assert result == {"message": "Memory deleted successfully!"}
    memory._delete_memory.assert_called_once_with("memory-1", existing_memory)
    decay_notice.assert_called_once_with(
        memory,
        "sync",
        "delete",
        "delete_count",
        "repeated_deletes",
        5,
        None,
    )
    first_run_notice.assert_not_called()


def test_sync_delete_below_threshold_uses_first_run_notice(monkeypatch):
    memory = make_sync_memory()
    memory.vector_store.get.return_value = SimpleNamespace(id="memory-1")
    decay_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete", MagicMock(return_value=None))
    monkeypatch.setattr(memory_main, "display_decay_usage_notice", decay_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    Memory.delete(memory, "memory-1")

    decay_notice.assert_not_called()
    first_run_notice.assert_called_once_with(memory, "sync", "delete")


def test_sync_delete_failure_does_not_trigger_decay_usage_notice(monkeypatch):
    memory = make_sync_memory()
    memory.vector_store.get.return_value = None
    detect_decay = MagicMock()
    decay_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete", detect_decay)
    monkeypatch.setattr(memory_main, "display_decay_usage_notice", decay_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    with pytest.raises(ValueError, match="Memory with id memory-1 not found"):
        Memory.delete(memory, "memory-1")

    detect_decay.assert_not_called()
    decay_notice.assert_not_called()
    first_run_notice.assert_not_called()


def test_sync_delete_all_decay_usage_runs_after_success(monkeypatch):
    memory = make_sync_memory()
    memories = [SimpleNamespace(id="memory-1"), SimpleNamespace(id="memory-2")]
    memory.vector_store.list.return_value = (memories, None)
    decay_notice = MagicMock()
    first_run_notice = MagicMock()
    detect_decay = MagicMock(return_value=("delete_all", "bulk_delete", None, 2))
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete_all", detect_decay)
    monkeypatch.setattr(memory_main, "display_decay_usage_notice", decay_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    result = Memory.delete_all(memory, user_id="u1")

    assert result == {"message": "Memories deleted successfully!"}
    assert memory._delete_memory.call_count == 2
    detect_decay.assert_called_once_with(2)
    decay_notice.assert_called_once_with(
        memory,
        "sync",
        "delete_all",
        "delete_all",
        "bulk_delete",
        None,
        2,
    )
    first_run_notice.assert_not_called()


def test_sync_delete_all_zero_deletes_uses_first_run_notice(monkeypatch):
    memory = make_sync_memory()
    memory.vector_store.list.return_value = ([], None)
    decay_notice = MagicMock()
    first_run_notice = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete_all", MagicMock(return_value=None))
    monkeypatch.setattr(memory_main, "display_decay_usage_notice", decay_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice", first_run_notice)

    Memory.delete_all(memory, user_id="u1")

    decay_notice.assert_not_called()
    first_run_notice.assert_called_once_with(memory, "sync", "delete_all")


@pytest.mark.asyncio
async def test_async_delete_decay_usage_runs_after_success(monkeypatch):
    memory = make_async_memory()
    existing_memory = SimpleNamespace(id="memory-1")
    memory.vector_store.get.return_value = existing_memory
    decay_notice = AsyncMock()
    first_run_notice = AsyncMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(
        memory_main,
        "detect_decay_usage_from_delete",
        MagicMock(return_value=("delete_count", "repeated_deletes", 5, None)),
    )
    monkeypatch.setattr(memory_main, "display_decay_usage_notice_async", decay_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", first_run_notice)

    result = await AsyncMemory.delete(memory, "memory-1")

    assert result == {"message": "Memory deleted successfully!"}
    memory._delete_memory.assert_awaited_once_with("memory-1", existing_memory)
    decay_notice.assert_awaited_once_with(
        memory,
        "async",
        "delete",
        "delete_count",
        "repeated_deletes",
        5,
        None,
    )
    first_run_notice.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_delete_failure_does_not_trigger_decay_usage_notice(monkeypatch):
    memory = make_async_memory()
    memory.vector_store.get.return_value = None
    detect_decay = MagicMock()
    decay_notice = AsyncMock()
    first_run_notice = AsyncMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete", detect_decay)
    monkeypatch.setattr(memory_main, "display_decay_usage_notice_async", decay_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", first_run_notice)

    with pytest.raises(ValueError, match="Memory with id memory-1 not found"):
        await AsyncMemory.delete(memory, "memory-1")

    detect_decay.assert_not_called()
    decay_notice.assert_not_awaited()
    first_run_notice.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_delete_all_decay_usage_runs_after_success(monkeypatch):
    memory = make_async_memory()
    memories = [SimpleNamespace(id="memory-1"), SimpleNamespace(id="memory-2")]
    memory.vector_store.list.return_value = (memories, None)
    decay_notice = AsyncMock()
    first_run_notice = AsyncMock()
    detect_decay = MagicMock(return_value=("delete_all", "bulk_delete", None, 2))
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete_all", detect_decay)
    monkeypatch.setattr(memory_main, "display_decay_usage_notice_async", decay_notice)
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", first_run_notice)

    result = await AsyncMemory.delete_all(memory, user_id="u1")

    assert result == {"message": "Memories deleted successfully!"}
    assert memory._delete_memory.await_count == 2
    detect_decay.assert_called_once_with(2)
    decay_notice.assert_awaited_once_with(
        memory,
        "async",
        "delete_all",
        "delete_all",
        "bulk_delete",
        None,
        2,
    )
    first_run_notice.assert_not_awaited()
