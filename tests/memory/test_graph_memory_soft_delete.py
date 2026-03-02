"""Tests for graph memory soft-delete behavior.

Verifies that _delete_entities marks relationships as invalid (soft-delete)
rather than permanently removing them, and that search/retrieval queries
exclude soft-deleted relationships by default.

See: https://github.com/mem0ai/mem0/issues/4187
"""

import os
import re
from unittest.mock import Mock, patch


def _read_graph_memory_source():
    """Read the graph_memory.py source for static analysis."""
    path = os.path.join(os.path.dirname(__file__), "..", "..", "mem0", "memory", "graph_memory.py")
    with open(path) as f:
        return f.read()


class TestSoftDeleteCypherSyntax:
    """Static analysis: verify Cypher queries use soft-delete pattern."""

    def test_delete_entities_uses_set_not_delete(self):
        """_delete_entities should SET r.valid = false, not DELETE r."""
        source = _read_graph_memory_source()
        # Find the _delete_entities method body
        match = re.search(r"def _delete_entities\(.*?\n(.*?)(?=\n    def |\nclass |\Z)", source, re.DOTALL)
        assert match, "_delete_entities method not found"
        body = match.group(1)
        # Should NOT contain bare "DELETE r"
        assert "DELETE r" not in body, (
            "_delete_entities still uses hard DELETE; expected SET r.valid = false"
        )
        # Should contain soft-delete SET
        assert "r.valid = false" in body, (
            "_delete_entities does not set r.valid = false"
        )
        assert "r.invalidated_at = datetime()" in body, (
            "_delete_entities does not set r.invalidated_at"
        )

    def test_delete_entities_filters_already_invalidated(self):
        """_delete_entities should only soft-delete currently valid relationships."""
        source = _read_graph_memory_source()
        match = re.search(r"def _delete_entities\(.*?\n(.*?)(?=\n    def |\nclass |\Z)", source, re.DOTALL)
        assert match
        body = match.group(1)
        assert "r.valid IS NULL OR r.valid = true" in body, (
            "_delete_entities should filter to only valid relationships before soft-deleting"
        )

    def test_search_graph_db_excludes_soft_deleted(self):
        """_search_graph_db queries should filter out soft-deleted relationships."""
        source = _read_graph_memory_source()
        match = re.search(r"def _search_graph_db\(.*?\n(.*?)(?=\n    def |\nclass |\Z)", source, re.DOTALL)
        assert match, "_search_graph_db method not found"
        body = match.group(1)
        # Both MATCH directions should filter
        occurrences = body.count("r.valid IS NULL OR r.valid = true")
        assert occurrences >= 2, (
            f"_search_graph_db has {occurrences} valid-filters but needs >= 2 "
            "(one for outgoing, one for incoming relationships)"
        )

    def test_get_all_excludes_soft_deleted(self):
        """get_all should filter out soft-deleted relationships."""
        source = _read_graph_memory_source()
        match = re.search(r"def get_all\(.*?\n(.*?)(?=\n    def |\nclass |\Z)", source, re.DOTALL)
        assert match, "get_all method not found"
        body = match.group(1)
        assert "r.valid IS NULL OR r.valid = true" in body, (
            "get_all does not filter soft-deleted relationships"
        )

    def test_delete_all_still_hard_deletes(self):
        """delete_all (explicit user action) should keep DETACH DELETE for full cleanup."""
        source = _read_graph_memory_source()
        match = re.search(r"def delete_all\(.*?\n(.*?)(?=\n    def |\nclass |\Z)", source, re.DOTALL)
        assert match, "delete_all method not found"
        body = match.group(1)
        assert "DETACH DELETE" in body, (
            "delete_all should still use DETACH DELETE for full user-requested cleanup"
        )


class TestSoftDeleteIntegration:
    """Integration-style test using mocked Neo4j graph."""

    def _create_graph_memory(self):
        """Create a MemoryGraph instance with mocked dependencies."""
        mock_neo4j_graph = Mock()
        mock_neo4j_graph.query = Mock(return_value=[])

        # Mock all heavy imports that graph_memory.py pulls in
        mock_modules = {
            "langchain_neo4j": Mock(),
            "rank_bm25": Mock(),
        }
        with patch.dict("sys.modules", mock_modules):
            from mem0.memory.graph_memory import MemoryGraph

            with patch.object(MemoryGraph, "__init__", lambda self, *a, **kw: None):
                mg = MemoryGraph.__new__(MemoryGraph)
                mg.graph = mock_neo4j_graph
                mg.embedding_model = Mock()
                mg.llm = Mock()
                mg.node_label = ":Entity"
                mg.threshold = 0.7
                mg.llm_provider = "openai"

            return mg, mock_neo4j_graph

    def test_delete_entities_sends_soft_delete_cypher(self):
        """Verify _delete_entities sends SET valid=false, not DELETE."""
        mg, mock_graph = self._create_graph_memory()
        mock_graph.query.return_value = [
            {"source": "Alice", "target": "Bob", "relationship": "KNOWS"}
        ]

        to_delete = [
            {"source": "alice", "destination": "bob", "relationship": "KNOWS"}
        ]
        filters = {"user_id": "user1"}

        mg._delete_entities(to_delete, filters)

        call_args = mock_graph.query.call_args
        cypher = call_args[0][0]
        assert "SET r.valid = false" in cypher, f"Expected soft-delete in Cypher:\n{cypher}"
        assert "r.invalidated_at = datetime()" in cypher
        assert "DELETE r" not in cypher, f"Found hard DELETE in Cypher:\n{cypher}"

    def test_get_all_cypher_filters_valid_relationships(self):
        """Verify get_all sends Cypher with valid-relationship filter."""
        mg, mock_graph = self._create_graph_memory()
        mock_graph.query.return_value = []

        mg.get_all(filters={"user_id": "user1"}, limit=10)

        call_args = mock_graph.query.call_args
        cypher = call_args[0][0]
        assert "r.valid IS NULL OR r.valid = true" in cypher, (
            f"get_all Cypher missing valid-filter:\n{cypher}"
        )

    def test_delete_entities_is_idempotent(self):
        """Soft-deleting an already-invalidated relationship should be a no-op.

        The WHERE clause filters to valid-only relationships, so a second
        call with the same entity won't match anything.
        """
        mg, mock_graph = self._create_graph_memory()
        # First call: matches one relationship
        mock_graph.query.return_value = [
            {"source": "Alice", "target": "Bob", "relationship": "KNOWS"}
        ]
        to_delete = [
            {"source": "alice", "destination": "bob", "relationship": "KNOWS"}
        ]
        filters = {"user_id": "user1"}
        mg._delete_entities(to_delete, filters)

        # Second call: no match (already invalidated)
        mock_graph.query.return_value = []
        results = mg._delete_entities(to_delete, filters)

        # Verify the Cypher still has the valid-filter (idempotent guard)
        cypher = mock_graph.query.call_args[0][0]
        assert "r.valid IS NULL OR r.valid = true" in cypher
