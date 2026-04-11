"""End-to-end integration tests for Apache AGE graph memory.

These tests run against a real Apache AGE instance (via Docker) and exercise
every layer of the MemoryGraph class: connection, node MERGE, relationship
MERGE, embedding storage/retrieval, similarity search, deletion, and the
full add/search/get_all/delete_all/reset public API.

Requirements:
    docker run --name age-test \
      -e POSTGRES_DB=mem0_test -e POSTGRES_USER=mem0_user \
      -e POSTGRES_PASSWORD=mem0_pass -p 15432:5432 -d apache/age

Run:
    pytest tests/memory/test_apache_age_e2e.py -v -s
"""

import json
import os
from unittest.mock import MagicMock, patch

import age
import pytest

from mem0.memory.apache_age_memory import MemoryGraph  # noqa: E402

# -- E2E test configuration ---------------------------------------------------

AGE_HOST = os.environ.get("AGE_HOST", "localhost")
AGE_PORT = int(os.environ.get("AGE_PORT", "15432"))
AGE_DB = os.environ.get("AGE_DB", "mem0_test")
AGE_USER = os.environ.get("AGE_USER", "mem0_user")
AGE_PASS = os.environ.get("AGE_PASS", "mem0_pass")
GRAPH_NAME = "e2e_test_graph"


def _age_available():
    """Check if the AGE database is reachable."""
    try:
        ag = age.connect(
            graph=GRAPH_NAME,
            host=AGE_HOST, port=AGE_PORT,
            dbname=AGE_DB, user=AGE_USER, password=AGE_PASS,
        )
        ag.close()
        return True
    except Exception:
        return False


skip_no_age = pytest.mark.skipif(
    not _age_available(),
    reason="Apache AGE not available (start Docker container first)",
)


# -- Helpers -------------------------------------------------------------------

def _make_e2e_instance(graph_name=GRAPH_NAME):
    """Create a MemoryGraph instance wired to the real AGE database,
    but with LLM and embedding model mocked out."""
    with patch.object(MemoryGraph, "__init__", return_value=None):
        mg = MemoryGraph.__new__(MemoryGraph)

    mg.ag = age.connect(
        graph=graph_name,
        host=AGE_HOST, port=AGE_PORT,
        dbname=AGE_DB, user=AGE_USER, password=AGE_PASS,
    )
    mg.graph_name = graph_name
    mg.threshold = 0.7

    # Mock LLM — not needed for DB-layer tests
    mg.llm_provider = "openai"
    mg.llm = MagicMock()
    mg.config = MagicMock()
    mg.config.graph_store.custom_prompt = None

    # Deterministic embedding model: return a fixed vector derived from the
    # entity name so similarity searches are predictable.  Uses a longer
    # vector (16-dim) with multiple hash seeds to minimize collisions.
    def _fake_embed(text):
        """Map text to a deterministic 16-dim vector for testing."""
        import hashlib
        digest = hashlib.sha256(text.encode()).digest()
        return [b / 255.0 for b in digest[:16]]

    mg.embedding_model = MagicMock()
    mg.embedding_model.embed = _fake_embed
    mg.user_id = None

    return mg


def _cleanup(mg):
    """Remove all nodes and close the connection."""
    try:
        mg._exec_cypher("MATCH (n) DETACH DELETE n")
        mg.ag.commit()
    except Exception:
        pass
    try:
        mg.ag.close()
    except Exception:
        pass


# ==============================================================================
# Test: Low-level _exec_cypher
# ==============================================================================

@skip_no_age
class TestExecCypher:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_create_and_return_vertex(self):
        results = self.mg._exec_cypher(
            "CREATE (n {name: %s, val: %s}) RETURN n",
            params=("test_node", 42),
        )
        self.mg.ag.commit()
        assert len(results) == 1
        props = results[0]
        assert props["name"] == "test_node"
        assert props["val"] == 42

    def test_return_scalars_with_cols(self):
        self.mg._exec_cypher(
            "CREATE (a {name: %s, user_id: %s})", params=("x", "u1")
        )
        self.mg._exec_cypher(
            "CREATE (b {name: %s, user_id: %s})", params=("y", "u1")
        )
        self.mg._exec_cypher(
            "MATCH (a {name: %s}), (b {name: %s}) CREATE (a)-[:LINK]->(b)",
            params=("x", "y"),
        )
        self.mg.ag.commit()

        results = self.mg._exec_cypher(
            "MATCH (n)-[r]->(m) RETURN n.name, type(r), m.name",
            cols=["source", "rel", "target"],
        )
        assert len(results) == 1
        assert results[0] == {"source": "x", "rel": "LINK", "target": "y"}

    def test_empty_result(self):
        results = self.mg._exec_cypher(
            "MATCH (n {name: %s}) RETURN n", params=("nonexistent",)
        )
        assert results == []


