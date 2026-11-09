"""A failed history write must not leave the just-inserted vector behind, and the
infer=False path must skip exact duplicates already in the store (#7879)."""

import hashlib
from unittest.mock import MagicMock

import pytest

from mem0.memory.main import AsyncMemory, Memory


def _make_memory(memory_cls, mocker):
    memory = memory_cls.__new__(memory_cls)
    memory.embedding_model = MagicMock()
    memory.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
    memory.vector_store = MagicMock()
    memory.vector_store.search.return_value = []
    memory.db = MagicMock()
    return memory


def _hit(text):
    hit = MagicMock()
    hit.payload = {"hash": hashlib.md5(text.encode()).hexdigest()}
    return hit


class TestHistoryFailureRollback:
    def test_sync_history_failure_removes_vector_and_reraises(self, mocker):
        memory = _make_memory(Memory, mocker)
        memory.db.add_history.side_effect = Exception("disk I/O error")

        with pytest.raises(Exception, match="disk I/O error"):
            memory._create_memory("likes tea", {"likes tea": [0.1]})

        memory.vector_store.insert.assert_called_once()
        memory.vector_store.delete.assert_called_once_with(vector_id=memory.vector_store.insert.call_args.kwargs["ids"][0])

    @pytest.mark.asyncio
    async def test_async_history_failure_removes_vector_and_reraises(self, mocker):
        memory = _make_memory(AsyncMemory, mocker)
        memory.db.add_history.side_effect = Exception("disk I/O error")

        with pytest.raises(Exception, match="disk I/O error"):
            await memory._create_memory("likes tea", {"likes tea": [0.1]})

        memory.vector_store.insert.assert_called_once()
        memory.vector_store.delete.assert_called_once_with(vector_id=memory.vector_store.insert.call_args.kwargs["ids"][0])

    def test_sync_history_success_keeps_vector(self, mocker):
        memory = _make_memory(Memory, mocker)

        memory._create_memory("likes tea", {"likes tea": [0.1]})

        memory.vector_store.insert.assert_called_once()
        memory.vector_store.delete.assert_not_called()


class TestInferFalseDuplicateSkip:
    def test_sync_duplicate_in_store_is_skipped(self, mocker):
        memory = _make_memory(Memory, mocker)
        memory.vector_store.search.return_value = [_hit("likes tea")]

        result = memory._add_to_vector_store(
            messages=[{"role": "user", "content": "likes tea"}],
            metadata={},
            filters={"user_id": "alice"},
            infer=False,
        )

        assert result == []
        memory.vector_store.insert.assert_not_called()

    def test_sync_non_duplicate_is_added(self, mocker):
        memory = _make_memory(Memory, mocker)
        memory.vector_store.search.return_value = [_hit("likes coffee")]

        result = memory._add_to_vector_store(
            messages=[{"role": "user", "content": "likes tea"}],
            metadata={},
            filters={"user_id": "alice"},
            infer=False,
        )

        assert len(result) == 1
        assert result[0]["event"] == "ADD"
        memory.vector_store.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_duplicate_in_store_is_skipped(self, mocker):
        memory = _make_memory(AsyncMemory, mocker)
        memory.vector_store.search.return_value = [_hit("likes tea")]

        result = await memory._add_to_vector_store(
            messages=[{"role": "user", "content": "likes tea"}],
            metadata={},
            effective_filters={"user_id": "alice"},
            infer=False,
        )

        assert result == []
        memory.vector_store.insert.assert_not_called()

    def test_search_failure_falls_back_to_insert(self, mocker):
        """A broken duplicate-check search must not block adding memories."""
        memory = _make_memory(Memory, mocker)
        memory.vector_store.search.side_effect = Exception("search backend down")

        result = memory._add_to_vector_store(
            messages=[{"role": "user", "content": "likes tea"}],
            metadata={},
            filters={"user_id": "alice"},
            infer=False,
        )

        assert len(result) == 1
        memory.vector_store.insert.assert_called_once()
