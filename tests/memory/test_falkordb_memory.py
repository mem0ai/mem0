"""Unit tests for mem0.memory.falkordb_memory (FalkorDB graph memory).

Mock-based: no actual FalkorDB connection required.
"""

from unittest.mock import MagicMock, patch

# falkordb and rank_bm25 are optional deps -- mock them so tests run without install
_falkordb_mock = MagicMock()
_rank_bm25_mock = MagicMock()
patch.dict("sys.modules", {
    "falkordb": _falkordb_mock,
    "rank_bm25": _rank_bm25_mock,
}).start()

from mem0.memory.falkordb_memory import MemoryGraph  # noqa: E402


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_query_result(header_names, rows):
    """Build a mock FalkorDB query result with .result_set and .header."""
    result = MagicMock()
    result.header = [(0, name) for name in header_names]
    result.result_set = rows
    return result


def _make_empty_result():
    """Build a mock FalkorDB query result with empty result_set."""
    result = MagicMock()
    result.header = []
    result.result_set = []
    return result


def _make_graph_wrapper_mock():
    """Create a properly configured graph_wrapper mock.

    The graph_wrapper proxies .query() calls to the per-user FalkorDB graph,
    and also exposes delete_graph() and reset_all_graphs().
    """
    wrapper = MagicMock()
    wrapper.query.return_value = []
    wrapper._database = "test_db"
    wrapper._get_graph.return_value = MagicMock()
    return wrapper


def _make_instance(*, fallback_llm=None, custom_prompt=None, threshold=0.7):
    """Create a MemoryGraph instance with mocked internals (bypass __init__)."""
    with patch.object(MemoryGraph, "__init__", return_value=None):
        inst = MemoryGraph.__new__(MemoryGraph)
        inst.config = MagicMock()
        inst.config.graph_store.custom_prompt = custom_prompt
        inst.config.graph_store.fallback_llm = None
        inst.config.embedder.provider = "openai"
        inst.config.embedder.config = {"model": "text-embedding-3-small", "api_key": "sk-test"}

        inst.graph_wrapper = _make_graph_wrapper_mock()

        inst.embedding_model = MagicMock()
        inst.embedding_model.embed.return_value = [0.1] * 128

        inst.llm = MagicMock()
        inst.llm_provider = "openai"
        inst.fallback_llm = fallback_llm
        inst.fallback_llm_provider = "openai" if fallback_llm else None
        inst.user_id = None
        inst.threshold = threshold

        # Attributes added in refactored __init__
        inst._indexed_user_graphs = set()
        inst.use_base_label = True
        inst.node_label = ":`__Entity__`"

        return inst


_FILTERS = {"user_id": "u1"}
_FILTERS_AGENT = {"user_id": "u1", "agent_id": "a1"}
_FILTERS_RUN = {"user_id": "u1", "agent_id": "a1", "run_id": "r1"}


# ===========================================================================
# TestInit
# ===========================================================================

