"""Tests that hash dedup runs BEFORE embedding in _add_to_vector_store.

Regression tests for the Phase 3/4/5 reorder: duplicate memories (by md5
against existing store hashes or within the batch) must be dropped before
any embed call is made, so the embedding provider is never charged for
texts that are skipped anyway.
"""

import hashlib
import json
from unittest.mock import MagicMock

import pytest

from mem0.memory.main import AsyncMemory, Memory


def _mem(text, idx):
    """Build a fake vector-store search hit with a payload hash."""
    hit = MagicMock()
    hit.id = f"existing-{idx}"
    hit.score = 0.9
    hit.payload = {"data": text, "hash": hashlib.md5(text.encode()).hexdigest()}
    return hit


def _setup_extract(memory, texts, existing=None):
    """Point the pipeline at a fixed extraction result.

    `existing` (list of fake search hits) must be passed here, not set
    separately, because this helper resets the vector_store mocks.
    """
    memory.llm.generate_response.return_value = json.dumps(
        {"memory": [{"id": str(i), "text": t} for i, t in enumerate(texts)]}
    )
    memory.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
    memory.embedding_model.embed_batch.return_value = [[0.1, 0.2, 0.3] for _ in texts]
    memory.vector_store.search.return_value = existing or []
    memory.vector_store.insert.return_value = None
    memory.db.get_last_messages.return_value = []
    memory.db.save_messages = MagicMock()
    memory.db.batch_add_history.return_value = None


def _build_memory(mocker, memory_cls):
    from tests.memory.test_main import _build_memory_instance

    memory = _build_memory_instance(mocker, memory_cls)
    return memory


class TestDedupBeforeEmbedSync:
    def test_existing_duplicate_not_embedded(self, mocker):
        """A fact whose md5 matches an existing memory must not reach embed."""
        memory = _build_memory(mocker, Memory)
        dup = "User likes hiking in the mountains"
        _setup_extract(memory, [dup, "User has a golden retriever named Max"], existing=[_mem(dup, 0)])

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I like hiking and have a dog"}],
            metadata={},
            filters={"user_id": "u1"},
            infer=True,
        )

        # First embed_batch call is Phase 4 (memory texts); a later one embeds entities
        embedded = memory.embedding_model.embed_batch.call_args_list[0].args[0]
        assert dup not in embedded
        assert embedded == ["User has a golden retriever named Max"]

    def test_in_batch_duplicate_embedded_once(self, mocker):
        """Two identical extractions embed one text, not two."""
        memory = _build_memory(mocker, Memory)
        text = "User drinks green tea every morning"
        _setup_extract(memory, [text, text, "User works at Acme Corp"])

        memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I drink tea and work at Acme"}],
            metadata={},
            filters={"user_id": "u1"},
            infer=True,
        )

        # First embed_batch call is Phase 4 (memory texts); a later one embeds entities
        embedded = memory.embedding_model.embed_batch.call_args_list[0].args[0]
        assert embedded.count(text) == 1
        assert embedded == [text, "User works at Acme Corp"]

    def test_all_duplicates_makes_no_embed_call(self, mocker):
        """Every fact a duplicate -> dedup short-circuits before any embedding."""
        memory = _build_memory(mocker, Memory)
        dup = "User lives in Seattle"
        _setup_extract(memory, [dup, dup], existing=[_mem(dup, 0)])

        result = memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I live in Seattle"}],
            metadata={},
            filters={"user_id": "u1"},
            infer=True,
        )

        assert result == []
        memory.embedding_model.embed_batch.assert_not_called()
        # Phase 1 embeds the query for retrieval ("search") — that one is
        # unavoidable. What must NOT happen is an "add" embed of the fact.
        add_embeds = [c for c in memory.embedding_model.embed.call_args_list if c.args[-1] == "add"]
        assert add_embeds == []


class TestDedupBeforeEmbedAsync:
    @pytest.mark.asyncio
    async def test_async_existing_duplicate_not_embedded(self, mocker):
        memory = _build_memory(mocker, AsyncMemory)
        dup = "User likes hiking in the mountains"
        _setup_extract(memory, [dup, "User has a golden retriever named Max"], existing=[_mem(dup, 0)])

        await memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I like hiking and have a dog"}],
            metadata={},
            effective_filters={"user_id": "u1"},
            infer=True,
        )

        # First embed_batch call is Phase 4 (memory texts); a later one embeds entities
        embedded = memory.embedding_model.embed_batch.call_args_list[0].args[0]
        assert dup not in embedded
        assert embedded == ["User has a golden retriever named Max"]

    @pytest.mark.asyncio
    async def test_async_all_duplicates_makes_no_embed_call(self, mocker):
        memory = _build_memory(mocker, AsyncMemory)
        dup = "User lives in Seattle"
        _setup_extract(memory, [dup], existing=[_mem(dup, 0)])

        result = await memory._add_to_vector_store(
            messages=[{"role": "user", "content": "I live in Seattle"}],
            metadata={},
            effective_filters={"user_id": "u1"},
            infer=True,
        )

        assert result == []
        memory.embedding_model.embed_batch.assert_not_called()
        add_embeds = [c for c in memory.embedding_model.embed.call_args_list if c.args[-1] == "add"]
        assert add_embeds == []
