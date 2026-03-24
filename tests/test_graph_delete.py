"""Tests for graph cleanup on memory deletion (issue #3245)."""

from unittest.mock import MagicMock, patch

import pytest

from mem0.configs.base import MemoryConfig


class MockVectorMemory:
    def __init__(self, memory_id, payload, score=0.8):
        self.id = memory_id
        self.payload = payload
        self.score = score


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_delete_calls_graph_cleanup_when_graph_enabled(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """When graph is enabled, delete() should call graph.delete() with memory text and filters."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory

    config = MemoryConfig()
    memory = Memory(config)

    # Enable graph with a mock
    memory.enable_graph = True
    memory.graph = MagicMock()

    # Set up vector store to return a memory with graph-relevant data
    mock_vector_store.get.return_value = MockVectorMemory(
        "mem-1",
        {
            "data": "Alice likes Bob",
            "user_id": "user-1",
            "agent_id": "agent-1",
            "hash": "abc",
        },
    )

    memory.delete("mem-1")

    # graph.delete should have been called with the memory text and filters
    memory.graph.delete.assert_called_once_with(
        "Alice likes Bob", {"user_id": "user-1", "agent_id": "agent-1"}
    )

    # _delete_memory should still have been called (vector store + history cleanup)
    mock_vector_store.delete.assert_called_once_with(vector_id="mem-1")


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_delete_skips_graph_when_not_enabled(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """When graph is not enabled, delete() should not attempt graph cleanup."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory

    config = MemoryConfig()
    memory = Memory(config)

    assert memory.enable_graph is False

    mock_vector_store.get.return_value = MockVectorMemory(
        "mem-1", {"data": "Alice likes Bob", "user_id": "user-1", "hash": "abc"}
    )

    result = memory.delete("mem-1")

    assert result == {"message": "Memory deleted successfully!"}
    mock_vector_store.delete.assert_called_once_with(vector_id="mem-1")


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_delete_continues_if_graph_cleanup_fails(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """If graph cleanup raises an exception, delete() should still succeed."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory

    config = MemoryConfig()
    memory = Memory(config)

    memory.enable_graph = True
    memory.graph = MagicMock()
    memory.graph.delete.side_effect = RuntimeError("Neo4j connection lost")

    mock_vector_store.get.return_value = MockVectorMemory(
        "mem-1", {"data": "Alice likes Bob", "user_id": "user-1", "hash": "abc"}
    )

    # Should not raise
    result = memory.delete("mem-1")
    assert result == {"message": "Memory deleted successfully!"}

    # Vector store deletion should still proceed
    mock_vector_store.delete.assert_called_once_with(vector_id="mem-1")


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_delete_skips_graph_when_no_user_id(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """Graph cleanup should be skipped if the memory has no user_id."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory

    config = MemoryConfig()
    memory = Memory(config)

    memory.enable_graph = True
    memory.graph = MagicMock()

    # Memory with no user_id
    mock_vector_store.get.return_value = MockVectorMemory(
        "mem-1", {"data": "Some data", "hash": "abc"}
    )

    memory.delete("mem-1")

    # graph.delete should NOT have been called since there's no user_id
    memory.graph.delete.assert_not_called()
    mock_vector_store.delete.assert_called_once_with(vector_id="mem-1")


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_delete_skips_graph_when_no_memory_text(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """Graph cleanup should be skipped if the memory has no text data."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory

    config = MemoryConfig()
    memory = Memory(config)

    memory.enable_graph = True
    memory.graph = MagicMock()

    mock_vector_store.get.return_value = MockVectorMemory(
        "mem-1", {"user_id": "user-1", "hash": "abc"}
    )

    memory.delete("mem-1")

    memory.graph.delete.assert_not_called()
    mock_vector_store.delete.assert_called_once_with(vector_id="mem-1")


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_delete_passes_all_filters_to_graph(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """Graph cleanup should include all available filters (user_id, agent_id, run_id)."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory

    config = MemoryConfig()
    memory = Memory(config)

    memory.enable_graph = True
    memory.graph = MagicMock()

    mock_vector_store.get.return_value = MockVectorMemory(
        "mem-1",
        {
            "data": "Alice likes Bob",
            "user_id": "user-1",
            "agent_id": "agent-1",
            "run_id": "run-1",
            "hash": "abc",
        },
    )

    memory.delete("mem-1")

    memory.graph.delete.assert_called_once_with(
        "Alice likes Bob",
        {"user_id": "user-1", "agent_id": "agent-1", "run_id": "run-1"},
    )


@pytest.mark.asyncio
@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
async def test_async_delete_calls_graph_cleanup(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """Async delete() should also perform graph cleanup."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import AsyncMemory

    config = MemoryConfig()
    memory = AsyncMemory(config)

    memory.enable_graph = True
    memory.graph = MagicMock()

    mock_vector_store.get.return_value = MockVectorMemory(
        "mem-1",
        {
            "data": "Alice likes Bob",
            "user_id": "user-1",
            "hash": "abc",
        },
    )

    result = await memory.delete("mem-1")

    assert result == {"message": "Memory deleted successfully!"}
    memory.graph.delete.assert_called_once_with("Alice likes Bob", {"user_id": "user-1"})
    mock_vector_store.delete.assert_called_once_with(vector_id="mem-1")


@pytest.mark.asyncio
@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
async def test_async_delete_continues_if_graph_cleanup_fails(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """Async delete() should continue even if graph cleanup fails."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import AsyncMemory

    config = MemoryConfig()
    memory = AsyncMemory(config)

    memory.enable_graph = True
    memory.graph = MagicMock()
    memory.graph.delete.side_effect = RuntimeError("Graph error")

    mock_vector_store.get.return_value = MockVectorMemory(
        "mem-1", {"data": "Alice likes Bob", "user_id": "user-1", "hash": "abc"}
    )

    result = await memory.delete("mem-1")
    assert result == {"message": "Memory deleted successfully!"}
    mock_vector_store.delete.assert_called_once_with(vector_id="mem-1")


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_delete_raises_for_nonexistent_memory_with_graph_enabled(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """delete() should raise ValueError for non-existent memory even with graph enabled."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory

    config = MemoryConfig()
    memory = Memory(config)

    memory.enable_graph = True
    memory.graph = MagicMock()

    mock_vector_store.get.return_value = None

    with pytest.raises(ValueError, match="Memory with id non-existent not found"):
        memory.delete("non-existent")

    memory.graph.delete.assert_not_called()
    mock_vector_store.delete.assert_not_called()


@pytest.mark.asyncio
@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
async def test_async_delete_raises_for_nonexistent_memory_with_graph_enabled(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """Async delete() should raise ValueError for non-existent memory even with graph enabled."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_store.get.return_value = None
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import AsyncMemory

    config = MemoryConfig()
    memory = AsyncMemory(config)

    memory.enable_graph = True
    memory.graph = MagicMock()

    with pytest.raises(ValueError, match="Memory with id non-existent not found"):
        await memory.delete("non-existent")

    memory.graph.delete.assert_not_called()
    mock_vector_store.delete.assert_not_called()


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_delete_all_does_not_trigger_per_memory_graph_cleanup(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """delete_all() should use graph.delete_all(), not per-memory graph.delete()."""
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory

    config = MemoryConfig()
    memory = Memory(config)

    memory.enable_graph = True
    memory.graph = MagicMock()

    mem1 = MockVectorMemory("mem-1", {"data": "Alice likes Bob", "user_id": "user-1"})
    mem2 = MockVectorMemory("mem-2", {"data": "Bob likes Charlie", "user_id": "user-1"})
    mock_vector_store.list.return_value = ([mem1, mem2], 2)
    mock_vector_store.get.return_value = MockVectorMemory(
        "mem-1", {"data": "Alice likes Bob", "user_id": "user-1"}
    )

    memory.delete_all(user_id="user-1")

    # graph.delete (per-memory) should NOT be called
    memory.graph.delete.assert_not_called()
    # graph.delete_all (bulk) SHOULD be called
    memory.graph.delete_all.assert_called_once_with({"user_id": "user-1"})


@patch("mem0.utils.factory.EmbedderFactory.create")
@patch("mem0.utils.factory.VectorStoreFactory.create")
@patch("mem0.utils.factory.LlmFactory.create")
@patch("mem0.memory.storage.SQLiteManager")
def test_internal_delete_memory_does_not_trigger_graph_cleanup(
    mock_sqlite, mock_llm_factory, mock_vector_factory, mock_embedder_factory
):
    """_delete_memory() should NOT call graph.delete() — only the public delete() does.

    This ensures that the DELETE branch inside _add_to_vector_store() (which calls
    _delete_memory directly) does not interfere with the parallel graph pipeline
    running in _add_to_graph().
    """
    mock_embedder_factory.return_value = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_factory.return_value = mock_vector_store
    mock_llm_factory.return_value = MagicMock()
    mock_sqlite.return_value = MagicMock()

    from mem0.memory.main import Memory

    config = MemoryConfig()
    memory = Memory(config)

    memory.enable_graph = True
    memory.graph = MagicMock()

    mock_vector_store.get.return_value = MockVectorMemory(
        "mem-1", {"data": "Alice likes Bob", "user_id": "user-1", "hash": "abc"}
    )

    # Call _delete_memory directly (as _add_to_vector_store does for DELETE events)
    memory._delete_memory("mem-1")

    # graph.delete should NOT have been called — graph cleanup is only in delete()
    memory.graph.delete.assert_not_called()
    # But vector store deletion should proceed
    mock_vector_store.delete.assert_called_once_with(vector_id="mem-1")


def test_graph_memory_delete_calls_internal_methods():
    """Test that MemoryGraph.delete() calls the expected internal pipeline methods."""
    from unittest.mock import patch as _patch

    # We need to mock the Neo4j import
    with _patch.dict("sys.modules", {"langchain_neo4j": MagicMock(), "rank_bm25": MagicMock()}):
        from mem0.memory.graph_memory import MemoryGraph

        with _patch.object(MemoryGraph, "__init__", return_value=None):
            graph = MemoryGraph.__new__(MemoryGraph)

            # Mock the internal methods
            graph._retrieve_nodes_from_data = MagicMock(
                return_value={"alice": "person", "bob": "person"}
            )
            graph._establish_nodes_relations_from_data = MagicMock(
                return_value=[
                    {"source": "alice", "destination": "bob", "relationship": "likes"}
                ]
            )
            graph._delete_entities = MagicMock(return_value=[])

            filters = {"user_id": "user-1"}
            graph.delete("Alice likes Bob", filters)

            graph._retrieve_nodes_from_data.assert_called_once_with("Alice likes Bob", filters)
            graph._establish_nodes_relations_from_data.assert_called_once_with(
                "Alice likes Bob", filters, {"alice": "person", "bob": "person"}
            )
            graph._delete_entities.assert_called_once_with(
                [{"source": "alice", "destination": "bob", "relationship": "likes"}],
                filters,
            )


def test_graph_memory_delete_skips_when_no_entities():
    """Test that MemoryGraph.delete() does nothing when no entities are extracted."""
    from unittest.mock import patch as _patch

    with _patch.dict("sys.modules", {"langchain_neo4j": MagicMock(), "rank_bm25": MagicMock()}):
        from mem0.memory.graph_memory import MemoryGraph

        with _patch.object(MemoryGraph, "__init__", return_value=None):
            graph = MemoryGraph.__new__(MemoryGraph)

            graph._retrieve_nodes_from_data = MagicMock(return_value={})
            graph._establish_nodes_relations_from_data = MagicMock()
            graph._delete_entities = MagicMock()

            graph.delete("Some text", {"user_id": "user-1"})

            graph._retrieve_nodes_from_data.assert_called_once()
            graph._establish_nodes_relations_from_data.assert_not_called()
            graph._delete_entities.assert_not_called()


def test_graph_memory_delete_handles_exception():
    """Test that MemoryGraph.delete() catches exceptions without raising."""
    from unittest.mock import patch as _patch

    with _patch.dict("sys.modules", {"langchain_neo4j": MagicMock(), "rank_bm25": MagicMock()}):
        from mem0.memory.graph_memory import MemoryGraph

        with _patch.object(MemoryGraph, "__init__", return_value=None):
            graph = MemoryGraph.__new__(MemoryGraph)

            graph._retrieve_nodes_from_data = MagicMock(
                side_effect=RuntimeError("LLM error")
            )

            # Should not raise
            graph.delete("Some text", {"user_id": "user-1"})