class TestInit:
    """Tests for MemoryGraph.__init__ configuration wiring."""

    def test_init_sets_basic_attributes(self):
        """Init should wire up graph_wrapper, embedding_model, llm, threshold."""
        config = MagicMock()
        config.graph_store.config.host = "localhost"
        config.graph_store.config.port = 6379
        config.graph_store.config.database = "test_graph"
        config.graph_store.config.username = None
        config.graph_store.config.password = None
        config.graph_store.custom_prompt = None
        config.graph_store.llm = None
        config.graph_store.fallback_llm = None
        config.graph_store.threshold = 0.8
        config.llm.provider = "openai"
        config.llm.config = {"api_key": "sk-test"}
        config.embedder.provider = "openai"
        config.embedder.config = {"embedding_dims": 384}
        config.vector_store.config = {}

        with patch("mem0.memory.falkordb_memory.FalkorDB") as mock_fdb, \
             patch("mem0.memory.falkordb_memory.EmbedderFactory") as mock_ef, \
             patch("mem0.memory.falkordb_memory.LlmFactory") as mock_lf:
            mock_graph = MagicMock()
            mock_fdb.return_value.select_graph.return_value = mock_graph
            mock_lf.create.return_value = MagicMock()
            mock_ef.create.return_value = MagicMock()

            mg = MemoryGraph(config)

            assert mg.config is config
            assert mg.threshold == 0.8
            # Per-user graph: FalkorDB client created but select_graph not called at init
            mock_fdb.assert_called_once_with(
                host="localhost", port=6379,
            )

    def test_init_graph_store_llm_takes_priority(self):
        """If graph_store.llm is configured, it should override config.llm."""
        config = MagicMock()
        config.graph_store.config.host = "localhost"
        config.graph_store.config.port = 6379
        config.graph_store.config.database = "test"
        config.graph_store.config.username = None
        config.graph_store.config.password = None
        config.graph_store.custom_prompt = None
        config.graph_store.llm.provider = "azure_openai"
        config.graph_store.llm.config = {"api_key": "az-key"}
        config.graph_store.fallback_llm = None
        config.graph_store.threshold = 0.7
        config.llm.provider = "openai"
        config.llm.config = {"api_key": "sk-test"}
        config.embedder.provider = "openai"
        config.embedder.config = {"embedding_dims": 384}
        config.vector_store.config = {}

        with patch("mem0.memory.falkordb_memory.FalkorDB") as mock_fdb, \
             patch("mem0.memory.falkordb_memory.EmbedderFactory"), \
             patch("mem0.memory.falkordb_memory.LlmFactory") as mock_lf:
            mock_fdb.return_value.select_graph.return_value = MagicMock()
            mock_lf.create.return_value = MagicMock()
            mg = MemoryGraph(config)
            assert mg.llm_provider == "azure_openai"

    def test_lazy_index_creation_on_first_access(self):
        """Indexes should be created lazily on first user graph access, not at init."""
        config = MagicMock()
        config.graph_store.config.host = "localhost"
        config.graph_store.config.port = 6379
        config.graph_store.config.database = "test"
        config.graph_store.config.username = None
        config.graph_store.config.password = None
        config.graph_store.custom_prompt = None
        config.graph_store.llm = None
        config.graph_store.fallback_llm = None
        config.graph_store.threshold = 0.7
        config.llm.provider = "openai"
        config.llm.config = {}
        config.embedder.provider = "openai"
        config.embedder.config = {"embedding_dims": 768}
        config.vector_store.config = {}

        with patch("mem0.memory.falkordb_memory.FalkorDB") as mock_fdb, \
             patch("mem0.memory.falkordb_memory.EmbedderFactory"), \
             patch("mem0.memory.falkordb_memory.LlmFactory") as mock_lf:
            mock_graph = MagicMock()
            mock_fdb.return_value.select_graph.return_value = mock_graph
            mock_lf.create.return_value = MagicMock()
            mg = MemoryGraph(config)

            # No index creation at init (lazy)
            mock_graph.create_node_vector_index.assert_not_called()
            mock_graph.create_node_range_index.assert_not_called()

            # Trigger lazy index creation
            mg._ensure_user_graph_indexes("test_user")

            mock_graph.create_node_range_index.assert_called_once_with("__Entity__", "name")
            # Second call should be cached (no additional index creation)
            mg._ensure_user_graph_indexes("test_user")
            mock_graph.create_node_range_index.assert_called_once()

    def test_init_fallback_llm_configured(self):
        """Init should set up fallback_llm when config provides it."""
        config = MagicMock()
        config.graph_store.config.host = "localhost"
        config.graph_store.config.port = 6379
        config.graph_store.config.database = "test"
        config.graph_store.config.username = None
        config.graph_store.config.password = None
        config.graph_store.custom_prompt = None
        config.graph_store.llm = None
        config.graph_store.fallback_llm.provider = "anthropic"
        config.graph_store.fallback_llm.config = {"api_key": "sk-fb"}
        config.graph_store.threshold = 0.7
        config.llm.provider = "openai"
        config.llm.config = {}
        config.embedder.provider = "openai"
        config.embedder.config = {"embedding_dims": 384}
        config.vector_store.config = {}

        with patch("mem0.memory.falkordb_memory.FalkorDB") as mock_fdb, \
             patch("mem0.memory.falkordb_memory.EmbedderFactory"), \
             patch("mem0.memory.falkordb_memory.LlmFactory") as mock_lf:
            mock_fdb.return_value.select_graph.return_value = MagicMock()
            fb_llm_mock = MagicMock()
            mock_lf.create.side_effect = [MagicMock(), fb_llm_mock]
            mg = MemoryGraph(config)
            assert mg.fallback_llm is fb_llm_mock
            assert mg.fallback_llm_provider == "anthropic"


# ===========================================================================
# TestAdd
# ===========================================================================

class TestAdd:
    """Tests for the add() orchestration method."""

    def test_add_returns_added_and_deleted(self):
        """add() should return dict with deleted_entities and added_entities."""
        inst = _make_instance()
        inst._retrieve_nodes_from_data = MagicMock(return_value={"alice": "person"})
        inst._establish_nodes_relations_from_data = MagicMock(return_value=[
            {"source": "alice", "relationship": "knows", "destination": "bob"},
        ])
        inst._search_graph_db = MagicMock(return_value=[])
        inst._get_delete_entities_from_search_output = MagicMock(return_value=[])
        inst._delete_entities = MagicMock(return_value=[])
        inst._add_entities = MagicMock(return_value=["added_item"])

        result = inst.add("Alice knows Bob", _FILTERS)

        assert "deleted_entities" in result
        assert "added_entities" in result
        assert result["added_entities"] == ["added_item"]

    def test_add_passes_entity_keys_to_search(self):
        """add() should pass the extracted entity names to _search_graph_db."""
        inst = _make_instance()
        inst._retrieve_nodes_from_data = MagicMock(return_value={"alice": "person", "bob": "person"})
        inst._establish_nodes_relations_from_data = MagicMock(return_value=[])
        inst._search_graph_db = MagicMock(return_value=[])
        inst._get_delete_entities_from_search_output = MagicMock(return_value=[])
        inst._delete_entities = MagicMock(return_value=[])
        inst._add_entities = MagicMock(return_value=[])

        inst.add("Alice and Bob", _FILTERS)

        call_kwargs = inst._search_graph_db.call_args[1]
        assert set(call_kwargs["node_list"]) == {"alice", "bob"}


# ===========================================================================
# TestSearch
# ===========================================================================

