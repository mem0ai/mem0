"""Tests for graph memory soft-delete behavior.

Verifies that _delete_entities marks relationships as invalid (soft-delete)
rather than permanently removing them, and that search/retrieval queries
exclude soft-deleted relationships by default.

See: https://github.com/mem0ai/mem0/issues/4187
"""

from unittest.mock import Mock, patch

# Mock optional deps at module level so the import works across all Python
# versions without triggering transitive C-extension reloads (numpy via
# qdrant_client). This matches the pattern in test_memgraph_memory.py.
_neo4j_mock = Mock()
patch.dict("sys.modules", {
    "langchain_neo4j": _neo4j_mock,
    "rank_bm25": Mock(),
}).start()

from mem0.memory.graph_memory import MemoryGraph  # noqa: E402


def _create_graph_memory():
    """Create a MemoryGraph instance with mocked dependencies."""
    with patch.object(MemoryGraph, "__init__", lambda self, *a, **kw: None):
        mg = MemoryGraph.__new__(MemoryGraph)
        mg.graph = Mock()
        mg.graph.query = Mock(return_value=[])
        mg.embedding_model = Mock()
        mg.embedding_model.embed = Mock(return_value=[0.1] * 128)
        mg.llm = Mock()
        mg.node_label = ":Entity"
        mg.threshold = 0.7
        mg.llm_provider = "openai"
    return mg


class TestSoftDelete:
    """Verify _delete_entities uses SET r.valid = false, not DELETE r."""

    def test_delete_entities_sends_soft_delete_cypher(self):
        mg = _create_graph_memory()
        mg.graph.query.return_value = [
            {"source": "Alice", "target": "Bob", "relationship": "KNOWS"}
        ]

        mg._delete_entities(
            [{"source": "alice", "destination": "bob", "relationship": "KNOWS"}],
            {"user_id": "user1"},
        )

        cypher = mg.graph.query.call_args[0][0]
        assert "SET r.valid = false" in cypher
        assert "r.invalidated_at = datetime()" in cypher
        assert "DELETE r" not in cypher

    def test_delete_entities_only_targets_valid_edges(self):
        mg = _create_graph_memory()
        mg._delete_entities(
            [{"source": "alice", "destination": "bob", "relationship": "KNOWS"}],
            {"user_id": "user1"},
        )

        cypher = mg.graph.query.call_args[0][0]
        assert "r.valid IS NULL OR r.valid = true" in cypher

    def test_delete_entities_is_idempotent(self):
        mg = _create_graph_memory()
        item = [{"source": "alice", "destination": "bob", "relationship": "KNOWS"}]
        filters = {"user_id": "user1"}

        mg.graph.query.return_value = [
            {"source": "Alice", "target": "Bob", "relationship": "KNOWS"}
        ]
        mg._delete_entities(item, filters)

        mg.graph.query.return_value = []
        mg._delete_entities(item, filters)

        # Both calls should have the same WHERE filter
        for c in mg.graph.query.call_args_list:
            assert "r.valid IS NULL OR r.valid = true" in c[0][0]


class TestSearchExcludesSoftDeleted:
    """Verify search and get_all filter out soft-deleted relationships."""

    def test_get_all_filters_soft_deleted(self):
        mg = _create_graph_memory()
        mg.get_all(filters={"user_id": "user1"}, limit=10)

        cypher = mg.graph.query.call_args[0][0]
        assert "r.valid IS NULL OR r.valid = true" in cypher

    def test_search_graph_db_filters_both_directions(self):
        """_search_graph_db must filter soft-deleted edges in both outgoing and incoming queries."""
        mg = _create_graph_memory()
        mg.graph.query.return_value = []

        mg._search_graph_db(node_list=["alice"], filters={"user_id": "user1"})

        cypher = mg.graph.query.call_args[0][0]
        # The UNION query has two MATCH branches — both must filter
        occurrences = cypher.count("r.valid IS NULL OR r.valid = true")
        assert occurrences >= 2, (
            f"_search_graph_db has {occurrences} valid-filter(s) but needs >= 2 "
            "(one for outgoing, one for incoming relationships)"
        )

    def test_delete_all_still_hard_deletes(self):
        mg = _create_graph_memory()
        mg.delete_all(filters={"user_id": "user1"})

        cypher = mg.graph.query.call_args[0][0]
        assert "DETACH DELETE" in cypher


