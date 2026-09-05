"""Tests for _remove_memory_from_entity_store optimisation (issue #4988).

Validates the targeted-filter fast path, broad-scan fallback, and the
entity deletion/update logic for both sync and async Memory classes.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mem0.memory.main import AsyncMemory, Memory


def _setup_mocks(mocker):
    """Patch factories so Memory/AsyncMemory.__init__ doesn't hit real stores."""
    mock_embedder = mocker.MagicMock()
    mock_embedder.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mocker.patch("mem0.utils.factory.EmbedderFactory.create", mock_embedder)

    mock_vector_store = mocker.MagicMock()
    mock_vector_store.return_value.search.return_value = []
    mocker.patch(
        "mem0.utils.factory.VectorStoreFactory.create",
        side_effect=[mock_vector_store.return_value, mocker.MagicMock()],
    )

    mock_llm = mocker.MagicMock()
    mocker.patch("mem0.utils.factory.LlmFactory.create", mock_llm)
    mocker.patch("mem0.memory.storage.SQLiteManager", mocker.MagicMock())

    return mock_embedder, mock_vector_store


# ---------------------------------------------------------------------------
# _extract_entity_rows
# ---------------------------------------------------------------------------


class TestExtractEntityRows:
    """Unit tests for the static helper that unwraps list() return formats."""

    def test_qdrant_scroll_tuple(self):
        row = SimpleNamespace(id="e1", payload={})
        result = Memory._extract_entity_rows(([row], "next_offset"))
        assert result == [row]

    def test_wrapped_list(self):
        row = SimpleNamespace(id="e1", payload={})
        result = Memory._extract_entity_rows([[row]])
        assert result == [row]

    def test_flat_list(self):
        row = SimpleNamespace(id="e1", payload={})
        result = Memory._extract_entity_rows([row])
        assert result == [row]

    def test_none(self):
        assert Memory._extract_entity_rows(None) == []

    def test_empty_list(self):
        assert Memory._extract_entity_rows([]) == []

    def test_empty_tuple(self):
        assert Memory._extract_entity_rows(()) == []


# ---------------------------------------------------------------------------
# Sync _get_entity_rows_for_memory / _remove_memory_from_entity_store
# ---------------------------------------------------------------------------


class TestSyncEntityCleanup:
    @pytest.fixture
    def memory(self, mocker):
        _setup_mocks(mocker)
        m = Memory()
        m._entity_store = MagicMock()
        m.embedding_model = MagicMock()
        m.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
        return m

    def test_fast_path_targeted_filter(self, memory):
        """When targeted filter returns results, broad scan is skipped."""
        row = SimpleNamespace(id="e1", payload={"linked_memory_ids": ["m1", "m2"], "data": "alice"})
        memory._entity_store.list.return_value = ([row], None)

        rows = memory._get_entity_rows_for_memory("m1", {"user_id": "u1"})
        assert rows == [row]
        # Only one call (targeted)
        memory._entity_store.list.assert_called_once_with(
            filters={"user_id": "u1", "linked_memory_ids": "m1"}, top_k=10000
        )

    def test_fallback_when_targeted_empty(self, memory):
        """When targeted filter returns empty, falls back to broad scan."""
        row = SimpleNamespace(id="e1", payload={"linked_memory_ids": ["m1"], "data": "alice"})
        memory._entity_store.list.side_effect = [
            ([], None),  # targeted returns empty
            ([row], None),  # broad scan
        ]

        rows = memory._get_entity_rows_for_memory("m1", {"user_id": "u1"})
        assert rows == [row]
        assert memory._entity_store.list.call_count == 2

    def test_fallback_when_targeted_raises(self, memory):
        """When targeted filter raises, falls back to broad scan."""
        row = SimpleNamespace(id="e1", payload={"linked_memory_ids": ["m1"], "data": "alice"})
        memory._entity_store.list.side_effect = [
            ValueError("unsupported filter"),
            ([row], None),
        ]

        rows = memory._get_entity_rows_for_memory("m1", {"user_id": "u1"})
        assert rows == [row]

    def test_remove_deletes_entity_when_last_link(self, memory):
        """Entity is deleted when memory_id is the only linked ID."""
        row = SimpleNamespace(id="e1", payload={"linked_memory_ids": ["m1"], "data": "alice"})
        memory._entity_store.list.return_value = ([row], None)

        memory._remove_memory_from_entity_store("m1", {"user_id": "u1"})

        memory._entity_store.delete.assert_called_once_with(vector_id="e1")
        memory._entity_store.update.assert_not_called()

    def test_remove_updates_entity_when_other_links_remain(self, memory):
        """Entity is updated (not deleted) when other links remain."""
        row = SimpleNamespace(id="e1", payload={"linked_memory_ids": ["m1", "m2"], "data": "alice"})
        memory._entity_store.list.return_value = ([row], None)

        memory._remove_memory_from_entity_store("m1", {"user_id": "u1"})

        memory._entity_store.delete.assert_not_called()
        memory._entity_store.update.assert_called_once()
        update_call = memory._entity_store.update.call_args
        assert update_call.kwargs["vector_id"] == "e1"
        assert update_call.kwargs["payload"]["linked_memory_ids"] == ["m2"]

    def test_remove_skips_unrelated_entities(self, memory):
        """Entities not referencing the target memory_id are skipped."""
        row_match = SimpleNamespace(id="e1", payload={"linked_memory_ids": ["m1"], "data": "alice"})
        row_other = SimpleNamespace(id="e2", payload={"linked_memory_ids": ["m99"], "data": "bob"})
        memory._entity_store.list.return_value = ([row_match, row_other], None)

        memory._remove_memory_from_entity_store("m1", {"user_id": "u1"})

        memory._entity_store.delete.assert_called_once_with(vector_id="e1")

    def test_remove_noop_when_entity_store_none(self, memory):
        """No-op when entity store is not initialized."""
        memory._entity_store = None
        # Should not raise
        memory._remove_memory_from_entity_store("m1", {"user_id": "u1"})

    def test_scan_limit_warning(self, memory, caplog):
        """Warning is logged when broad scan hits the limit."""
        # Create exactly _ENTITY_SCAN_LIMIT rows
        memory._ENTITY_SCAN_LIMIT = 5
        rows = [SimpleNamespace(id=f"e{i}", payload={"linked_memory_ids": ["other"], "data": f"x{i}"}) for i in range(5)]
        memory._entity_store.list.side_effect = [
            ([], None),  # targeted empty
            (rows, None),  # broad scan hits limit
        ]

        import logging

        with caplog.at_level(logging.WARNING):
            result = memory._get_entity_rows_for_memory("m1", {"user_id": "u1"})

        assert len(result) == 5
        assert "hit limit" in caplog.text


