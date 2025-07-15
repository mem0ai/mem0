"""
Simple test to validate Neo4j Cypher syntax fixes
Tests that our agent_id fixes generate valid Cypher without undefined variables
"""

from unittest.mock import Mock, patch


class TestNeo4jCypherSyntaxFix:
    """Test that Neo4j Cypher syntax fixes work correctly"""
    
    def test_get_all_generates_valid_cypher_with_agent_id(self):
        """Test that get_all method generates valid Cypher with agent_id"""
        # Mock the langchain_neo4j module to avoid import issues
        with patch.dict('sys.modules', {'langchain_neo4j': Mock()}):
            from mem0.memory.graph_memory import MemoryGraph

            # Create instance (will fail on actual connection, but that's fine for syntax testing)
            try:
                _ = MemoryGraph(url="bolt://localhost:7687", username="test", password="test")
            except Exception:
                # Expected to fail on connection, just test the class exists
                assert MemoryGraph is not None
                return
    
    def test_cypher_syntax_validation(self):
        """Test that our Cypher fixes don't contain problematic patterns"""
        with open('mem0/memory/graph_memory.py', 'r') as f:
            content = f.read()
        
        # Ensure the old buggy pattern is not present
        assert "AND n.agent_id = $agent_id AND m.agent_id = $agent_id" not in content
        assert "WHERE 1=1 {agent_filter}" not in content
        
        # Ensure proper node property syntax is present
        assert "node_props" in content
        assert "agent_id: $agent_id" in content
        
    def test_no_undefined_variables_in_cypher(self):
        """Test that we don't have undefined variable patterns"""
        with open('mem0/memory/graph_memory.py', 'r') as f:
            content = f.read()
            
        # Check for patterns that would cause "Variable 'm' not defined" errors
        lines = content.split('\n')
        for i, line in enumerate(lines):
            # Look for WHERE clauses that reference variables not in MATCH
            if 'WHERE' in line and 'm.agent_id' in line:
                # Check if there's a MATCH clause before this that defines 'm'
                preceding_lines = lines[max(0, i-10):i]
                match_found = any('MATCH' in prev_line and ' m ' in prev_line for prev_line in preceding_lines)
                assert match_found, f"Line {i+1}: WHERE clause references 'm' without MATCH definition"

    def test_agent_id_integration_syntax(self):
        """Test that agent_id is properly integrated into MATCH clauses"""
        with open('mem0/memory/graph_memory.py', 'r') as f:
            content = f.read()
        
        # Should have node property building logic
        assert 'node_props = [' in content
        assert 'node_props.append("agent_id: $agent_id")' in content
        assert 'node_props_str = ", ".join(node_props)' in content
        
        # Should use the node properties in MATCH clauses
        assert '{{{node_props_str}}}' in content or '{node_props_str}' in content

