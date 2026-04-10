"""
End-to-end tests for graph cleanup on memory deletion (issue #3245).

Uses a real Kuzu embedded database to verify that graph entities are
correctly cleaned up when memories are deleted. LLM and embedding calls
are mocked to provide deterministic entity extraction.

Tests are skipped automatically if kuzu is not installed.
"""

import shutil
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from mem0.configs.base import MemoryConfig

try:
    import kuzu  # noqa: F401
    _kuzu_available = True
except ImportError:
    _kuzu_available = False

requires_kuzu = pytest.mark.skipif(not _kuzu_available, reason="kuzu is not installed")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node_count(kuzu_graph):
    """Return total node count in the Kuzu graph."""
    result = kuzu_graph.execute("MATCH (n:Entity) RETURN count(n) AS cnt")
    rows = list(result.rows_as_dict())
    return int(rows[0]["cnt"])


def _edge_count(kuzu_graph):
    """Return total edge count in the Kuzu graph."""
    result = kuzu_graph.execute("MATCH ()-[r:CONNECTED_TO]->() RETURN count(r) AS cnt")
    rows = list(result.rows_as_dict())
    return int(rows[0]["cnt"])


def _get_edges(kuzu_graph):
    """Return all edges as list of (source, relationship, destination) tuples."""
    result = kuzu_graph.execute(
        "MATCH (s:Entity)-[r:CONNECTED_TO]->(d:Entity) "
        "RETURN s.name AS src, r.name AS rel, d.name AS dst"
    )
    return [(row["src"], row["rel"], row["dst"]) for row in result.rows_as_dict()]


def _get_nodes(kuzu_graph):
    """Return all node names."""
    result = kuzu_graph.execute("MATCH (n:Entity) RETURN n.name AS name, n.user_id AS uid")
    return [(row["name"], row["uid"]) for row in result.rows_as_dict()]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class MockVectorMemory:
    """Mimics the object returned by vector_store.get()."""

    def __init__(self, memory_id, payload, score=0.8):
        self.id = memory_id
        self.payload = payload
        self.score = score


@pytest.fixture
def kuzu_graph_memory():
    """
    Create a real Kuzu-backed MemoryGraph with mocked LLM and embedder.
    Yields (graph_memory_instance, kuzu_connection) then cleans up.
    """
    import os

    import kuzu

    tmpdir = tempfile.mkdtemp()
    db_path = os.path.join(tmpdir, "test.kuzu")
    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)

    # We'll construct the MemoryGraph by bypassing __init__ and setting up manually
    from mem0.memory.kuzu_memory import MemoryGraph

    mg = MemoryGraph.__new__(MemoryGraph)

    # Real Kuzu connection
    mg.db = db
    mg.graph = conn
    mg.node_label = ":Entity"
    mg.rel_label = ":CONNECTED_TO"
    mg.kuzu_create_schema()

    # Deterministic embedding: use one-hot-style vectors per entity name
    # to avoid accidental cosine similarity matches between different entities
    embedding_dims = 64
    mg.embedding_dims = embedding_dims

    _embed_cache = {}
    _embed_counter = [0]

    def deterministic_embed(text):
        """Generate a deterministic, near-orthogonal embedding for each unique text."""
        text_lower = text.lower().strip()
        if text_lower not in _embed_cache:
            # Create a sparse vector — set a unique dimension to 1.0
            vec = [0.0] * embedding_dims
            idx = _embed_counter[0] % embedding_dims
            vec[idx] = 1.0
            # Add small noise to other dims so it's not exactly zero
            import hashlib

            h = hashlib.sha256(text_lower.encode()).digest()
            for i in range(embedding_dims):
                vec[i] += float(h[i % len(h)]) / 25500.0  # tiny noise
            norm = sum(v * v for v in vec) ** 0.5
            _embed_cache[text_lower] = [v / norm for v in vec]
            _embed_counter[0] += 1
        return _embed_cache[text_lower]

    mock_embedder = MagicMock()
    mock_embedder.embed.side_effect = deterministic_embed
    mock_embedder.config.embedding_dims = embedding_dims
    mg.embedding_model = mock_embedder

    # Mock LLM — configured per-test via mock_embedder
    mg.llm = MagicMock()
    mg.llm_provider = "openai"
    mg.user_id = None
    # High threshold so only identical entity names merge, not similar ones
    mg.threshold = 0.99
    mg.config = MagicMock()
    mg.config.graph_store.custom_prompt = None

    yield mg, conn

    # Cleanup
    conn.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _setup_llm_for_entities(mg, entities, relations):
    """
    Configure the mock LLM to return specific entities and relations.

    entities: list of {"entity": str, "entity_type": str}
    relations: list of {"source": str, "destination": str, "relationship": str}
    """

    def generate_response(messages, tools):
        # Detect which tool is being called based on tool definition names
        tool_names = []
        for t in tools:
            if isinstance(t, dict):
                fn = t.get("function", t)
                tool_names.append(fn.get("name", ""))
            else:
                tool_names.append(getattr(t, "name", str(t)))

        if any("extract_entities" in n for n in tool_names):
            return {
                "tool_calls": [
                    {
                        "name": "extract_entities",
                        "arguments": {"entities": entities},
                    }
                ]
            }
        elif any("establish" in n or "relation" in n for n in tool_names):
            return {
                "tool_calls": [
                    {
                        "name": "establish_nodes_relations",
                        "arguments": {"entities": relations},
                    }
                ]
            }
        elif any("delete" in n for n in tool_names):
            # For _get_delete_entities_from_search_output during add() — return nothing to delete
            return {"tool_calls": []}
        return {"tool_calls": []}

    mg.llm.generate_response.side_effect = generate_response


