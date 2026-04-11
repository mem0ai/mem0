from unittest.mock import MagicMock, Mock, patch

# age and rank_bm25 are optional deps — mock them so tests run without install
_age_mock = Mock()
patch.dict("sys.modules", {
    "age": _age_mock,
    "age.models": Mock(),
    "rank_bm25": Mock(),
}).start()

from mem0.memory.apache_age_memory import MemoryGraph, _cosine_similarity  # noqa: E402


def _make_instance():
    with patch.object(MemoryGraph, "__init__", return_value=None):
        instance = MemoryGraph.__new__(MemoryGraph)
        instance.llm_provider = "openai"
        instance.llm = MagicMock()
        instance.embedding_model = MagicMock()
        instance.config = MagicMock()
        instance.config.graph_store.custom_prompt = None
        instance.ag = MagicMock()
        instance.graph_name = "test_graph"
        instance.threshold = 0.7
        return instance


class TestCosineSimilarity:
    """Tests for the _cosine_similarity helper."""

    def test_identical_vectors(self):
        assert abs(_cosine_similarity([1, 0, 0], [1, 0, 0]) - 1.0) < 1e-6

    def test_orthogonal_vectors(self):
        assert abs(_cosine_similarity([1, 0, 0], [0, 1, 0])) < 1e-6

    def test_zero_vector(self):
        assert _cosine_similarity([0, 0, 0], [1, 2, 3]) == 0.0


class TestRetrieveNodesFromData:
    """Tests for _retrieve_nodes_from_data in Apache AGE MemoryGraph."""

    def test_normal_entities_extracted(self):
        instance = _make_instance()
        instance.llm.generate_response.return_value = {
            "tool_calls": [{"name": "extract_entities", "arguments": {"entities": [
                {"entity": "Alice", "entity_type": "person"},
                {"entity": "hiking", "entity_type": "activity"},
            ]}}]
        }
        result = instance._retrieve_nodes_from_data("Alice loves hiking", {"user_id": "u1"})
        assert result == {"alice": "person", "hiking": "activity"}

    def test_malformed_entity_missing_entity_type_is_skipped(self):
        instance = _make_instance()
        instance.llm.generate_response.return_value = {
            "tool_calls": [{"name": "extract_entities", "arguments": {"entities": [
                {"entity": "matrix multiplication", "entity_type": "task"},
                {"entity": "task"},
                {"entity": "ReLU", "entity_type": "task"},
            ]}}]
        }
        result = instance._retrieve_nodes_from_data("some text", {"user_id": "u1"})
        assert "matrix_multiplication" in result
        assert "relu" in result
        assert "task" not in result

    def test_missing_entities_key_returns_empty(self):
        instance = _make_instance()
        instance.llm.generate_response.return_value = {
            "tool_calls": [{"name": "extract_entities", "arguments": {"text": "Hello."}}]
        }
        result = instance._retrieve_nodes_from_data("Hello.", {"user_id": "u1"})
        assert result == {}

    def test_none_tool_calls_returns_empty(self):
        instance = _make_instance()
        instance.llm.generate_response.return_value = {"tool_calls": None}
        result = instance._retrieve_nodes_from_data("hello world", {"user_id": "u1"})
        assert result == {}


class TestEstablishNodesRelationsFromData:
    """Tests for _establish_nodes_relations_from_data in Apache AGE MemoryGraph."""

    def test_none_response_does_not_crash(self):
        instance = _make_instance()
        instance.llm.generate_response.return_value = None
        result = instance._establish_nodes_relations_from_data(
            "Hello world", {"user_id": "u1"}, {}
        )
        assert result == []

    def test_empty_tool_calls_returns_empty(self):
        instance = _make_instance()
        instance.llm.generate_response.return_value = {"tool_calls": []}
        result = instance._establish_nodes_relations_from_data(
            "Hello world", {"user_id": "u1"}, {}
        )
        assert result == []

    def test_valid_entities_returned(self):
        instance = _make_instance()
        instance.llm.generate_response.return_value = {
            "tool_calls": [{"name": "add_entities", "arguments": {"entities": [
                {"source": "alice", "relationship": "loves", "destination": "hiking"}
            ]}}]
        }
        result = instance._establish_nodes_relations_from_data(
            "Alice loves hiking", {"user_id": "u1"}, {"alice": "person"}
        )
        assert len(result) == 1
        assert result[0]["source"] == "alice"