class TestSearch:
    """Tests for the search() method (vector search + BM25 reranking)."""

    def setup_method(self):
        """Reset the module-level rank_bm25 mock between tests."""
        _rank_bm25_mock.reset_mock()

    def test_returns_empty_when_no_search_output(self):
        """search() should return [] when _search_graph_db yields nothing."""
        inst = _make_instance()
        inst._retrieve_nodes_from_data = MagicMock(return_value={"alice": "person"})
        inst._search_graph_db = MagicMock(return_value=[])

        result = inst.search("Who is Alice?", _FILTERS)
        assert result == []

    def test_search_applies_bm25_reranking(self):
        """search() should instantiate BM25Okapi and call get_top_n."""
        inst = _make_instance()
        inst._retrieve_nodes_from_data = MagicMock(return_value={"alice": "person"})
        inst._search_graph_db = MagicMock(return_value=[
            {"source": "alice", "relationship": "knows", "destination": "bob"},
            {"source": "alice", "relationship": "likes", "destination": "hiking"},
        ])

        mock_bm25_instance = MagicMock()
        mock_bm25_instance.get_top_n.return_value = [
            ["alice", "knows", "bob"],
        ]
        _rank_bm25_mock.BM25Okapi.return_value = mock_bm25_instance

        result = inst.search("alice knows someone", _FILTERS, limit=5)

        _rank_bm25_mock.BM25Okapi.assert_called()
        assert len(result) == 1
        assert result[0]["source"] == "alice"
        assert result[0]["relationship"] == "knows"
        assert result[0]["destination"] == "bob"

    def test_search_returns_formatted_dicts(self):
        """search() results should have source/relationship/destination keys."""
        inst = _make_instance()
        inst._retrieve_nodes_from_data = MagicMock(return_value={"x": "t"})
        inst._search_graph_db = MagicMock(return_value=[
            {"source": "a", "relationship": "r", "destination": "b"},
        ])
        mock_bm25 = MagicMock()
        mock_bm25.get_top_n.return_value = [["a", "r", "b"]]
        _rank_bm25_mock.BM25Okapi.return_value = mock_bm25

        results = inst.search("query", _FILTERS)
        for r in results:
            assert set(r.keys()) == {"source", "relationship", "destination"}


# ===========================================================================
# TestDelete
# ===========================================================================

class TestDelete:
    """Tests for the delete() method (graph cleanup for memory deletion)."""

    def test_delete_extracts_and_deletes_entities(self):
        """delete() should extract entities then delete matching relationships."""
        inst = _make_instance()
        inst._retrieve_nodes_from_data = MagicMock(return_value={"alice": "person"})
        inst._establish_nodes_relations_from_data = MagicMock(return_value=[
            {"source": "alice", "relationship": "knows", "destination": "bob"},
        ])
        inst._delete_entities = MagicMock(return_value=[])

        inst.delete("Alice knows Bob", _FILTERS)

        inst._delete_entities.assert_called_once()

    def test_delete_no_entities_skips_cleanup(self):
        """delete() should skip cleanup when no entities found."""
        inst = _make_instance()
        inst._retrieve_nodes_from_data = MagicMock(return_value={})
        inst._establish_nodes_relations_from_data = MagicMock()

        inst.delete("nothing here", _FILTERS)

        inst._establish_nodes_relations_from_data.assert_not_called()

    def test_delete_handles_exception_gracefully(self):
        """delete() should catch exceptions and not raise."""
        inst = _make_instance()
        inst._retrieve_nodes_from_data = MagicMock(side_effect=Exception("LLM fail"))

        # Should not raise
        inst.delete("some text", _FILTERS)


# ===========================================================================
# TestDeleteEntities
# ===========================================================================

class TestDeleteEntities:
    """Tests for _delete_entities (soft-delete: SET r.valid = false)."""

    def test_soft_delete_invalidates_relationship(self):
        """_delete_entities should issue SET r.valid = false in Cypher."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = [
            {"source": "alice", "target": "bob", "relationship": "knows"},
        ]

        to_delete = [{"source": "alice", "destination": "bob", "relationship": "knows"}]
        results = inst._delete_entities(to_delete, _FILTERS)

        assert len(results) == 1
        cypher = inst.graph_wrapper.query.call_args[0][0]
        assert "r.valid = false" in cypher
        assert "r.invalidated_at = timestamp()" in cypher
        assert "DELETE r" not in cypher

    def test_backtick_wraps_relationship(self):
        """Relationship types must be backtick-wrapped in Cypher."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = []

        to_delete = [{"source": "rei", "destination": "python", "relationship": "likes"}]
        inst._delete_entities(to_delete, _FILTERS)

        cypher = inst.graph_wrapper.query.call_args[0][0]
        assert ":`likes`" in cypher

    def test_with_agent_id_filter(self):
        """Filters with agent_id should appear in node props."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = []

        to_delete = [{"source": "x", "destination": "y", "relationship": "r"}]
        inst._delete_entities(to_delete, _FILTERS_AGENT)

        cypher = inst.graph_wrapper.query.call_args[0][0]
        params = inst.graph_wrapper.query.call_args.kwargs["params"]
        assert params["agent_id"] == "a1"
        assert "agent_id" in cypher

    def test_multiple_items(self):
        """Each item in to_be_deleted should produce one graph_wrapper.query call."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = []

        items = [
            {"source": "a", "destination": "b", "relationship": "r1"},
            {"source": "c", "destination": "d", "relationship": "r2"},
        ]
        results = inst._delete_entities(items, _FILTERS)

        assert len(results) == 2
        assert inst.graph_wrapper.query.call_count == 2

    def test_skips_item_missing_fields(self):
        """Items missing required fields should be skipped gracefully."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = []

        items = [
            {"source": "a"},  # missing destination and relationship
            {"source": "c", "destination": "d", "relationship": "r2"},
        ]
        results = inst._delete_entities(items, _FILTERS)

        # Only the valid item should produce a result
        assert len(results) == 1
        # Verify only one query was executed (invalid item was skipped)
        assert inst.graph_wrapper.query.call_count == 1

    def test_skips_empty_string_values(self):
        """Items with empty string values should be skipped."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = []

        items = [
            {"source": "", "destination": "d", "relationship": "r"},
            {"source": "a", "destination": "b", "relationship": "r"},
        ]
        results = inst._delete_entities(items, _FILTERS)
        assert len(results) == 1
        assert inst.graph_wrapper.query.call_count == 1


