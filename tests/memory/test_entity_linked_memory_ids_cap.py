"""Regression tests for unbounded `linked_memory_ids` growth (issue #6923).

The OSS entity index stores every memory linked to an entity in one
`linked_memory_ids` metadata array, rewritten in full on each update. With no
bound, a high-cardinality entity can push that single array past a backend
metadata limit — e.g. embedded Chroma's SQLite segment, which is known to
stall around 5,461 elements (chroma-core/chroma#2181). `MemoryConfig` now
exposes `entity_max_linked_memory_ids` (default 5000): once the merged list
would exceed the cap, `_bounded_linked_memory_ids` drops the oldest IDs
(FIFO) so the newest ones are kept. `cap=None`/`0` restores the old
unbounded behavior.

Two layers are covered:
  * `_bounded_linked_memory_ids` directly — the merge/evict/dedup logic.
  * All four growth sites (sync/async, single-entity/batch) actually apply
    the cap via `self.config.entity_max_linked_memory_ids`, using the same
    mocked-entity_store pattern as TestAddPipelineEntityEmbeddingCountGuard.
"""

from unittest.mock import MagicMock, Mock

import pytest

from mem0.configs.base import MemoryConfig
from mem0.memory.main import AsyncMemory, Memory, _bounded_linked_memory_ids

from tests.memory.test_main import _setup_mocks


# ---------------------------------------------------------------------------
# 1. Pure helper: merge / evict / dedup semantics
# ---------------------------------------------------------------------------


class TestBoundedLinkedMemoryIds:
    def test_appends_new_id_under_cap(self):
        assert _bounded_linked_memory_ids(["a", "b"], ["c"], 5) == ["a", "b", "c"]

    def test_evicts_oldest_when_over_cap(self):
        # 3 existing + 2 new = 5, cap 3 -> keep the 3 newest, oldest-first order.
        result = _bounded_linked_memory_ids(["a", "b", "c"], ["d", "e"], 3)
        assert result == ["c", "d", "e"]

    def test_duplicate_new_id_is_not_double_counted(self):
        # "b" is already present; re-adding it must not push out "a".
        result = _bounded_linked_memory_ids(["a", "b"], ["b"], 2)
        assert result == ["a", "b"]

    def test_cap_none_disables_bound(self):
        many = [f"m{i}" for i in range(10)]
        result = _bounded_linked_memory_ids(many, ["m-new"], None)
        assert result == many + ["m-new"]

    def test_cap_zero_disables_bound(self):
        many = [f"m{i}" for i in range(10)]
        result = _bounded_linked_memory_ids(many, ["m-new"], 0)
        assert result == many + ["m-new"]

    def test_cap_negative_disables_bound(self):
        result = _bounded_linked_memory_ids(["a"], ["b"], -1)
        assert result == ["a", "b"]

    def test_does_not_exceed_cap_when_many_new_ids_at_once(self):
        # Batch-add path can union many memory_ids into one entity in one call.
        result = _bounded_linked_memory_ids([], [f"m{i}" for i in range(10)], 3)
        assert len(result) == 3
        assert result == ["m7", "m8", "m9"]

    def test_existing_not_a_list_is_coerced(self):
        # Defensive: a set/tuple existing value (should not normally occur, but
        # payload.get(..., []) could return anything a caller stashed there).
        result = _bounded_linked_memory_ids(("a", "b"), ["c"], 5)
        assert result == ["a", "b", "c"]

    def test_does_not_mutate_existing_list_argument(self):
        original = ["a", "b"]
        _bounded_linked_memory_ids(original, ["c"], 5)
        assert original == ["a", "b"], "helper must not mutate the caller's list in place"


# ---------------------------------------------------------------------------
# 2. Sync single-entity path: Memory._upsert_entity
# ---------------------------------------------------------------------------


