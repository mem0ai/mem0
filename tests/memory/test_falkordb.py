import numpy as np
import pytest
from unittest.mock import Mock, patch
from mem0.memory.falkordb_memory import MemoryGraph


class TestFalkorDB:
    """Test that FalkorDB memory works correctly"""

    embeddings = {
        "alice": np.random.uniform(0.0, 0.9, 384).tolist(),
        "bob": np.random.uniform(0.0, 0.9, 384).tolist(),
        "charlie": np.random.uniform(0.0, 0.9, 384).tolist(),
        "dave": np.random.uniform(0.0, 0.9, 384).tolist(),
    }

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for testing"""
        config = Mock()

        # Mock embedder config
        config.embedder.provider = "mock_embedder"
        config.embedder.config = {"model": "mock_model", "embedding_dims": 384}
        config.vector_store.config = {"dimensions": 384}

        # Mock graph store config
        config.graph_store.config.host = "localhost"
        config.graph_store.config.port = 6379
        config.graph_store.config.username = None
        config.graph_store.config.password = None
        config.graph_store.config.graph_name = "test_graph"
        config.graph_store.custom_prompt = None
        config.graph_store.llm = None

        # Mock LLM config
        config.llm.provider = "mock_llm"
        config.llm.config = {"api_key": "test_key"}
        return config

    @pytest.fixture
    def mock_embedding_model(self):
        """Create a mock embedding model"""
        mock_model = Mock()
        mock_model.config.embedding_dims = 384

        def mock_embed(text):
            return self.embeddings.get(text, np.random.uniform(0.0, 0.9, 384).tolist())

        mock_model.embed.side_effect = mock_embed
        return mock_model

    @pytest.fixture
    def mock_llm(self):
        """Create a mock LLM"""
        mock_llm = Mock()
        mock_llm.generate_response.return_value = {
            "tool_calls": [
                {
                    "name": "extract_entities",
                    "arguments": {"entities": [{"entity": "test_entity", "entity_type": "test_type"}]},
                }
            ]
        }
        return mock_llm

    @pytest.fixture
    def mock_falkordb(self):
        """Create a mock FalkorDB connection"""
        mock_db = Mock()
        mock_graph = Mock()
        
        # Mock query results structure with header and result_set
        mock_result = Mock()
        mock_result.result_set = []
        mock_result.header = []
        mock_graph.query.return_value = mock_result
        
        mock_db.select_graph.return_value = mock_graph
        return mock_db, mock_graph

    @patch("mem0.memory.falkordb_memory.falkordb.FalkorDB")
    @patch("mem0.memory.falkordb_memory.EmbedderFactory")
    @patch("mem0.memory.falkordb_memory.LlmFactory")
    def test_falkordb_memory_initialization(
        self, mock_llm_factory, mock_embedder_factory, mock_falkordb_class, mock_config, mock_embedding_model, mock_llm, mock_falkordb
    ):
        """Test that FalkorDB memory initializes correctly"""
        # Setup mocks
        mock_db, mock_graph = mock_falkordb
        mock_falkordb_class.return_value = mock_db
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Create instance
        falkordb_memory = MemoryGraph(mock_config)

        # Verify initialization
        assert falkordb_memory.config == mock_config
        assert falkordb_memory.embedding_model == mock_embedding_model
        assert falkordb_memory.embedding_dims == 384
        assert falkordb_memory.llm == mock_llm
        assert falkordb_memory.threshold == 0.7
        
        # Verify FalkorDB connection
        mock_falkordb_class.assert_called_once_with(
            host="localhost",
            port=6379,
            username=None,
            password=None,
        )
        mock_db.select_graph.assert_called_once_with("test_graph")

    @patch("mem0.memory.falkordb_memory.falkordb.FalkorDB")
    @patch("mem0.memory.falkordb_memory.EmbedderFactory")
    @patch("mem0.memory.falkordb_memory.LlmFactory")
    def test_falkordb_add_entities(
        self, mock_llm_factory, mock_embedder_factory, mock_falkordb_class, mock_config, mock_embedding_model, mock_llm, mock_falkordb
    ):
        """Test adding entities to the graph"""
        # Setup mocks
        mock_db, mock_graph = mock_falkordb
        mock_falkordb_class.return_value = mock_db
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Mock query results for add operations
        mock_result = Mock()
        # Header should be list of tuples: (type, column_name)
        mock_result.header = [(0, "source"), (0, "relationship"), (0, "target")]
        mock_result.result_set = [
            ["alice", "knows", "bob"],
            ["bob", "knows", "charlie"]
        ]
        mock_graph.query.return_value = mock_result

        falkordb_memory = MemoryGraph(mock_config)

        filters = {"user_id": "test_user", "agent_id": "test_agent", "run_id": "test_run"}
        data = [
            {"source": "alice", "destination": "bob", "relationship": "knows"},
            {"source": "bob", "destination": "charlie", "relationship": "knows"},
        ]

        result = falkordb_memory._add_entities(data, filters, {})
        
        # Verify add operations were called
        assert len(result) == 2
        assert mock_graph.query.call_count >= 2

    @patch("mem0.memory.falkordb_memory.falkordb.FalkorDB")
    @patch("mem0.memory.falkordb_memory.EmbedderFactory")
    @patch("mem0.memory.falkordb_memory.LlmFactory")
    def test_falkordb_search_graph_db(
        self, mock_llm_factory, mock_embedder_factory, mock_falkordb_class, mock_config, mock_embedding_model, mock_llm, mock_falkordb
    ):
        """Test searching the graph database"""
        # Setup mocks
        mock_db, mock_graph = mock_falkordb
        mock_falkordb_class.return_value = mock_db
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Mock search results
        mock_result = Mock()
        # Header should be list of tuples: (type, column_name)
        mock_result.header = [(0, "source"), (0, "relationship"), (0, "target")]
        mock_result.result_set = [["alice", "knows", "bob"]]
        mock_graph.query.return_value = mock_result

        falkordb_memory = MemoryGraph(mock_config)

        filters = {"user_id": "test_user"}
        node_list = ["alice", "bob"]

        results = falkordb_memory._search_graph_db(node_list, filters, limit=10)
        
        # Should find relationships
        assert isinstance(results, list)
        # Should have called query for each node and direction
        assert mock_graph.query.call_count >= len(node_list)

    @patch("mem0.memory.falkordb_memory.falkordb.FalkorDB")
    @patch("mem0.memory.falkordb_memory.EmbedderFactory")
    @patch("mem0.memory.falkordb_memory.LlmFactory")
    def test_falkordb_delete_entities(
        self, mock_llm_factory, mock_embedder_factory, mock_falkordb_class, mock_config, mock_embedding_model, mock_llm, mock_falkordb
    ):
        """Test deleting entities from the graph"""
        # Setup mocks
        mock_db, mock_graph = mock_falkordb
        mock_falkordb_class.return_value = mock_db
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Mock delete results
        mock_result = Mock()
        # Header should be list of tuples: (type, column_name)
        mock_result.header = [(0, "source"), (0, "relationship"), (0, "target")]
        mock_result.result_set = [["alice", "knows", "bob"]]
        mock_graph.query.return_value = mock_result

        falkordb_memory = MemoryGraph(mock_config)

        filters = {"user_id": "test_user"}
        to_be_deleted = [
            {"source": "alice", "destination": "bob", "relationship": "knows"}
        ]

        result = falkordb_memory._delete_entities(to_be_deleted, filters)
        
        # Verify delete operation was called
        assert len(result) == 1
        assert mock_graph.query.called

    @patch("mem0.memory.falkordb_memory.falkordb.FalkorDB")
    @patch("mem0.memory.falkordb_memory.EmbedderFactory")
    @patch("mem0.memory.falkordb_memory.LlmFactory")
    def test_falkordb_get_all(
        self, mock_llm_factory, mock_embedder_factory, mock_falkordb_class, mock_config, mock_embedding_model, mock_llm, mock_falkordb
    ):
        """Test getting all relationships from the graph"""
        # Setup mocks
        mock_db, mock_graph = mock_falkordb
        mock_falkordb_class.return_value = mock_db
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Mock get_all results
        mock_result = Mock()
        # Header should be list of tuples: (type, column_name)
        mock_result.header = [(0, "source"), (0, "relationship"), (0, "target")]
        mock_result.result_set = [
            [f"entity_{i}", "knows", f"entity_{i+1}"] for i in range(3)
        ]
        mock_graph.query.return_value = mock_result

        falkordb_memory = MemoryGraph(mock_config)

        filters = {"user_id": "test_user"}
        results = falkordb_memory.get_all(filters, limit=10)

        # Should return formatted results
        assert len(results) == 3
        for result in results:
            assert "source" in result
            assert "relationship" in result
            assert "target" in result

    @patch("mem0.memory.falkordb_memory.falkordb.FalkorDB")
    @patch("mem0.memory.falkordb_memory.EmbedderFactory")
    @patch("mem0.memory.falkordb_memory.LlmFactory")
    def test_falkordb_delete_all(
        self, mock_llm_factory, mock_embedder_factory, mock_falkordb_class, mock_config, mock_embedding_model, mock_llm, mock_falkordb
    ):
        """Test deleting all entities for a user"""
        # Setup mocks
        mock_db, mock_graph = mock_falkordb
        mock_falkordb_class.return_value = mock_db
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Mock delete_all results
        mock_result = Mock()
        mock_result.result_set = []
        mock_graph.query.return_value = mock_result

        falkordb_memory = MemoryGraph(mock_config)

        filters = {"user_id": "test_user", "agent_id": "test_agent"}
        falkordb_memory.delete_all(filters)

        # Verify delete operation was called with proper filters
        mock_graph.query.assert_called()
        call_args = mock_graph.query.call_args
        query = call_args[0][0]
        params = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]
        
        # Should include user_id and agent_id in the query
        assert "user_id: $user_id" in query
        assert "agent_id: $agent_id" in query
        assert params["user_id"] == "test_user"
        assert params["agent_id"] == "test_agent"

    @patch("mem0.memory.falkordb_memory.falkordb.FalkorDB")
    @patch("mem0.memory.falkordb_memory.EmbedderFactory")
    @patch("mem0.memory.falkordb_memory.LlmFactory")
    def test_falkordb_reset(
        self, mock_llm_factory, mock_embedder_factory, mock_falkordb_class, mock_config, mock_embedding_model, mock_llm, mock_falkordb
    ):
        """Test resetting the entire graph"""
        # Setup mocks
        mock_db, mock_graph = mock_falkordb
        mock_falkordb_class.return_value = mock_db
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Mock reset results
        mock_result = Mock()
        mock_result.result_set = []
        mock_graph.query.return_value = mock_result

        falkordb_memory = MemoryGraph(mock_config)

        falkordb_memory.reset()

        # Verify reset operation was called
        mock_graph.query.assert_called()
        call_args = mock_graph.query.call_args
        query = call_args[0][0]
        
        # Should be a MATCH (n) DETACH DELETE n query
        assert "MATCH (n)" in query
        assert "DETACH DELETE n" in query

    @patch("mem0.memory.falkordb_memory.falkordb.FalkorDB")
    @patch("mem0.memory.falkordb_memory.EmbedderFactory")
    @patch("mem0.memory.falkordb_memory.LlmFactory")
    def test_falkordb_search_with_bm25(
        self, mock_llm_factory, mock_embedder_factory, mock_falkordb_class, mock_config, mock_embedding_model, mock_llm, mock_falkordb
    ):
        """Test search functionality with BM25 scoring"""
        # Setup mocks
        mock_db, mock_graph = mock_falkordb
        mock_falkordb_class.return_value = mock_db
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Mock LLM response for entity extraction
        mock_llm.generate_response.return_value = {
            "tool_calls": [
                {
                    "name": "extract_entities",
                    "arguments": {"entities": [{"entity": "alice", "entity_type": "person"}]},
                }
            ]
        }

        # Mock search results
        mock_result = Mock()
        # Header should be list of tuples: (type, column_name)
        mock_result.header = [(0, "source"), (0, "relationship"), (0, "target")]
        mock_result.result_set = [["alice", "knows", "bob"]]
        mock_graph.query.return_value = mock_result

        falkordb_memory = MemoryGraph(mock_config)

        filters = {"user_id": "test_user"}
        query = "alice knows someone"

        results = falkordb_memory.search(query, filters, limit=5)

        # Should return a list (empty if no results, but still a list)
        assert isinstance(results, list)
        # Should have called LLM for entity extraction
        assert mock_llm.generate_response.called

    def test_remove_spaces_from_entities(self):
        """Test utility function for removing spaces from entities"""
        with patch("mem0.memory.falkordb_memory.falkordb.FalkorDB"), \
             patch("mem0.memory.falkordb_memory.EmbedderFactory"), \
             patch("mem0.memory.falkordb_memory.LlmFactory"):
            
            config = Mock()
            config.embedder.provider = "mock"
            config.embedder.config = {"embedding_dims": 384}
            config.vector_store.config = {}
            config.graph_store.config.host = "localhost"
            config.graph_store.config.port = 6379
            config.graph_store.config.username = None
            config.graph_store.config.password = None
            config.graph_store.config.graph_name = "test"
            config.llm.provider = "mock"
            config.llm.config = {}
            
            falkordb_memory = MemoryGraph(config)
            
            entities = [
                {"source": "  alice  ", "destination": "  bob  "},
                {"source": "charlie   ", "destination": " dave"},
            ]
            
            cleaned = falkordb_memory._remove_spaces_from_entities(entities)
            
            assert cleaned[0]["source"] == "alice"
            assert cleaned[0]["destination"] == "bob"
            assert cleaned[1]["source"] == "charlie"
            assert cleaned[1]["destination"] == "dave"