import pytest
from unittest.mock import Mock, patch
from mem0.memory.main import Memory
from mem0.configs.base import MemoryConfig

@pytest.fixture(autouse=True)
def mock_openai():
    with patch('openai.OpenAI') as mock:
        mock.return_value = Mock()
        yield mock


@pytest.fixture
def memory_instance():
    with patch('mem0.utils.factory.EmbedderFactory') as mock_embedder, \
         patch('mem0.utils.factory.VectorStoreFactory') as mock_vector_store, \
         patch('mem0.utils.factory.LlmFactory') as mock_llm, \
         patch('mem0.memory.storage.SQLiteManager') as mock_db, \
         patch('mem0.memory.telemetry.capture_event'):
        mock_embedder.create.return_value = Mock()
        mock_vector_store.create.return_value = Mock()
        mock_llm.create.return_value = Mock()
        
        return Memory(MemoryConfig())


def test_add(memory_instance):
    memory_instance._add_to_vector_store = Mock(return_value=[{"memory": "Test memory", "event": "ADD"}])
    memory_instance._add_to_graph = Mock(return_value=[])

    result = memory_instance.add(
        messages=[{"role": "user", "content": "Test message"}],
        user_id="test_user"
    )

    assert "message" in result
    assert result["message"] == "ok"

    memory_instance._add_to_vector_store.assert_called_once_with(
        [{"role": "user", "content": "Test message"}],
        {"user_id": "test_user"},
        {"user_id": "test_user"}
    )
    memory_instance._add_to_graph.assert_called_once()


def test_get(memory_instance):
    mock_memory = Mock(id="test_id", payload={"data": "Test memory", "user_id": "test_user"})
    memory_instance.vector_store.get = Mock(return_value=mock_memory)

    result = memory_instance.get("test_id")

    assert result["id"] == "test_id"
    assert result["memory"] == "Test memory"
    assert result["user_id"] == "test_user"


def test_search(memory_instance):
    mock_memories = [
        Mock(id="1", payload={"data": "Memory 1", "user_id": "test_user"}, score=0.9),
        Mock(id="2", payload={"data": "Memory 2", "user_id": "test_user"}, score=0.8)
    ]
    memory_instance.vector_store.search = Mock(return_value=mock_memories)
    memory_instance.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])

    result = memory_instance.search("test query", user_id="test_user")

    assert len(result) == 2
    assert result[0]["id"] == "1"
    assert result[0]["memory"] == "Memory 1"
    assert result[0]["user_id"] == "test_user"
    assert result[0]["score"] == 0.9
    assert result[1]["id"] == "2"
    assert result[1]["memory"] == "Memory 2"
    assert result[1]["user_id"] == "test_user"
    assert result[1]["score"] == 0.8

    memory_instance.vector_store.search.assert_called_once_with(
        query=[0.1, 0.2, 0.3],
        limit=100,
        filters={"user_id": "test_user"}
    )
    memory_instance.embedding_model.embed.assert_called_once_with("test query")


def test_update(memory_instance):
    memory_instance._update_memory = Mock()

    result = memory_instance.update("test_id", "Updated memory")

    memory_instance._update_memory.assert_called_once_with("test_id", "Updated memory")
    assert result["message"] == "Memory updated successfully!"


def test_delete(memory_instance):
    memory_instance._delete_memory = Mock()

    result = memory_instance.delete("test_id")

    memory_instance._delete_memory.assert_called_once_with("test_id")
    assert result["message"] == "Memory deleted successfully!"


def test_delete_all(memory_instance):
    mock_memories = [Mock(id="1"), Mock(id="2")]
    memory_instance.vector_store.list = Mock(return_value=(mock_memories, None))
    memory_instance._delete_memory = Mock()

    result = memory_instance.delete_all(user_id="test_user")

    assert memory_instance._delete_memory.call_count == 2
    assert result["message"] == "Memories deleted successfully!"


def test_reset(memory_instance):
    memory_instance.vector_store.delete_col = Mock()
    memory_instance.db.reset = Mock()

    memory_instance.reset()

    memory_instance.vector_store.delete_col.assert_called_once()
    memory_instance.db.reset.assert_called_once()


if __name__ == "__main__":
    pytest.main()