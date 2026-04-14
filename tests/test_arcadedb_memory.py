"""Tests for ArcadeDB graph memory backend."""

import importlib.metadata
import json
import sys
from unittest.mock import MagicMock, patch

import pytest

# Patch importlib.metadata.version so mem0.__init__ doesn't fail
# when the package isn't installed in editable mode.
_orig_version = importlib.metadata.version


def _patched_version(name):
    if name == "mem0ai":
        return "0.0.0-test"
    return _orig_version(name)


importlib.metadata.version = _patched_version


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_config(enable_gav=False):
    """Build a mock config object matching the structure expected by MemoryGraph."""
    config = MagicMock()
    config.graph_store.config.url = "http://localhost:2480"
    config.graph_store.config.database = "testdb"
    config.graph_store.config.username = "root"
    config.graph_store.config.password = "arcadedb"
    config.graph_store.config.enable_gav = enable_gav
    config.graph_store.config.gav_vertex_type = "Entity"
    config.graph_store.config.gav_edge_type = None
    config.graph_store.threshold = 0.7
    config.graph_store.custom_prompt = None
    config.graph_store.llm = None
    config.llm.provider = "openai"
    config.llm.config = None
    config.embedder.provider = "openai"
    config.embedder.config = {}
    config.vector_store.config = None
    return config


def _make_graph(enable_gav=False):
    """Instantiate MemoryGraph with all external deps mocked."""
    with patch("mem0.memory.arcadedb_memory.EmbedderFactory") as mock_emb_factory, \
         patch("mem0.memory.arcadedb_memory.LlmFactory") as mock_llm_factory, \
         patch("mem0.memory.arcadedb_memory.requests") as mock_requests:

        mock_embedder = MagicMock()
        mock_embedder.embed.return_value = [0.1] * 1536
        mock_emb_factory.create.return_value = mock_embedder

        mock_llm = MagicMock()
        mock_llm_factory.create.return_value = mock_llm

        # Mock HTTP responses for schema setup
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"result": []}
        mock_requests.post.return_value = mock_resp

        from mem0.memory.arcadedb_memory import MemoryGraph
        config = _mock_config(enable_gav=enable_gav)
        graph = MemoryGraph(config)

        # Re-attach mocks for assertions in tests
        graph._mock_requests = mock_requests
        graph._mock_embedder = mock_embedder
        graph._mock_llm = mock_llm

    return graph


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

class TestSchemaCreation:
    def test_ensure_schema_creates_vertex_type_and_index(self):
        """_ensure_schema should POST SQL commands for vertex type and index."""
        with patch("mem0.memory.arcadedb_memory.EmbedderFactory") as mock_emb_factory, \
             patch("mem0.memory.arcadedb_memory.LlmFactory") as mock_llm_factory, \
             patch("mem0.memory.arcadedb_memory.requests") as mock_requests:

            mock_embedder = MagicMock()
            mock_embedder.embed.return_value = [0.1] * 1536
            mock_emb_factory.create.return_value = mock_embedder
            mock_llm_factory.create.return_value = MagicMock()

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"result": []}
            mock_requests.post.return_value = mock_resp

            from mem0.memory.arcadedb_memory import MemoryGraph
            config = _mock_config()
            MemoryGraph(config)

            # Check that SQL commands were issued
            calls = mock_requests.post.call_args_list
            sql_commands = []
            for call in calls:
                body = call[1].get("json") or (call[0][1] if len(call[0]) > 1 else None)
                if body and isinstance(body, dict) and body.get("language") == "sql":
                    sql_commands.append(body["command"])

            assert any("CREATE VERTEX TYPE Entity" in cmd for cmd in sql_commands)
            assert any("LSM_VECTOR" in cmd for cmd in sql_commands)


# ---------------------------------------------------------------------------
# add / search / delete / get_all / reset
# ---------------------------------------------------------------------------