# ===========================================================================
# TestDeleteAll
# ===========================================================================

class TestDeleteAll:
    """Tests for delete_all() (hard delete: DETACH DELETE or graph deletion)."""

    def test_delete_all_with_user_id_only(self):
        """delete_all with only user_id should call graph_wrapper.delete_graph()."""
        inst = _make_instance()

        inst.delete_all(_FILTERS)

        inst.graph_wrapper.delete_graph.assert_called_once_with("u1")

    def test_delete_all_with_agent_id(self):
        """delete_all with agent_id should issue DETACH DELETE with agent_id filter."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = []

        inst.delete_all(_FILTERS_AGENT)

        cypher = inst.graph_wrapper.query.call_args[0][0]
        assert "DETACH DELETE n" in cypher
        assert "agent_id" in cypher
        params = inst.graph_wrapper.query.call_args.kwargs["params"]
        assert params["agent_id"] == "a1"

    def test_delete_all_with_run_id(self):
        """delete_all with run_id should include it in node props."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = []

        inst.delete_all(_FILTERS_RUN)

        cypher = inst.graph_wrapper.query.call_args[0][0]
        assert "run_id" in cypher
        params = inst.graph_wrapper.query.call_args.kwargs["params"]
        assert params["run_id"] == "r1"


# ===========================================================================
# TestGetAll
# ===========================================================================