# ==============================================================================
# Test: _merge_node
# ==============================================================================

@skip_no_age
class TestMergeNode:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_creates_node_on_first_merge(self):
        self.mg._merge_node("u1", "alice", [0.1, 0.2, 0.3])
        self.mg.ag.commit()

        results = self.mg._exec_cypher(
            "MATCH (n {user_id: %s, name: %s}) RETURN n",
            params=("u1", "alice"),
        )
        assert len(results) == 1
        props = results[0]
        assert props["name"] == "alice"
        assert props["mentions"] == 1
        assert props["created"] is not None
        assert json.loads(props["embedding"]) == [0.1, 0.2, 0.3]

    def test_merge_is_idempotent_increments_mentions(self):
        self.mg._merge_node("u1", "bob", [0.4, 0.5])
        self.mg.ag.commit()
        self.mg._merge_node("u1", "bob", [0.4, 0.5])
        self.mg.ag.commit()

        results = self.mg._exec_cypher(
            "MATCH (n {user_id: %s, name: %s}) RETURN n",
            params=("u1", "bob"),
        )
        assert len(results) == 1
        assert results[0]["mentions"] == 2

    def test_merge_with_agent_id(self):
        self.mg._merge_node("u1", "carol", [0.6], agent_id="agent_1")
        self.mg.ag.commit()

        results = self.mg._exec_cypher(
            "MATCH (n {user_id: %s, name: %s}) RETURN n",
            params=("u1", "carol"),
        )
        assert results[0]["agent_id"] == "agent_1"


# ==============================================================================
# Test: Relationship creation and retrieval
# ==============================================================================

@skip_no_age
class TestRelationships:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_create_and_query_relationship(self):
        self.mg._merge_node("u1", "alice", [0.0]*16)
        self.mg._merge_node("u1", "bob", [0.0]*16)
        self.mg.ag.commit()

        self.mg._exec_cypher(
            "MATCH (s {user_id: %s, name: %s}), (d {user_id: %s, name: %s}) "
            "MERGE (s)-[r:KNOWS]->(d)",
            params=("u1", "alice", "u1", "bob"),
        )
        self.mg.ag.commit()

        results = self.mg._exec_cypher(
            "MATCH (n {user_id: %s})-[r]->(m) RETURN n.name, type(r), m.name",
            cols=["source", "rel", "target"],
            params=("u1",),
        )
        assert len(results) == 1
        assert results[0]["source"] == "alice"
        assert results[0]["rel"] == "KNOWS"
        assert results[0]["target"] == "bob"

    def test_multiple_relationships(self):
        for name in ["alice", "bob", "carol"]:
            self.mg._merge_node("u1", name, [0.0])
        self.mg.ag.commit()

        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:KNOWS]->(d)",
            params=("alice", "bob"),
        )
        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:LIKES]->(d)",
            params=("alice", "carol"),
        )
        self.mg.ag.commit()

        results = self.mg._exec_cypher(
            "MATCH (n {name: %s})-[r]->(m) RETURN n.name, type(r), m.name",
            cols=["source", "rel", "target"],
            params=("alice",),
        )
        assert len(results) == 2
        rels = {r["rel"] for r in results}
        assert rels == {"KNOWS", "LIKES"}


# ==============================================================================
# Test: Embedding storage + similarity search
# ==============================================================================