class TestAddFlow:
    def test_add_calls_llm_and_creates_entities(self):
        graph = _make_graph()

        # Mock LLM to return entities and relations
        graph.llm.generate_response.side_effect = [
            # _retrieve_nodes_from_data
            {"tool_calls": [{"name": "extract_entities", "arguments": {
                "entities": [
                    {"entity": "Alice", "entity_type": "person"},
                    {"entity": "AcmeCorp", "entity_type": "organization"},
                ]
            }}]},
            # _establish_nodes_relations_from_data
            {"tool_calls": [{"name": "establish_relations", "arguments": {
                "entities": [
                    {"source": "Alice", "destination": "AcmeCorp", "relationship": "works_at"},
                ]
            }}]},
            # _get_delete_entities_from_search_output
            {"tool_calls": []},
        ]

        # Mock _exec_command for all subsequent calls
        with patch.object(graph, "_exec_command", return_value=[]):
            with patch.object(graph, "_search_similar_nodes", return_value=[]):
                result = graph.add("Alice works at AcmeCorp", {"user_id": "user1"})

        assert "added_entities" in result
        assert "deleted_entities" in result

    def test_add_increments_mutation_count(self):
        graph = _make_graph()
        initial_count = graph._mutation_count

        graph.llm.generate_response.side_effect = [
            {"tool_calls": [{"name": "extract_entities", "arguments": {"entities": []}}]},
            {"tool_calls": [{"name": "establish_relations", "arguments": {"entities": []}}]},
            {"tool_calls": []},
        ]

        with patch.object(graph, "_exec_command", return_value=[]):
            with patch.object(graph, "_search_similar_nodes", return_value=[]):
                graph.add("test", {"user_id": "user1"})

        assert graph._mutation_count == initial_count + 1


class TestSearchFlow:
    def test_search_returns_bm25_reranked_results(self):
        graph = _make_graph()

        graph.llm.generate_response.return_value = {
            "tool_calls": [{"name": "extract_entities", "arguments": {
                "entities": [{"entity": "Alice", "entity_type": "person"}]
            }}]
        }

        mock_relations = [
            {"source": "alice", "relationship": "works_at", "destination": "acmecorp", "similarity": 0.9},
            {"source": "alice", "relationship": "lives_in", "destination": "new_york", "similarity": 0.8},
        ]

        with patch.object(graph, "_search_graph_db", return_value=mock_relations):
            results = graph.search("Where does Alice work?", {"user_id": "user1"})

        assert len(results) > 0
        assert "source" in results[0]
        assert "relationship" in results[0]
        assert "destination" in results[0]

    def test_search_returns_empty_for_no_results(self):
        graph = _make_graph()

        graph.llm.generate_response.return_value = {
            "tool_calls": [{"name": "extract_entities", "arguments": {"entities": []}}]
        }

        with patch.object(graph, "_search_graph_db", return_value=[]):
            results = graph.search("unknown query", {"user_id": "user1"})

        assert results == []


class TestDeleteFlow:
    def test_delete_soft_deletes_relationships(self):
        graph = _make_graph()

        graph.llm.generate_response.side_effect = [
            {"tool_calls": [{"name": "extract_entities", "arguments": {
                "entities": [{"entity": "Alice", "entity_type": "person"}]
            }}]},
            {"tool_calls": [{"name": "establish_relations", "arguments": {
                "entities": [
                    {"source": "Alice", "destination": "AcmeCorp", "relationship": "works_at"},
                ]
            }}]},
        ]

        with patch.object(graph, "_exec_command", return_value=[]) as mock_exec:
            graph.delete("Alice works at AcmeCorp", {"user_id": "user1"})

            # Check that a Cypher command with SET r.valid = false was issued
            cypher_calls = [
                c for c in mock_exec.call_args_list
                if c[0][0] == "cypher" and "valid = false" in c[0][1]
            ]
            assert len(cypher_calls) > 0

    def test_delete_skips_when_no_entities(self):
        graph = _make_graph()

        graph.llm.generate_response.return_value = {
            "tool_calls": [{"name": "extract_entities", "arguments": {"entities": []}}]
        }

        with patch.object(graph, "_exec_command", return_value=[]) as mock_exec:
            graph.delete("no entities here", {"user_id": "user1"})

        # Should not attempt any delete cypher
        cypher_calls = [
            c for c in mock_exec.call_args_list
            if c[0][0] == "cypher" and "valid = false" in c[0][1]
        ]
        assert len(cypher_calls) == 0

    def test_delete_handles_exception_gracefully(self):
        graph = _make_graph()

        graph.llm.generate_response.side_effect = RuntimeError("LLM error")

        # Should not raise
        graph.delete("some text", {"user_id": "user1"})


