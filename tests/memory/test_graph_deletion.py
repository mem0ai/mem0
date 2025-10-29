from unittest.mock import Mock, patch

import numpy as np
import pytest

from mem0.memory.kuzu_memory import MemoryGraph


class TestKuzuGraphDeletion:
    """Test - Graph memory deletion for Kuzu database"""

    embeddings = {
        "alice": np.random.uniform(0.0, 0.9, 384).tolist(),
        "bob": np.random.uniform(0.0, 0.9, 384).tolist(),
        "charlie": np.random.uniform(0.0, 0.9, 384).tolist(),
        "dave": np.random.uniform(0.0, 0.9, 384).tolist(),
    }

    @pytest.fixture
    def mock_config(self):
        """Create mock configuration for Kuzu testing"""
        config = Mock()
        config.embedder.provider = "mock_embedder"
        config.embedder.config = {"model": "mock_model"}
        config.vector_store.config = {"dimensions": 384}
        config.graph_store.config.db = ":memory:"
        config.llm.provider = "mock_llm"
        config.llm.config = {"api_key": "test_key"}
        return config

    @pytest.fixture
    def mock_embedding_model(self):
        """Create mock embedding model"""
        mock_model = Mock()
        mock_model.config.embedding_dims = 384

        def mock_embed(text):
            return self.embeddings.get(text, np.random.uniform(0.0, 0.9, 384).tolist())

        mock_model.embed.side_effect = mock_embed
        return mock_model

    @pytest.fixture
    def mock_llm(self):
        """Create mock LLM for entity extraction"""
        mock_llm = Mock()
        mock_llm.generate_response.return_value = {
            "tool_calls": [
                {
                    "name": "extract_entities",
                    "arguments": {"entities": [{"entity": "alice", "entity_type": "person"}]},
                }
            ]
        }
        return mock_llm

    @patch("mem0.memory.kuzu_memory.EmbedderFactory")
    @patch("mem0.memory.kuzu_memory.LlmFactory")
    def test_delete_single_relationship(
        self, mock_llm_factory, mock_embedder_factory, mock_config, mock_embedding_model, mock_llm
    ):
        """Test - Deletion removes specified relationship between entities"""
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        kuzu_memory = MemoryGraph(mock_config)
        
        filters = {"user_id": "test_user"}
        
        # Add single relationship
        data_add = [
            {"source": "alice", "destination": "bob", "relationship": "knows"},
        ]
        
        kuzu_memory._add_entities(data_add, filters, {})
        
        # Verify it was added
        assert get_node_count(kuzu_memory) == 2
        assert get_edge_count(kuzu_memory) == 1
        
        # Delete the relationship
        data_delete = [
            {"source": "alice", "destination": "bob", "relationship": "knows"},
        ]
        
        result = kuzu_memory._delete_entities(data_delete, filters)
        
        # Verify relationship was deleted but nodes remain
        assert len(result) > 0
        assert get_edge_count(kuzu_memory) == 0
        # Nodes stay even when relationships are deleted
        assert get_node_count(kuzu_memory) == 2

    @patch("mem0.memory.kuzu_memory.EmbedderFactory")
    @patch("mem0.memory.kuzu_memory.LlmFactory")
    def test_delete_one_of_multiple_relationships(
        self, mock_llm_factory, mock_embedder_factory, mock_config, mock_embedding_model, mock_llm
    ):
        """Test - Deleting one relationship preserves other relationships for same entities"""
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        kuzu_memory = MemoryGraph(mock_config)
        
        filters = {"user_id": "test_user"}
        
        # Add multiple relationships
        data1 = [
            {"source": "alice", "destination": "bob", "relationship": "knows"},
        ]
        data2 = [
            {"source": "alice", "destination": "bob", "relationship": "likes"},
        ]
        
        kuzu_memory._add_entities(data1, filters, {})
        kuzu_memory._add_entities(data2, filters, {})
        
        # Verify both relationships exist
        assert get_node_count(kuzu_memory) == 2
        assert get_edge_count(kuzu_memory) == 2
        
        # Delete only one relationship
        data_delete = [
            {"source": "alice", "destination": "bob", "relationship": "knows"},
        ]
        
        result = kuzu_memory._delete_entities(data_delete, filters)
        
        # Verify only one relationship was deleted
        assert len(result) > 0
        assert get_edge_count(kuzu_memory) == 1
        assert get_node_count(kuzu_memory) == 2

    @patch("mem0.memory.kuzu_memory.EmbedderFactory")
    @patch("mem0.memory.kuzu_memory.LlmFactory")
    def test_delete_with_filters_isolates_user_data(
        self, mock_llm_factory, mock_embedder_factory, mock_config, mock_embedding_model, mock_llm
    ):
        """Test - Deletion with filters only affects data for specified user/agent/run"""
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        kuzu_memory = MemoryGraph(mock_config)
        
        # Add data for user1
        filters_user1 = {"user_id": "user1", "agent_id": "agent1"}
        data_user1 = [
            {"source": "alice", "destination": "bob", "relationship": "knows"},
        ]
        kuzu_memory._add_entities(data_user1, filters_user1, {})
        
        # Add data for user2
        filters_user2 = {"user_id": "user2", "agent_id": "agent2"}
        data_user2 = [
            {"source": "alice", "destination": "bob", "relationship": "knows"},
        ]
        kuzu_memory._add_entities(data_user2, filters_user2, {})
        
        # Verify both exist (4 nodes: 2 alices, 2 bobs; 2 edges)
        total_nodes = get_node_count(kuzu_memory)
        total_edges = get_edge_count(kuzu_memory)
        assert total_nodes >= 2  # At minimum 2 nodes
        assert total_edges == 2
        
        # Delete user1's data
        data_delete = [
            {"source": "alice", "destination": "bob", "relationship": "knows"},
        ]
        result = kuzu_memory._delete_entities(data_delete, filters_user1)
        
        # Verify only user1's relationship was deleted
        assert len(result) > 0
        assert get_edge_count(kuzu_memory) == 1

    @patch("mem0.memory.kuzu_memory.EmbedderFactory")
    @patch("mem0.memory.kuzu_memory.LlmFactory")
    def test_delete_nonexistent_relationship(
        self, mock_llm_factory, mock_embedder_factory, mock_config, mock_embedding_model, mock_llm
    ):
        """Test - Attempting to delete nonexistent relationship returns empty result without errors"""
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        kuzu_memory = MemoryGraph(mock_config)
        
        filters = {"user_id": "test_user"}
        
        # Try to delete relationship that doesn't exist
        data_delete = [
            {"source": "nonexistent", "destination": "entity", "relationship": "knows"},
        ]
        
        result = kuzu_memory._delete_entities(data_delete, filters)
        
        # Should return empty result without throwing errors
        assert result is not None
        assert len(result) >= 0
        assert get_node_count(kuzu_memory) == 0
        assert get_edge_count(kuzu_memory) == 0

    @patch("mem0.memory.kuzu_memory.EmbedderFactory")
    @patch("mem0.memory.kuzu_memory.LlmFactory")
    def test_delete_all_removes_all_user_data(
        self, mock_llm_factory, mock_embedder_factory, mock_config, mock_embedding_model, mock_llm
    ):
        """Test - delete_all method removes all nodes and relationships for specified filters"""
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        kuzu_memory = MemoryGraph(mock_config)
        
        filters = {"user_id": "test_user"}
        
        # Add multiple relationships
        data = [
            {"source": "alice", "destination": "bob", "relationship": "knows"},
            {"source": "bob", "destination": "charlie", "relationship": "knows"},
            {"source": "charlie", "destination": "alice", "relationship": "likes"},
        ]
        
        kuzu_memory._add_entities(data, filters, {})
        
        # Verify data was added
        assert get_node_count(kuzu_memory) > 0
        assert get_edge_count(kuzu_memory) > 0
        
        # Delete all
        kuzu_memory.delete_all(filters)
        
        # Verify everything was deleted
        assert get_node_count(kuzu_memory) == 0
        assert get_edge_count(kuzu_memory) == 0

    @patch("mem0.memory.kuzu_memory.EmbedderFactory")
    @patch("mem0.memory.kuzu_memory.LlmFactory")
    def test_add_then_delete_then_readd(
        self, mock_llm_factory, mock_embedder_factory, mock_config, mock_embedding_model, mock_llm
    ):
        """Test - Entities can be re-added after deletion"""
        mock_embedder_factory.create.return_value = mock_embedding_model
        mock_llm_factory.create.return_value = mock_llm

        kuzu_memory = MemoryGraph(mock_config)
        
        filters = {"user_id": "test_user"}
        
        data = [
            {"source": "alice", "destination": "bob", "relationship": "knows"},
        ]
        
        # Add
        kuzu_memory._add_entities(data, filters, {})
        assert get_edge_count(kuzu_memory) == 1
        
        # Delete
        kuzu_memory._delete_entities(data, filters)
        assert get_edge_count(kuzu_memory) == 0
        
        # Re-add
        kuzu_memory._add_entities(data, filters, {})
        assert get_edge_count(kuzu_memory) == 1


def get_node_count(kuzu_memory):
    """Helper - Count total nodes in Kuzu graph"""
    results = kuzu_memory.kuzu_execute(
        """
        MATCH (n)
        RETURN COUNT(n) as count
        """
    )
    return int(results[0]['count'])


def get_edge_count(kuzu_memory):
    """Helper - Count total edges in Kuzu graph"""
    results = kuzu_memory.kuzu_execute(
        """
        MATCH (n)-[e]->(m)
        RETURN COUNT(e) as count
        """
    )
    return int(results[0]['count'])