class TestSyncSingleEntityCap:
    @pytest.fixture
    def mock_memory(self, mocker):
        _setup_mocks(mocker)
        memory = Memory()
        memory.config = MemoryConfig(entity_max_linked_memory_ids=3)
        memory.embedding_model = Mock()
        memory.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
        return memory

    def test_update_path_evicts_oldest_when_over_cap(self, mock_memory):
        existing_payload = {"data": "Alice", "linked_memory_ids": ["m1", "m2", "m3"]}
        match = MagicMock(id="entity-1", payload=existing_payload)

        mock_memory._entity_store = Mock()
        mock_memory._entity_store.list = Mock(return_value=[])
        mock_memory._entity_store.search = Mock(return_value=[])
        mock_memory._existing_entities_by_text = Mock(return_value={"alice": match})
        mock_memory._entity_store.update = Mock()

        mock_memory._upsert_entity("Alice", "person", "m4", {"user_id": "u1"})

        mock_memory._entity_store.update.assert_called_once()
        sent_payload = mock_memory._entity_store.update.call_args.kwargs["payload"]
        assert sent_payload["linked_memory_ids"] == ["m2", "m3", "m4"]

    def test_new_entity_insert_is_a_single_id_list(self, mock_memory):
        mock_memory._entity_store = Mock()
        mock_memory._entity_store.list = Mock(return_value=[])
        mock_memory._entity_store.search = Mock(return_value=[])
        mock_memory._existing_entities_by_text = Mock(return_value={})
        mock_memory._entity_store.insert = Mock()

        mock_memory._upsert_entity("Bob", "person", "m1", {"user_id": "u1"})

        mock_memory._entity_store.insert.assert_called_once()
        payloads = mock_memory._entity_store.insert.call_args.kwargs["payloads"]
        assert payloads[0]["linked_memory_ids"] == ["m1"]

    def test_uncapped_config_preserves_old_unbounded_behavior(self, mocker):
        _setup_mocks(mocker)
        memory = Memory()
        memory.config = MemoryConfig(entity_max_linked_memory_ids=None)
        memory.embedding_model = Mock()
        memory.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])

        existing_payload = {"data": "Alice", "linked_memory_ids": ["m1", "m2", "m3"]}
        match = MagicMock(id="entity-1", payload=existing_payload)
        memory._entity_store = Mock()
        memory._entity_store.list = Mock(return_value=[])
        memory._entity_store.search = Mock(return_value=[])
        memory._existing_entities_by_text = Mock(return_value={"alice": match})
        memory._entity_store.update = Mock()

        memory._upsert_entity("Alice", "person", "m4", {"user_id": "u1"})

        sent_payload = memory._entity_store.update.call_args.kwargs["payload"]
        assert sent_payload["linked_memory_ids"] == ["m1", "m2", "m3", "m4"]


# ---------------------------------------------------------------------------
# 3. Sync batch path: Memory._add_to_vector_store Phase 7 (batch entity linking)
# ---------------------------------------------------------------------------


class TestSyncBatchEntityCap:
    @pytest.fixture
    def mock_memory(self, mocker):
        mock_llm, _ = _setup_mocks(mocker)
        memory = Memory()
        memory.config = MemoryConfig(entity_max_linked_memory_ids=3)
        memory.custom_instructions = None
        memory.api_version = "v1.1"
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()
        memory.db.batch_add_history = MagicMock()
        return memory

    def test_batch_update_evicts_oldest_when_over_cap(self, mock_memory, mocker):
        mock_memory.llm.generate_response.return_value = (
            '{"memory": [{"text": "Alice met Bob"}, {"text": "Alice called Carol"}]}'
        )
        mock_memory.embedding_model = Mock()
        mock_memory.embedding_model.embed_batch = Mock(side_effect=lambda texts, action: [[0.1] * 10 for _ in texts])

        existing_payload = {"data": "Alice", "linked_memory_ids": ["m1", "m2", "m3"]}
        match = MagicMock(id="entity-1", payload=existing_payload, score=1.0)
        mock_memory._entity_store = Mock()
        mock_memory._entity_store.search_batch = Mock(return_value=[[match]])
        mock_memory._entity_store.update = Mock()
        mock_memory._entity_store.insert = Mock()

        mocker.patch(
            "mem0.memory.main.extract_entities_batch",
            return_value=[[("person", "Alice")], [("person", "Alice")]],
        )
        mocker.patch("mem0.memory.main.capture_event")

        result = mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "Alice met Bob; Alice called Carol"}],
            metadata={},
            filters={"user_id": "u1"},
            infer=True,
        )

        assert len(result) == 2
        mock_memory._entity_store.update.assert_called_once()
        sent_payload = mock_memory._entity_store.update.call_args.kwargs["payload"]
        # 3 pre-existing ids + 2 new ones = 5, cap 3 -> the 2 new ids must survive
        # (they are the newest) and exactly 1 of the 3 pre-existing ids is evicted.
        assert len(sent_payload["linked_memory_ids"]) == 3
        new_ids = {r["id"] for r in result}
        assert new_ids <= set(sent_payload["linked_memory_ids"])

    def test_batch_new_entity_insert_is_capped(self, mock_memory, mocker):
        mock_memory.llm.generate_response.return_value = (
            '{"memory": [{"text": "Dave met Erin"}, {"text": "Dave called Frank"}, '
            '{"text": "Dave emailed Grace"}, {"text": "Dave texted Heidi"}]}'
        )
        mock_memory.embedding_model = Mock()
        mock_memory.embedding_model.embed_batch = Mock(side_effect=lambda texts, action: [[0.1] * 10 for _ in texts])

        mock_memory._entity_store = Mock()
        mock_memory._entity_store.search_batch = Mock(return_value=[[]])
        mock_memory._entity_store.update = Mock()
        mock_memory._entity_store.insert = Mock()

        mocker.patch(
            "mem0.memory.main.extract_entities_batch",
            return_value=[
                [("person", "Dave")],
                [("person", "Dave")],
                [("person", "Dave")],
                [("person", "Dave")],
            ],
        )
        mocker.patch("mem0.memory.main.capture_event")

        result = mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "Dave met Erin; Dave called Frank; Dave emailed Grace; Dave texted Heidi"}],
            metadata={},
            filters={"user_id": "u1"},
            infer=True,
        )

        assert len(result) == 4
        mock_memory._entity_store.insert.assert_called_once()
        payloads = mock_memory._entity_store.insert.call_args.kwargs["payloads"]
        assert len(payloads[0]["linked_memory_ids"]) == 3, (
            "a brand-new entity linked to 4 memories in one add() call must still respect the cap"
        )