# ---------------------------------------------------------------------------
# Async _get_entity_rows_for_memory / _remove_memory_from_entity_store
# ---------------------------------------------------------------------------


class TestAsyncEntityCleanup:
    @pytest.fixture
    def memory(self, mocker):
        _setup_mocks(mocker)
        m = AsyncMemory()
        m._entity_store = MagicMock()
        m.embedding_model = MagicMock()
        m.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
        return m

    @pytest.mark.asyncio
    async def test_fast_path_targeted_filter(self, memory):
        """Async: targeted filter returns results → no broad scan."""
        row = SimpleNamespace(id="e1", payload={"linked_memory_ids": ["m1", "m2"], "data": "alice"})
        memory._entity_store.list.return_value = ([row], None)

        rows = await memory._get_entity_rows_for_memory("m1", {"user_id": "u1"})
        assert rows == [row]

    @pytest.mark.asyncio
    async def test_fallback_when_targeted_empty(self, memory):
        """Async: targeted empty → broad scan fallback."""
        row = SimpleNamespace(id="e1", payload={"linked_memory_ids": ["m1"], "data": "alice"})
        memory._entity_store.list.side_effect = [
            ([], None),
            ([row], None),
        ]

        rows = await memory._get_entity_rows_for_memory("m1", {"user_id": "u1"})
        assert rows == [row]

    @pytest.mark.asyncio
    async def test_remove_deletes_entity_when_last_link(self, memory):
        """Async: entity deleted when it's the last linked memory."""
        row = SimpleNamespace(id="e1", payload={"linked_memory_ids": ["m1"], "data": "alice"})
        memory._entity_store.list.return_value = ([row], None)

        await memory._remove_memory_from_entity_store("m1", {"user_id": "u1"})

        memory._entity_store.delete.assert_called_once_with(vector_id="e1")

    @pytest.mark.asyncio
    async def test_remove_updates_entity_when_other_links_remain(self, memory):
        """Async: entity updated when other links remain."""
        row = SimpleNamespace(id="e1", payload={"linked_memory_ids": ["m1", "m2"], "data": "alice"})
        memory._entity_store.list.return_value = ([row], None)

        await memory._remove_memory_from_entity_store("m1", {"user_id": "u1"})

        memory._entity_store.delete.assert_not_called()
        memory._entity_store.update.assert_called_once()
        update_call = memory._entity_store.update.call_args
        assert update_call.kwargs["vector_id"] == "e1"
        assert update_call.kwargs["payload"]["linked_memory_ids"] == ["m2"]