class TestRemoveSpacesFromEntities:
    """Tests for _remove_spaces_from_entities."""

    def test_spaces_and_case(self):
        instance = _make_instance()
        entities = [{"source": "Alice Smith", "relationship": "Works At", "destination": "Big Corp"}]
        result = instance._remove_spaces_from_entities(entities)
        assert result[0]["source"] == "alice_smith"
        assert result[0]["relationship"] == "works_at"
        assert result[0]["destination"] == "big_corp"


class TestFindSimilarNode:
    """Tests for _find_similar_node."""

    def test_returns_none_when_no_nodes(self):
        instance = _make_instance()
        instance._exec_cypher = MagicMock(return_value=[])
        result = instance._find_similar_node([1.0, 0.0], {"user_id": "u1"}, threshold=0.9)
        assert result is None

    def test_returns_best_match_above_threshold(self):
        instance = _make_instance()
        instance._exec_cypher = MagicMock(return_value=[
            {"name": "alice", "embedding": [1.0, 0.0], "user_id": "u1"},
            {"name": "bob", "embedding": [0.0, 1.0], "user_id": "u1"},
        ])
        result = instance._find_similar_node([1.0, 0.0], {"user_id": "u1"}, threshold=0.9)
        assert result["name"] == "alice"

    def test_filters_by_agent_id(self):
        instance = _make_instance()
        instance._exec_cypher = MagicMock(return_value=[
            {"name": "alice", "embedding": [1.0, 0.0], "user_id": "u1", "agent_id": "a2"},
        ])
        result = instance._find_similar_node(
            [1.0, 0.0], {"user_id": "u1", "agent_id": "a1"}, threshold=0.9
        )
        assert result is None


class TestDeleteAll:
    """Tests for delete_all."""

    def test_calls_exec_cypher_and_commits(self):
        instance = _make_instance()
        instance._exec_cypher = MagicMock(return_value=[])
        instance.delete_all({"user_id": "u1"})
        instance._exec_cypher.assert_called_once()
        instance.ag.commit.assert_called_once()


class TestGetAll:
    """Tests for get_all."""

    def test_returns_formatted_results(self):
        instance = _make_instance()
        instance._exec_cypher = MagicMock(return_value=[
            {"source": "alice", "relationship": "KNOWS", "target": "bob"},
            {"source": "alice", "relationship": "LIKES", "target": "hiking"},
        ])
        results = instance.get_all({"user_id": "u1"}, top_k=10)
        assert len(results) == 2
        assert results[0]["source"] == "alice"
        assert results[0]["relationship"] == "KNOWS"
        assert results[0]["target"] == "bob"

    def test_passes_limit_to_cypher(self):
        """Limit is enforced via LIMIT in the Cypher query, not Python slicing."""
        instance = _make_instance()
        instance._exec_cypher = MagicMock(return_value=[
            {"source": "n0", "relationship": "R", "target": "m0"},
        ])
        instance.get_all({"user_id": "u1"}, top_k=3)
        # Verify limit was passed as a parameter to the query
        cypher_stmt = instance._exec_cypher.call_args[0][0]
        assert "LIMIT %s" in cypher_stmt
        params = instance._exec_cypher.call_args[1].get("params") or instance._exec_cypher.call_args[0][2]
        assert 3 in params


class TestAdd:
    """Tests for the add orchestration method."""

    def test_add_returns_added_and_deleted(self):
        instance = _make_instance()
        instance._retrieve_nodes_from_data = MagicMock(return_value={"alice": "person"})
        instance._establish_nodes_relations_from_data = MagicMock(return_value=[
            {"source": "alice", "relationship": "knows", "destination": "bob"}
        ])
        instance._search_graph_db = MagicMock(return_value=[])
        instance._get_delete_entities_from_search_output = MagicMock(return_value=[])
        instance._delete_entities = MagicMock(return_value=[])
        instance._add_entities = MagicMock(return_value=["added"])

        result = instance.add("Alice knows Bob", {"user_id": "u1"})
        assert "deleted_entities" in result
        assert "added_entities" in result
        assert result["added_entities"] == ["added"]


class TestSearch:
    """Tests for the search method."""

    def test_returns_empty_when_no_search_output(self):
        instance = _make_instance()
        instance._retrieve_nodes_from_data = MagicMock(return_value={"alice": "person"})
        instance._search_graph_db = MagicMock(return_value=[])
        result = instance.search("Who is Alice?", {"user_id": "u1"})
        assert result == []
