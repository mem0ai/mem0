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


class _StatefulStore:
    """Fake vector store that returns at most `page_size` rows and only drops a
    row when delete() runs. This makes the pagination loop load-bearing: if
    deletion is moved outside the loop, list() never shrinks and the drain
    exhausts its iteration cap instead of terminating on pre-canned empty pages.
    """

    def __init__(self, ids, page_size):
        self._ids = list(ids)
        self._page_size = page_size
        self.list_calls = 0

    def list(self, filters=None, top_k=None):
        self.list_calls += 1
        page = [SimpleNamespace(id=i) for i in self._ids[: self._page_size]]
        return (page, None)

    def delete(self, memory_id):
        if memory_id in self._ids:
            self._ids.remove(memory_id)


def test_sync_delete_all_is_load_bearing_with_stateful_store(monkeypatch):
    memory = _make_sync_memory()
    store = _StatefulStore(ids=[f"m{i}" for i in range(5)], page_size=2)
    memory.vector_store = store
    memory._delete_memory = MagicMock(side_effect=store.delete)
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete_all", MagicMock(return_value=None))
    monkeypatch.setattr(memory_main, "display_first_run_notice", MagicMock())
    monkeypatch.setattr(memory_main, "display_decay_usage_notice", MagicMock())

    Memory.delete_all(memory, user_id="u1")

    assert store._ids == []
    assert memory._delete_memory.call_count == 5


def test_sync_delete_all_propagates_delete_failures(monkeypatch):
    memory = _make_sync_memory()
    memory.vector_store.list.return_value = ([SimpleNamespace(id="m0")], None)
    memory._delete_memory.side_effect = RuntimeError("backend down")
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete_all", MagicMock(return_value=None))
    monkeypatch.setattr(memory_main, "display_first_run_notice", MagicMock())

    # Pre-pagination contract: a failed delete must surface, not be swallowed
    # while still returning the success message.
    with pytest.raises(RuntimeError, match="backend down"):
        Memory.delete_all(memory, user_id="u1")


def test_sync_delete_all_tolerates_stale_all_seen_page(monkeypatch):
    memory = _make_sync_memory()
    row = SimpleNamespace(id="m0")
    later = SimpleNamespace(id="m1")
    # Page with m0, then a stale page still showing (already-deleted) m0 due to
    # refresh lag, then a previously-hidden m1 appears, then empty.
    memory.vector_store.list.side_effect = [
        ([row], None),
        ([row], None),
        ([later], None),
        ([], None),
    ]
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete_all", MagicMock(return_value=None))
    monkeypatch.setattr(memory_main, "display_first_run_notice", MagicMock())

    Memory.delete_all(memory, user_id="u1")

    deleted_ids = [c.args[0] for c in memory._delete_memory.call_args_list]
    assert deleted_ids == ["m0", "m1"]


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


@pytest.mark.asyncio
async def test_async_delete_all_is_load_bearing_with_stateful_store(monkeypatch):
    memory = _make_async_memory()
    store = _StatefulStore(ids=[f"a{i}" for i in range(5)], page_size=2)
    memory.vector_store = store

    async def _delete(memory_id, skip_entity_cleanup=False):
        store.delete(memory_id)

    memory._delete_memory = AsyncMock(side_effect=_delete)
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete_all", MagicMock(return_value=None))
    monkeypatch.setattr(memory_main, "display_first_run_notice_async", AsyncMock())
    monkeypatch.setattr(memory_main, "display_decay_usage_notice_async", AsyncMock())

    await AsyncMemory.delete_all(memory, user_id="u1")

    # If deletion were moved outside the loop, list() would never shrink and
    # the loop would run until the iteration cap; instead it drains cleanly.
    assert store._ids == []
    assert memory._delete_memory.await_count == 5
