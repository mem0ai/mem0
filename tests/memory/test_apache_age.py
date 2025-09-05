import numpy as np
import pytest
from unittest.mock import Mock, patch, MagicMock
from mem0.memory.apache_age_memory import MemoryGraph


class TestApacheAge:
    """Test that Apache AGE memory works correctly"""

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
        config.embedder.config = {"model": "mock_model"}
        config.vector_store.config = {"dimensions": 384}

        # Mock graph store config
        config.graph_store.config.host = "localhost"
        config.graph_store.config.port = 5432
        config.graph_store.config.database = "test_db"
        config.graph_store.config.username = "test_user"
        config.graph_store.config.password = "test_pass"
        config.graph_store.config.graph_name = "test_graph"
        config.graph_store.config.base_label = True
        config.graph_store.custom_prompt = None

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
    def mock_connection(self):
        """Create a mock PostgreSQL connection"""
        mock_conn = Mock()
        mock_conn.autocommit = True
        
        # Mock cursor
        mock_cursor = Mock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_cursor.execute = Mock()
        mock_cursor.fetchall = Mock(return_value=[])
        
        mock_conn.cursor.return_value = mock_cursor
        return mock_conn

    @patch("mem0.memory.apache_age_memory.psycopg2")
    @patch("mem0.memory.apache_age_memory.age")
    @patch("mem0.memory.apache_age_memory.EmbedderFactory")
    @patch("mem0.memory.apache_age_memory.LlmFactory")
    def test_apache_age_memory_initialization(
        self, mock_llm_factory, mock_embedder_factory, mock_age, mock_psycopg2, 
        mock_config, mock_embedding_model, mock_llm, mock_connection
    ):
        """Test that Apache AGE memory initializes correctly"""
        # Setup mocks
        mock_psycopg2.connect.return_value = mock_connection
        mock_age.setUpAge = Mock()
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Create instance
        age_memory = MemoryGraph(mock_config)

        # Verify initialization
        assert age_memory.config == mock_config
        assert age_memory.connection == mock_connection
        assert age_memory.graph_name == "test_graph"
        assert age_memory.embedding_model == mock_embedding_model
        assert age_memory.node_label == "__Entity__"
        assert age_memory.llm == mock_llm
        assert age_memory.threshold == 0.7

        # Verify PostgreSQL connection was established
        mock_psycopg2.connect.assert_called_once_with(
            host="localhost",
            port=5432,
            database="test_db",
            user="test_user",
            password="test_pass"
        )

        # Verify AGE was set up
        mock_age.setUpAge.assert_called_once_with(mock_connection, "test_graph")

    @patch("mem0.memory.apache_age_memory.psycopg2")
    @patch("mem0.memory.apache_age_memory.age")
    @patch("mem0.memory.apache_age_memory.EmbedderFactory")
    @patch("mem0.memory.apache_age_memory.LlmFactory")
    def test_execute_cypher(
        self, mock_llm_factory, mock_embedder_factory, mock_age, mock_psycopg2,
        mock_config, mock_embedding_model, mock_llm, mock_connection
    ):
        """Test Cypher query execution"""
        # Setup mocks
        mock_psycopg2.connect.return_value = mock_connection
        mock_age.setUpAge = Mock()
        mock_age.age_to_dict.return_value = {"test": "result"}
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Mock cursor with RealDictCursor
        mock_cursor = Mock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_cursor.execute = Mock()
        mock_cursor.fetchall = Mock(return_value=[{"result": "test_agtype"}])
        
        mock_connection.cursor.return_value = mock_cursor

        # Create instance
        age_memory = MemoryGraph(mock_config)

        # Test query execution
        result = age_memory._execute_cypher("MATCH (n) RETURN n", {"param": "value"})

        # Verify cursor was used correctly
        mock_connection.cursor.assert_called()
        mock_cursor.execute.assert_called()
        mock_age.age_to_dict.assert_called_with("test_agtype")
        assert result == [{"test": "result"}]

    @patch("mem0.memory.apache_age_memory.psycopg2")
    @patch("mem0.memory.apache_age_memory.age")
    @patch("mem0.memory.apache_age_memory.EmbedderFactory")
    @patch("mem0.memory.apache_age_memory.LlmFactory")
    def test_add_method(
        self, mock_llm_factory, mock_embedder_factory, mock_age, mock_psycopg2,
        mock_config, mock_embedding_model, mock_llm, mock_connection
    ):
        """Test the add method"""
        # Setup mocks
        mock_psycopg2.connect.return_value = mock_connection
        mock_age.setUpAge = Mock()
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Mock cursor
        mock_cursor = Mock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_cursor.execute = Mock()
        mock_cursor.fetchall = Mock(return_value=[])
        
        mock_connection.cursor.return_value = mock_cursor

        # Create instance
        age_memory = MemoryGraph(mock_config)

        # Mock the private methods
        age_memory._retrieve_nodes_from_data = Mock(return_value={"alice": "person", "bob": "person"})
        age_memory._establish_nodes_relations_from_data = Mock(return_value=[
            {"source": "alice", "destination": "bob", "relationship": "knows"}
        ])
        age_memory._search_graph_db = Mock(return_value=[])
        age_memory._get_delete_entities_from_search_output = Mock(return_value=[])
        age_memory._delete_entities = Mock(return_value=[])
        age_memory._add_entities = Mock(return_value=[{"source": "alice", "relationship": "knows", "target": "bob"}])

        # Test add method
        filters = {"user_id": "test_user"}
        result = age_memory.add("Alice knows Bob", filters)

        # Verify the method calls
        age_memory._retrieve_nodes_from_data.assert_called_once_with("Alice knows Bob", filters)
        age_memory._establish_nodes_relations_from_data.assert_called_once()
        age_memory._search_graph_db.assert_called_once()
        age_memory._get_delete_entities_from_search_output.assert_called_once()
        age_memory._delete_entities.assert_called_once()
        age_memory._add_entities.assert_called_once()

        # Verify result structure
        assert "deleted_entities" in result
        assert "added_entities" in result

    @patch("mem0.memory.apache_age_memory.psycopg2")
    @patch("mem0.memory.apache_age_memory.age")
    @patch("mem0.memory.apache_age_memory.EmbedderFactory")
    @patch("mem0.memory.apache_age_memory.LlmFactory")
    def test_search_method(
        self, mock_llm_factory, mock_embedder_factory, mock_age, mock_psycopg2,
        mock_config, mock_embedding_model, mock_llm, mock_connection
    ):
        """Test the search method"""
        # Setup mocks
        mock_psycopg2.connect.return_value = mock_connection
        mock_age.setUpAge = Mock()
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Mock cursor
        mock_cursor = Mock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_cursor.execute = Mock()
        mock_cursor.fetchall = Mock(return_value=[])
        
        mock_connection.cursor.return_value = mock_cursor

        # Create instance
        age_memory = MemoryGraph(mock_config)

        # Mock the private methods
        age_memory._retrieve_nodes_from_data = Mock(return_value={"alice": "person"})
        age_memory._search_graph_db = Mock(return_value=[
            {"source": "alice", "relationship": "knows", "destination": "bob"},
            {"source": "bob", "relationship": "likes", "destination": "charlie"}
        ])

        # Test search method
        filters = {"user_id": "test_user"}
        result = age_memory.search("Alice", filters)

        # Verify the method calls
        age_memory._retrieve_nodes_from_data.assert_called_once_with("Alice", filters)
        age_memory._search_graph_db.assert_called_once()

        # Verify result is a list
        assert isinstance(result, list)

    @patch("mem0.memory.apache_age_memory.psycopg2")
    @patch("mem0.memory.apache_age_memory.age")
    @patch("mem0.memory.apache_age_memory.EmbedderFactory")
    @patch("mem0.memory.apache_age_memory.LlmFactory")
    def test_delete_all_method(
        self, mock_llm_factory, mock_embedder_factory, mock_age, mock_psycopg2,
        mock_config, mock_embedding_model, mock_llm, mock_connection
    ):
        """Test the delete_all method"""
        # Setup mocks
        mock_psycopg2.connect.return_value = mock_connection
        mock_age.setUpAge = Mock()
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Mock cursor
        mock_cursor = Mock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_cursor.execute = Mock()
        mock_cursor.fetchall = Mock(return_value=[])
        
        mock_connection.cursor.return_value = mock_cursor

        # Create instance
        age_memory = MemoryGraph(mock_config)
        age_memory._execute_cypher = Mock()

        # Test delete_all method
        filters = {"user_id": "test_user", "agent_id": "test_agent"}
        age_memory.delete_all(filters)

        # Verify _execute_cypher was called
        age_memory._execute_cypher.assert_called_once()
        call_args = age_memory._execute_cypher.call_args
        cypher_query = call_args[0][0]
        params = call_args[0][1]

        # Verify the query structure
        assert "MATCH (n:__Entity__)" in cypher_query
        assert "DETACH DELETE n" in cypher_query
        assert params["user_id"] == "test_user"
        assert params["agent_id"] == "test_agent"

    @patch("mem0.memory.apache_age_memory.psycopg2")
    @patch("mem0.memory.apache_age_memory.age")
    @patch("mem0.memory.apache_age_memory.EmbedderFactory")
    @patch("mem0.memory.apache_age_memory.LlmFactory")
    def test_get_all_method(
        self, mock_llm_factory, mock_embedder_factory, mock_age, mock_psycopg2,
        mock_config, mock_embedding_model, mock_llm, mock_connection
    ):
        """Test the get_all method"""
        # Setup mocks
        mock_psycopg2.connect.return_value = mock_connection
        mock_age.setUpAge = Mock()
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Mock cursor
        mock_cursor = Mock()
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=None)
        mock_cursor.execute = Mock()
        mock_cursor.fetchall = Mock(return_value=[])
        
        mock_connection.cursor.return_value = mock_cursor

        # Create instance
        age_memory = MemoryGraph(mock_config)
        age_memory._execute_cypher = Mock(return_value=[
            {"source": "alice", "relationship": "knows", "target": "bob"},
            {"source": "bob", "relationship": "likes", "target": "charlie"}
        ])

        # Test get_all method
        filters = {"user_id": "test_user"}
        result = age_memory.get_all(filters)

        # Verify _execute_cypher was called
        age_memory._execute_cypher.assert_called_once()

        # Verify result structure
        assert len(result) == 2
        assert result[0]["source"] == "alice"
        assert result[0]["relationship"] == "knows"
        assert result[0]["target"] == "bob"

    def test_compute_cosine_similarity(self):
        """Test cosine similarity computation"""
        # Create a mock instance to test the static method
        with patch("mem0.memory.apache_age_memory.psycopg2"), \
             patch("mem0.memory.apache_age_memory.age"), \
             patch("mem0.memory.apache_age_memory.EmbedderFactory"), \
             patch("mem0.memory.apache_age_memory.LlmFactory"):
            
            config = Mock()
            config.graph_store.config.host = "localhost"
            config.graph_store.config.port = 5432
            config.graph_store.config.database = "test_db"
            config.graph_store.config.username = "test_user"
            config.graph_store.config.password = "test_pass"
            config.graph_store.config.graph_name = "test_graph"
            config.graph_store.config.base_label = True
            
            age_memory = MemoryGraph(config)

            # Test identical vectors
            vec1 = [1, 0, 0]
            vec2 = [1, 0, 0]
            similarity = age_memory._compute_cosine_similarity(vec1, vec2)
            assert abs(similarity - 1.0) < 1e-6

            # Test orthogonal vectors
            vec1 = [1, 0, 0]
            vec2 = [0, 1, 0]
            similarity = age_memory._compute_cosine_similarity(vec1, vec2)
            assert abs(similarity - 0.0) < 1e-6

            # Test opposite vectors
            vec1 = [1, 0, 0]
            vec2 = [-1, 0, 0]
            similarity = age_memory._compute_cosine_similarity(vec1, vec2)
            assert abs(similarity - (-1.0)) < 1e-6
