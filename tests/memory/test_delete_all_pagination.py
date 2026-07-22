"""delete_all must drain every page of matching memories, not just list()'s first page."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from mem0.memory import main as memory_main
from mem0.memory.main import AsyncMemory, Memory, _DELETE_ALL_PAGE_SIZE


def _make_sync_memory():
    memory = MagicMock(spec=Memory)
    memory.vector_store = MagicMock()
    memory._delete_memory = MagicMock()
    memory._entity_store = None
    return memory


def _make_async_memory():
    memory = MagicMock(spec=AsyncMemory)
    memory.vector_store = MagicMock()
    memory._delete_memory = AsyncMock()
    memory._entity_store = None
    memory._bulk_clear_entity_store = AsyncMock()
    return memory


def test_sync_delete_all_paginates_until_empty(monkeypatch):
    memory = _make_sync_memory()
    page1 = [SimpleNamespace(id=f"m{i}") for i in range(3)]
    page2 = [SimpleNamespace(id=f"m{i}") for i in range(3, 5)]
    memory.vector_store.list.side_effect = [(page1, None), (page2, None), ([], None)]
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete_all", MagicMock(return_value=None))
    monkeypatch.setattr(memory_main, "display_first_run_notice", MagicMock())
    monkeypatch.setattr(memory_main, "display_decay_usage_notice", MagicMock())

    Memory.delete_all(memory, user_id="u1")

    assert memory.vector_store.list.call_count == 3
    for call in memory.vector_store.list.call_args_list:
        assert call.kwargs.get("top_k") == _DELETE_ALL_PAGE_SIZE or (
            len(call.args) >= 2 and call.args[1] == _DELETE_ALL_PAGE_SIZE
        ) or call.kwargs == {"filters": {"user_id": "u1"}, "top_k": _DELETE_ALL_PAGE_SIZE}
    assert memory._delete_memory.call_count == 5
    deleted_ids = [c.args[0] for c in memory._delete_memory.call_args_list]
    assert deleted_ids == ["m0", "m1", "m2", "m3", "m4"]


def test_sync_delete_all_passes_filters_and_top_k(monkeypatch):
    memory = _make_sync_memory()
    memory.vector_store.list.return_value = ([], None)
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete_all", MagicMock(return_value=None))
    monkeypatch.setattr(memory_main, "display_first_run_notice", MagicMock())

    Memory.delete_all(memory, user_id="alice", agent_id="bot")

    memory.vector_store.list.assert_called_with(
        filters={"user_id": "alice", "agent_id": "bot"}, top_k=_DELETE_ALL_PAGE_SIZE
    )


@pytest.mark.asyncio
async def test_async_delete_all_paginates_until_empty(monkeypatch):
    memory = _make_async_memory()
    page1 = [SimpleNamespace(id="a"), SimpleNamespace(id="b")]
    page2 = [SimpleNamespace(id="c")]
    memory.vector_store.list.side_effect = [(page1, None), (page2, None), ([], None)]
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete_all", MagicMock(return_value=None))
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", AsyncMock())
    monkeypatch.setattr(memory_main, "display_decay_usage_notice_async", AsyncMock())

    await AsyncMemory.delete_all(memory, user_id="u1")

    assert memory.vector_store.list.call_count == 3
    assert memory._delete_memory.await_count == 3
