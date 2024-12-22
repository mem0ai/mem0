import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.base import MemoryConfig
from mem0.memory.main import Memory
from mem0.utils.factory import VectorStoreFactory


@pytest.fixture(autouse=True)
def mock_openai():
    os.environ["OPENAI_API_KEY"] = "123"
    with patch("openai.OpenAI") as mock:
        mock.return_value = Mock()
        yield mock


@pytest.fixture
def memory_instance():
    with patch("mem0.utils.factory.EmbedderFactory") as mock_embedder, patch(
        "mem0.utils.factory.VectorStoreFactory"
    ) as mock_vector_store, patch("mem0.utils.factory.LlmFactory") as mock_llm, patch(
        "mem0.memory.telemetry.capture_event"
    ), patch("mem0.memory.graph_memory.MemoryGraph"):
        mock_embedder.create.return_value = Mock()
        mock_vector_store.create.return_value = Mock()
        mock_llm.create.return_value = Mock()

        config = MemoryConfig(version="v1.1")
        config.graph_store.config = {"some_config": "value"}
        return Memory(config)


@pytest.mark.parametrize("version, enable_graph", [("v1.0", False), ("v1.1", True)])
def test_add(memory_instance, version, enable_graph):
    memory_instance.config.version = version
    memory_instance.enable_graph = enable_graph
    memory_instance._add_to_vector_store = Mock(return_value=[{"memory": "Test memory", "event": "ADD"}])
    memory_instance._add_to_graph = Mock(return_value=[])

    result = memory_instance.add(messages=[{"role": "user", "content": "Test message"}], user_id="test_user")

    assert "results" in result
    assert result["results"] == [{"memory": "Test memory", "event": "ADD"}]
    assert "relations" in result
    assert result["relations"] == []

    memory_instance._add_to_vector_store.assert_called_once_with(
        [{"role": "user", "content": "Test message"}], {"user_id": "test_user"}, {"user_id": "test_user"}, True
    )

    # Remove the conditional assertion for _add_to_graph
    memory_instance._add_to_graph.assert_called_once_with(
        [{"role": "user", "content": "Test message"}], {"user_id": "test_user"}
    )

@pytest.mark.parametrize("version, enable_graph, infer", [
    ("v1.0", False, False), 
    ("v1.1", True, True), 
    ("v1.1", True, False)
])
def test_add_with_inference(memory_instance, version, enable_graph, infer):
    memory_instance.config.version = version
    memory_instance.enable_graph = enable_graph
    
    # Setup mocks
    memory_instance.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
    memory_instance.vector_store.insert = Mock()
    memory_instance.vector_store.search = Mock(return_value=[])
    memory_instance.db.add_history = Mock()
    memory_instance._add_to_graph = Mock(return_value=[])
    
    # Mock LLM responses for inference case
    if infer:
        memory_instance.llm.generate_response = Mock(side_effect=[
            '{"facts": ["Test fact 1", "Test fact 2"]}',  # First call for fact retrieval
            '{"memory": [{"event": "ADD", "text": "Test fact 1"},{"event": "ADD", "text": "Test fact 2"}]}'  # Second call for memory actions
        ])
    else:
        memory_instance.llm.generate_response = Mock()
    
    # Execute
    result = memory_instance.add(
        messages=[{"role": "user", "content": "Test fact 1 Text fact 2"}], 
        user_id="test_user", 
        infer=infer
    )

    # Verify basic structure of result
    assert "results" in result
    assert "relations" in result
    assert isinstance(result["results"], list)
    assert isinstance(result["relations"], list)

    # Verify LLM behavior
    if infer:
        # Should be called twice: once for fact retrieval, once for memory actions
        assert memory_instance.llm.generate_response.call_count == 2
        
        # Verify first call (fact retrieval)
        first_call = memory_instance.llm.generate_response.call_args_list[0]
        assert len(first_call[1]['messages']) == 2
        assert first_call[1]['messages'][0]['role'] == 'system'
        assert first_call[1]['messages'][1]['role'] == 'user'
        
        # Verify embedding was called for the facts
        assert memory_instance.embedding_model.embed.call_count == 2
        
        # Verify vector store operations
        assert memory_instance.vector_store.insert.call_count == 2
    else:
        # For non-inference case, should directly create memory without LLM
        memory_instance.llm.generate_response.assert_not_called()
        # Should still embed the original message
        memory_instance.embedding_model.embed.assert_called_once_with("user: Test fact 1 Text fact 2\n")
        memory_instance.vector_store.insert.assert_called_once()

    # Verify graph behavior
    memory_instance._add_to_graph.assert_called_once_with(
        [{"role": "user", "content": "Test fact 1 Text fact 2"}], {"user_id": "test_user"}
    )

    if version == "v1.1":
        assert isinstance(result, dict)
        assert "results" in result
        assert "relations" in result
    else:
        assert isinstance(result["results"], list)


