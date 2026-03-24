from unittest.mock import MagicMock, patch

from mem0.configs.base import MemoryConfig
from mem0.memory.main import Memory


class MockVectorMemory:
    def __init__(self, memory_id: str):
        self.id = memory_id
        self.payload = {"data": f"memory-{memory_id}"}


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.memory.main.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_delete_all_handles_flat_list_from_vector_store(
    mock_sqlite,
    mock_llm_factory,
    mock_vector_factory,
    mock_embedder_factory,
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    config = MemoryConfig()
    memory = Memory(config)
    memory.enable_graph = False
    memory._delete_memory = MagicMock()

    mock_vector_store.list.return_value = [MockVectorMemory("1"), MockVectorMemory("2")]

    result = memory.delete_all(user_id="user-1")

    assert result == {"message": "Memories deleted successfully!"}
    assert memory._delete_memory.call_count == 2
    memory._delete_memory.assert_any_call("1")
    memory._delete_memory.assert_any_call("2")


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.memory.main.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_delete_all_handles_tuple_from_vector_store(
    mock_sqlite,
    mock_llm_factory,
    mock_vector_factory,
    mock_embedder_factory,
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    config = MemoryConfig()
    memory = Memory(config)
    memory.enable_graph = False
    memory._delete_memory = MagicMock()

    mock_vector_store.list.return_value = ([MockVectorMemory("1"), MockVectorMemory("2")], 2)

    result = memory.delete_all(user_id="user-1")

    assert result == {"message": "Memories deleted successfully!"}
    assert memory._delete_memory.call_count == 2
    memory._delete_memory.assert_any_call("1")
    memory._delete_memory.assert_any_call("2")
