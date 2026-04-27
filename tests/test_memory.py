import json
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from mem0 import Memory
from mem0.configs.base import MemoryConfig
from mem0.memory.utils import normalize_facts


class MockVectorMemory:
    """Mock memory object for testing incomplete payloads."""

    def __init__(self, memory_id: str, payload: dict, score: float = 0.8):
        self.id = memory_id
        self.payload = payload
        self.score = score


@pytest.fixture
def memory_client():
    with patch.object(Memory, "__init__", return_value=None):
        client = Memory()
        client.add = MagicMock(return_value={"results": [{"id": "1", "memory": "Name is John Doe.", "event": "ADD"}]})
        client.get = MagicMock(return_value={"id": "1", "memory": "Name is John Doe."})
        client.update = MagicMock(return_value={"message": "Memory updated successfully!"})
        client.delete = MagicMock(return_value={"message": "Memory deleted successfully!"})
        client.history = MagicMock(return_value=[{"memory": "I like Indian food."}, {"memory": "I like Italian food."}])
        client.get_all = MagicMock(return_value=["Name is John Doe.", "Name is John Doe. I like to code in Python."])
        yield client


def test_create_memory(memory_client):
    data = "Name is John Doe."
    result = memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    assert result["results"][0]["memory"] == data


def test_get_memory(memory_client):
    data = "Name is John Doe."
    memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    result = memory_client.get("1")
    assert result["memory"] == data


def test_update_memory(memory_client):
    data = "Name is John Doe."
    memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    new_data = "Name is John Kapoor."
    update_result = memory_client.update("1", text=new_data)
    assert update_result["message"] == "Memory updated successfully!"


def test_delete_memory(memory_client):
    data = "Name is John Doe."
    memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    delete_result = memory_client.delete("1")
    assert delete_result["message"] == "Memory deleted successfully!"


def test_history(memory_client):
    data = "I like Indian food."
    memory_client.add([{"role": "user", "content": data}], user_id="test_user")
    memory_client.update("1", text="I like Italian food.")
    history = memory_client.history("1")
    assert history[0]["memory"] == "I like Indian food."
    assert history[1]["memory"] == "I like Italian food."