class TestMergeResetsValidFlag:
    """Verify MERGE in _add_entities sets r.valid = true.

    Critical: after soft-delete, a MERGE that matches the existing
    (invalidated) edge must reset valid=true, or the edge becomes
    a zombie -- exists but invisible to queries.
    """

    def _run_add_entities(self, source_found, dest_found):
        """Helper: call _add_entities with configurable node search results."""
        mg = _create_graph_memory()

        source_result = (
            [{"elementId(source_candidate)": "src_id_1"}] if source_found else []
        )
        dest_result = (
            [{"elementId(destination_candidate)": "dst_id_1"}] if dest_found else []
        )

        mg._search_source_node = Mock(return_value=source_result)
        mg._search_destination_node = Mock(return_value=dest_result)

        mg._add_entities(
            [{"source": "alice", "destination": "bob", "relationship": "KNOWS"}],
            {"user_id": "user1"},
            entity_type_map={},
        )

        cypher = mg.graph.query.call_args[0][0]
        return cypher

    def test_merge_sets_valid_true_when_source_found(self):
        cypher = self._run_add_entities(source_found=True, dest_found=False)
        assert "r.valid = true" in cypher

    def test_merge_sets_valid_true_when_dest_found(self):
        cypher = self._run_add_entities(source_found=False, dest_found=True)
        assert "r.valid = true" in cypher

    def test_merge_sets_valid_true_when_both_found(self):
        cypher = self._run_add_entities(source_found=True, dest_found=True)
        assert "r.valid = true" in cypher

    def test_merge_sets_valid_true_when_neither_found(self):
        cypher = self._run_add_entities(source_found=False, dest_found=False)
        assert "r.valid = true" in cypher

    def test_merge_clears_invalidated_at_on_resurrection(self):
        """When a soft-deleted edge is resurrected via MERGE, invalidated_at must be cleared.

        Without this, a resurrected edge (valid=true) still carries stale
        invalidated_at metadata, which corrupts temporal reasoning queries.
        """
        for label, src, dst in [
            ("source found", True, False),
            ("dest found", False, True),
            ("both found", True, True),
            ("neither found", False, False),
        ]:
            cypher = self._run_add_entities(source_found=src, dest_found=dst)
            assert "r.invalidated_at = null" in cypher, (
                f"MERGE path '{label}': ON MATCH SET does not clear r.invalidated_at. "
                "Resurrected edges will have stale invalidation timestamps."
            )


