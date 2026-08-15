"""Regression tests for issue #6982.

The V3 additive extraction prompt (`ADDITIVE_EXTRACTION_PROMPT`) asks the LLM to
emit a `linked_memory_ids` field on each extracted memory, pointing at related
Existing Memories so retrieval can build a semantic graph between them. But
`_add_to_vector_store`'s Phase 4 (sync and async) only ever read `text` and
`attributed_to` off each extracted memory dict — `linked_memory_ids` was parsed
out of the LLM response and then silently discarded before it ever reached the
vector-store payload.

There is a second, related defect the fix also addresses: Existing Memories are
shown to the LLM with anti-hallucination index strings ("0", "1", ...) instead
of their real vector-store IDs (`uuid_mapping` in `_add_to_vector_store` maps
index -> real ID), but the prompt told the LLM those Existing Memory ids were
UUIDs and to emit UUIDs back in `linked_memory_ids`. Since the LLM was never
shown a real UUID, any `linked_memory_ids` value it produced already had to be
one of the index strings — the prompt's stated contract didn't match what the
pipeline actually presented.

The fix:
  * `_resolve_linked_memory_ids(raw, uuid_mapping)` translates the LLM's index
    strings back to real vector-store IDs, dropping anything that isn't a
    string or doesn't resolve to a known index (a hallucinated/malformed
    value) rather than persisting it.
  * Phase 4 (sync + async) now calls this and, when non-empty, stores the
    resolved list under `linked_memory_ids` in the payload sent to
    `vector_store.insert`.
  * The prompt's "Existing Memories" section and its two linking examples
    (Example 10, Example 12) now describe/use index strings consistently
    instead of claiming UUIDs.

Layers covered:
  * `_resolve_linked_memory_ids` directly — translation/dedup/drop semantics.
  * The sync and async `_add_to_vector_store` Phase 4 loops — the resolved
    field actually lands in the persisted payload.
"""

from unittest.mock import MagicMock, Mock

import pytest

from mem0.memory.main import AsyncMemory, Memory, _resolve_linked_memory_ids

from tests.memory.test_main import _setup_mocks


# ---------------------------------------------------------------------------
# 1. Pure helper: index -> real-ID translation semantics
# ---------------------------------------------------------------------------


class TestResolveLinkedMemoryIds:
    def test_resolves_known_indices_to_real_ids(self):
        mapping = {"0": "uuid-a", "1": "uuid-b"}
        assert _resolve_linked_memory_ids(["0", "1"], mapping) == ["uuid-a", "uuid-b"]

    def test_preserves_input_order(self):
        mapping = {"0": "uuid-a", "1": "uuid-b", "2": "uuid-c"}
        assert _resolve_linked_memory_ids(["2", "0"], mapping) == ["uuid-c", "uuid-a"]

    def test_drops_unknown_index_silently(self):
        # The LLM hallucinated an index that was never shown to it.
        mapping = {"0": "uuid-a"}
        assert _resolve_linked_memory_ids(["0", "5"], mapping) == ["uuid-a"]

    def test_drops_non_string_entries(self):
        mapping = {"0": "uuid-a"}
        assert _resolve_linked_memory_ids(["0", 1, None, 3.5], mapping) == ["uuid-a"]

    def test_dedupes_repeated_indices(self):
        mapping = {"0": "uuid-a"}
        assert _resolve_linked_memory_ids(["0", "0"], mapping) == ["uuid-a"]

    def test_dedupes_when_two_indices_map_to_same_real_id(self):
        # Defensive: shouldn't happen given how uuid_mapping is built, but the
        # resolver must not emit a duplicate real ID either way.
        mapping = {"0": "uuid-a", "1": "uuid-a"}
        assert _resolve_linked_memory_ids(["0", "1"], mapping) == ["uuid-a"]

    def test_empty_list_returns_empty(self):
        assert _resolve_linked_memory_ids([], {"0": "uuid-a"}) == []

    def test_none_returns_empty(self):
        assert _resolve_linked_memory_ids(None, {"0": "uuid-a"}) == []

    def test_non_list_returns_empty(self):
        assert _resolve_linked_memory_ids("0", {"0": "uuid-a"}) == []

    def test_empty_mapping_drops_everything(self):
        assert _resolve_linked_memory_ids(["0", "1"], {}) == []


