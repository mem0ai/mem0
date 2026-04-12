from unittest.mock import MagicMock, Mock, patch

# langchain_neo4j and rank_bm25 are optional deps — mock them so tests run without install
_neo4j_mock = Mock()
patch.dict("sys.modules", {
    "langchain_neo4j": _neo4j_mock,
    "rank_bm25": Mock(),
}).start()

from mem0.memory.graph_memory import MemoryGraph  # noqa: E402


def _make_instance():
    with patch.object(MemoryGraph, "__init__", return_value=None):
        instance = MemoryGraph.__new__(MemoryGraph)
        instance.llm_provider = "openai"
        instance.llm = MagicMock()
        instance.embedding_model = MagicMock()
        instance.config = MagicMock()
        instance.config.graph_store.custom_prompt = None
        return instance


class TestAddEarlyReturn:
    """Tests for early-return guards in add()."""

    def test_add_returns_early_when_entity_type_map_is_empty(self):
        """When _retrieve_nodes_from_data returns empty dict, add() should
        skip all subsequent LLM calls and return empty results."""
        instance = _make_instance()
        instance.llm.generate_response.return_value = {"tool_calls": None}
        instance._establish_nodes_relations_from_data = MagicMock()
        instance._search_graph_db = MagicMock()
        instance._get_delete_entities_from_search_output = MagicMock()

        result = instance.add("hello world", {"user_id": "u1"})

        assert result == {"deleted_entities": [], "added_entities": []}
        instance._establish_nodes_relations_from_data.assert_not_called()
        instance._search_graph_db.assert_not_called()
        instance._get_delete_entities_from_search_output.assert_not_called()

    def test_get_delete_entities_returns_early_when_search_output_is_empty(self):
        """When search_output is empty, _get_delete_entities_from_search_output
        should return [] without calling LLM."""
        instance = _make_instance()

        result = instance._get_delete_entities_from_search_output([], "some data", {"user_id": "u1"})

        assert result == []
        instance.llm.generate_response.assert_not_called()