def test_list_memories(memory_client):
    data1 = "Name is John Doe."
    data2 = "Name is John Doe. I like to code in Python."
    memory_client.add([{"role": "user", "content": data1}], user_id="test_user")
    memory_client.add([{"role": "user", "content": data2}], user_id="test_user")
    memories = memory_client.get_all(filters={"user_id": "test_user"})
    assert data1 in memories
    assert data2 in memories


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_collection_name_preserved_after_reset(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    test_collection_name = "mem0"
    config = MemoryConfig()
    config.vector_store.config.collection_name = test_collection_name

    memory = Memory(config)

    assert memory.collection_name == test_collection_name
    assert memory.config.vector_store.config.collection_name == test_collection_name

    memory.reset()

    assert memory.collection_name == test_collection_name
    assert memory.config.vector_store.config.collection_name == test_collection_name

    reset_calls = [call for call in mock_vector_factory.call_args_list if len(mock_vector_factory.call_args_list) > 2]
    if reset_calls:
        reset_config = reset_calls[-1][0][1]
        assert reset_config.collection_name == test_collection_name, f"Reset used wrong collection name: {reset_config.collection_name}"


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_search_handles_incomplete_payloads(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """Test that search operations handle memory objects with missing 'data' key gracefully."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    config = MemoryConfig()
    memory = MemoryClass(config)

    # Create test data with both complete and incomplete payloads
    incomplete_memory = MockVectorMemory("mem_1", {"hash": "abc123"})
    complete_memory = MockVectorMemory("mem_2", {"data": "content", "hash": "def456"})

    mock_vector_store.search.return_value = [incomplete_memory, complete_memory]

    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [0.1, 0.2, 0.3]
    memory.embedding_model = mock_embedder

    result = memory._search_vector_store("test", {"user_id": "test"}, 10)

    # v3 search pipeline skips entries where payload has no "data" key
    assert len(result) == 1
    assert result[0]["id"] == "mem_2"
    assert result[0]["memory"] == "content"


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_get_all_handles_nested_list_from_chroma(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Test that get_all() handles nested list return from Chroma/Milvus.

    Issue #3674: Some vector stores return [[mem1, mem2]] instead of [mem1, mem2]
    This test ensures the unified unwrapping logic handles this correctly.
    """
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    config = MemoryConfig()
    memory = MemoryClass(config)

    # Create test data
    mem1 = MockVectorMemory("mem_1", {"data": "My dog name is Sheru"})
    mem2 = MockVectorMemory("mem_2", {"data": "I like to code in Python"})
    mem3 = MockVectorMemory("mem_3", {"data": "I live in California"})

    # Chroma/Milvus returns nested list: [[mem1, mem2, mem3]]
    mock_vector_store.list.return_value = [[mem1, mem2, mem3]]

    result = memory._get_all_from_vector_store({"user_id": "test"}, 100)

    # Should successfully unwrap and return 3 memories
    assert len(result) == 3
    assert result[0]["memory"] == "My dog name is Sheru"
    assert result[1]["memory"] == "I like to code in Python"
    assert result[2]["memory"] == "I live in California"


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_get_all_handles_tuple_from_qdrant(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Test that get_all() handles tuple return from Qdrant.

    Qdrant returns: ([mem1, mem2], count)
    Should unwrap to [mem1, mem2]
    """
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    config = MemoryConfig()
    memory = MemoryClass(config)

    mem1 = MockVectorMemory("mem_1", {"data": "Memory 1"})
    mem2 = MockVectorMemory("mem_2", {"data": "Memory 2"})

    # Qdrant returns tuple: ([mem1, mem2], count)
    mock_vector_store.list.return_value = ([mem1, mem2], 100)

    result = memory._get_all_from_vector_store({"user_id": "test"}, 100)

    assert len(result) == 2
    assert result[0]["memory"] == "Memory 1"
    assert result[1]["memory"] == "Memory 2"


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_get_all_handles_flat_list_from_postgres(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Test that get_all() handles flat list return from PostgreSQL.

    PostgreSQL returns: [mem1, mem2]
    Should keep as-is without unwrapping
    """
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    config = MemoryConfig()
    memory = MemoryClass(config)

    mem1 = MockVectorMemory("mem_1", {"data": "Memory 1"})
    mem2 = MockVectorMemory("mem_2", {"data": "Memory 2"})

    # PostgreSQL returns flat list: [mem1, mem2]
    mock_vector_store.list.return_value = [mem1, mem2]

    result = memory._get_all_from_vector_store({"user_id": "test"}, 100)

    assert len(result) == 2
    assert result[0]["memory"] == "Memory 1"
    assert result[1]["memory"] == "Memory 2"


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_add_infer_with_malformed_llm_facts(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Repro for: 'list' object has no attribute 'replace' on infer=true.

    When an LLM (especially smaller models like llama3.1:8b) returns facts as
    objects ({"fact": "..."} or {"text": "..."}) instead of plain strings,
    the embedding model's .replace() call crashes with AttributeError.
    """
    mock_embedder = MagicMock()
    mock_embedder.embed.side_effect = lambda text, action: (_ for _ in ()).throw(
        AttributeError("'dict' object has no attribute 'replace'")
    ) if not isinstance(text, str) else [0.1, 0.2, 0.3]
    mock_embedder_factory.return_value = mock_embedder

    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = []
    mock_vector_factory.return_value = mock_vector_store

    # LLM returns malformed facts: dicts instead of strings
    malformed_response = json.dumps({
        "facts": [
            {"fact": "User likes Python"},
            {"text": "User is a developer"},
        ]
    })
    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = malformed_response
    mock_llm_factory.return_value = mock_llm

    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    config = MemoryConfig()
    memory = MemoryClass(config)

    # This should NOT raise AttributeError
    memory._add_to_vector_store(
        messages=[{"role": "user", "content": "I like Python and I'm a developer"}],
        metadata={"user_id": "test_user"},
        filters={"user_id": "test_user"},
        infer=True,
    )


def test_normalize_facts_plain_strings():
    assert normalize_facts(["fact one", "fact two"]) == ["fact one", "fact two"]


def test_normalize_facts_dict_with_fact_key():
    assert normalize_facts([{"fact": "User likes Python"}]) == ["User likes Python"]


def test_normalize_facts_dict_with_text_key():
    assert normalize_facts([{"text": "User is a developer"}]) == ["User is a developer"]


def test_normalize_facts_mixed():
    raw = [
        "plain string",
        {"fact": "from fact key"},
        {"text": "from text key"},
    ]
    assert normalize_facts(raw) == ["plain string", "from fact key", "from text key"]


def test_normalize_facts_filters_empty_strings():
    assert normalize_facts(["", "valid", ""]) == ["valid"]


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_delete_nonexistent_memory_raises_error(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Test that delete() raises ValueError when memory_id does not exist
    and does not attempt to delete from the vector store.

    Issue #3849: memory.delete() fails with AttributeError when memory not found.
    Should raise a clear ValueError instead.
    """
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    config = MemoryConfig()
    memory = MemoryClass(config)

    mock_vector_store.get.return_value = None

    with pytest.raises(ValueError, match="Memory with id non-existent-id not found"):
        memory.delete("non-existent-id")

    mock_vector_store.delete.assert_not_called()


@pytest.mark.asyncio
@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
async def test_async_delete_nonexistent_memory_raises_error(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Test that async delete() raises ValueError when memory_id does not exist
    and does not attempt to delete from the vector store.

    Issue #3849: memory.delete() fails with AttributeError when memory not found.
    Should raise a clear ValueError instead.
    """
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_store.get.return_value = None
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import AsyncMemory
    config = MemoryConfig()
    memory = AsyncMemory(config)

    with pytest.raises(ValueError, match="Memory with id non-existent-id not found"):
        await memory.delete("non-existent-id")

    mock_vector_store.delete.assert_not_called()


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_update_nonexistent_memory_raises_error(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Test that _update_memory() raises ValueError when memory_id does not exist.

    Same class of bug as #3849 — vector_store.get() returns None and code
    accesses .payload without a null check.
    """
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    config = MemoryConfig()
    memory = MemoryClass(config)

    mock_vector_store.get.return_value = None

    with pytest.raises(ValueError, match="Memory with id non-existent-id not found"):
        memory._update_memory("non-existent-id", "new data", {"new data": [0.1, 0.2]})

    mock_vector_store.update.assert_not_called()


@pytest.mark.asyncio
@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
async def test_async_update_nonexistent_memory_raises_error(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Test that async _update_memory() raises ValueError when memory_id does not exist.

    Same class of bug as #3849 — vector_store.get() returns None and code
    accesses .payload without a null check.
    """
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_store.get.return_value = None
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import AsyncMemory
    config = MemoryConfig()
    memory = AsyncMemory(config)

    with pytest.raises(ValueError, match="Memory with id non-existent-id not found"):
        await memory._update_memory("non-existent-id", "new data", {"new data": [0.1, 0.2]})

    mock_vector_store.update.assert_not_called()


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_add_infer_false_embeds_once(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Regression test for issue #3723: adding with infer=False should not trigger duplicate embedding calls.

    Root cause: _create_memory expected a dict for existing_embeddings but received a raw list[float],
    causing the cache check `data in existing_embeddings` to always fail and trigger a redundant embed.
    """
    embedder = MagicMock()
    embedder.embed.return_value = [0.1, 0.2, 0.3]
    embedder.config = MagicMock(embedding_dims=3)
    mock_embedder_factory.return_value = embedder

    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = []
    mock_vector_store.insert.return_value = None
    mock_vector_store.get.return_value = None
    telemetry_vector_store = MagicMock()
    mock_vector_factory.side_effect = [mock_vector_store, telemetry_vector_store]

    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    memory = MemoryClass(MemoryConfig())

    memory.add("foo", user_id="test_user", infer=False)

    assert embedder.embed.call_count == 1
    mock_vector_store.insert.assert_called_once()


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_add_infer_true_caches_embedding_on_llm_rewrite(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Regression test for issue #3723 (infer=True path): when the LLM rewrites a fact during the
    ADD action, the embedding should be computed once and cached, not computed again inside _create_memory.
    """
    embedder = MagicMock()
    embedder.embed.return_value = [0.1, 0.2, 0.3]
    embedder.config = MagicMock(embedding_dims=3)
    mock_embedder_factory.return_value = embedder

    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = []
    mock_vector_store.insert.return_value = None
    mock_vector_store.get.return_value = None
    telemetry_vector_store = MagicMock()
    mock_vector_factory.side_effect = [mock_vector_store, telemetry_vector_store]

    # V3 single-call extraction: LLM returns extracted memories directly
    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = json.dumps(
        {"memory": [{"text": "The user enjoys Python"}]}
    )
    mock_llm_factory.return_value = mock_llm

    # embed_batch is used in Phase 3 for all extracted memories
    embedder.embed_batch.return_value = [[0.4, 0.5, 0.6]]

    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    memory = MemoryClass(MemoryConfig())

    memory.add("I like Python", user_id="test_user", infer=True)

    # V3 pipeline: embed called once for search query (Phase 1),
    # embed_batch called once for extracted memories (Phase 3)
    assert embedder.embed.call_count == 1
    assert embedder.embed_batch.call_count == 1
    mock_vector_store.insert.assert_called_once()


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_update_infer_true_caches_embedding_on_llm_rewrite(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Regression test for issue #3723 (infer=True path): V3 is ADD-only, so this test verifies
    that the single-call extraction pipeline embeds via embed_batch, not individual embed calls.
    """
    embedder = MagicMock()
    embedder.embed.return_value = [0.1, 0.2, 0.3]
    embedder.config = MagicMock(embedding_dims=3)
    mock_embedder_factory.return_value = embedder

    # Existing memory that will be returned from search
    existing_memory = MockVectorMemory(
        memory_id="existing-mem-id",
        payload={
            "data": "User likes Python",
            "hash": "abc123",
            "created_at": "2025-01-01T00:00:00+00:00",
        },
    )

    mock_vector_store = MagicMock()
    mock_vector_store.search.return_value = [existing_memory]
    mock_vector_store.get.return_value = existing_memory
    mock_vector_store.insert.return_value = None
    mock_vector_store.update.return_value = None
    mock_vector_store.keyword_search.return_value = None
    telemetry_vector_store = MagicMock()
    mock_vector_factory.side_effect = [mock_vector_store, telemetry_vector_store]

    # V3 single-call extraction: LLM returns extracted memories directly
    mock_llm = MagicMock()
    mock_llm.generate_response.return_value = json.dumps(
        {"memory": [{"text": "The user loves Python"}]}
    )
    mock_llm_factory.return_value = mock_llm

    # embed_batch is used in Phase 3 for all extracted memories
    embedder.embed_batch.return_value = [[0.4, 0.5, 0.6]]

    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    memory = MemoryClass(MemoryConfig())

    memory.add("I love Python now", user_id="test_user", infer=True)

    # V3 pipeline: embed called once for search query (Phase 1),
    # embed_batch called once for extracted memories (Phase 3)
    assert embedder.embed.call_count == 1
    assert embedder.embed_batch.call_count == 1
    mock_vector_store.insert.assert_called_once()


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.main.SQLiteManager')
def test_delete_memory_history_has_timestamps(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Test that deleting a memory records created_at and updated_at in history.

    Ensures DELETE operations preserve the original creation timestamp
    and record the deletion time for proper audit trails.
    """
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    config = MemoryConfig()
    memory = MemoryClass(config)

    existing_memory = MagicMock()
    existing_memory.payload = {
        "data": "I like Python.",
        "created_at": "2024-01-01T00:00:00+00:00",
        "actor_id": None,
        "role": None,
    }
    mock_vector_store.get.return_value = existing_memory

    memory.delete("mem-123")

    call_kwargs = memory.db.add_history.call_args.kwargs
    assert call_kwargs["created_at"] == "2024-01-01T00:00:00+00:00"
    assert call_kwargs["updated_at"] is not None
    datetime.fromisoformat(call_kwargs["updated_at"])  # verify valid ISO timestamp


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.main.SQLiteManager')
def test_delete_memory_normalizes_non_utc_created_at(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """Test that non-UTC created_at timestamps are normalized to UTC on delete."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    config = MemoryConfig()
    memory = MemoryClass(config)

    existing_memory = MagicMock()
    existing_memory.payload = {
        "data": "I like Python.",
        "created_at": "2024-01-01T05:00:00+05:00",  # UTC+5
        "actor_id": None,
        "role": None,
    }
    mock_vector_store.get.return_value = existing_memory

    memory.delete("mem-123")

    call_kwargs = memory.db.add_history.call_args.kwargs
    assert call_kwargs["created_at"] == "2024-01-01T00:00:00+00:00"  # normalized to UTC


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.main.SQLiteManager')
def test_delete_memory_missing_created_at(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """Test that delete works when created_at is absent from the payload (pre-existing memories)."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    config = MemoryConfig()
    memory = MemoryClass(config)

    existing_memory = MagicMock()
    existing_memory.payload = {
        "data": "I like Python.",
        "actor_id": None,
        "role": None,
    }
    mock_vector_store.get.return_value = existing_memory

    memory.delete("mem-123")

    call_kwargs = memory.db.add_history.call_args.kwargs
    assert call_kwargs["created_at"] is None
    assert call_kwargs["updated_at"] is not None
    datetime.fromisoformat(call_kwargs["updated_at"])  # verify valid ISO timestamp


@pytest.mark.asyncio
@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.main.SQLiteManager')
async def test_async_delete_memory_history_has_timestamps(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Test that async deleting a memory records created_at and updated_at in history.

    Ensures async DELETE operations preserve the original creation timestamp
    and record the deletion time for proper audit trails.
    """
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import AsyncMemory
    config = MemoryConfig()
    memory = AsyncMemory(config)

    existing_memory = MagicMock()
    existing_memory.payload = {
        "data": "I like Python.",
        "created_at": "2024-01-01T00:00:00+00:00",
        "actor_id": None,
        "role": None,
    }
    mock_vector_store.get.return_value = existing_memory

    await memory.delete("mem-123")

    call_kwargs = memory.db.add_history.call_args.kwargs
    assert call_kwargs["created_at"] == "2024-01-01T00:00:00+00:00"
    assert call_kwargs["updated_at"] is not None
    datetime.fromisoformat(call_kwargs["updated_at"])  # verify valid ISO timestamp


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
class TestProcessMetadataFiltersMerge:
    """Regression tests for issue #3952: multiple operators on the same key must be merged."""

    def _make_memory(self, mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
        mock_embedder_factory.return_value = MagicMock()
        mock_vector_factory.return_value = MagicMock()
        mock_llm_factory.return_value = MagicMock()
        mock_sqlite.return_value = MagicMock()
        from mem0.memory.main import Memory as MemoryClass
        return MemoryClass(MemoryConfig())

    def test_multiple_operators_same_key_merged(self, mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
        """Filters like created_at: {gte: X, lte: Y} must preserve both operators."""
        memory = self._make_memory(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory)
        result = memory._process_metadata_filters({
            "created_at": {"gte": 1000, "lte": 2000}
        })
        assert result == {"created_at": {"gte": 1000, "lte": 2000}}

    def test_single_operator_still_works(self, mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
        """Single operator filters must continue to work."""
        memory = self._make_memory(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory)
        result = memory._process_metadata_filters({
            "created_at": {"gte": 1000}
        })
        assert result == {"created_at": {"gte": 1000}}

    def test_multiple_keys_with_multiple_operators(self, mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
        """Multiple keys each with multiple operators."""
        memory = self._make_memory(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory)
        result = memory._process_metadata_filters({
            "created_at": {"gte": 1000, "lte": 2000},
            "score": {"gt": 0.5, "lt": 0.9},
        })
        assert result == {
            "created_at": {"gte": 1000, "lte": 2000},
            "score": {"gt": 0.5, "lt": 0.9},
        }

    def test_and_same_key_different_operators_merged(self, mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
        """AND with same key in separate conditions must merge operators (issue #4850)."""
        memory = self._make_memory(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory)
        result = memory._process_metadata_filters({
            "AND": [{"price": {"gt": 10}}, {"price": {"lt": 20}}]
        })
        assert result == {"price": {"gt": 10, "lt": 20}}

    def test_and_same_key_three_operators_merged(self, mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
        """AND with three conditions on the same key must merge all operators."""
        memory = self._make_memory(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory)
        result = memory._process_metadata_filters({
            "AND": [{"price": {"gte": 5}}, {"price": {"lte": 100}}, {"price": {"ne": 50}}]
        })
        assert result == {"price": {"gte": 5, "lte": 100, "ne": 50}}

    def test_and_mixed_keys_with_same_key_overlap(self, mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
        """AND with a mix of same-key and different-key conditions."""
        memory = self._make_memory(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory)
        result = memory._process_metadata_filters({
            "AND": [{"price": {"gt": 10}}, {"category": "electronics"}, {"price": {"lt": 20}}]
        })
        assert result == {"price": {"gt": 10, "lt": 20}, "category": "electronics"}

    def test_and_simple_equality_no_merge(self, mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
        """AND with simple equality values on the same key — last value wins."""
        memory = self._make_memory(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory)
        result = memory._process_metadata_filters({
            "AND": [{"status": "active"}, {"status": "pending"}]
        })
        assert result == {"status": "pending"}


# --- Issue #3040: reset() should clean up graph database ---

@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_reset_skips_graph_when_graph_disabled(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """Test that reset() does NOT call graph.reset() when graph is disabled."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    config = MemoryConfig()
    memory = Memory(config)

    # Graph is disabled by default (graph is None)
    memory.graph = None

    memory.reset()

    # graph should remain None after reset
    assert memory.graph is None


# ─── Entity Param Rejection Tests ─────────────────────────────────────────────
@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_search_rejects_user_id_kwarg(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """search() should reject user_id as top-level kwarg."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    config = MemoryConfig()
    memory = Memory(config)

    with pytest.raises(ValueError, match=r"user_id.*filters"):
        memory.search("test query", user_id="u1")


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_get_all_rejects_user_id_kwarg(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """get_all() should reject user_id as top-level kwarg."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    config = MemoryConfig()
    memory = Memory(config)

    with pytest.raises(ValueError, match=r"user_id.*filters"):
        memory.get_all(user_id="u1")


# ─── Regression: AsyncMemory._create_memory must store text_lemmatized ─────────
@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_sync_create_memory_stores_text_lemmatized(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """Sync Memory._create_memory must include text_lemmatized in payload for BM25 keyword search."""
    embedder = MagicMock()
    embedder.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder_factory.return_value = embedder

    mock_vector_store = MagicMock()
    mock_vector_store.insert.return_value = None
    telemetry_vector_store = MagicMock()
    mock_vector_factory.side_effect = [mock_vector_store, telemetry_vector_store]

    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    memory = MemoryClass(MemoryConfig())

    data = "I love hiking in the mountains"
    embeddings = {data: [0.1, 0.2, 0.3]}
    metadata = {"user_id": "test_user"}

    memory._create_memory(data, embeddings, metadata)

    # Check that text_lemmatized was stored in the payload
    insert_call = mock_vector_store.insert.call_args
    payload = insert_call.kwargs.get("payloads") or insert_call[1].get("payloads")
    assert payload is not None and len(payload) == 1
    assert "text_lemmatized" in payload[0], "Sync _create_memory must store text_lemmatized for BM25"
    assert payload[0]["text_lemmatized"] != "", "text_lemmatized must not be empty"


@pytest.mark.asyncio
@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
async def test_async_create_memory_stores_text_lemmatized(mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory):
    """
    Regression test: AsyncMemory._create_memory must include text_lemmatized
    in the vector store payload.

    Without text_lemmatized, memories created via AsyncMemory with infer=False
    are invisible to BM25 keyword search, silently degrading search recall for
    all async users.
    """
    embedder = MagicMock()
    embedder.embed.return_value = [0.1, 0.2, 0.3]
    mock_embedder_factory.return_value = embedder

    mock_vector_store = MagicMock()
    mock_vector_store.insert.return_value = None
    mock_vector_factory.return_value = mock_vector_store

    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import AsyncMemory
    memory = AsyncMemory(MemoryConfig())

    data = "I love hiking in the mountains"
    embeddings = {data: [0.1, 0.2, 0.3]}
    metadata = {"user_id": "test_user"}

    await memory._create_memory(data, embeddings, metadata)

    # Check that text_lemmatized was stored in the payload
    insert_call = mock_vector_store.insert.call_args
    payload = insert_call.kwargs.get("payloads") or insert_call[1].get("payloads")
    assert payload is not None and len(payload) == 1
    assert "text_lemmatized" in payload[0], (
        "AsyncMemory._create_memory must store text_lemmatized for BM25 keyword search"
    )
    assert payload[0]["text_lemmatized"] != "", "text_lemmatized must not be empty"