class TestDeleteAll:
    def test_delete_all_with_user_id(self):
        graph = _make_graph()

        with patch.object(graph, "_exec_cypher") as mock_cypher:
            graph.delete_all({"user_id": "user1"})

            mock_cypher.assert_called_once()
            call_query = mock_cypher.call_args[0][0]
            assert "DETACH DELETE" in call_query
            assert "user_id" in call_query

    def test_delete_all_with_agent_and_run_id(self):
        graph = _make_graph()

        with patch.object(graph, "_exec_cypher") as mock_cypher:
            graph.delete_all({"user_id": "user1", "agent_id": "agent1", "run_id": "run1"})

            call_query = mock_cypher.call_args[0][0]
            call_params = mock_cypher.call_args[1].get("params") or mock_cypher.call_args[0][1]
            assert "agent_id" in call_query
            assert "run_id" in call_query


class TestGetAll:
    def test_get_all_returns_formatted_results(self):
        graph = _make_graph()

        mock_results = [
            {"source": "alice", "relationship": "works_at", "target": "acmecorp"},
            {"source": "bob", "relationship": "knows", "target": "alice"},
        ]

        with patch.object(graph, "_exec_cypher", return_value=mock_results):
            results = graph.get_all({"user_id": "user1"}, limit=50)

        assert len(results) == 2
        assert results[0]["source"] == "alice"
        assert results[0]["relationship"] == "works_at"
        assert results[0]["target"] == "acmecorp"

    def test_get_all_filters_by_agent_id(self):
        graph = _make_graph()

        with patch.object(graph, "_exec_cypher", return_value=[]) as mock_cypher:
            graph.get_all({"user_id": "user1", "agent_id": "agent1"})

            call_query = mock_cypher.call_args[0][0]
            assert "agent_id" in call_query


class TestReset:
    def test_reset_detach_deletes_all(self):
        graph = _make_graph()

        with patch.object(graph, "_exec_cypher") as mock_cypher:
            graph.reset()

            mock_cypher.assert_called_once_with("MATCH (n) DETACH DELETE n")


# ---------------------------------------------------------------------------
# Multi-tenant filtering
# ---------------------------------------------------------------------------

class TestMultiTenantFiltering:
    def test_search_similar_nodes_filters_by_user_id(self):
        graph = _make_graph()

        mock_results = [
            {"name": "alice", "user_id": "user1", "embedding": [0.1] * 1536, "$distance": 0.1},
            {"name": "bob", "user_id": "user2", "embedding": [0.2] * 1536, "$distance": 0.1},
        ]

        with patch.object(graph, "_exec_sql", return_value=mock_results):
            matches = graph._search_similar_nodes([0.1] * 1536, {"user_id": "user1"})

        assert len(matches) == 1
        assert matches[0]["name"] == "alice"

    def test_search_similar_nodes_filters_by_agent_id(self):
        graph = _make_graph()

        mock_results = [
            {"name": "alice", "user_id": "user1", "agent_id": "agent1", "embedding": [0.1] * 1536, "$distance": 0.1},
            {"name": "bob", "user_id": "user1", "agent_id": "agent2", "embedding": [0.2] * 1536, "$distance": 0.1},
        ]

        with patch.object(graph, "_exec_sql", return_value=mock_results):
            matches = graph._search_similar_nodes(
                [0.1] * 1536, {"user_id": "user1", "agent_id": "agent1"}
            )

        assert len(matches) == 1
        assert matches[0]["name"] == "alice"


# ---------------------------------------------------------------------------
# Node merge (two-phase)
# ---------------------------------------------------------------------------

class TestNodeMerge:
    def test_merge_node_creates_new_when_not_exists(self):
        graph = _make_graph()

        with patch.object(graph, "_exec_cypher") as mock_cypher:
            # First call returns empty (node doesn't exist), second creates it
            mock_cypher.side_effect = [[], [{"n": {"name": "alice"}}]]

            graph._merge_node("user1", "alice", [0.1] * 10)

            assert mock_cypher.call_count == 2
            # Second call should be CREATE
            create_call = mock_cypher.call_args_list[1][0][0]
            assert "CREATE" in create_call

    def test_merge_node_updates_when_exists(self):
        graph = _make_graph()

        with patch.object(graph, "_exec_cypher") as mock_cypher:
            # First call returns existing node, second updates it
            mock_cypher.side_effect = [[{"n": {"name": "alice"}}], [{"n": {"name": "alice"}}]]

            graph._merge_node("user1", "alice", [0.1] * 10)

            assert mock_cypher.call_count == 2
            # Second call should be SET (update)
            update_call = mock_cypher.call_args_list[1][0][0]
            assert "SET" in update_call
            assert "mentions" in update_call


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

