"""Unit tests for the entity-boost embedding batching in search().

Covers the perf fix that replaces the serial per-entity ``embed()`` loop with a
single ``embed_batch()`` call (with serial fallback on batch failure) in both
the sync (``Memory._compute_entity_boosts``) and async
(``AsyncMemory._compute_entity_boosts_async``) paths.
"""

import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.base import MemoryConfig
from mem0.memory.main import AsyncMemory, Memory


QUERY_ENTITIES = [
    ("PROPER", "Alice"),
    ("PROPER", "Bob"),
    ("PROPER", "Carol"),
    ("PROPER", "Dave"),
    ("PROPER", "Eve"),
    ("COMPOUND", "Acme Corp"),
]
FILTERS = {"user_id": "test_user"}


@pytest.fixture(autouse=True)
def _mock_openai_env():
    os.environ["OPENAI_API_KEY"] = "123"
    with patch("openai.OpenAI") as mock:
        mock.return_value = Mock()
        yield mock


def _build_sync_memory():
    with (
        patch("mem0.utils.factory.EmbedderFactory") as mock_embedder,
        patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
        patch("mem0.utils.factory.LlmFactory") as mock_llm,
        patch("mem0.memory.telemetry.capture_event"),
    ):
        mock_embedder.create.return_value = Mock()
        mock_vector_store.create.return_value = Mock()
        mock_llm.create.return_value = Mock()
        memory = Memory(MemoryConfig(version="v1.1"))
    memory.embedding_model = Mock()
    memory._entity_store = Mock()
    memory.entity_store.search = memory._entity_store.search
    return memory


def _build_async_memory():
    with (
        patch("mem0.utils.factory.EmbedderFactory") as mock_embedder,
        patch("mem0.memory.main.VectorStoreFactory") as mock_vector_store,
        patch("mem0.utils.factory.LlmFactory") as mock_llm,
        patch("mem0.memory.telemetry.capture_event"),
    ):
        mock_embedder.create.return_value = Mock()
        mock_vector_store.create.return_value = Mock()
        mock_llm.create.return_value = Mock()
        memory = AsyncMemory(MemoryConfig(version="v1.1"))
    memory.embedding_model = Mock()
    memory._entity_store = Mock()
    memory.entity_store.search = memory._entity_store.search
    return memory


def _make_vector(idx: int):
    return [float(idx)] * 8


# ─── Sync ────────────────────────────────────────────────────────────────

class TestComputeEntityBoostsSync:
    def test_uses_embed_batch_once_for_all_entities(self):
        memory = _build_sync_memory()
        memory.embedding_model.embed_batch.return_value = [
            _make_vector(i) for i in range(len(QUERY_ENTITIES))
        ]
        memory.entity_store.search.return_value = []

        memory._compute_entity_boosts(QUERY_ENTITIES, FILTERS)

        assert memory.embedding_model.embed_batch.call_count == 1
        batched_texts = memory.embedding_model.embed_batch.call_args[0][0]
        assert batched_texts == [t for _, t in QUERY_ENTITIES]
        assert memory.embedding_model.embed_batch.call_args[0][1] == "search"
        # Per-entity embed() must NOT be invoked when batch succeeds.
        assert memory.embedding_model.embed.call_count == 0

    def test_falls_back_to_serial_embed_on_batch_failure(self):
        memory = _build_sync_memory()
        memory.embedding_model.embed_batch.side_effect = Exception("batch failed")
        memory.embedding_model.embed.side_effect = [
            _make_vector(i) for i in range(len(QUERY_ENTITIES))
        ]
        memory.entity_store.search.return_value = []

        memory._compute_entity_boosts(QUERY_ENTITIES, FILTERS)

        assert memory.embedding_model.embed_batch.call_count == 1
        assert memory.embedding_model.embed.call_count == len(QUERY_ENTITIES)
        for call, (_, text) in zip(
            memory.embedding_model.embed.call_args_list, QUERY_ENTITIES
        ):
            assert call.args[0] == text
            assert call.args[1] == "search"

    def test_serial_fallback_tolerates_individual_embed_failures(self):
        memory = _build_sync_memory()
        memory.embedding_model.embed_batch.side_effect = Exception("batch failed")

        # Entity index 2 ("Carol") fails to embed; others succeed.
        def embed_side_effect(text, action):
            failing = QUERY_ENTITIES[2][1]
            if text == failing:
                raise Exception("entity embed failed")
            return _make_vector(len(text))

        memory.embedding_model.embed.side_effect = embed_side_effect
        memory.entity_store.search.return_value = []

        # Must not raise — failure of one entity does not abort the rest.
        result = memory._compute_entity_boosts(QUERY_ENTITIES, FILTERS)
        assert isinstance(result, dict)

        # entity_store.search called once per successful entity (5 of 6).
        assert memory.entity_store.search.call_count == len(QUERY_ENTITIES) - 1

    def test_skips_entity_when_store_search_raises(self):
        memory = _build_sync_memory()
        vectors = [_make_vector(i) for i in range(len(QUERY_ENTITIES))]
        memory.embedding_model.embed_batch.return_value = vectors

        call_count = {"n": 0}

        def search_side_effect(**kwargs):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise Exception("backend hiccup")
            return []

        memory.entity_store.search.side_effect = search_side_effect

        # Must not raise — per-entity isolation preserved.
        result = memory._compute_entity_boosts(QUERY_ENTITIES, FILTERS)
        assert isinstance(result, dict)
        assert memory.entity_store.search.call_count == len(QUERY_ENTITIES)

    def test_produces_expected_boost_values(self):
        memory = _build_sync_memory()
        memory.embedding_model.embed_batch.return_value = [
            _make_vector(i) for i in range(len(QUERY_ENTITIES))
        ]

        # One entity match per call, each linking to a unique memory id.
        # similarity 0.8, num_linked 1 → memory_count_weight = 1.0
        # ENTITY_BOOST_WEIGHT is 0.5 → boost = 0.8 * 0.5 * 1.0 = 0.4
        def search_side_effect(**kwargs):
            entity_text = kwargs["query"]
            idx = [t for _, t in QUERY_ENTITIES].index(entity_text)
            match = Mock()
            match.score = 0.8
            match.payload = {"linked_memory_ids": [f"mem-{idx}"]}
            return [match]

        memory.entity_store.search.side_effect = search_side_effect

        result = memory._compute_entity_boosts(QUERY_ENTITIES, FILTERS)
        assert result == {f"mem-{i}": 0.4 for i in range(len(QUERY_ENTITIES))}

    def test_returns_empty_when_no_entities(self):
        memory = _build_sync_memory()
        result = memory._compute_entity_boosts([], FILTERS)
        assert result == {}
        assert memory.embedding_model.embed_batch.call_count == 0
        assert memory.embedding_model.embed.call_count == 0