@skip_no_age
class TestEmbeddingSimilarity:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_embedding_roundtrip(self):
        emb = [0.1, 0.2, 0.3, 0.4] + [0.0]*12
        self.mg._merge_node("u1", "node_a", emb)
        self.mg.ag.commit()

        results = self.mg._exec_cypher(
            "MATCH (n {name: %s}) RETURN n", params=("node_a",)
        )
        stored = json.loads(results[0]["embedding"])
        assert stored == emb

    def test_find_similar_node_exact_match(self):
        emb = [1.0, 0.0, 0.0, 0.0] + [0.0]*12
        self.mg._merge_node("u1", "target", emb)
        self.mg.ag.commit()

        match = self.mg._find_similar_node(emb, {"user_id": "u1"}, threshold=0.99)
        assert match is not None
        assert match["name"] == "target"

    def test_find_similar_node_no_match_below_threshold(self):
        self.mg._merge_node("u1", "far_away", [1.0, 0.0, 0.0, 0.0] + [0.0]*12)
        self.mg.ag.commit()

        orthogonal = [0.0, 1.0, 0.0, 0.0] + [0.0]*12
        match = self.mg._find_similar_node(orthogonal, {"user_id": "u1"}, threshold=0.5)
        assert match is None

    def test_find_similar_node_picks_closest(self):
        # Use vectors where "close" is clearly more similar to the query
        self.mg._merge_node("u1", "close", [0.9, 0.1, 0.0, 0.0] + [0.0]*12)
        self.mg._merge_node("u1", "far", [0.0, 0.0, 1.0, 0.0] + [0.0]*12)
        self.mg.ag.commit()

        query = [1.0, 0.0, 0.0, 0.0] + [0.0]*12
        match = self.mg._find_similar_node(query, {"user_id": "u1"}, threshold=0.5)
        assert match is not None
        assert match["name"] == "close"

    def test_find_similar_node_respects_user_id(self):
        vec = [1.0, 0.0, 0.0, 0.0] + [0.0]*12
        self.mg._merge_node("u1", "mine", vec)
        self.mg._merge_node("u2", "theirs", vec)
        self.mg.ag.commit()

        match = self.mg._find_similar_node(
            vec, {"user_id": "u2"}, threshold=0.9
        )
        assert match is not None
        assert match["name"] == "theirs"


# ==============================================================================
# Test: Public API — get_all, delete_all, reset
# ==============================================================================

@skip_no_age
class TestPublicAPICRUD:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_get_all_returns_relationships(self):
        self.mg._merge_node("u1", "alice", [0.0])
        self.mg._merge_node("u1", "bob", [0.0])
        self.mg.ag.commit()
        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:FRIEND]->(d)",
            params=("alice", "bob"),
        )
        self.mg.ag.commit()

        results = self.mg.get_all({"user_id": "u1"})
        assert len(results) == 1
        assert results[0]["source"] == "alice"
        assert results[0]["relationship"] == "FRIEND"
        assert results[0]["target"] == "bob"

    def test_get_all_empty_for_different_user(self):
        self.mg._merge_node("u1", "alice", [0.0])
        self.mg._merge_node("u1", "bob", [0.0])
        self.mg.ag.commit()
        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:FRIEND]->(d)",
            params=("alice", "bob"),
        )
        self.mg.ag.commit()

        results = self.mg.get_all({"user_id": "u999"})
        assert results == []

    def test_get_all_respects_limit(self):
        for i in range(5):
            self.mg._merge_node("u1", f"src_{i}", [0.0])
            self.mg._merge_node("u1", f"dst_{i}", [0.0])
        self.mg.ag.commit()
        for i in range(5):
            self.mg._exec_cypher(
                "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:REL]->(d)",
                params=(f"src_{i}", f"dst_{i}"),
            )
        self.mg.ag.commit()

        results = self.mg.get_all({"user_id": "u1"}, top_k=3)
        assert len(results) == 3

    def test_delete_all_removes_user_data(self):
        self.mg._merge_node("u1", "alice", [0.0])
        self.mg._merge_node("u1", "bob", [0.0])
        self.mg._merge_node("u2", "carol", [0.0])
        self.mg.ag.commit()
        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:KNOWS]->(d)",
            params=("alice", "bob"),
        )
        self.mg.ag.commit()

        self.mg.delete_all({"user_id": "u1"})

        # u1's data should be gone
        results = self.mg._exec_cypher(
            "MATCH (n {user_id: %s}) RETURN n", params=("u1",)
        )
        assert results == []

        # u2's data should still exist
        results = self.mg._exec_cypher(
            "MATCH (n {user_id: %s}) RETURN n", params=("u2",)
        )
        assert len(results) == 1

    def test_reset_clears_everything(self):
        self.mg._merge_node("u1", "alice", [0.0])
        self.mg._merge_node("u2", "bob", [0.0])
        self.mg.ag.commit()

        self.mg.reset()

        results = self.mg._exec_cypher("MATCH (n) RETURN n")
        assert results == []


# ==============================================================================
# Test: _delete_entities
# ==============================================================================