def test_get(memory_instance):
    mock_memory = Mock(
        id="test_id",
        payload={
            "data": "Test memory",
            "user_id": "test_user",
            "hash": "test_hash",
            "created_at": "2023-01-01T00:00:00",
            "updated_at": "2023-01-02T00:00:00",
            "extra_field": "extra_value",
        },
    )
    memory_instance.vector_store.get = Mock(return_value=mock_memory)

    result = memory_instance.get("test_id")

    assert result["id"] == "test_id"
    assert result["memory"] == "Test memory"
    assert result["user_id"] == "test_user"
    assert result["hash"] == "test_hash"
    assert result["created_at"] == "2023-01-01T00:00:00"
    assert result["updated_at"] == "2023-01-02T00:00:00"
    assert result["metadata"] == {"extra_field": "extra_value"}


@pytest.mark.parametrize("version, enable_graph", [("v1.0", False), ("v1.1", True)])
def test_search(memory_instance, version, enable_graph):
    memory_instance.config.version = version
    memory_instance.enable_graph = enable_graph
    mock_memories = [
        Mock(id="1", payload={"data": "Memory 1", "user_id": "test_user"}, score=0.9),
        Mock(id="2", payload={"data": "Memory 2", "user_id": "test_user"}, score=0.8),
    ]
    memory_instance.vector_store.search = Mock(return_value=mock_memories)
    memory_instance.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])
    memory_instance.graph.search = Mock(return_value=[{"relation": "test_relation"}])

    result = memory_instance.search("test query", user_id="test_user")

    if version == "v1.1":
        assert "results" in result
        assert len(result["results"]) == 2
        assert result["results"][0]["id"] == "1"
        assert result["results"][0]["memory"] == "Memory 1"
        assert result["results"][0]["user_id"] == "test_user"
        assert result["results"][0]["score"] == 0.9
        if enable_graph:
            assert "relations" in result
            assert result["relations"] == [{"relation": "test_relation"}]
        else:
            assert "relations" not in result
    else:
        assert isinstance(result, dict)
        assert "results" in result
        assert len(result["results"]) == 2
        assert result["results"][0]["id"] == "1"
        assert result["results"][0]["memory"] == "Memory 1"
        assert result["results"][0]["user_id"] == "test_user"
        assert result["results"][0]["score"] == 0.9

    memory_instance.vector_store.search.assert_called_once_with(
        query=[0.1, 0.2, 0.3], limit=100, filters={"user_id": "test_user"}
    )
    memory_instance.embedding_model.embed.assert_called_once_with("test query")

    if enable_graph:
        memory_instance.graph.search.assert_called_once_with("test query", {"user_id": "test_user"}, 100)
    else:
        memory_instance.graph.search.assert_not_called()