# ─── Async ──────────────────────────────────────────────────────────────


@pytest.fixture
def _flatten_asyncio_to_thread():
    """Run ``asyncio.to_thread`` calls inline so assertions on mocks work."""

    async def _inline(fn, *args, **kwargs):
        return fn(*args, **kwargs)

    with patch("mem0.memory.main.asyncio.to_thread", side_effect=_inline):
        yield


@pytest.mark.asyncio
class TestComputeEntityBoostsAsync:
    async def test_uses_embed_batch_once_for_all_entities(
        self, _flatten_asyncio_to_thread
    ):
        memory = _build_async_memory()
        memory.embedding_model.embed_batch.return_value = [
            _make_vector(i) for i in range(len(QUERY_ENTITIES))
        ]
        memory.entity_store.search.return_value = []

        await memory._compute_entity_boosts_async(QUERY_ENTITIES, FILTERS)

        assert memory.embedding_model.embed_batch.call_count == 1
        batched_texts = memory.embedding_model.embed_batch.call_args[0][0]
        assert batched_texts == [t for _, t in QUERY_ENTITIES]
        assert memory.embedding_model.embed_batch.call_args[0][1] == "search"
        assert memory.embedding_model.embed.call_count == 0

    async def test_falls_back_to_serial_embed_on_batch_failure(
        self, _flatten_asyncio_to_thread
    ):
        memory = _build_async_memory()
        memory.embedding_model.embed_batch.side_effect = Exception("batch failed")
        memory.embedding_model.embed.side_effect = [
            _make_vector(i) for i in range(len(QUERY_ENTITIES))
        ]
        memory.entity_store.search.return_value = []

        await memory._compute_entity_boosts_async(QUERY_ENTITIES, FILTERS)

        assert memory.embedding_model.embed_batch.call_count == 1
        assert memory.embedding_model.embed.call_count == len(QUERY_ENTITIES)

    async def test_serial_fallback_tolerates_individual_embed_failures(
        self, _flatten_asyncio_to_thread
    ):
        memory = _build_async_memory()
        memory.embedding_model.embed_batch.side_effect = Exception("batch failed")

        def embed_side_effect(text, action):
            if text == QUERY_ENTITIES[2][1]:
                raise Exception("entity embed failed")
            return _make_vector(len(text))

        memory.embedding_model.embed.side_effect = embed_side_effect
        memory.entity_store.search.return_value = []

        result = await memory._compute_entity_boosts_async(QUERY_ENTITIES, FILTERS)
        assert isinstance(result, dict)
        assert memory.entity_store.search.call_count == len(QUERY_ENTITIES) - 1

    async def test_produces_expected_boost_values(self, _flatten_asyncio_to_thread):
        memory = _build_async_memory()
        memory.embedding_model.embed_batch.return_value = [
            _make_vector(i) for i in range(len(QUERY_ENTITIES))
        ]

        def search_side_effect(**kwargs):
            entity_text = kwargs["query"]
            idx = [t for _, t in QUERY_ENTITIES].index(entity_text)
            match = Mock()
            match.score = 0.8
            match.payload = {"linked_memory_ids": [f"mem-{idx}"]}
            return [match]

        memory.entity_store.search.side_effect = search_side_effect

        result = await memory._compute_entity_boosts_async(QUERY_ENTITIES, FILTERS)
        assert result == {f"mem-{i}": 0.4 for i in range(len(QUERY_ENTITIES))}

    async def test_returns_empty_when_no_entities(self, _flatten_asyncio_to_thread):
        memory = _build_async_memory()
        result = await memory._compute_entity_boosts_async([], FILTERS)
        assert result == {}
        assert memory.embedding_model.embed_batch.call_count == 0
        assert memory.embedding_model.embed.call_count == 0
