"""
Test cases for Neo4j agent_id functionality fix
Validates that the Cypher syntax error has been resolved
"""

from unittest.mock import Mock, patch

import pytest

from mem0.memory.graph_memory import MemoryGraph


class TestNeo4jAgentIsolation:
    """Test agent_id functionality in Neo4j graph memory operations"""
    
    @pytest.fixture
    def mock_neo4j_driver(self):
        """Mock Neo4j driver for testing"""
        mock_driver = Mock()
        mock_session = Mock()
        mock_driver.session.return_value = mock_session
        return mock_driver, mock_session
    
    @pytest.fixture
    def graph_memory(self, mock_neo4j_driver):
        """Create MemoryGraph instance with mocked driver"""
        driver, session = mock_neo4j_driver
        with patch('mem0.memory.graph_memory.GraphDatabase.driver', return_value=driver):
            memory = MemoryGraph(
                url="bolt://localhost:7687",
                username="neo4j", 
                password="password"
            )
            memory.driver = driver
            return memory, session

    def test_get_all_with_agent_id(self, graph_memory):
        """Test get_all method with agent_id parameter"""
        memory, mock_session = graph_memory
        
        # Mock return data
        mock_session.run.return_value = [
            {"source": "user", "relationship": "KNOWS", "target": "concept"}
        ]
        
        # Test filters with agent_id
        filters = {"user_id": "test_user", "agent_id": "agent_123"}
        _ = memory.get_all(filters, limit=10)
        
        # Verify the query was called
        assert mock_session.run.called
        call_args = mock_session.run.call_args
        
        # Verify agent_id is properly included in parameters
        assert "agent_id" in call_args[1]
        assert call_args[1]["agent_id"] == "agent_123"
        
        # Verify query contains proper node property syntax
        query = call_args[0][0]
        assert "agent_id: $agent_id" in query
        # Verify the old buggy pattern is NOT present
        assert "AND m.agent_id = $agent_id" not in query

    def test_get_all_without_agent_id(self, graph_memory):
        """Test get_all method without agent_id (backward compatibility)"""
        memory, mock_session = graph_memory
        
        mock_session.run.return_value = []
        
        # Test filters without agent_id
        filters = {"user_id": "test_user"}
        memory.get_all(filters, limit=10)
        
        # Verify agent_id is not in parameters when not provided
        call_args = mock_session.run.call_args
        assert "agent_id" not in call_args[1]
        
        # Query should still work without agent_id
        query = call_args[0][0]
        assert "user_id: $user_id" in query

    def test_search_graph_db_with_agent_id(self, graph_memory):
        """Test _search_graph_db method with agent_id"""
        memory, mock_session = graph_memory
        
        # Mock embedding model
        memory.embedding_model = Mock()
        memory.embedding_model.embed.return_value = [0.1, 0.2, 0.3]
        
        mock_session.run.return_value = [
            {"source": "test", "relationship": "RELATES", "target": "concept", "similarity": 0.8}
        ]
        
        filters = {"user_id": "test_user", "agent_id": "agent_123"}
        _ = memory._search_graph_db(["test_node"], filters, limit=5)
        
        # Verify query execution
        assert mock_session.run.called
        call_args = mock_session.run.call_args
        
        # Check agent_id in parameters
        assert call_args[1]["agent_id"] == "agent_123"
        
        # Verify proper node property syntax in query
        query = call_args[0][0]
        assert "agent_id: $agent_id" in query

    def test_delete_entities_with_agent_id(self, graph_memory):
        """Test _delete_entities method with agent_id"""
        memory, mock_session = graph_memory
        
        mock_session.run.return_value = [{"deleted_count": 1}]
        
        to_be_deleted = [{
            "source": "user",
            "destination": "concept", 
            "relationship": "KNOWS"
        }]
        filters = {"user_id": "test_user", "agent_id": "agent_123"}
        
        memory._delete_entities(to_be_deleted, filters)
        
        # Verify query execution
        assert mock_session.run.called
        call_args = mock_session.run.call_args
        
        # Check parameters include agent_id
        assert call_args[1]["agent_id"] == "agent_123"
        
        # Verify proper MATCH clause syntax
        query = call_args[0][0]
        assert "agent_id: $agent_id" in query
        # Ensure old buggy pattern is not present
        assert "WHERE n.agent_id = $agent_id AND m.agent_id = $agent_id" not in query

    def test_cypher_syntax_validation(self, graph_memory):
        """Test that all generated queries have valid Cypher syntax"""
        memory, mock_session = graph_memory
        
        # Test various scenarios to ensure no undefined variables
        test_cases = [
            {"user_id": "user1", "agent_id": "agent1"},
            {"user_id": "user2"},
            {"user_id": "user3", "agent_id": "agent3"}
        ]
        
        for filters in test_cases:
            # Test get_all
            mock_session.run.return_value = []
            memory.get_all(filters)
            
            # Verify no undefined variables in query
            call_args = mock_session.run.call_args
            query = call_args[0][0]
            
            # Ensure all variables in query are properly declared
            # The fix should prevent "Variable 'm' not defined" errors
            assert self._validate_cypher_variables(query), f"Invalid Cypher syntax in query: {query}"

    def _validate_cypher_variables(self, query):
        """
        Basic validation that variables are not referenced without declaration
        This prevents the original "Variable 'm' not defined" error
        """
        # Check for the specific pattern that caused the bug
        if "AND m.agent_id = $agent_id" in query and "MATCH" not in query.split("AND m.agent_id")[0]:
            return False
        return True 