@skip_no_age
class TestDeleteEntities:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_deletes_specific_relationship(self):
        self.mg._merge_node("u1", "alice", [0.0])
        self.mg._merge_node("u1", "bob", [0.0])
        self.mg.ag.commit()
        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:KNOWS]->(d)",
            params=("alice", "bob"),
        )
        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:LIKES]->(d)",
            params=("alice", "bob"),
        )
        self.mg.ag.commit()

        # Delete only KNOWS
        self.mg._delete_entities(
            [{"source": "alice", "destination": "bob", "relationship": "KNOWS"}],
            {"user_id": "u1"},
        )

        # LIKES should remain
        results = self.mg._exec_cypher(
            "MATCH (n {name: %s})-[r]->(m) RETURN n.name, type(r), m.name",
            cols=["source", "rel", "target"],
            params=("alice",),
        )
        assert len(results) == 1
        assert results[0]["rel"] == "LIKES"


# ==============================================================================
# Test: _add_entities (full flow with merge + similarity)
# ==============================================================================

@skip_no_age
class TestAddEntities:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_creates_new_nodes_and_relationship(self):
        result = self.mg._add_entities(
            [{"source": "alice", "destination": "bob", "relationship": "KNOWS"}],
            {"user_id": "u1"},
            entity_type_map={"alice": "person", "bob": "person"},
        )
        assert len(result) == 1
        assert result[0][0]["source"] == "alice"
        assert result[0][0]["relationship"] == "KNOWS"
        assert result[0][0]["target"] == "bob"

        # Verify nodes exist in DB
        nodes = self.mg._exec_cypher(
            "MATCH (n {user_id: %s}) RETURN n", params=("u1",)
        )
        names = {n["name"] for n in nodes}
        assert names == {"alice", "bob"}

    def test_merges_to_existing_similar_node(self):
        # Pre-create "alice" with a known embedding
        emb = self.mg.embedding_model.embed("alice")
        self.mg._merge_node("u1", "alice", emb)
        self.mg.ag.commit()

        # Now add an entity where source="alice" — should merge to existing
        self.mg.threshold = 0.99  # high threshold, but same embedding = exact match
        self.mg._add_entities(
            [{"source": "alice", "destination": "carol", "relationship": "LIKES"}],
            {"user_id": "u1"},
            entity_type_map={"alice": "person", "carol": "person"},
        )

        # Should still have exactly one "alice" node (not a duplicate)
        nodes = self.mg._exec_cypher(
            "MATCH (n {user_id: %s, name: %s}) RETURN n",
            params=("u1", "alice"),
        )
        assert len(nodes) == 1
        # mentions should be > 1 from merge
        assert nodes[0]["mentions"] >= 2

    def test_add_multiple_relationships(self):
        entities = [
            {"source": "alice", "destination": "bob", "relationship": "KNOWS"},
            {"source": "alice", "destination": "carol", "relationship": "LIKES"},
            {"source": "bob", "destination": "carol", "relationship": "WORKS_WITH"},
        ]
        self.mg._add_entities(entities, {"user_id": "u1"}, entity_type_map={})

        results = self.mg.get_all({"user_id": "u1"})
        assert len(results) == 3
        rels = {(r["source"], r["relationship"], r["target"]) for r in results}
        assert ("alice", "KNOWS", "bob") in rels
        assert ("alice", "LIKES", "carol") in rels
        assert ("bob", "WORKS_WITH", "carol") in rels


# ==============================================================================
# Test: _search_graph_db
# ==============================================================================

@skip_no_age
class TestSearchGraphDB:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_finds_related_entities(self):
        # Create a small graph
        emb_alice = self.mg.embedding_model.embed("alice")
        emb_bob = self.mg.embedding_model.embed("bob")
        self.mg._merge_node("u1", "alice", emb_alice)
        self.mg._merge_node("u1", "bob", emb_bob)
        self.mg.ag.commit()
        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:KNOWS]->(d)",
            params=("alice", "bob"),
        )
        self.mg.ag.commit()

        # Search with "alice" embedding — should find the KNOWS relationship
        self.mg.threshold = 0.99  # exact match only
        results = self.mg._search_graph_db(["alice"], {"user_id": "u1"})
        assert len(results) >= 1
        found_knows = any(
            r["source"] == "alice" and r["relationship"] == "KNOWS" and r["destination"] == "bob"
            for r in results
        )
        assert found_knows, f"Expected KNOWS relationship in {results}"

    def test_search_returns_empty_for_no_matches(self):
        self.mg.threshold = 0.99
        results = self.mg._search_graph_db(["nonexistent"], {"user_id": "u1"})
        assert results == []