# ---------------------------------------------------------------------------
# 2. Sync Phase 4: the resolved field must reach the persisted payload
# ---------------------------------------------------------------------------


class TestSyncAddPersistsLinkedMemoryIds:
    @pytest.fixture
    def mock_memory(self, mocker):
        mock_llm, _ = _setup_mocks(mocker)
        memory = Memory()
        memory.config = mocker.MagicMock()
        memory.config.custom_instructions = None
        memory.config.custom_update_memory_prompt = None
        memory.custom_instructions = None
        memory.api_version = "v1.1"
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()
        memory.db.batch_add_history = MagicMock()
        memory._entity_store = Mock()
        memory._entity_store.search_batch = Mock(return_value=[[]])
        return memory

    def test_linked_memory_ids_resolved_into_payload(self, mock_memory, mocker):
        existing = MagicMock(id="uuid-poppy", payload={"data": "User has a dog named Poppy", "hash": "h1"})
        mock_memory.vector_store.search = Mock(return_value=[existing])
        mock_memory.llm.generate_response.return_value = (
            '{"memory": [{"text": "Poppy had a vet checkup", "linked_memory_ids": ["0"]}]}'
        )
        mock_memory.embedding_model = Mock()
        mock_memory.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
        mock_memory.embedding_model.embed_batch = Mock(return_value=[[0.1, 0.2, 0.3]])
        mocker.patch("mem0.memory.main.extract_entities_batch", return_value=[[]])
        mocker.patch("mem0.memory.main.capture_event")

        result = mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "Poppy had a vet checkup"}],
            metadata={"user_id": "u1"},
            filters={"user_id": "u1"},
            infer=True,
        )

        assert len(result) == 1
        payload = mock_memory.vector_store.insert.call_args.kwargs["payloads"][0]
        assert payload["linked_memory_ids"] == ["uuid-poppy"], (
            "the LLM-computed link to the Existing Memory must survive into the persisted payload"
        )

    def test_hallucinated_index_is_dropped_not_persisted(self, mock_memory, mocker):
        # No Existing Memories were shown to the LLM, so uuid_mapping is empty —
        # any linked_memory_ids value it produces is necessarily hallucinated.
        mock_memory.vector_store.search = Mock(return_value=[])
        mock_memory.llm.generate_response.return_value = (
            '{"memory": [{"text": "User likes tea", "linked_memory_ids": ["0"]}]}'
        )
        mock_memory.embedding_model = Mock()
        mock_memory.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
        mock_memory.embedding_model.embed_batch = Mock(return_value=[[0.1, 0.2, 0.3]])
        mocker.patch("mem0.memory.main.extract_entities_batch", return_value=[[]])
        mocker.patch("mem0.memory.main.capture_event")

        mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "User likes tea"}],
            metadata={"user_id": "u1"},
            filters={"user_id": "u1"},
            infer=True,
        )

        payload = mock_memory.vector_store.insert.call_args.kwargs["payloads"][0]
        assert "linked_memory_ids" not in payload

    def test_omitted_field_leaves_payload_unchanged(self, mock_memory, mocker):
        mock_memory.vector_store.search = Mock(return_value=[])
        mock_memory.llm.generate_response.return_value = '{"memory": [{"text": "User likes coffee"}]}'
        mock_memory.embedding_model = Mock()
        mock_memory.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
        mock_memory.embedding_model.embed_batch = Mock(return_value=[[0.1, 0.2, 0.3]])
        mocker.patch("mem0.memory.main.extract_entities_batch", return_value=[[]])
        mocker.patch("mem0.memory.main.capture_event")

        mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "User likes coffee"}],
            metadata={"user_id": "u1"},
            filters={"user_id": "u1"},
            infer=True,
        )

        payload = mock_memory.vector_store.insert.call_args.kwargs["payloads"][0]
        assert "linked_memory_ids" not in payload

    def test_multiple_links_resolved_in_order(self, mock_memory, mocker):
        poppy = MagicMock(id="uuid-poppy", payload={"data": "User has a dog named Poppy", "hash": "h1"})
        shopify = MagicMock(id="uuid-shopify", payload={"data": "User works at Shopify", "hash": "h2"})
        mock_memory.vector_store.search = Mock(return_value=[poppy, shopify])
        mock_memory.llm.generate_response.return_value = (
            '{"memory": [{"text": "Poppy checkup and team switch", "linked_memory_ids": ["1", "0"]}]}'
        )
        mock_memory.embedding_model = Mock()
        mock_memory.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
        mock_memory.embedding_model.embed_batch = Mock(return_value=[[0.1, 0.2, 0.3]])
        mocker.patch("mem0.memory.main.extract_entities_batch", return_value=[[]])
        mocker.patch("mem0.memory.main.capture_event")

        mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "Poppy checkup and team switch"}],
            metadata={"user_id": "u1"},
            filters={"user_id": "u1"},
            infer=True,
        )

        payload = mock_memory.vector_store.insert.call_args.kwargs["payloads"][0]
        assert payload["linked_memory_ids"] == ["uuid-shopify", "uuid-poppy"]


