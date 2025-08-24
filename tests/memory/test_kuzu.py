import numpy as np
import pytest
from unittest.mock import Mock, patch
from mem0.memory.kuzu_memory import MemoryGraph


class TestKuzu:
    """Test that Kuzu memory works correctly"""

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
        config.graph_store.config.db = ":memory:"

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
            return self.embeddings[text]

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

    @patch("mem0.memory.kuzu_memory.EmbedderFactory")
    @patch("mem0.memory.kuzu_memory.LlmFactory")
    def test_kuzu_memory_initialization(
        self, mock_llm_factory, mock_embedder_factory, mock_config, mock_embedding_model, mock_llm
    ):
        """Test that Kuzu memory initializes correctly"""
        # Setup mocks
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        # Create instance
        kuzu_memory = MemoryGraph(mock_config)

        # Verify initialization
        assert kuzu_memory.config == mock_config
        assert kuzu_memory.embedding_model == mock_embedding_model
        assert kuzu_memory.embedding_dims == 384
        assert kuzu_memory.llm == mock_llm
        assert kuzu_memory.threshold == 0.7


    @patch("mem0.memory.kuzu_memory.EmbedderFactory")
    @patch("mem0.memory.kuzu_memory.LlmFactory")
    def test_kuzu(self, mock_llm_factory, mock_embedder_factory, mock_config, mock_embedding_model, mock_llm):
        """Test adding memory to the graph"""
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        kuzu_memory = MemoryGraph(mock_config)

        filters = {"user_id": "test_user", "agent_id": "test_agent", "run_id": "test_run"}
        data1 = [
            {"source": "alice", "destination": "bob", "relationship": "knows"},
            {"source": "bob", "destination": "charlie", "relationship": "knows"},
            {"source": "charlie", "destination": "alice", "relationship": "knows"},
        ]
        data2 = [
            {"source": "charlie", "destination": "alice", "relationship": "likes"},
        ]

        result = kuzu_memory._add_entities(data1, filters, {})
        assert result[0] == [{"source": "alice", "relationship": "knows", "target": "bob"}]
        assert result[1] == [{"source": "bob", "relationship": "knows", "target": "charlie"}]
        assert result[2] == [{"source": "charlie", "relationship": "knows", "target": "alice"}]
        assert get_node_count(kuzu_memory) == 3
        assert get_edge_count(kuzu_memory) == 3

        result = kuzu_memory._add_entities(data2, filters, {})
        assert result[0] == [{"source": "charlie", "relationship": "likes", "target": "alice"}]
        assert get_node_count(kuzu_memory) == 3
        assert get_edge_count(kuzu_memory) == 4

        data3 = [
            {"source": "dave", "destination": "alice", "relationship": "admires"}
        ]
        result = kuzu_memory._add_entities(data3, filters, {})
        assert result[0] == [{"source": "dave", "relationship": "admires", "target": "alice"}]
        assert get_node_count(kuzu_memory) == 4  # dave is new
        assert get_edge_count(kuzu_memory) == 5

        results = kuzu_memory.get_all(filters)
        assert set([f"{result['source']}_{result['relationship']}_{result['target']}" for result in results]) == set([
            "alice_knows_bob",
            "bob_knows_charlie",
            "charlie_likes_alice",
            "charlie_knows_alice",
            "dave_admires_alice"
        ])

        results = kuzu_memory._search_graph_db(["bob"], filters, threshold=0.8)
        assert set([f"{result['source']}_{result['relationship']}_{result['destination']}" for result in results]) == set([
            "alice_knows_bob",
            "bob_knows_charlie",
        ])

        result = kuzu_memory._delete_entities(data2, filters)
        assert result[0] == [{"source": "charlie", "relationship": "likes", "target": "alice"}]
        assert get_node_count(kuzu_memory) == 4
        assert get_edge_count(kuzu_memory) == 4

        result = kuzu_memory._delete_entities(data1, filters)
        assert result[0] == [{"source": "alice", "relationship": "knows", "target": "bob"}]
        assert result[1] == [{"source": "bob", "relationship": "knows", "target": "charlie"}]
        assert result[2] == [{"source": "charlie", "relationship": "knows", "target": "alice"}]
        assert get_node_count(kuzu_memory) == 4
        assert get_edge_count(kuzu_memory) == 1

        result = kuzu_memory.delete_all(filters)
        assert get_node_count(kuzu_memory) == 0
        assert get_edge_count(kuzu_memory) == 0

        result = kuzu_memory._add_entities(data2, filters, {})
        assert result[0] == [{"source": "charlie", "relationship": "likes", "target": "alice"}]
        assert get_node_count(kuzu_memory) == 2
        assert get_edge_count(kuzu_memory) == 1

        result = kuzu_memory.reset()
        assert get_node_count(kuzu_memory) == 0
        assert get_edge_count(kuzu_memory) == 0

def get_node_count(kuzu_memory):
    results = kuzu_memory.kuzu_execute(
        """
        MATCH (n)
        RETURN COUNT(n) as count
        """
    )
    return int(results[0]['count'])

def get_edge_count(kuzu_memory):
    results = kuzu_memory.kuzu_execute(
        """
        MATCH (n)-[e]->(m)
        RETURN COUNT(e) as count
        """
    )
    return int(results[0]['count'])