def test_update(memory_instance):
    memory_instance.embedding_model = Mock()
    memory_instance.embedding_model.embed = Mock(return_value=[0.1, 0.2, 0.3])

    memory_instance._update_memory = Mock()

    result = memory_instance.update("test_id", "Updated memory")

    memory_instance._update_memory.assert_called_once_with(
        "test_id", "Updated memory", {"Updated memory": [0.1, 0.2, 0.3]}
    )

    assert result["message"] == "Memory updated successfully!"


def test_delete(memory_instance):
    memory_instance._delete_memory = Mock()

    result = memory_instance.delete("test_id")

    memory_instance._delete_memory.assert_called_once_with("test_id")
    assert result["message"] == "Memory deleted successfully!"


@pytest.mark.parametrize("version, enable_graph", [("v1.0", False), ("v1.1", True)])
def test_delete_all(memory_instance, version, enable_graph):
    memory_instance.config.version = version
    memory_instance.enable_graph = enable_graph
    mock_memories = [Mock(id="1"), Mock(id="2")]
    memory_instance.vector_store.list = Mock(return_value=(mock_memories, None))
    memory_instance._delete_memory = Mock()
    memory_instance.graph.delete_all = Mock()

    result = memory_instance.delete_all(user_id="test_user")

    assert memory_instance._delete_memory.call_count == 2

    if enable_graph:
        memory_instance.graph.delete_all.assert_called_once_with({"user_id": "test_user"})
    else:
        memory_instance.graph.delete_all.assert_not_called()

    assert result["message"] == "Memories deleted successfully!"


def test_reset(memory_instance):
    memory_instance.vector_store.delete_col = Mock()
    # persisting vector store to make sure previous collection is deleted
    initial_vector_store = memory_instance.vector_store
    memory_instance.db.reset = Mock()

    with patch.object(VectorStoreFactory, "create", return_value=Mock()) as mock_create:
        memory_instance.reset()

        initial_vector_store.delete_col.assert_called_once()
        memory_instance.db.reset.assert_called_once()
        mock_create.assert_called_once_with(
            memory_instance.config.vector_store.provider, memory_instance.config.vector_store.config
        )


@pytest.mark.parametrize(
    "version, enable_graph, expected_result",
    [
        ("v1.0", False, {"results": [{"id": "1", "memory": "Memory 1", "user_id": "test_user"}]}),
        ("v1.1", False, {"results": [{"id": "1", "memory": "Memory 1", "user_id": "test_user"}]}),
        (
            "v1.1",
            True,
            {
                "results": [{"id": "1", "memory": "Memory 1", "user_id": "test_user"}],
                "relations": [{"source": "entity1", "relationship": "rel", "target": "entity2"}],
            },
        ),
    ],
)
def test_get_all(memory_instance, version, enable_graph, expected_result):
    memory_instance.config.version = version
    memory_instance.enable_graph = enable_graph
    mock_memories = [Mock(id="1", payload={"data": "Memory 1", "user_id": "test_user"})]
    memory_instance.vector_store.list = Mock(return_value=(mock_memories, None))
    memory_instance.graph.get_all = Mock(
        return_value=[{"source": "entity1", "relationship": "rel", "target": "entity2"}]
    )

    result = memory_instance.get_all(user_id="test_user")

    assert isinstance(result, dict)
    assert "results" in result
    assert len(result["results"]) == len(expected_result["results"])
    for expected_item, result_item in zip(expected_result["results"], result["results"]):
        assert all(key in result_item for key in expected_item)
        assert result_item["id"] == expected_item["id"]
        assert result_item["memory"] == expected_item["memory"]
        assert result_item["user_id"] == expected_item["user_id"]

    if enable_graph:
        assert "relations" in result
        assert result["relations"] == expected_result["relations"]
    else:
        assert "relations" not in result

    memory_instance.vector_store.list.assert_called_once_with(filters={"user_id": "test_user"}, limit=100)

    if enable_graph:
        memory_instance.graph.get_all.assert_called_once_with({"user_id": "test_user"}, 100)
    else:
        memory_instance.graph.get_all.assert_not_called()
