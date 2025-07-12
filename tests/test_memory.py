import pytest
from unittest.mock import patch, MagicMock

from mem0 import Memory
from mem0.configs.base import MemoryConfig


@pytest.fixture
def memory_store():
    return Memory()


@pytest.mark.skip(reason="Not implemented")
def test_create_memory(memory_store):
    data = "Name is John Doe."
    memory_id = memory_store.create(data=data)
    assert memory_store.get(memory_id) == data


@pytest.mark.skip(reason="Not implemented")
def test_get_memory(memory_store):
    data = "Name is John Doe."
    memory_id = memory_store.create(data=data)
    retrieved_data = memory_store.get(memory_id)
    assert retrieved_data == data


@pytest.mark.skip(reason="Not implemented")
def test_update_memory(memory_store):
    data = "Name is John Doe."
    memory_id = memory_store.create(data=data)
    new_data = "Name is John Kapoor."
    updated_memory = memory_store.update(memory_id, new_data)
    assert updated_memory == new_data
    assert memory_store.get(memory_id) == new_data


@pytest.mark.skip(reason="Not implemented")
def test_delete_memory(memory_store):
    data = "Name is John Doe."
    memory_id = memory_store.create(data=data)
    memory_store.delete(memory_id)
    assert memory_store.get(memory_id) is None


@pytest.mark.skip(reason="Not implemented")
def test_history(memory_store):
    data = "I like Indian food."
    memory_id = memory_store.create(data=data)
    history = memory_store.history(memory_id)
    assert history == [data]
    assert memory_store.get(memory_id) == data

    new_data = "I like Italian food."
    memory_store.update(memory_id, new_data)
    history = memory_store.history(memory_id)
    assert history == [data, new_data]
    assert memory_store.get(memory_id) == new_data


@pytest.mark.skip(reason="Not implemented")
def test_list_memories(memory_store):
    data1 = "Name is John Doe."
    data2 = "Name is John Doe. I like to code in Python."
    memory_store.create(data=data1)
    memory_store.create(data=data2)
    memories = memory_store.list()
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