class TestHTTPClient:
    def test_exec_command_posts_to_correct_url(self):
        graph = _make_graph()

        with patch("mem0.memory.arcadedb_memory.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"result": [{"foo": "bar"}]}
            mock_requests.post.return_value = mock_resp

            result = graph._exec_command("sql", "SELECT 1")

            mock_requests.post.assert_called_once()
            call_url = mock_requests.post.call_args[0][0]
            assert "/api/v1/command/testdb" in call_url

    def test_exec_command_retries_on_404(self):
        graph = _make_graph()

        with patch("mem0.memory.arcadedb_memory.requests") as mock_requests:
            resp_404 = MagicMock()
            resp_404.status_code = 404

            resp_ok = MagicMock()
            resp_ok.status_code = 200
            resp_ok.json.return_value = {"result": []}

            mock_requests.post.side_effect = [resp_404, resp_ok, resp_ok]

            result = graph._exec_command("sql", "SELECT 1")
            assert result == []


# ---------------------------------------------------------------------------
# GAV (Graph Analytics View)
# ---------------------------------------------------------------------------

class TestGAV:
    def test_gav_disabled_by_default(self):
        graph = _make_graph(enable_gav=False)
        assert graph.enable_gav is False

    def test_gav_enabled_creates_view(self):
        with patch("mem0.memory.arcadedb_memory.EmbedderFactory") as mock_emb_factory, \
             patch("mem0.memory.arcadedb_memory.LlmFactory") as mock_llm_factory, \
             patch("mem0.memory.arcadedb_memory.requests") as mock_requests:

            mock_embedder = MagicMock()
            mock_embedder.embed.return_value = [0.1] * 1536
            mock_emb_factory.create.return_value = mock_embedder
            mock_llm_factory.create.return_value = MagicMock()

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"result": []}
            mock_requests.post.return_value = mock_resp

            from mem0.memory.arcadedb_memory import MemoryGraph
            config = _mock_config(enable_gav=True)
            graph = MemoryGraph(config)

            # Check that CREATE GRAPH ANALYTICS VIEW was called
            calls = mock_requests.post.call_args_list
            sql_commands = []
            for call in calls:
                body = call[1].get("json") or {}
                if isinstance(body, dict) and body.get("language") == "sql":
                    sql_commands.append(body.get("command", ""))

            assert any("GRAPH ANALYTICS VIEW" in cmd for cmd in sql_commands)

    def test_gav_refresh_after_mutations(self):
        graph = _make_graph(enable_gav=True)
        graph._gav_exists = True
        graph._mutation_count = 50

        with patch.object(graph, "_exec_sql") as mock_sql:
            graph._maybe_refresh_gav()
            # Should have attempted to drop and recreate
            assert mock_sql.call_count >= 1

    def test_search_includes_pagerank_when_gav_active(self):
        graph = _make_graph(enable_gav=True)
        graph._gav_exists = True

        graph.llm.generate_response.return_value = {
            "tool_calls": [{"name": "extract_entities", "arguments": {
                "entities": [{"entity": "Alice", "entity_type": "person"}]
            }}]
        }

        mock_relations = [
            {"source": "alice", "relationship": "works_at", "destination": "acmecorp", "similarity": 0.9},
        ]

        with patch.object(graph, "_search_graph_db", return_value=mock_relations):
            with patch.object(graph, "_get_pagerank", return_value=0.85):
                results = graph.search("Where does Alice work?", {"user_id": "user1"})

        assert len(results) == 1
        assert results[0].get("pagerank") == 0.85


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_http_error_raises(self):
        graph = _make_graph()

        with patch("mem0.memory.arcadedb_memory.requests") as mock_requests:
            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_resp.raise_for_status.side_effect = Exception("Internal Server Error")
            mock_requests.post.return_value = mock_resp

            with pytest.raises(Exception, match="Internal Server Error"):
                graph._exec_command("sql", "INVALID SQL")