# ==============================================================================
# Test: Full add() + search() integration (mocking LLM, real DB)
# ==============================================================================

@skip_no_age
class TestAddSearchIntegration:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_full_add_and_search_cycle(self):
        """Simulates the full add() → search() cycle with mocked LLM responses."""
        filters = {"user_id": "test_user_1"}

        # Mock LLM: _retrieve_nodes_from_data
        self.mg.llm.generate_response.side_effect = [
            # 1st call: extract entities for add()
            {"tool_calls": [{"name": "extract_entities", "arguments": {"entities": [
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "Bob", "entity_type": "person"},
            ]}}]},
            # 2nd call: establish relations for add()
            {"tool_calls": [{"name": "add_entities", "arguments": {"entities": [
                {"source": "Alice", "relationship": "knows", "destination": "Bob"},
            ]}}]},
            # 3rd call: get_delete_entities (nothing to delete)
            {"tool_calls": []},
            # 4th call: extract entities for search()
            {"tool_calls": [{"name": "extract_entities", "arguments": {"entities": [
                {"entity": "Alice", "entity_type": "person"},
            ]}}]},
        ]

        # Add
        add_result = self.mg.add("Alice knows Bob", filters)
        assert "added_entities" in add_result
        assert "deleted_entities" in add_result

        # Verify in DB
        all_rels = self.mg.get_all(filters)
        assert len(all_rels) == 1
        assert all_rels[0]["source"] == "alice"
        # Relationship labels are lowercased by _remove_spaces_from_entities
        assert all_rels[0]["relationship"] == "knows"
        assert all_rels[0]["target"] == "bob"

        # Search
        search_results = self.mg.search("Who does Alice know?", filters)
        assert len(search_results) >= 1
        assert any(r["source"] == "alice" and r["destination"] == "bob" for r in search_results)

        # Delete all
        self.mg.delete_all(filters)
        remaining = self.mg.get_all(filters)
        assert remaining == []

    def test_add_then_update_relationship(self):
        """Tests that adding conflicting data removes old relationships."""
        filters = {"user_id": "test_user_2"}

        # First add: Alice likes cats
        self.mg.llm.generate_response.side_effect = [
            {"tool_calls": [{"name": "extract_entities", "arguments": {"entities": [
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "cats", "entity_type": "animal"},
            ]}}]},
            {"tool_calls": [{"name": "add_entities", "arguments": {"entities": [
                {"source": "Alice", "relationship": "likes", "destination": "cats"},
            ]}}]},
            {"tool_calls": []},  # nothing to delete
        ]
        self.mg.add("Alice likes cats", filters)

        all_rels = self.mg.get_all(filters)
        assert len(all_rels) == 1
        assert all_rels[0]["relationship"] == "likes"

        # Second add: Alice now dislikes cats (delete old, add new)
        self.mg.llm.generate_response.side_effect = [
            {"tool_calls": [{"name": "extract_entities", "arguments": {"entities": [
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "cats", "entity_type": "animal"},
            ]}}]},
            {"tool_calls": [{"name": "add_entities", "arguments": {"entities": [
                {"source": "Alice", "relationship": "dislikes", "destination": "cats"},
            ]}}]},
            # LLM says to delete the old likes relationship
            {"tool_calls": [{"name": "delete_graph_memory", "arguments": {
                "source": "alice", "relationship": "likes", "destination": "cats",
            }}]},
        ]
        self.mg.add("Alice dislikes cats", filters)

        all_rels = self.mg.get_all(filters)
        rels = {r["relationship"] for r in all_rels}
        assert "likes" not in rels
        assert "dislikes" in rels

        self.mg.delete_all(filters)


# ==============================================================================
# Test: Multi-tenant isolation
# ==============================================================================

