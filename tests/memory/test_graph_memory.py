import pytest
from unittest.mock import Mock, patch

from mem0.configs.base import MemoryConfig
from mem0.memory.graph_memory import MemoryGraph


@pytest.fixture
def mock_config():
    config = Mock(spec=MemoryConfig)
    config.graph_store = Mock()
    config.graph_store.config = Mock()
    config.graph_store.config.url = "bolt://localhost:7687"
    config.graph_store.config.username = "neo4j"
    config.graph_store.config.password = "password"
    config.graph_store.llm = Mock()
    config.graph_store.llm.provider = "mock"
    config.embedder = Mock()
    config.embedder.provider = "mock"
    config.embedder.config = {}
    config.vector_store = Mock()
    config.vector_store.config = {}
    config.llm = Mock()
    config.llm.provider = "mock"
    config.llm.config = {}
    return config

@pytest.fixture
def memory_graph(mock_config):
    with patch('mem0.memory.graph_memory.Neo4jGraph') as mock_neo4j:
        mock_neo4j.return_value = Mock()
        mock_neo4j.return_value.query.return_value = [
            {"source": "John", "relationship": "knows", "target": "Jane"},
            {"source": "Jane", "relationship": "works_with", "target": "Bob"}
        ]
        with patch('mem0.utils.factory.EmbedderFactory.create') as mock_embedder:
            mock_embedder.return_value = Mock()
            with patch('mem0.utils.factory.LlmFactory.create') as mock_llm:
                mock_llm.return_value = Mock()
                graph = MemoryGraph(mock_config)
                return graph

def test_memory_graph_initialization(memory_graph, mock_config):
    """Test that MemoryGraph initializes correctly with config"""
    assert memory_graph.config == mock_config
    assert memory_graph.threshold == 0.7
    assert memory_graph.user_id is None
    assert memory_graph.llm_provider == "mock"

def test_search_with_filters(memory_graph):
    """Test search functionality with filters"""
    query = "test query"
    filters = {"type": "person", "user_id": "test_user"}
    limit = 10
    
    # Mock the internal methods
    memory_graph._retrieve_nodes_from_data = Mock(return_value={"node1": "type1", "node2": "type2"})
    memory_graph._search_graph_db = Mock(return_value=[
        {"source": "John", "relatationship": "knows", "destination": "Jane"},
        {"source": "Jane", "relatationship": "works_with", "destination": "Bob"}
    ])
    
    result = memory_graph.search(query, filters, limit)
    
    assert isinstance(result, list)
    assert len(result) > 0
    assert "source" in result[0]
    assert "relationship" in result[0]
    assert "destination" in result[0]

def test_delete_all(memory_graph):
    """Test delete_all functionality"""
    filters = {"type": "person", "user_id": "test_user"}
    
    # Mock the graph query method
    memory_graph.graph.query = Mock()
    
    memory_graph.delete_all(filters)
    
    memory_graph.graph.query.assert_called_once()

def test_get_all(memory_graph):
    """Test get_all functionality"""
    filters = {"type": "person", "user_id": "test_user"}
    limit = 10
    
    result = memory_graph.get_all(filters, limit)
    
    assert isinstance(result, list)
    assert len(result) > 0
    assert "source" in result[0]
    assert "relationship" in result[0]
    assert "target" in result[0]

def test_remove_spaces_from_entities(memory_graph):
    """Test _remove_spaces_from_entities helper method"""
    entity_list = [
        {"source": "John Doe", "relationship": "knows", "destination": "Jane Smith"},
        {"source": "Jane Smith", "relationship": "works with", "destination": "Bob Wilson"},
        {"source": "Bob Wilson", "relationship": "reports to", "destination": "John Doe"}
    ]
    expected = [
        {"source": "john_doe", "relationship": "knows", "destination": "jane_smith"},
        {"source": "jane_smith", "relationship": "works_with", "destination": "bob_wilson"},
        {"source": "bob_wilson", "relationship": "reports_to", "destination": "john_doe"}
    ]
    
    result = memory_graph._remove_spaces_from_entities(entity_list)
    
    assert result == expected 
    