class TestCypherConsistency:
    """Verify all MERGE blocks use consistent property names and variable aliases."""

    def _get_merge_cypher(self, source_found, dest_found):
        mg = _create_graph_memory()
        mg._search_source_node = Mock(
            return_value=[{"elementId(source_candidate)": "id1"}] if source_found else []
        )
        mg._search_destination_node = Mock(
            return_value=[{"elementId(destination_candidate)": "id2"}] if dest_found else []
        )
        mg._add_entities(
            [{"source": "alice", "destination": "bob", "relationship": "KNOWS"}],
            {"user_id": "user1"},
            entity_type_map={},
        )
        return mg.graph.query.call_args[0][0]

    def test_all_blocks_use_created_at_not_created(self):
        """All MERGE blocks must use r.created_at, not r.created."""
        for label, src, dst in [
            ("source found", True, False),
            ("dest found", False, True),
            ("both found", True, True),
            ("neither found", False, False),
        ]:
            cypher = self._get_merge_cypher(src, dst)
            assert "r.created_at" in cypher, (
                f"MERGE path '{label}': uses r.created instead of r.created_at"
            )

    def test_all_blocks_use_r_not_rel(self):
        """All MERGE blocks must use 'r' as the relationship variable, not 'rel'."""
        for label, src, dst in [
            ("source found", True, False),
            ("dest found", False, True),
            ("both found", True, True),
            ("neither found", False, False),
        ]:
            cypher = self._get_merge_cypher(src, dst)
            assert "rel." not in cypher, (
                f"MERGE path '{label}': uses 'rel' variable instead of 'r'"
            )

    def test_all_blocks_set_updated_at_on_create(self):
        """All MERGE blocks must set r.updated_at on CREATE for consistent timestamps."""
        for label, src, dst in [
            ("source found", True, False),
            ("dest found", False, True),
            ("both found", True, True),
            ("neither found", False, False),
        ]:
            cypher = self._get_merge_cypher(src, dst)
            assert "r.updated_at = timestamp()" in cypher, (
                f"MERGE path '{label}': missing r.updated_at on CREATE SET"
            )


class TestSoftDeleteWithFilters:
    """Verify soft-delete works correctly with agent_id and run_id filters."""

    def test_delete_entities_with_agent_id(self):
        mg = _create_graph_memory()
        mg._delete_entities(
            [{"source": "alice", "destination": "bob", "relationship": "KNOWS"}],
            {"user_id": "user1", "agent_id": "agent1"},
        )

        cypher = mg.graph.query.call_args[0][0]
        params = mg.graph.query.call_args[1]["params"]
        assert "SET r.valid = false" in cypher
        assert "agent_id: $agent_id" in cypher
        assert params["agent_id"] == "agent1"

    def test_delete_entities_with_run_id(self):
        mg = _create_graph_memory()
        mg._delete_entities(
            [{"source": "alice", "destination": "bob", "relationship": "KNOWS"}],
            {"user_id": "user1", "run_id": "run1"},
        )

        cypher = mg.graph.query.call_args[0][0]
        params = mg.graph.query.call_args[1]["params"]
        assert "SET r.valid = false" in cypher
        assert "run_id: $run_id" in cypher
        assert params["run_id"] == "run1"

    def test_get_all_with_agent_id_filters_soft_deleted(self):
        mg = _create_graph_memory()
        mg.get_all(filters={"user_id": "user1", "agent_id": "agent1"}, limit=10)

        cypher = mg.graph.query.call_args[0][0]
        assert "r.valid IS NULL OR r.valid = true" in cypher
        assert "agent_id: $agent_id" in cypher

    def test_merge_with_agent_id_sets_valid_true(self):
        mg = _create_graph_memory()
        mg._search_source_node = Mock(
            return_value=[{"elementId(source_candidate)": "id1"}]
        )
        mg._search_destination_node = Mock(return_value=[])

        mg._add_entities(
            [{"source": "alice", "destination": "bob", "relationship": "KNOWS"}],
            {"user_id": "user1", "agent_id": "agent1"},
            entity_type_map={},
        )

        cypher = mg.graph.query.call_args[0][0]
        assert "r.valid = true" in cypher
        assert "agent_id: $agent_id" in cypher


class TestResetAndCleanup:
    """Verify reset and delete_all use hard-delete (DETACH DELETE)."""

    def test_reset_uses_detach_delete(self):
        mg = _create_graph_memory()
        mg.reset()

        cypher = mg.graph.query.call_args[0][0]
        assert "DETACH DELETE" in cypher
        assert "valid" not in cypher.lower()

    def test_delete_all_does_not_soft_delete(self):
        mg = _create_graph_memory()
        mg.delete_all(filters={"user_id": "user1"})

        cypher = mg.graph.query.call_args[0][0]
        assert "DETACH DELETE" in cypher
        assert "r.valid = false" not in cypher