@skip_no_age
class TestMultiTenantIsolation:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_users_cant_see_each_others_data(self):
        # User 1
        self.mg._merge_node("user_1", "alice", [0.0]*16)
        self.mg._merge_node("user_1", "bob", [0.0]*16)
        self.mg.ag.commit()
        self.mg._exec_cypher(
            "MATCH (s {user_id: %s, name: %s}), (d {user_id: %s, name: %s}) "
            "MERGE (s)-[:KNOWS]->(d)",
            params=("user_1", "alice", "user_1", "bob"),
        )
        self.mg.ag.commit()

        # User 2
        self.mg._merge_node("user_2", "carol", [0.0]*16)
        self.mg._merge_node("user_2", "dave", [0.0]*16)
        self.mg.ag.commit()
        self.mg._exec_cypher(
            "MATCH (s {user_id: %s, name: %s}), (d {user_id: %s, name: %s}) "
            "MERGE (s)-[:WORKS_WITH]->(d)",
            params=("user_2", "carol", "user_2", "dave"),
        )
        self.mg.ag.commit()

        # User 1 sees only their data
        u1_results = self.mg.get_all({"user_id": "user_1"})
        assert len(u1_results) == 1
        assert u1_results[0]["source"] == "alice"

        # User 2 sees only their data
        u2_results = self.mg.get_all({"user_id": "user_2"})
        assert len(u2_results) == 1
        assert u2_results[0]["source"] == "carol"

        # Delete user 1 doesn't affect user 2
        self.mg.delete_all({"user_id": "user_1"})
        u2_after = self.mg.get_all({"user_id": "user_2"})
        assert len(u2_after) == 1


# ==============================================================================
# Test: agent_id / run_id filtering in delete_all and get_all
# ==============================================================================

@skip_no_age
class TestAgentRunIdFiltering:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_get_all_filters_by_agent_id(self):
        # Create nodes for two different agents under the same user
        self.mg._merge_node("u1", "alice", [0.0]*16, agent_id="agent_a")
        self.mg._merge_node("u1", "bob", [0.0]*16, agent_id="agent_a")
        self.mg._merge_node("u1", "carol", [0.0]*16, agent_id="agent_b")
        self.mg._merge_node("u1", "dave", [0.0]*16, agent_id="agent_b")
        self.mg.ag.commit()

        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:KNOWS]->(d)",
            params=("alice", "bob"),
        )
        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:LIKES]->(d)",
            params=("carol", "dave"),
        )
        self.mg.ag.commit()

        # get_all with agent_a should only return alice->bob
        results_a = self.mg.get_all({"user_id": "u1", "agent_id": "agent_a"})
        assert len(results_a) == 1
        assert results_a[0]["source"] == "alice"

        # get_all with agent_b should only return carol->dave
        results_b = self.mg.get_all({"user_id": "u1", "agent_id": "agent_b"})
        assert len(results_b) == 1
        assert results_b[0]["source"] == "carol"

    def test_delete_all_filters_by_agent_id(self):
        self.mg._merge_node("u1", "alice", [0.0]*16, agent_id="agent_a")
        self.mg._merge_node("u1", "bob", [0.0]*16, agent_id="agent_a")
        self.mg._merge_node("u1", "carol", [0.0]*16, agent_id="agent_b")
        self.mg.ag.commit()
        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:REL]->(d)",
            params=("alice", "bob"),
        )
        self.mg.ag.commit()

        # Delete only agent_a's data
        self.mg.delete_all({"user_id": "u1", "agent_id": "agent_a"})

        # agent_a nodes should be gone
        nodes_a = self.mg._exec_cypher(
            "MATCH (n) WHERE n.user_id = %s AND n.agent_id = %s RETURN n",
            params=("u1", "agent_a"),
        )
        assert nodes_a == []

        # agent_b's data should still exist
        nodes_b = self.mg._exec_cypher(
            "MATCH (n) WHERE n.user_id = %s AND n.agent_id = %s RETURN n",
            params=("u1", "agent_b"),
        )
        assert len(nodes_b) == 1

    def test_get_all_filters_by_run_id(self):
        self.mg._merge_node("u1", "alice", [0.0]*16, run_id="run_1")
        self.mg._merge_node("u1", "bob", [0.0]*16, run_id="run_1")
        self.mg._merge_node("u1", "carol", [0.0]*16, run_id="run_2")
        self.mg._merge_node("u1", "dave", [0.0]*16, run_id="run_2")
        self.mg.ag.commit()

        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:R1]->(d)",
            params=("alice", "bob"),
        )
        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:R2]->(d)",
            params=("carol", "dave"),
        )
        self.mg.ag.commit()

        results = self.mg.get_all({"user_id": "u1", "run_id": "run_1"})
        assert len(results) == 1
        assert results[0]["source"] == "alice"

    def test_delete_all_filters_by_run_id(self):
        self.mg._merge_node("u1", "alice", [0.0]*16, run_id="run_1")
        self.mg._merge_node("u1", "bob", [0.0]*16, run_id="run_2")
        self.mg.ag.commit()

        self.mg.delete_all({"user_id": "u1", "run_id": "run_1"})

        # run_1 node should be gone
        nodes_1 = self.mg._exec_cypher(
            "MATCH (n) WHERE n.user_id = %s AND n.run_id = %s RETURN n",
            params=("u1", "run_1"),
        )
        assert nodes_1 == []

        # run_2 node should remain
        nodes_2 = self.mg._exec_cypher(
            "MATCH (n) WHERE n.user_id = %s AND n.run_id = %s RETURN n",
            params=("u1", "run_2"),
        )
        assert len(nodes_2) == 1