# ---------------------------------------------------------------------------
# 4. Async single-entity path: AsyncMemory._upsert_entity_async
# ---------------------------------------------------------------------------


class TestAsyncSingleEntityCap:
    @pytest.fixture
    def mock_async_memory(self, mocker):
        _setup_mocks(mocker)
        memory = AsyncMemory()
        memory.config = MemoryConfig(entity_max_linked_memory_ids=3)
        memory.embedding_model = Mock()
        memory.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
        return memory

    @pytest.mark.asyncio
    async def test_update_path_evicts_oldest_when_over_cap(self, mock_async_memory):
        existing_payload = {"data": "Alice", "linked_memory_ids": ["m1", "m2", "m3"]}
        match = MagicMock(id="entity-1", payload=existing_payload)

        mock_async_memory._entity_store = Mock()
        mock_async_memory._entity_store.list = Mock(return_value=[])
        mock_async_memory._entity_store.search = Mock(return_value=[])
        mock_async_memory._existing_entities_by_text = Mock(return_value={"alice": match})
        mock_async_memory._entity_store.update = Mock()

        await mock_async_memory._upsert_entity_async("Alice", "person", "m4", {"user_id": "u1"})

        mock_async_memory._entity_store.update.assert_called_once()
        sent_payload = mock_async_memory._entity_store.update.call_args.kwargs["payload"]
        assert sent_payload["linked_memory_ids"] == ["m2", "m3", "m4"]


# ---------------------------------------------------------------------------
# 5. Async batch path: AsyncMemory._add_to_vector_store Phase 7
# ---------------------------------------------------------------------------


class TestAsyncBatchEntityCap:
    @pytest.fixture
    def mock_async_memory(self, mocker):
        mock_llm, _ = _setup_mocks(mocker)
        memory = AsyncMemory()
        memory.config = MemoryConfig(entity_max_linked_memory_ids=3)
        memory.custom_instructions = None
        memory.api_version = "v1.1"
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()
        memory.db.batch_add_history = MagicMock()
        return memory

    @pytest.mark.asyncio
    async def test_batch_update_evicts_oldest_when_over_cap(self, mock_async_memory, mocker):
        mock_async_memory.llm.generate_response.return_value = (
            '{"memory": [{"text": "Alice met Bob"}, {"text": "Alice called Carol"}]}'
        )
        mock_async_memory.embedding_model = Mock()
        mock_async_memory.embedding_model.embed_batch = Mock(side_effect=lambda texts, action: [[0.1] * 10 for _ in texts])

        existing_payload = {"data": "Alice", "linked_memory_ids": ["m1", "m2", "m3"]}
        match = MagicMock(id="entity-1", payload=existing_payload, score=1.0)
        mock_async_memory._entity_store = Mock()
        mock_async_memory._entity_store.search_batch = Mock(return_value=[[match]])
        mock_async_memory._entity_store.update = Mock()
        mock_async_memory._entity_store.insert = Mock()

        mocker.patch(
            "mem0.memory.main.extract_entities_batch",
            return_value=[[("person", "Alice")], [("person", "Alice")]],
        )
        mocker.patch("mem0.memory.main.capture_event")

        result = await mock_async_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "Alice met Bob; Alice called Carol"}],
            metadata={},
            effective_filters={"user_id": "u1"},
            infer=True,
        )

        assert len(result) == 2
        mock_async_memory._entity_store.update.assert_called_once()
        sent_payload = mock_async_memory._entity_store.update.call_args.kwargs["payload"]
        assert len(sent_payload["linked_memory_ids"]) == 3
        new_ids = {r["id"] for r in result}
        assert new_ids <= set(sent_payload["linked_memory_ids"])