# ---------------------------------------------------------------------------
# End-to-end tests
# ---------------------------------------------------------------------------


@requires_kuzu
class TestKuzuGraphDeleteE2E:
    """End-to-end tests using a real Kuzu database."""

    def test_add_creates_nodes_and_edges(self, kuzu_graph_memory):
        """Baseline: verify add() actually creates graph data."""
        mg, conn = kuzu_graph_memory

        _setup_llm_for_entities(
            mg,
            entities=[
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Bob", "entity_type": "person"},
            ],
            relations=[
                {"source": "Alice", "destination": "Bob", "relationship": "likes"},
            ],
        )

        filters = {"user_id": "test_user"}
        mg.add("Alice likes Bob", filters)

        assert _node_count(conn) == 2
        assert _edge_count(conn) == 1
        edges = _get_edges(conn)
        assert ("alice", "likes", "bob") in edges

    def test_delete_removes_edges_created_by_add(self, kuzu_graph_memory):
        """Core test: delete() should remove the relationships that add() created."""
        mg, conn = kuzu_graph_memory

        _setup_llm_for_entities(
            mg,
            entities=[
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Bob", "entity_type": "person"},
            ],
            relations=[
                {"source": "Alice", "destination": "Bob", "relationship": "likes"},
            ],
        )

        filters = {"user_id": "test_user"}
        mg.add("Alice likes Bob", filters)

        assert _edge_count(conn) == 1

        # Now delete using the same text — should remove the relationship
        mg.delete("Alice likes Bob", filters)

        assert _edge_count(conn) == 0
        # Nodes remain (we don't delete nodes on single memory delete)
        assert _node_count(conn) == 2

    def test_delete_only_removes_matching_edges(self, kuzu_graph_memory):
        """delete() should only remove edges matching the extracted relationships."""
        mg, conn = kuzu_graph_memory

        # First add: Alice likes Bob
        _setup_llm_for_entities(
            mg,
            entities=[
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Bob", "entity_type": "person"},
            ],
            relations=[
                {"source": "Alice", "destination": "Bob", "relationship": "likes"},
            ],
        )
        filters = {"user_id": "test_user"}
        mg.add("Alice likes Bob", filters)

        # Second add: Alice knows Charlie
        _setup_llm_for_entities(
            mg,
            entities=[
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Charlie", "entity_type": "person"},
            ],
            relations=[
                {"source": "Alice", "destination": "Charlie", "relationship": "knows"},
            ],
        )
        mg.add("Alice knows Charlie", filters)

        assert _edge_count(conn) == 2

        # Delete only the "Alice likes Bob" memory
        _setup_llm_for_entities(
            mg,
            entities=[
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Bob", "entity_type": "person"},
            ],
            relations=[
                {"source": "Alice", "destination": "Bob", "relationship": "likes"},
            ],
        )
        mg.delete("Alice likes Bob", filters)

        assert _edge_count(conn) == 1
        edges = _get_edges(conn)
        assert ("alice", "knows", "charlie") in edges
        assert ("alice", "likes", "bob") not in edges

    def test_delete_with_different_user_id_does_not_affect_other_users(self, kuzu_graph_memory):
        """delete() scoped to user_id should not touch another user's graph data."""
        mg, conn = kuzu_graph_memory

        _setup_llm_for_entities(
            mg,
            entities=[
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Bob", "entity_type": "person"},
            ],
            relations=[
                {"source": "Alice", "destination": "Bob", "relationship": "likes"},
            ],
        )

        # Add for user1
        mg.add("Alice likes Bob", {"user_id": "user1"})
        # Add same data for user2
        mg.add("Alice likes Bob", {"user_id": "user2"})

        assert _edge_count(conn) == 2

        # Delete only user1's data
        mg.delete("Alice likes Bob", {"user_id": "user1"})

        assert _edge_count(conn) == 1
        # Remaining edge belongs to user2
        nodes = _get_nodes(conn)
        user2_nodes = [n for n in nodes if n[1] == "user2"]
        assert len(user2_nodes) == 2

    def test_delete_nonexistent_relationship_is_safe(self, kuzu_graph_memory):
        """delete() on data that doesn't exist in the graph should be a no-op."""
        mg, conn = kuzu_graph_memory

        _setup_llm_for_entities(
            mg,
            entities=[
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Bob", "entity_type": "person"},
            ],
            relations=[
                {"source": "Alice", "destination": "Bob", "relationship": "hates"},
            ],
        )

        filters = {"user_id": "test_user"}

        # Nothing in the graph yet
        assert _edge_count(conn) == 0
        assert _node_count(conn) == 0

        # Should not raise
        mg.delete("Alice hates Bob", filters)

        assert _edge_count(conn) == 0
        assert _node_count(conn) == 0

    def test_delete_with_llm_failure_does_not_raise(self, kuzu_graph_memory):
        """If LLM fails during entity extraction, delete() should not raise."""
        mg, conn = kuzu_graph_memory

        # Make LLM raise
        mg.llm.generate_response.side_effect = RuntimeError("LLM service down")

        filters = {"user_id": "test_user"}

        # Should not raise
        mg.delete("Alice likes Bob", filters)

    def test_delete_with_empty_entity_extraction(self, kuzu_graph_memory):
        """If LLM returns no entities, delete() should be a no-op."""
        mg, conn = kuzu_graph_memory

        # Add real data
        _setup_llm_for_entities(
            mg,
            entities=[
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Bob", "entity_type": "person"},
            ],
            relations=[
                {"source": "Alice", "destination": "Bob", "relationship": "likes"},
            ],
        )
        filters = {"user_id": "test_user"}
        mg.add("Alice likes Bob", filters)
        assert _edge_count(conn) == 1

        # Now delete but LLM returns no entities
        _setup_llm_for_entities(mg, entities=[], relations=[])
        mg.delete("some text", filters)

        # Data should still be there
        assert _edge_count(conn) == 1

    def test_delete_all_removes_everything_for_user(self, kuzu_graph_memory):
        """delete_all() should remove all nodes/edges for a user (baseline behavior)."""
        mg, conn = kuzu_graph_memory

        _setup_llm_for_entities(
            mg,
            entities=[
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Bob", "entity_type": "person"},
            ],
            relations=[
                {"source": "Alice", "destination": "Bob", "relationship": "likes"},
            ],
        )
        filters = {"user_id": "test_user"}
        mg.add("Alice likes Bob", filters)

        _setup_llm_for_entities(
            mg,
            entities=[
                {"entity": "Bob", "entity_type": "person"},
                {"entity": "Charlie", "entity_type": "person"},
            ],
            relations=[
                {"source": "Bob", "destination": "Charlie", "relationship": "knows"},
            ],
        )
        mg.add("Bob knows Charlie", filters)

        assert _node_count(conn) >= 3
        assert _edge_count(conn) == 2

        mg.delete_all(filters)

        assert _node_count(conn) == 0
        assert _edge_count(conn) == 0

    def test_add_delete_add_cycle(self, kuzu_graph_memory):
        """Verify that add → delete → re-add works correctly."""
        mg, conn = kuzu_graph_memory

        _setup_llm_for_entities(
            mg,
            entities=[
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Bob", "entity_type": "person"},
            ],
            relations=[
                {"source": "Alice", "destination": "Bob", "relationship": "likes"},
            ],
        )
        filters = {"user_id": "test_user"}

        # Add
        mg.add("Alice likes Bob", filters)
        assert _edge_count(conn) == 1

        # Delete
        mg.delete("Alice likes Bob", filters)
        assert _edge_count(conn) == 0

        # Re-add
        mg.add("Alice likes Bob", filters)
        assert _edge_count(conn) == 1
        edges = _get_edges(conn)
        assert ("alice", "likes", "bob") in edges