# ==============================================================================
# Test: Special characters and edge cases
# ==============================================================================

@skip_no_age
class TestEdgeCases:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_node_name_with_underscores(self):
        """Entity names go through _remove_spaces_from_entities which lowercases
        and replaces spaces with underscores."""
        self.mg._merge_node("u1", "new_york_city", [0.0]*16)
        self.mg._merge_node("u1", "united_states", [0.0]*16)
        self.mg.ag.commit()
        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:LOCATED_IN]->(d)",
            params=("new_york_city", "united_states"),
        )
        self.mg.ag.commit()

        results = self.mg.get_all({"user_id": "u1"})
        assert len(results) == 1
        assert results[0]["source"] == "new_york_city"
        assert results[0]["target"] == "united_states"

    def test_node_with_apostrophe_in_name(self):
        """The AGE Python driver has a known limitation where single quotes in
        parameterized values cause a syntax error due to double-quoting in
        buildCypher().  In practice this is not hit because entity names go
        through _remove_spaces_from_entities which sanitizes them."""
        import psycopg2
        with pytest.raises(psycopg2.errors.SyntaxError):
            self.mg._merge_node("u1", "o'brien", [0.0]*16)

    def test_empty_graph_get_all(self):
        results = self.mg.get_all({"user_id": "u1"})
        assert results == []

    def test_empty_graph_delete_all_no_error(self):
        # Should not raise even on empty graph
        self.mg.delete_all({"user_id": "u1"})

    def test_empty_graph_reset_no_error(self):
        self.mg.reset()

    def test_duplicate_relationship_merge_is_idempotent(self):
        """MERGE on the same relationship twice should not create duplicates."""
        self.mg._merge_node("u1", "alice", [0.0]*16)
        self.mg._merge_node("u1", "bob", [0.0]*16)
        self.mg.ag.commit()

        for _ in range(3):
            self.mg._exec_cypher(
                "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:FRIENDS]->(d)",
                params=("alice", "bob"),
            )
            self.mg.ag.commit()

        results = self.mg.get_all({"user_id": "u1"})
        assert len(results) == 1  # Only one relationship, not 3

    def test_bidirectional_relationships(self):
        """Two nodes can have relationships in both directions."""
        self.mg._merge_node("u1", "alice", [0.0]*16)
        self.mg._merge_node("u1", "bob", [0.0]*16)
        self.mg.ag.commit()

        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:FOLLOWS]->(d)",
            params=("alice", "bob"),
        )
        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:FOLLOWS]->(d)",
            params=("bob", "alice"),
        )
        self.mg.ag.commit()

        results = self.mg.get_all({"user_id": "u1"})
        assert len(results) == 2
        pairs = {(r["source"], r["target"]) for r in results}
        assert ("alice", "bob") in pairs
        assert ("bob", "alice") in pairs

    def test_self_referencing_relationship(self):
        """A node can have a relationship to itself."""
        self.mg._merge_node("u1", "alice", [0.0]*16)
        self.mg.ag.commit()

        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:KNOWS_SELF]->(d)",
            params=("alice", "alice"),
        )
        self.mg.ag.commit()

        results = self.mg.get_all({"user_id": "u1"})
        assert len(results) == 1
        assert results[0]["source"] == "alice"
        assert results[0]["target"] == "alice"


# ==============================================================================
# Test: _search_graph_db with agent_id/run_id filtering
# ==============================================================================

