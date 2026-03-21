import json
import threading
from copy import deepcopy
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
    memories = memory_client.get_all(user_id="test_user")
    assert data1 in memories
    assert data2 in memories


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_add_runs_vector_store_on_caller_thread_when_graph_disabled(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    config = MemoryConfig()
    memory = MemoryClass(config)
    memory.enable_graph = False

    caller_thread_id = threading.get_ident()

    def thread_bound_add(*_args, **_kwargs):
        assert threading.get_ident() == caller_thread_id, "_add_to_vector_store ran on a worker thread"
        return []

    memory._add_to_vector_store = MagicMock(side_effect=thread_bound_add)
    memory._add_to_graph = MagicMock(return_value=[])

    result = memory.add(messages=[{"role": "user", "content": "hello"}], user_id="test-user", infer=False)

    assert result == {"results": []}
    memory._add_to_vector_store.assert_called_once()
    memory._add_to_graph.assert_not_called()


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_get_all_runs_vector_store_on_caller_thread_when_graph_disabled(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    config = MemoryConfig()
    memory = MemoryClass(config)
    memory.enable_graph = False

    caller_thread_id = threading.get_ident()

    def thread_bound_get_all(*_args, **_kwargs):
        assert threading.get_ident() == caller_thread_id, "_get_all_from_vector_store ran on a worker thread"
        return []

    memory._get_all_from_vector_store = MagicMock(side_effect=thread_bound_get_all)

    result = memory.get_all(user_id="test-user", limit=10)

    assert result == {"results": []}
    memory._get_all_from_vector_store.assert_called_once()


@patch('mem0.utils.factory.EmbedderFactory.create')
@patch('mem0.utils.factory.VectorStoreFactory.create')
@patch('mem0.utils.factory.LlmFactory.create')
@patch('mem0.memory.storage.SQLiteManager')
def test_search_runs_vector_store_on_caller_thread_when_graph_disabled(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass
    config = MemoryConfig()
    memory = MemoryClass(config)
    memory.enable_graph = False
    memory.reranker = None

    caller_thread_id = threading.get_ident()

    def thread_bound_search(*_args, **_kwargs):
        assert threading.get_ident() == caller_thread_id, "_search_vector_store ran on a worker thread"
        return []

    memory._search_vector_store = MagicMock(side_effect=thread_bound_search)

    result = memory.search(query="hello", user_id="test-user", limit=5)

    assert result == {"results": []}
    memory._search_vector_store.assert_called_once()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_add_runs_vector_store_on_caller_thread_for_graph_enabled_local_qdrant(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    config = MemoryConfig()
    memory = MemoryClass(config)
    memory.enable_graph = True
    memory.config.vector_store.provider = "qdrant"
    memory.vector_store.is_local = True

    caller_thread_id = threading.get_ident()

    def thread_bound_add(*_args, **_kwargs):
        assert threading.get_ident() == caller_thread_id, "_add_to_vector_store ran on a worker thread"
        return []

    memory._add_to_vector_store = MagicMock(side_effect=thread_bound_add)
    memory._add_to_graph = MagicMock(return_value=[])

    result = memory.add(messages=[{"role": "user", "content": "hello"}], user_id="test-user", infer=False)

    assert result == {"results": [], "relations": []}
    memory._add_to_vector_store.assert_called_once()
    memory._add_to_graph.assert_called_once()
    memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_get_all_runs_vector_store_on_caller_thread_for_graph_enabled_local_qdrant(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    config = MemoryConfig()
    memory = MemoryClass(config)
    memory.enable_graph = True
    memory.config.vector_store.provider = "qdrant"
    memory.vector_store.is_local = True
    memory.graph = MagicMock()
    memory.graph.get_all = MagicMock(return_value=[])

    caller_thread_id = threading.get_ident()

    def thread_bound_get_all(*_args, **_kwargs):
        assert threading.get_ident() == caller_thread_id, "_get_all_from_vector_store ran on a worker thread"
        return []

    memory._get_all_from_vector_store = MagicMock(side_effect=thread_bound_get_all)

    result = memory.get_all(user_id="test-user", limit=10)

    assert result == {"results": [], "relations": []}
    memory._get_all_from_vector_store.assert_called_once()
    memory.graph.get_all.assert_called_once()
    memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_search_runs_vector_store_on_caller_thread_for_graph_enabled_local_qdrant(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    config = MemoryConfig()
    memory = MemoryClass(config)
    memory.enable_graph = True
    memory.config.vector_store.provider = "qdrant"
    memory.vector_store.is_local = True
    memory.reranker = None
    memory.graph = MagicMock()
    memory.graph.search = MagicMock(return_value=[])

    caller_thread_id = threading.get_ident()

    def thread_bound_search(*_args, **_kwargs):
        assert threading.get_ident() == caller_thread_id, "_search_vector_store ran on a worker thread"
        return []

    memory._search_vector_store = MagicMock(side_effect=thread_bound_search)

    result = memory.search(query="hello", user_id="test-user", limit=5)

    assert result == {"results": [], "relations": []}
    memory._search_vector_store.assert_called_once()
    memory.graph.search.assert_called_once()
    memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_search_falls_back_to_caller_thread_when_qdrant_local_status_unknown(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory, caplog
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    class DummyVectorStore:
        pass

    config = MemoryConfig()
    memory = MemoryClass(config)
    memory.enable_graph = True
    memory.config.vector_store.provider = "qdrant"
    memory.vector_store = DummyVectorStore()
    memory.reranker = None
    memory.graph = MagicMock()
    memory.graph.search = MagicMock(return_value=[])

    caller_thread_id = threading.get_ident()

    def thread_bound_search(*_args, **_kwargs):
        assert threading.get_ident() == caller_thread_id, "_search_vector_store ran on a worker thread"
        return []

    memory._search_vector_store = MagicMock(side_effect=thread_bound_search)

    with caplog.at_level("WARNING", logger="mem0.memory.main"):
        result = memory.search(query="hello", user_id="test-user", limit=5)

    assert result == {"results": [], "relations": []}
    assert any("local status is unavailable" in record.message for record in caplog.records)
    memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_add_uses_distinct_filter_dicts_for_vector_and_graph(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    config = MemoryConfig()
    memory = MemoryClass(config)
    memory.enable_graph = True
    memory.config.vector_store.provider = "qdrant"
    memory.vector_store.is_local = True

    nested_filters = {"user_id": "test-user", "nested": {"topics": ["python"]}}
    seen = {}
    marker_set = threading.Event()

    def vector_side_effect(_messages, _metadata, filters, _infer):
        seen["vector_filter_id"] = id(filters)
        filters["nested"]["topics"].append("vector")
        marker_set.set()
        return []

    def graph_side_effect(_messages, filters):
        marker_set.wait(timeout=1)
        seen["graph_filter_id"] = id(filters)
        seen["graph_nested_topics"] = filters["nested"]["topics"]
        return []

    memory._add_to_vector_store = MagicMock(side_effect=vector_side_effect)
    memory._add_to_graph = MagicMock(side_effect=graph_side_effect)

    with patch(
        "mem0.memory.main._build_filters_and_metadata",
        return_value=({"user_id": "test-user"}, deepcopy(nested_filters)),
    ):
        result = memory.add(messages=[{"role": "user", "content": "hello"}], user_id="test-user", infer=False)

    assert result == {"results": [], "relations": []}
    assert seen["vector_filter_id"] != seen["graph_filter_id"]
    assert seen["graph_nested_topics"] == ["python"]
    memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_get_all_uses_distinct_filter_dicts_for_vector_and_graph(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    config = MemoryConfig()
    memory = MemoryClass(config)
    memory.enable_graph = True
    memory.config.vector_store.provider = "qdrant"
    memory.vector_store.is_local = True
    memory.graph = MagicMock()

    nested_filters = {"user_id": "test-user", "nested": {"topics": ["python"]}}
    seen = {}
    marker_set = threading.Event()

    def vector_side_effect(filters, _limit):
        seen["vector_filter_id"] = id(filters)
        filters["nested"]["topics"].append("vector")
        marker_set.set()
        return []

    def graph_side_effect(filters, _limit):
        marker_set.wait(timeout=1)
        seen["graph_filter_id"] = id(filters)
        seen["graph_nested_topics"] = filters["nested"]["topics"]
        return []

    memory._get_all_from_vector_store = MagicMock(side_effect=vector_side_effect)
    memory.graph.get_all = MagicMock(side_effect=graph_side_effect)

    with patch(
        "mem0.memory.main._build_filters_and_metadata",
        return_value=({}, deepcopy(nested_filters)),
    ):
        result = memory.get_all(user_id="test-user", limit=10)

    assert result == {"results": [], "relations": []}
    assert seen["vector_filter_id"] != seen["graph_filter_id"]
    assert seen["graph_nested_topics"] == ["python"]
    memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_search_uses_distinct_filter_dicts_for_vector_and_graph(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    config = MemoryConfig()
    memory = MemoryClass(config)
    memory.enable_graph = True
    memory.config.vector_store.provider = "qdrant"
    memory.vector_store.is_local = True
    memory.reranker = None
    memory.graph = MagicMock()

    nested_filters = {"user_id": "test-user", "nested": {"topics": ["python"]}}
    seen = {}
    marker_set = threading.Event()

    def vector_side_effect(_query, filters, _limit, _threshold):
        seen["vector_filter_id"] = id(filters)
        filters["nested"]["topics"].append("vector")
        marker_set.set()
        return []

    def graph_side_effect(_query, filters, _limit):
        marker_set.wait(timeout=1)
        seen["graph_filter_id"] = id(filters)
        seen["graph_nested_topics"] = filters["nested"]["topics"]
        return []

    memory._search_vector_store = MagicMock(side_effect=vector_side_effect)
    memory.graph.search = MagicMock(side_effect=graph_side_effect)

    with patch(
        "mem0.memory.main._build_filters_and_metadata",
        return_value=({}, deepcopy(nested_filters)),
    ):
        result = memory.search(query="hello", user_id="test-user", limit=5)

    assert result == {"results": [], "relations": []}
    assert seen["vector_filter_id"] != seen["graph_filter_id"]
    assert seen["graph_nested_topics"] == ["python"]
    memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_sync_executor_is_reused_across_repeated_sync_calls(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    config = MemoryConfig()
    memory = MemoryClass(config)
    memory.enable_graph = True
    memory.config.vector_store.provider = "chroma"
    memory.reranker = None
    memory.graph = MagicMock()
    memory.graph.search = MagicMock(return_value=[])
    memory._search_vector_store = MagicMock(return_value=[])

    memory.search(query="hello", user_id="test-user", limit=5)
    first_executor = memory._sync_executor

    memory.search(query="hello", user_id="test-user", limit=5)

    assert first_executor is not None
    assert memory._sync_executor is first_executor
    memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_reset_shuts_down_sync_executor_and_clears_cached_instance(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    config = MemoryConfig()
    memory = MemoryClass(config)
    fake_executor = MagicMock()
    memory._sync_executor = fake_executor

    memory.reset()

    fake_executor.shutdown.assert_called_once_with(wait=True)
    assert memory._sync_executor is None


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_add_runs_vector_store_on_worker_thread_for_graph_enabled_remote_qdrant(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    config = MemoryConfig()
    memory = MemoryClass(config)
    memory.enable_graph = True
    memory.config.vector_store.provider = "qdrant"
    memory.vector_store.is_local = False

    caller_thread_id = threading.get_ident()
    seen = {}

    def vector_side_effect(*_args, **_kwargs):
        seen["vector_thread_id"] = threading.get_ident()
        return []

    memory._add_to_vector_store = MagicMock(side_effect=vector_side_effect)
    memory._add_to_graph = MagicMock(return_value=[])

    result = memory.add(messages=[{"role": "user", "content": "hello"}], user_id="test-user", infer=False)

    assert result == {"results": [], "relations": []}
    assert seen["vector_thread_id"] != caller_thread_id
    memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_search_runs_vector_store_on_worker_thread_for_graph_enabled_non_qdrant_without_warning(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory, caplog
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    class DummyVectorStore:
        pass

    config = MemoryConfig()
    memory = MemoryClass(config)
    memory.enable_graph = True
    memory.config.vector_store.provider = "chroma"
    memory.vector_store = DummyVectorStore()
    memory.reranker = None
    memory.graph = MagicMock()
    memory.graph.search = MagicMock(return_value=[])

    caller_thread_id = threading.get_ident()
    seen = {}

    def thread_bound_search(*_args, **_kwargs):
        seen["vector_thread_id"] = threading.get_ident()
        return []

    memory._search_vector_store = MagicMock(side_effect=thread_bound_search)

    with caplog.at_level("WARNING", logger="mem0.memory.main"):
        result = memory.search(query="hello", user_id="test-user", limit=5)

    assert result == {"results": [], "relations": []}
    assert seen["vector_thread_id"] != caller_thread_id
    assert not any("local status is unavailable" in record.message for record in caplog.records)
    memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_get_sync_executor_lazy_singleton_per_instance(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    memory = MemoryClass(MemoryConfig())
    assert memory._sync_executor is None

    executor1 = memory._get_sync_executor()
    executor2 = memory._get_sync_executor()

    assert executor1 is executor2
    memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_shutdown_sync_executor_is_idempotent(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    memory = MemoryClass(MemoryConfig())
    fake_executor = MagicMock()
    memory._sync_executor = fake_executor

    memory._shutdown_sync_executor()
    memory._shutdown_sync_executor()

    fake_executor.shutdown.assert_called_once_with(wait=True)
    assert memory._sync_executor is None


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_reset_with_no_cached_executor_is_noop_for_shutdown(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    memory = MemoryClass(MemoryConfig())
    memory._sync_executor = None

    memory.reset()

    assert memory._sync_executor is None


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_del_swallows_sync_executor_shutdown_errors(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    memory = MemoryClass(MemoryConfig())
    memory._shutdown_sync_executor = MagicMock(side_effect=RuntimeError("boom"))

    memory.__del__()

    memory._shutdown_sync_executor.assert_called_once()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_add_nested_filters_are_isolated_for_non_qdrant_parallel_branch(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    nested_filters = {"user_id": "test-user", "nested": {"topics": ["python"]}}
    memory = MemoryClass(MemoryConfig())
    memory.enable_graph = True
    memory.config.vector_store.provider = "chroma"

    seen = {}
    marker_set = threading.Event()

    def vector_side_effect(_messages, _metadata, filters, _infer):
        seen["vector_filter_id"] = id(filters)
        filters["nested"]["topics"].append("vector")
        marker_set.set()
        return []

    def graph_side_effect(_messages, filters):
        marker_set.wait(timeout=1)
        seen["graph_filter_id"] = id(filters)
        seen["graph_nested_topics"] = filters["nested"]["topics"]
        return []

    memory._add_to_vector_store = MagicMock(side_effect=vector_side_effect)
    memory._add_to_graph = MagicMock(side_effect=graph_side_effect)

    with patch(
        "mem0.memory.main._build_filters_and_metadata",
        return_value=({"user_id": "test-user"}, deepcopy(nested_filters)),
    ):
        result = memory.add(messages=[{"role": "user", "content": "hello"}], user_id="test-user", infer=False)

    assert result == {"results": [], "relations": []}
    assert seen["vector_filter_id"] != seen["graph_filter_id"]
    assert seen["graph_nested_topics"] == ["python"]
    memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_get_all_nested_filters_are_isolated_for_non_qdrant_parallel_branch(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    nested_filters = {"user_id": "test-user", "nested": {"topics": ["python"]}}
    memory = MemoryClass(MemoryConfig())
    memory.enable_graph = True
    memory.config.vector_store.provider = "chroma"
    memory.graph = MagicMock()

    seen = {}
    marker_set = threading.Event()

    def vector_side_effect(filters, _limit):
        seen["vector_filter_id"] = id(filters)
        filters["nested"]["topics"].append("vector")
        marker_set.set()
        return []

    def graph_side_effect(filters, _limit):
        marker_set.wait(timeout=1)
        seen["graph_filter_id"] = id(filters)
        seen["graph_nested_topics"] = filters["nested"]["topics"]
        return []

    memory._get_all_from_vector_store = MagicMock(side_effect=vector_side_effect)
    memory.graph.get_all = MagicMock(side_effect=graph_side_effect)

    with patch(
        "mem0.memory.main._build_filters_and_metadata",
        return_value=({}, deepcopy(nested_filters)),
    ):
        result = memory.get_all(user_id="test-user", limit=10)

    assert result == {"results": [], "relations": []}
    assert seen["vector_filter_id"] != seen["graph_filter_id"]
    assert seen["graph_nested_topics"] == ["python"]
    memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_search_nested_filters_are_isolated_for_non_qdrant_parallel_branch(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    nested_filters = {"user_id": "test-user", "nested": {"topics": ["python"]}}
    memory = MemoryClass(MemoryConfig())
    memory.enable_graph = True
    memory.config.vector_store.provider = "chroma"
    memory.reranker = None
    memory.graph = MagicMock()

    seen = {}
    marker_set = threading.Event()

    def vector_side_effect(_query, filters, _limit, _threshold):
        seen["vector_filter_id"] = id(filters)
        filters["nested"]["topics"].append("vector")
        marker_set.set()
        return []

    def graph_side_effect(_query, filters, _limit):
        marker_set.wait(timeout=1)
        seen["graph_filter_id"] = id(filters)
        seen["graph_nested_topics"] = filters["nested"]["topics"]
        return []

    memory._search_vector_store = MagicMock(side_effect=vector_side_effect)
    memory.graph.search = MagicMock(side_effect=graph_side_effect)

    with patch(
        "mem0.memory.main._build_filters_and_metadata",
        return_value=({}, deepcopy(nested_filters)),
    ):
        result = memory.search(query="hello", user_id="test-user", limit=5)

    assert result == {"results": [], "relations": []}
    assert seen["vector_filter_id"] != seen["graph_filter_id"]
    assert seen["graph_nested_topics"] == ["python"]
    memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_run_sync_vector_and_graph_raises_when_vector_callable_fails(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    memory = MemoryClass(MemoryConfig())
    memory.enable_graph = True
    memory.config.vector_store.provider = "chroma"

    def vector_fail():
        raise RuntimeError("vector failed")

    def graph_ok():
        return []

    try:
        with pytest.raises(RuntimeError, match="vector failed"):
            memory._run_sync_vector_and_graph(vector_fail, graph_ok)
    finally:
        memory._shutdown_sync_executor()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_run_sync_vector_and_graph_raises_when_graph_callable_fails(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    memory = MemoryClass(MemoryConfig())
    memory.enable_graph = True
    memory.config.vector_store.provider = "chroma"

    def vector_ok():
        return []

    def graph_fail():
        raise RuntimeError("graph failed")

    try:
        with pytest.raises(RuntimeError, match="graph failed"):
            memory._run_sync_vector_and_graph(vector_ok, graph_fail)
    finally:
        memory._shutdown_sync_executor()


@pytest.mark.parametrize("iteration", range(50))
@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_repeatability_parallel_search_branch(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory, iteration
):
    del iteration
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_factory.return_value = MagicMock()
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory as MemoryClass

    memory = MemoryClass(MemoryConfig())
    memory.enable_graph = True
    memory.config.vector_store.provider = "chroma"
    memory.reranker = None
    memory.graph = MagicMock()
    memory.graph.search = MagicMock(return_value=[])
    memory._search_vector_store = MagicMock(return_value=[])

    result = memory.search(query="hello", user_id="test-user", limit=5)

    assert result == {"results": [], "relations": []}
    memory._shutdown_sync_executor()


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
