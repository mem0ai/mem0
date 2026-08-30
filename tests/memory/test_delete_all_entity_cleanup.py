from types import SimpleNamespace
from unittest.mock import MagicMock

from mem0.memory import main as memory_main
from mem0.memory.main import Memory


def make_sync_memory():
    memory = Memory.__new__(Memory)
    memory.vector_store = MagicMock()
    memory._delete_memory = MagicMock()
    memory._entity_store = None
    return memory


def test_delete_all_defers_entity_cleanup_to_bulk_clear(monkeypatch):
    """delete_all must not run per-memory entity cleanup; one bulk clear at the end."""
    memory = make_sync_memory()
    memory._entity_store = MagicMock()  # initialized, so the bulk clear path runs
    memories = [SimpleNamespace(id="memory-1"), SimpleNamespace(id="memory-2")]
    memory.vector_store.list.side_effect = [(memories, None), ([], None)]
    memory._remove_memory_from_entity_store = MagicMock()
    memory._bulk_clear_entity_store = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete_all", MagicMock(return_value=None))
    monkeypatch.setattr(memory_main, "display_first_run_notice", MagicMock())

    Memory.delete_all(memory, user_id="u1")

    memory._remove_memory_from_entity_store.assert_not_called()
    memory._bulk_clear_entity_store.assert_called_once_with({"user_id": "u1"})
    for call in memory._delete_memory.call_args_list:
        assert call.kwargs.get("skip_entity_cleanup") is True


def test_delete_all_lists_entity_store_once_not_per_memory(monkeypatch):
    """With an entity store attached, delete_all lists it once in total, not once per memory."""
    memory = make_sync_memory()
    memory._entity_store = MagicMock()
    memory._entity_store.list.return_value = [SimpleNamespace(id="entity-1")]
    memories = [SimpleNamespace(id=f"memory-{i}") for i in range(5)]
    memory.vector_store.list.side_effect = [(memories, None), ([], None)]
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete_all", MagicMock(return_value=None))
    monkeypatch.setattr(memory_main, "display_first_run_notice", MagicMock())

    Memory.delete_all(memory, user_id="u1")

    assert memory._entity_store.list.call_count == 1
    memory._entity_store.delete.assert_called_once_with(vector_id="entity-1")


def test_single_delete_still_cleans_entity_store(monkeypatch):
    """A plain delete() keeps its per-memory entity cleanup — only delete_all defers it."""
    memory = make_sync_memory()
    del memory._delete_memory  # exercise the real _delete_memory implementation
    memory.db = MagicMock()
    memory._entity_store = MagicMock()
    memory.vector_store.get.return_value = SimpleNamespace(id="memory-1", payload={"user_id": "u1"})
    memory._remove_memory_from_entity_store = MagicMock()
    monkeypatch.setattr(memory_main, "capture_event", MagicMock())
    monkeypatch.setattr(memory_main, "detect_decay_usage_from_delete", MagicMock(return_value=None))
    monkeypatch.setattr(memory_main, "display_first_run_notice", MagicMock())

    Memory.delete(memory, "memory-1")

    memory._remove_memory_from_entity_store.assert_called_once_with("memory-1", {"user_id": "u1"})