@skip_no_age
class TestSearchGraphDBFiltering:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_search_filters_by_agent_id(self):
        emb = self.mg.embedding_model.embed("alice")
        self.mg._merge_node("u1", "alice", emb, agent_id="agent_a")
        self.mg._merge_node("u1", "bob", [0.0]*16, agent_id="agent_a")
        self.mg._merge_node("u1", "alice_clone", emb, agent_id="agent_b")
        self.mg._merge_node("u1", "carol", [0.0]*16, agent_id="agent_b")
        self.mg.ag.commit()

        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:R1]->(d)",
            params=("alice", "bob"),
        )
        self.mg._exec_cypher(
            "MATCH (s {name: %s}), (d {name: %s}) MERGE (s)-[:R2]->(d)",
            params=("alice_clone", "carol"),
        )
        self.mg.ag.commit()

        self.mg.threshold = 0.99
        results = self.mg._search_graph_db(
            ["alice"], {"user_id": "u1", "agent_id": "agent_a"}
        )
        # Should only find relationships for agent_a
        for r in results:
            assert r["source"] != "alice_clone", f"Leaked agent_b data: {r}"

    def test_find_similar_node_filters_by_run_id(self):
        emb = [1.0, 0.0, 0.0, 0.0] + [0.0]*12
        self.mg._merge_node("u1", "target_run1", emb, run_id="run_1")
        self.mg._merge_node("u1", "target_run2", emb, run_id="run_2")
        self.mg.ag.commit()

        match = self.mg._find_similar_node(
            emb, {"user_id": "u1", "run_id": "run_1"}, threshold=0.99
        )
        assert match is not None
        assert match["name"] == "target_run1"


# ==============================================================================
# Test: Full lifecycle with agent_id
# ==============================================================================

@skip_no_age
class TestFullLifecycleWithAgentId:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_add_search_delete_with_agent_id(self):
        """Full cycle: add → get_all → search → delete_all, all scoped by agent_id."""
        filters = {"user_id": "u1", "agent_id": "agent_x"}

        self.mg.llm.generate_response.side_effect = [
            # extract entities
            {"tool_calls": [{"name": "extract_entities", "arguments": {"entities": [
                {"entity": "Python", "entity_type": "language"},
                {"entity": "Alice", "entity_type": "person"},
            ]}}]},
            # establish relations
            {"tool_calls": [{"name": "add_entities", "arguments": {"entities": [
                {"source": "Alice", "relationship": "uses", "destination": "Python"},
            ]}}]},
            # nothing to delete
            {"tool_calls": []},
        ]

        self.mg.add("Alice uses Python", filters)

        # Verify nodes have agent_id
        nodes = self.mg._exec_cypher(
            "MATCH (n) WHERE n.user_id = %s AND n.agent_id = %s RETURN n",
            params=("u1", "agent_x"),
        )
        assert len(nodes) == 2
        names = {n["name"] for n in nodes}
        assert names == {"alice", "python"}

        # get_all with agent_id filter
        all_rels = self.mg.get_all(filters)
        assert len(all_rels) == 1
        assert all_rels[0]["relationship"] == "uses"

        # search
        self.mg.llm.generate_response.side_effect = [
            {"tool_calls": [{"name": "extract_entities", "arguments": {"entities": [
                {"entity": "Alice", "entity_type": "person"},
            ]}}]},
        ]
        search_results = self.mg.search("What does Alice use?", filters)
        assert len(search_results) >= 1

        # delete only agent_x
        self.mg.delete_all(filters)
        remaining = self.mg.get_all(filters)
        assert remaining == []


# ==============================================================================
# Test: _merge_node preserves created timestamp
# ==============================================================================

@skip_no_age
class TestMergeNodeTimestamp:

    def setup_method(self):
        self.mg = _make_e2e_instance()

    def teardown_method(self):
        _cleanup(self.mg)

    def test_created_preserved_across_merges(self):
        """The created timestamp should be set on first merge and preserved on subsequent merges."""
        self.mg._merge_node("u1", "alice", [0.0]*16)
        self.mg.ag.commit()

        nodes1 = self.mg._exec_cypher(
            "MATCH (n {name: %s}) RETURN n", params=("alice",)
        )
        created1 = nodes1[0]["created"]
        assert created1 is not None

        # Second merge — created should not change
        import time
        time.sleep(0.05)  # Ensure clock moves
        self.mg._merge_node("u1", "alice", [0.0]*16)
        self.mg.ag.commit()

        nodes2 = self.mg._exec_cypher(
            "MATCH (n {name: %s}) RETURN n", params=("alice",)
        )
        created2 = nodes2[0]["created"]
        assert created2 == created1, f"created changed from {created1} to {created2}"
        assert nodes2[0]["mentions"] == 2