@requires_kuzu
class TestMemoryDeleteWithGraphE2E:
    """
    End-to-end tests for Memory.delete() with graph enabled.

    Uses a real Kuzu database for the graph store and mocks for
    the vector store, LLM, and embedder.
    """

    @pytest.fixture
    def memory_with_graph(self):
        """Create a Memory instance with a real Kuzu graph backend."""
        import os

        import kuzu

        tmpdir = tempfile.mkdtemp()

        with (
            patch("mem0.utils.factory.EmbedderFactory.create") as mock_embedder_factory,
            patch("mem0.utils.factory.VectorStoreFactory.create") as mock_vector_factory,
            patch("mem0.utils.factory.LlmFactory.create") as mock_llm_factory,
            patch("mem0.memory.storage.SQLiteManager") as mock_sqlite,
        ):
            _mem_embed_cache = {}
            _mem_embed_counter = [0]

            def _mem_deterministic_embed(text, *args, **kwargs):
                text_lower = text.lower().strip()
                if text_lower not in _mem_embed_cache:
                    import hashlib

                    vec = [0.0] * 64
                    idx = _mem_embed_counter[0] % 64
                    vec[idx] = 1.0
                    h = hashlib.sha256(text_lower.encode()).digest()
                    for i in range(64):
                        vec[i] += float(h[i % len(h)]) / 25500.0
                    norm = sum(v * v for v in vec) ** 0.5
                    _mem_embed_cache[text_lower] = [v / norm for v in vec]
                    _mem_embed_counter[0] += 1
                return _mem_embed_cache[text_lower]

            mock_embedder = MagicMock()
            mock_embedder.embed.side_effect = _mem_deterministic_embed
            mock_embedder.config.embedding_dims = 64
            mock_embedder_factory.return_value = mock_embedder

            mock_vector_store = MagicMock()
            mock_vector_factory.return_value = mock_vector_store

            mock_llm = MagicMock()
            mock_llm_factory.return_value = mock_llm

            mock_sqlite.return_value = MagicMock()

            from mem0.memory.main import Memory

            config = MemoryConfig()
            memory = Memory(config)

            # Now wire up a real Kuzu graph
            db_path = os.path.join(tmpdir, "test.kuzu")
            db = kuzu.Database(db_path)
            conn = kuzu.Connection(db)

            from mem0.memory.kuzu_memory import MemoryGraph as KuzuMemoryGraph

            graph = KuzuMemoryGraph.__new__(KuzuMemoryGraph)
            graph.db = db
            graph.graph = conn
            graph.node_label = ":Entity"
            graph.rel_label = ":CONNECTED_TO"
            graph.kuzu_create_schema()
            graph.embedding_dims = 64
            graph.embedding_model = mock_embedder
            graph.llm = mock_llm
            graph.llm_provider = "openai"
            graph.user_id = None
            graph.threshold = 0.99
            graph.config = MagicMock()
            graph.config.graph_store.custom_prompt = None

            memory.graph = graph

            yield memory, mock_vector_store, mock_llm, conn

            conn.close()
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_memory_delete_triggers_graph_cleanup(self, memory_with_graph):
        """
        Full integration: Memory.delete() should clean up both vector store and graph.
        """
        memory, mock_vs, mock_llm, conn = memory_with_graph

        # 1. Manually add entities to the graph (simulating what add() would do)
        _setup_llm_for_memory_graph(
            mock_llm,
            entities=[
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Bob", "entity_type": "person"},
            ],
            relations=[
                {"source": "Alice", "destination": "Bob", "relationship": "likes"},
            ],
        )
        memory.graph.add("Alice likes Bob", {"user_id": "user-1"})
        assert _edge_count(conn) == 1

        # 2. Set up mock vector store to return this memory
        mock_vs.get.return_value = MockVectorMemory(
            "mem-1",
            {"data": "Alice likes Bob", "user_id": "user-1", "hash": "abc"},
        )

        # 3. Delete the memory
        result = memory.delete("mem-1")

        assert result == {"message": "Memory deleted successfully!"}

        # 4. Verify graph was cleaned up
        assert _edge_count(conn) == 0

        # 5. Verify vector store was also cleaned up
        mock_vs.delete.assert_called_once_with(vector_id="mem-1")

    def test_memory_delete_with_graph_preserves_other_users_data(self, memory_with_graph):
        """Deleting user1's memory should not affect user2's graph data."""
        memory, mock_vs, mock_llm, conn = memory_with_graph

        _setup_llm_for_memory_graph(
            mock_llm,
            entities=[
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Bob", "entity_type": "person"},
            ],
            relations=[
                {"source": "Alice", "destination": "Bob", "relationship": "likes"},
            ],
        )

        # Add data for two users
        memory.graph.add("Alice likes Bob", {"user_id": "user-1"})
        memory.graph.add("Alice likes Bob", {"user_id": "user-2"})
        assert _edge_count(conn) == 2

        # Delete only user-1's memory
        mock_vs.get.return_value = MockVectorMemory(
            "mem-1",
            {"data": "Alice likes Bob", "user_id": "user-1", "hash": "abc"},
        )
        memory.delete("mem-1")

        # user-2's data should be intact
        assert _edge_count(conn) == 1
        nodes = _get_nodes(conn)
        remaining_user_ids = set(uid for _, uid in nodes)
        assert "user-2" in remaining_user_ids

    def test_memory_delete_graph_failure_still_deletes_vector(self, memory_with_graph):
        """If graph cleanup fails, vector store deletion should still proceed."""
        memory, mock_vs, mock_llm, conn = memory_with_graph

        # Make LLM raise during entity extraction (graph cleanup will fail)
        mock_llm.generate_response.side_effect = RuntimeError("LLM exploded")

        mock_vs.get.return_value = MockVectorMemory(
            "mem-1",
            {"data": "Alice likes Bob", "user_id": "user-1", "hash": "abc"},
        )

        result = memory.delete("mem-1")

        assert result == {"message": "Memory deleted successfully!"}
        mock_vs.delete.assert_called_once_with(vector_id="mem-1")

    def test_memory_delete_all_uses_bulk_not_per_memory(self, memory_with_graph):
        """delete_all() should use delete_all() on graph, not per-memory delete()."""
        memory, mock_vs, mock_llm, conn = memory_with_graph

        _setup_llm_for_memory_graph(
            mock_llm,
            entities=[
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Bob", "entity_type": "person"},
            ],
            relations=[
                {"source": "Alice", "destination": "Bob", "relationship": "likes"},
            ],
        )
        memory.graph.add("Alice likes Bob", {"user_id": "user-1"})
        assert _edge_count(conn) == 1

        # Set up vector store to return memories for deletion
        mem1 = MockVectorMemory("mem-1", {"data": "Alice likes Bob", "user_id": "user-1"})
        mock_vs.list.return_value = ([mem1], 1)
        mock_vs.get.return_value = mem1

        memory.delete_all(user_id="user-1")

        # After delete_all, graph should be empty (via graph.delete_all)
        assert _edge_count(conn) == 0
        assert _node_count(conn) == 0

    def test_memory_delete_nonexistent_raises_without_graph_side_effects(self, memory_with_graph):
        """Deleting a non-existent memory should raise ValueError without touching graph."""
        memory, mock_vs, mock_llm, conn = memory_with_graph

        # Add some graph data that should NOT be affected
        _setup_llm_for_memory_graph(
            mock_llm,
            entities=[
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Bob", "entity_type": "person"},
            ],
            relations=[
                {"source": "Alice", "destination": "Bob", "relationship": "likes"},
            ],
        )
        memory.graph.add("Alice likes Bob", {"user_id": "user-1"})
        assert _edge_count(conn) == 1

        # Memory doesn't exist in vector store
        mock_vs.get.return_value = None

        with pytest.raises(ValueError, match="Memory with id non-existent not found"):
            memory.delete("non-existent")

        # Graph data should be untouched
        assert _edge_count(conn) == 1


def _setup_llm_for_memory_graph(mock_llm, entities, relations):
    """Configure mock LLM for the Memory-level graph operations."""

    def generate_response(messages, tools):
        tool_names = []
        for t in tools:
            if isinstance(t, dict):
                fn = t.get("function", t)
                tool_names.append(fn.get("name", ""))
            else:
                tool_names.append(getattr(t, "name", str(t)))

        if any("extract_entities" in n for n in tool_names):
            return {
                "tool_calls": [
                    {
                        "name": "extract_entities",
                        "arguments": {"entities": entities},
                    }
                ]
            }
        elif any("establish" in n or "relation" in n for n in tool_names):
            return {
                "tool_calls": [
                    {
                        "name": "establish_nodes_relations",
                        "arguments": {"entities": relations},
                    }
                ]
            }
        elif any("delete" in n for n in tool_names):
            return {"tool_calls": []}
        return {"tool_calls": []}

    mock_llm.generate_response.side_effect = generate_response