class TestGetAll:
    """Tests for get_all()."""

    def test_returns_formatted_results(self):
        """get_all should return list of dicts with source/relationship/target."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = [
            {"source": "alice", "relationship": "KNOWS", "target": "bob"},
            {"source": "alice", "relationship": "LIKES", "target": "hiking"},
        ]

        results = inst.get_all(_FILTERS, limit=10)

        assert len(results) == 2
        assert results[0] == {"source": "alice", "relationship": "KNOWS", "target": "bob"}
        assert results[1] == {"source": "alice", "relationship": "LIKES", "target": "hiking"}

    def test_get_all_respects_limit_param(self):
        """The limit parameter should appear in the Cypher LIMIT clause."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = []

        inst.get_all(_FILTERS, limit=42)

        cypher = inst.graph_wrapper.query.call_args[0][0]
        assert "LIMIT 42" in cypher

    def test_get_all_with_agent_id_filter(self):
        """get_all should include agent_id in node props."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = []

        inst.get_all(_FILTERS_AGENT, limit=5)

        cypher = inst.graph_wrapper.query.call_args[0][0]
        assert "agent_id" in cypher
        params = inst.graph_wrapper.query.call_args.kwargs["params"]
        assert params["agent_id"] == "a1"

    def test_get_all_filters_invalid_relationships(self):
        """get_all query should include valid relationship filter."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = []

        inst.get_all(_FILTERS, limit=10)

        cypher = inst.graph_wrapper.query.call_args[0][0]
        assert "r.valid IS NULL OR r.valid = true" in cypher

    def test_get_all_empty_returns_empty_list(self):
        """get_all should return [] when no results."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = []

        results = inst.get_all(_FILTERS)
        assert results == []


# ===========================================================================
# TestReset
# ===========================================================================

class TestReset:
    """Tests for reset()."""

    def test_reset_calls_reset_all_graphs(self):
        """reset() should call graph_wrapper.reset_all_graphs()."""
        inst = _make_instance()

        inst.reset()

        inst.graph_wrapper.reset_all_graphs.assert_called_once()

    def test_reset_clears_indexed_cache(self):
        """reset() should clear the _indexed_user_graphs cache."""
        inst = _make_instance()
        inst._indexed_user_graphs.add("user1")
        inst._indexed_user_graphs.add("user2")

        inst.reset()

        assert inst._indexed_user_graphs == set()


# ===========================================================================
# TestBatchEmbed
# ===========================================================================

class TestBatchEmbed:
    """Tests for _batch_embed()."""

    def test_empty_input_returns_empty(self):
        """_batch_embed([]) should return []."""
        inst = _make_instance()
        assert inst._batch_embed([]) == []

    def test_non_openai_falls_back_to_sequential(self):
        """For non-OpenAI providers, _batch_embed should call embed() per text."""
        inst = _make_instance()
        inst.config.embedder.provider = "huggingface"
        inst.embedding_model.embed.side_effect = lambda t: [0.5] * 4

        result = inst._batch_embed(["hello", "world"])

        assert len(result) == 2
        assert inst.embedding_model.embed.call_count == 2

    def test_openai_uses_batch_api(self):
        """For openai provider, _batch_embed should call OpenAI embeddings.create."""
        inst = _make_instance()
        inst.config.embedder.provider = "openai"
        inst.config.embedder.config = {"model": "text-embedding-3-small", "api_key": "sk-test"}

        mock_resp = MagicMock()
        mock_item_0 = MagicMock()
        mock_item_0.index = 0
        mock_item_0.embedding = [0.1, 0.2]
        mock_item_1 = MagicMock()
        mock_item_1.index = 1
        mock_item_1.embedding = [0.3, 0.4]
        mock_resp.data = [mock_item_1, mock_item_0]  # intentionally unordered

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_resp
        inst._openai_embed_client = mock_client  # bypass _get_openai_embed_client

        result = inst._batch_embed(["hello", "world"])

        assert result == [[0.1, 0.2], [0.3, 0.4]]  # sorted by index

    def test_openai_batch_fallback_on_error(self):
        """If OpenAI batch API fails, should fall back to sequential embed()."""
        inst = _make_instance()
        inst.config.embedder.provider = "openai"
        inst.config.embedder.config = {"model": "text-embedding-3-small", "api_key": "sk-test"}
        inst.embedding_model.embed.return_value = [0.9, 0.8]

        mock_client = MagicMock()
        mock_client.embeddings.create.side_effect = Exception("API down")
        inst._openai_embed_client = mock_client

        result = inst._batch_embed(["a", "b"])

        assert len(result) == 2
        assert inst.embedding_model.embed.call_count == 2

    def test_batch_embed_dict_config(self):
        """_batch_embed should work with dict-based embedder config."""
        inst = _make_instance()
        inst.config.embedder.provider = "openai"
        inst.config.embedder.config = {"model": "m1", "api_key": "k1", "embedding_dims": 256}

        mock_resp = MagicMock()
        mock_item = MagicMock()
        mock_item.index = 0
        mock_item.embedding = [1.0]
        mock_resp.data = [mock_item]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_resp
        inst._openai_embed_client = mock_client

        result = inst._batch_embed(["test"])
        assert result == [[1.0]]
        # dimensions should be passed when embedding_dims is set
        call_kwargs = mock_client.embeddings.create.call_args[1]
        assert call_kwargs["dimensions"] == 256

    def test_batch_embed_pydantic_config(self):
        """_batch_embed should work with Pydantic-style (attribute-based) config."""
        inst = _make_instance()
        inst.config.embedder.provider = "openai"

        pydantic_cfg = MagicMock(spec=[])  # empty spec so isinstance(dict) is False
        pydantic_cfg.model = "m1"
        pydantic_cfg.api_key = "k1"
        pydantic_cfg.openai_base_url = None
        pydantic_cfg.embedding_dims = None
        inst.config.embedder.config = pydantic_cfg

        mock_resp = MagicMock()
        mock_item = MagicMock()
        mock_item.index = 0
        mock_item.embedding = [2.0]
        mock_resp.data = [mock_item]

        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_resp
        inst._openai_embed_client = mock_client

        result = inst._batch_embed(["test"])
        assert result == [[2.0]]


# ===========================================================================
# TestAddEntities
# ===========================================================================

class TestAddEntities:
    """Tests for _add_entities (node lookup via _search_node_by_embedding)."""

    def test_both_nodes_not_found_creates_both(self):
        """When neither source nor dest exist, MERGE both nodes."""
        inst = _make_instance()
        inst._batch_embed = MagicMock(return_value=[[0.1] * 4, [0.2] * 4])
        inst._search_node_by_embedding = MagicMock(return_value=None)
        inst.graph_wrapper.query.return_value = [
            {"source": "alice", "relationship": "knows", "target": "bob"},
        ]

        data = [{"source": "alice", "destination": "bob", "relationship": "knows"}]
        result = inst._add_entities(data, _FILTERS, {"alice": "person", "bob": "person"})

        assert len(result) == 1
        cypher = inst.graph_wrapper.query.call_args[0][0]
        assert "MERGE (source" in cypher
        assert "MERGE (destination" in cypher

    def test_source_found_dest_not(self):
        """When source exists but dest does not, MATCH source + MERGE dest."""
        inst = _make_instance()
        inst._batch_embed = MagicMock(return_value=[[0.1] * 4, [0.2] * 4])
        # Return node_id for first call (source=alice), None for second (dest=bob)
        inst._search_node_by_embedding = MagicMock(side_effect=[42, None])
        inst.graph_wrapper.query.return_value = [
            {"source": "alice", "relationship": "knows", "target": "bob"},
        ]

        data = [{"source": "alice", "destination": "bob", "relationship": "knows"}]
        result = inst._add_entities(data, _FILTERS, {"alice": "person"})

        assert len(result) == 1
        cypher = inst.graph_wrapper.query.call_args[0][0]
        assert "id(source) = $source_id" in cypher
        assert "MERGE (destination" in cypher

    def test_dest_found_source_not(self):
        """When dest exists but source does not, MERGE source + MATCH dest."""
        inst = _make_instance()
        inst._batch_embed = MagicMock(return_value=[[0.1] * 4, [0.2] * 4])
        # Return None for first call (source=alice), node_id for second (dest=bob)
        inst._search_node_by_embedding = MagicMock(side_effect=[None, 99])
        inst.graph_wrapper.query.return_value = [
            {"source": "alice", "relationship": "knows", "target": "bob"},
        ]

        data = [{"source": "alice", "destination": "bob", "relationship": "knows"}]
        result = inst._add_entities(data, _FILTERS, {})

        assert len(result) == 1
        cypher = inst.graph_wrapper.query.call_args[0][0]
        assert "id(destination) = $destination_id" in cypher
        assert "MERGE (source" in cypher

    def test_both_nodes_found(self):
        """When both nodes exist, MATCH both and MERGE relationship."""
        inst = _make_instance()
        inst._batch_embed = MagicMock(return_value=[[0.1] * 4, [0.2] * 4])
        inst._search_node_by_embedding = MagicMock(side_effect=[42, 99])
        inst.graph_wrapper.query.return_value = [
            {"source": "alice", "relationship": "knows", "target": "bob"},
        ]

        data = [{"source": "alice", "destination": "bob", "relationship": "knows"}]
        result = inst._add_entities(data, _FILTERS, {})

        assert len(result) == 1
        cypher = inst.graph_wrapper.query.call_args[0][0]
        assert "id(source) = $source_id" in cypher
        assert "id(destination) = $destination_id" in cypher

    def test_skips_item_missing_required_fields(self):
        """Items missing source/destination/relationship should be skipped."""
        inst = _make_instance()
        inst._batch_embed = MagicMock(return_value=[[0.1] * 4, [0.2] * 4])
        inst._search_node_by_embedding = MagicMock(return_value=None)
        inst.graph_wrapper.query.return_value = [
            {"source": "alice", "relationship": "knows", "target": "bob"},
        ]

        data = [
            {"source": "alice"},  # missing destination and relationship
            {"source": "alice", "destination": "bob", "relationship": "knows"},
        ]
        result = inst._add_entities(data, _FILTERS, {})
        assert len(result) == 1

    def test_skips_item_with_empty_string_values(self):
        """Items with empty string values should be skipped."""
        inst = _make_instance()
        inst._batch_embed = MagicMock(return_value=[[0.1] * 4, [0.2] * 4])
        inst._search_node_by_embedding = MagicMock(return_value=None)
        inst.graph_wrapper.query.return_value = [
            {"source": "alice", "relationship": "knows", "target": "bob"},
        ]

        data = [
            {"source": "", "destination": "bob", "relationship": "knows"},
            {"source": "alice", "destination": "bob", "relationship": "knows"},
        ]
        result = inst._add_entities(data, _FILTERS, {})
        assert len(result) == 1

    def test_empty_input_returns_empty(self):
        """_add_entities([]) should return []."""
        inst = _make_instance()
        assert inst._add_entities([], _FILTERS, {}) == []

    def test_relationship_backtick_wrapped(self):
        """Relationship in Cypher should be backtick-wrapped."""
        inst = _make_instance()
        inst._batch_embed = MagicMock(return_value=[[0.1] * 4, [0.2] * 4])
        inst._search_node_by_embedding = MagicMock(return_value=None)
        inst.graph_wrapper.query.return_value = []

        data = [{"source": "alice", "destination": "bob", "relationship": "works_at"}]
        inst._add_entities(data, _FILTERS, {})

        cypher = inst.graph_wrapper.query.call_args[0][0]
        assert ":`works_at`" in cypher

    def test_add_entities_with_agent_and_run_filters(self):
        """_add_entities should include agent_id and run_id in node props when provided."""
        inst = _make_instance()
        inst._batch_embed = MagicMock(return_value=[[0.1] * 4, [0.2] * 4])
        inst._search_node_by_embedding = MagicMock(return_value=None)
        inst.graph_wrapper.query.return_value = []

        data = [{"source": "alice", "destination": "bob", "relationship": "knows"}]
        inst._add_entities(data, _FILTERS_RUN, {})

        params = inst.graph_wrapper.query.call_args.kwargs["params"]
        assert params.get("agent_id") == "a1"
        assert params.get("run_id") == "r1"


# ===========================================================================
# TestRemoveSpacesFromEntities
# ===========================================================================

class TestRemoveSpacesFromEntities:
    """Tests for _remove_spaces_from_entities."""

    def test_lowercases_and_replaces_spaces(self):
        """Should lowercase and replace spaces with underscores."""
        inst = _make_instance()
        entities = [{"source": "Alice Smith", "relationship": "Works At", "destination": "Big Corp"}]
        result = inst._remove_spaces_from_entities(entities)
        assert result[0]["source"] == "alice_smith"
        assert result[0]["destination"] == "big_corp"

    def test_normalizes_relationship_via_sanitize(self):
        """Relationship should be sanitized for Cypher compatibility."""
        inst = _make_instance()
        entities = [{"source": "a", "relationship": "Works At", "destination": "b"}]
        result = inst._remove_spaces_from_entities(entities)
        assert result[0]["relationship"] == "works_at"

    def test_returns_cleaned_list(self):
        """_remove_spaces_from_entities should return a cleaned list."""
        inst = _make_instance()
        entities = [{"source": "A B", "relationship": "R", "destination": "C D"}]
        returned = inst._remove_spaces_from_entities(entities)
        assert len(returned) == 1
        assert returned[0]["source"] == "a_b"


# ===========================================================================
# TestFallbackLLM
# ===========================================================================

class TestFallbackLLM:
    """Tests for fallback LLM behavior in entity/relation extraction."""

    def _entity_response(self, entities):
        """Build a standard extract_entities tool call response."""
        return {
            "tool_calls": [{
                "name": "extract_entities",
                "arguments": {"entities": entities},
            }]
        }

    def test_primary_success_does_not_trigger_fallback(self):
        """When primary LLM returns valid entities, fallback should not be called."""
        fb_llm = MagicMock()
        inst = _make_instance(fallback_llm=fb_llm)
        inst.llm.generate_response.return_value = self._entity_response([
            {"entity": "alice", "entity_type": "person"},
        ])

        result = inst._retrieve_nodes_from_data("Alice", _FILTERS)

        assert "alice" in result
        fb_llm.generate_response.assert_not_called()

    def test_primary_empty_triggers_fallback(self):
        """When primary LLM returns no entities (None tool_calls), fallback should be tried."""
        fb_llm = MagicMock()
        fb_llm.generate_response.return_value = {
            "tool_calls": [{
                "name": "extract_entities",
                "arguments": {"entities": [
                    {"entity": "Bob", "entity_type": "person"},
                ]},
            }]
        }
        inst = _make_instance(fallback_llm=fb_llm)
        inst.llm.generate_response.return_value = {"tool_calls": None}

        result = inst._retrieve_nodes_from_data("Bob is here", _FILTERS)

        fb_llm.generate_response.assert_called_once()
        assert "bob" in result

    def test_primary_parse_error_triggers_fallback(self):
        """When primary LLM returns malformed data, fallback should kick in."""
        fb_llm = MagicMock()
        fb_llm.generate_response.return_value = self._entity_response([
            {"entity": "charlie", "entity_type": "person"},
        ])
        inst = _make_instance(fallback_llm=fb_llm)
        # Missing 'tool_calls' key entirely -- iterating over None will raise
        inst.llm.generate_response.return_value = {"result": "some text"}

        result = inst._retrieve_nodes_from_data("charlie", _FILTERS)

        fb_llm.generate_response.assert_called_once()
        assert "charlie" in result

    def test_fallback_also_fails_gracefully(self):
        """When both primary and fallback fail, should return empty dict."""
        fb_llm = MagicMock()
        fb_llm.generate_response.side_effect = Exception("Fallback LLM down")
        inst = _make_instance(fallback_llm=fb_llm)
        inst.llm.generate_response.return_value = {"tool_calls": None}

        result = inst._retrieve_nodes_from_data("data", _FILTERS)
        assert result == {}

    def test_no_fallback_configured_returns_empty_on_failure(self):
        """When no fallback LLM and primary fails, return empty dict."""
        inst = _make_instance(fallback_llm=None)
        inst.llm.generate_response.return_value = {"tool_calls": None}

        result = inst._retrieve_nodes_from_data("data", _FILTERS)
        assert result == {}

    def test_relation_extraction_fallback_when_no_valid_entities(self):
        """_establish_nodes_relations should fallback when ALL primary entities lack fields."""
        fb_llm = MagicMock()
        fb_llm.generate_response.return_value = {
            "tool_calls": [{
                "name": "add_entities",
                "arguments": {"entities": [
                    {"source": "alice", "relationship": "likes", "destination": "hiking"},
                ]},
            }]
        }
        inst = _make_instance(fallback_llm=fb_llm)
        # Primary returns entity missing 'destination' (0 valid)
        inst.llm.generate_response.return_value = {
            "tool_calls": [{
                "name": "add_entities",
                "arguments": {"entities": [
                    {"source": "alice", "relationship": "likes"},
                ]},
            }]
        }

        result = inst._establish_nodes_relations_from_data(
            "Alice likes hiking", _FILTERS, {"alice": "person"}
        )

        fb_llm.generate_response.assert_called_once()
        assert len(result) == 1
        assert result[0]["destination"] == "hiking"

    def test_relation_extraction_no_fallback_when_some_valid(self):
        """If primary returns at least one valid entity, fallback should NOT trigger."""
        fb_llm = MagicMock()
        inst = _make_instance(fallback_llm=fb_llm)
        # One valid, one invalid
        inst.llm.generate_response.return_value = {
            "tool_calls": [{
                "name": "add_entities",
                "arguments": {"entities": [
                    {"source": "alice", "relationship": "knows", "destination": "bob"},
                    {"source": "incomplete"},
                ]},
            }]
        }

        result = inst._establish_nodes_relations_from_data(
            "Alice knows Bob", _FILTERS, {"alice": "person"}
        )

        fb_llm.generate_response.assert_not_called()
        assert len(result) == 1
        assert result[0]["source"] == "alice"


# ===========================================================================
# TestSearchGraphDB
# ===========================================================================

class TestSearchGraphDB:
    """Tests for _search_graph_db (vector search pipeline)."""

    def test_returns_parsed_results(self):
        """_search_graph_db should parse results from graph_wrapper.query."""
        inst = _make_instance()
        inst.embedding_model.embed.return_value = [0.1] * 4

        # First call: vector search returns similar nodes
        # Second call: outgoing relations
        # Third call: incoming relations
        inst.graph_wrapper.query.side_effect = [
            [{"node_id": 1, "node_name": "alice", "score": 0.95}],
            [{"source": "alice", "source_id": 1, "relationship": "knows",
              "relation_id": 100, "destination": "bob", "destination_id": 2}],
            [],  # no incoming
        ]

        results = inst._search_graph_db(["alice"], _FILTERS)
        assert len(results) == 1
        assert results[0]["source"] == "alice"

    def test_empty_node_list_returns_empty(self):
        """_search_graph_db with empty node_list should return []."""
        inst = _make_instance()
        results = inst._search_graph_db([], _FILTERS)
        assert results == []

    def test_no_results_returns_empty(self):
        """When vector search returns empty results, should return []."""
        inst = _make_instance()
        inst.embedding_model.embed.return_value = [0.1] * 4
        inst.graph_wrapper.query.return_value = []

        results = inst._search_graph_db(["alice"], _FILTERS)
        assert results == []


# ===========================================================================
# TestRetrieveNodesFromData
# ===========================================================================

class TestRetrieveNodesFromData:
    """Tests for _retrieve_nodes_from_data (entity extraction via LLM)."""

    def test_normal_entities_extracted(self):
        """Should extract entities and normalize to lowercase with underscores."""
        inst = _make_instance()
        inst.llm.generate_response.return_value = {
            "tool_calls": [{"name": "extract_entities", "arguments": {"entities": [
                {"entity": "Alice Smith", "entity_type": "person"},
                {"entity": "hiking", "entity_type": "activity"},
            ]}}]
        }
        result = inst._retrieve_nodes_from_data("Alice Smith loves hiking", _FILTERS)
        assert result == {"alice_smith": "person", "hiking": "activity"}

    def test_none_tool_calls_returns_empty(self):
        """When tool_calls is None, should return empty dict (no fallback configured)."""
        inst = _make_instance()
        inst.llm.generate_response.return_value = {"tool_calls": None}
        result = inst._retrieve_nodes_from_data("hello", _FILTERS)
        assert result == {}

    def test_ignores_non_extract_entities_tool_calls(self):
        """Tool calls with names other than extract_entities should be ignored."""
        inst = _make_instance()
        inst.llm.generate_response.return_value = {
            "tool_calls": [
                {"name": "other_tool", "arguments": {"entities": []}},
                {"name": "extract_entities", "arguments": {"entities": [
                    {"entity": "test", "entity_type": "thing"},
                ]}},
            ]
        }
        result = inst._retrieve_nodes_from_data("test", _FILTERS)
        assert result == {"test": "thing"}


# ===========================================================================
# TestEstablishNodesRelationsFromData
# ===========================================================================

class TestEstablishNodesRelationsFromData:
    """Tests for _establish_nodes_relations_from_data."""

    def test_valid_entities_returned(self):
        """Should return cleaned entities list."""
        inst = _make_instance()
        inst.llm.generate_response.return_value = {
            "tool_calls": [{"name": "add_entities", "arguments": {"entities": [
                {"source": "Alice", "relationship": "Knows", "destination": "Bob"},
            ]}}]
        }
        result = inst._establish_nodes_relations_from_data(
            "Alice knows Bob", _FILTERS, {"alice": "person"}
        )
        assert len(result) == 1
        assert result[0]["source"] == "alice"

    def test_empty_tool_calls_returns_empty(self):
        """Empty tool_calls should produce empty list."""
        inst = _make_instance()
        inst.llm.generate_response.return_value = {"tool_calls": []}
        result = inst._establish_nodes_relations_from_data("text", _FILTERS, {})
        assert result == []

    def test_filters_out_incomplete_entities(self):
        """Entities missing required fields should be filtered out."""
        inst = _make_instance()
        inst.llm.generate_response.return_value = {
            "tool_calls": [{"name": "add_entities", "arguments": {"entities": [
                {"source": "alice", "relationship": "knows", "destination": "bob"},
                {"source": "charlie"},  # incomplete
            ]}}]
        }
        result = inst._establish_nodes_relations_from_data("text", _FILTERS, {})
        assert len(result) == 1
        assert result[0]["source"] == "alice"

    def test_filters_out_entities_with_empty_values(self):
        """Entities with empty string values should be filtered out."""
        inst = _make_instance()
        inst.llm.generate_response.return_value = {
            "tool_calls": [{"name": "add_entities", "arguments": {"entities": [
                {"source": "  ", "relationship": "knows", "destination": "bob"},
                {"source": "alice", "relationship": "knows", "destination": "bob"},
            ]}}]
        }
        result = inst._establish_nodes_relations_from_data("text", _FILTERS, {})
        assert len(result) == 1


# ===========================================================================
# TestSearchNodeByEmbedding
# ===========================================================================

class TestSearchNodeByEmbedding:
    """Tests for _search_node_by_embedding (vector-based node lookup)."""

    def test_returns_node_id_when_found(self):
        """_search_node_by_embedding should return node_id when a match exists."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = [{"node_id": 42}]

        result = inst._search_node_by_embedding([0.1] * 4, _FILTERS)
        assert result == 42

    def test_returns_none_when_not_found(self):
        """_search_node_by_embedding should return None when no matches."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = []

        result = inst._search_node_by_embedding([0.1] * 4, _FILTERS)
        assert result is None

    def test_includes_agent_id_in_params(self):
        """_search_node_by_embedding should include agent_id when provided."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = []

        inst._search_node_by_embedding([0.1] * 4, _FILTERS_AGENT)

        params = inst.graph_wrapper.query.call_args.kwargs["params"]
        assert params["agent_id"] == "a1"
        cypher = inst.graph_wrapper.query.call_args[0][0]
        assert "agent_id" in cypher

    def test_includes_run_id_in_params(self):
        """_search_node_by_embedding should include run_id when provided."""
        inst = _make_instance()
        inst.graph_wrapper.query.return_value = []

        inst._search_node_by_embedding([0.1] * 4, _FILTERS_RUN)

        params = inst.graph_wrapper.query.call_args.kwargs["params"]
        assert params["run_id"] == "r1"

    def test_handles_vector_index_not_exist(self):
        """_search_node_by_embedding should return None when query raises exception."""
        inst = _make_instance()
        inst.graph_wrapper.query.side_effect = Exception("vector index not found")

        result = inst._search_node_by_embedding([0.1] * 4, _FILTERS)
        assert result is None