# ---------------------------------------------------------------------------
# 3. Async Phase 4: same contract as sync
# ---------------------------------------------------------------------------


class TestAsyncAddPersistsLinkedMemoryIds:
    @pytest.fixture
    def mock_memory(self, mocker):
        mock_llm, _ = _setup_mocks(mocker)
        memory = AsyncMemory()
        memory.config = mocker.MagicMock()
        memory.config.custom_instructions = None
        memory.config.custom_update_memory_prompt = None
        memory.custom_instructions = None
        memory.api_version = "v1.1"
        memory.db.get_last_messages = MagicMock(return_value=[])
        memory.db.save_messages = MagicMock()
        memory.db.batch_add_history = MagicMock()
        memory._entity_store = Mock()
        memory._entity_store.search_batch = Mock(return_value=[[]])
        return memory

    @pytest.mark.asyncio
    async def test_linked_memory_ids_resolved_into_payload(self, mock_memory, mocker):
        existing = MagicMock(id="uuid-poppy", payload={"data": "User has a dog named Poppy", "hash": "h1"})
        mock_memory.vector_store.search = Mock(return_value=[existing])
        mock_memory.llm.generate_response.return_value = (
            '{"memory": [{"text": "Poppy had a vet checkup", "linked_memory_ids": ["0"]}]}'
        )
        mock_memory.embedding_model = Mock()
        mock_memory.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
        mock_memory.embedding_model.embed_batch = Mock(return_value=[[0.1, 0.2, 0.3]])
        mocker.patch("mem0.memory.main.extract_entities_batch", return_value=[[]])
        mocker.patch("mem0.memory.main.capture_event")

        result = await mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "Poppy had a vet checkup"}],
            metadata={"user_id": "u1"},
            effective_filters={"user_id": "u1"},
            infer=True,
        )

        assert len(result) == 1
        payload = mock_memory.vector_store.insert.call_args.kwargs["payloads"][0]
        assert payload["linked_memory_ids"] == ["uuid-poppy"]

    @pytest.mark.asyncio
    async def test_hallucinated_index_is_dropped_not_persisted(self, mock_memory, mocker):
        mock_memory.vector_store.search = Mock(return_value=[])
        mock_memory.llm.generate_response.return_value = (
            '{"memory": [{"text": "User likes tea", "linked_memory_ids": ["0"]}]}'
        )
        mock_memory.embedding_model = Mock()
        mock_memory.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
        mock_memory.embedding_model.embed_batch = Mock(return_value=[[0.1, 0.2, 0.3]])
        mocker.patch("mem0.memory.main.extract_entities_batch", return_value=[[]])
        mocker.patch("mem0.memory.main.capture_event")

        await mock_memory._add_to_vector_store(
            messages=[{"role": "user", "content": "User likes tea"}],
            metadata={"user_id": "u1"},
            effective_filters={"user_id": "u1"},
            infer=True,
        )

        payload = mock_memory.vector_store.insert.call_args.kwargs["payloads"][0]
        assert "linked_memory_ids" not in payload
