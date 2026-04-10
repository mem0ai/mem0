import json
from unittest.mock import MagicMock, patch

import pytest

from mem0 import Memory
from mem0.configs.base import MemoryConfig


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
    memories = memory_client.get_all(user_id="test_user")
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
    
    assert len(result) == 2
    memories_by_id = {mem["id"]: mem for mem in result}

    assert memories_by_id["mem_1"]["memory"] == ""
    assert memories_by_id["mem_2"]["memory"] == "content"


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


@patch("mem0.memory.main.capture_event", MagicMock())
@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_reconciliation_cache_refreshes_after_update_before_none_same_batch(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """
    Regression: id_to_mem_map must reflect post-UPDATE state before a later NONE
    (session metadata refresh) for the same memory id in one reconciliation pass.
    Otherwise NONE deep-copies a stale payload and can revert content from the UPDATE.
    """
    mock_embedder_factory.return_value = MagicMock()
    mock_embedder_factory.return_value.embed.return_value = [0.1, 0.2, 0.3]
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm = MagicMock()
    mock_llm_factory.return_value = mock_llm
    mock_sqlite.return_value = MagicMock()

    mem_id = "mem-same-batch"
    stored_payload = {
        "data": "stale before update",
        "user_id": "u1",
        "agent_id": "agent_before",
        "run_id": "run_before",
        "created_at": "2020-01-01T00:00:00",
    }

    def search_impl(*args, **kwargs):
        return [MockVectorMemory(mem_id, dict(stored_payload))]

    def get_impl(vector_id=None, **kwargs):
        vid = vector_id if vector_id is not None else kwargs.get("vector_id")
        if vid == mem_id:
            return MockVectorMemory(mem_id, dict(stored_payload))
        return None

    def update_impl(vector_id=None, vector=None, payload=None, **kwargs):
        if payload is not None:
            stored_payload.clear()
            stored_payload.update(payload)

    mock_vector_store.search.side_effect = search_impl
    mock_vector_store.get.side_effect = get_impl
    mock_vector_store.update.side_effect = update_impl

    call_count = {"n": 0}

    def llm_side_effect(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return json.dumps({"facts": ["user likes pizza"]})
        return json.dumps(
            {
                "memory": [
                    {
                        "id": "0",
                        "text": "updated by reconciliation",
                        "event": "UPDATE",
                        "old_memory": "stale before update",
                    },
                    {
                        "id": "0",
                        "text": "updated by reconciliation",
                        "event": "NONE",
                    },
                ]
            }
        )

    mock_llm.generate_response.side_effect = llm_side_effect

    from mem0.memory.main import Memory as MemoryClass

    config = MemoryConfig()
    memory = MemoryClass(config)
    memory.embedding_model = mock_embedder_factory.return_value
    memory.vector_store = mock_vector_store
    memory.llm = mock_llm
    memory.enable_graph = False

    messages = [{"role": "user", "content": "I like pizza"}]
    metadata = {"user_id": "u1", "agent_id": "agent_new", "run_id": "run_new"}
    filters = {"user_id": "u1"}

    memory._add_to_vector_store(messages, metadata, filters, infer=True)

    assert stored_payload["data"] == "updated by reconciliation"
    assert stored_payload["agent_id"] == "agent_new"
    assert stored_payload["run_id"] == "run_new"
