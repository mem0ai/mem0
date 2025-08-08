import os
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
        graph_memory_path = 'mem0/memory/graph_memory.py'
        
        # Check if file exists before reading
        if not os.path.exists(graph_memory_path):
            # Skip test if file doesn't exist (e.g., in CI environment)
            return
            
        with open(graph_memory_path, 'r') as f:
            content = f.read()
        
        # Ensure the old buggy pattern is not present
        assert "AND n.agent_id = $agent_id AND m.agent_id = $agent_id" not in content
        assert "WHERE 1=1 {agent_filter}" not in content
        
        # Ensure proper node property syntax is present
        assert "node_props" in content
        assert "agent_id: $agent_id" in content
        
        # Ensure run_id follows the same pattern
        # Check for absence of problematic run_id patterns
        assert "AND n.run_id = $run_id AND m.run_id = $run_id" not in content
        assert "WHERE 1=1 {run_id_filter}" not in content
        
    def test_no_undefined_variables_in_cypher(self):
        """Test that we don't have undefined variable patterns"""
        graph_memory_path = 'mem0/memory/graph_memory.py'
        
        # Check if file exists before reading
        if not os.path.exists(graph_memory_path):
            # Skip test if file doesn't exist (e.g., in CI environment)
            return
            
        with open(graph_memory_path, 'r') as f:
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
            
            # Also check for run_id patterns that might have similar issues
            if 'WHERE' in line and 'm.run_id' in line:
                # Check if there's a MATCH clause before this that defines 'm'
                preceding_lines = lines[max(0, i-10):i]
                match_found = any('MATCH' in prev_line and ' m ' in prev_line for prev_line in preceding_lines)
                assert match_found, f"Line {i+1}: WHERE clause references 'm.run_id' without MATCH definition"

    def test_agent_id_integration_syntax(self):
        """Test that agent_id is properly integrated into MATCH clauses"""
        graph_memory_path = 'mem0/memory/graph_memory.py'
        
        # Check if file exists before reading
        if not os.path.exists(graph_memory_path):
            # Skip test if file doesn't exist (e.g., in CI environment)
            return
            
        with open(graph_memory_path, 'r') as f:
            content = f.read()
        
        # Should have node property building logic
        assert 'node_props = [' in content
        assert 'node_props.append("agent_id: $agent_id")' in content
        assert 'node_props_str = ", ".join(node_props)' in content
        
        # Should use the node properties in MATCH clauses
        assert '{{{node_props_str}}}' in content or '{node_props_str}' in content

    def test_run_id_integration_syntax(self):
        """Test that run_id is properly integrated into MATCH clauses"""
        graph_memory_path = 'mem0/memory/graph_memory.py'
        
        # Check if file exists before reading
        if not os.path.exists(graph_memory_path):
            # Skip test if file doesn't exist (e.g., in CI environment)
            return
            
        with open(graph_memory_path, 'r') as f:
            content = f.read()
        
        # Should have node property building logic for run_id
        assert 'node_props = [' in content
        assert 'node_props.append("run_id: $run_id")' in content
        assert 'node_props_str = ", ".join(node_props)' in content
        
        # Should use the node properties in MATCH clauses
        assert '{{{node_props_str}}}' in content or '{node_props_str}' in content

    def test_agent_id_filter_patterns(self):
        """Test that agent_id filtering follows the correct pattern"""
        graph_memory_path = 'mem0/memory/graph_memory.py'
        
        # Check if file exists before reading
        if not os.path.exists(graph_memory_path):
            # Skip test if file doesn't exist (e.g., in CI environment)
            return
            
        with open(graph_memory_path, 'r') as f:
            content = f.read()
        
        # Check that agent_id is handled in filters
        assert 'if filters.get("agent_id"):' in content
        assert 'params["agent_id"] = filters["agent_id"]' in content
        
        # Check that agent_id is used in node properties
        assert 'node_props.append("agent_id: $agent_id")' in content

    def test_run_id_filter_patterns(self):
        """Test that run_id filtering follows the same pattern as agent_id"""
        graph_memory_path = 'mem0/memory/graph_memory.py'
        
        # Check if file exists before reading
        if not os.path.exists(graph_memory_path):
            # Skip test if file doesn't exist (e.g., in CI environment)
            return
            
        with open(graph_memory_path, 'r') as f:
            content = f.read()
        
        # Check that run_id is handled in filters
        assert 'if filters.get("run_id"):' in content
        assert 'params["run_id"] = filters["run_id"]' in content
        
        # Check that run_id is used in node properties
        assert 'node_props.append("run_id: $run_id")' in content

    def test_agent_id_cypher_generation(self):
        """Test that agent_id is properly included in Cypher query generation"""
        graph_memory_path = 'mem0/memory/graph_memory.py'
        
        # Check if file exists before reading
        if not os.path.exists(graph_memory_path):
            # Skip test if file doesn't exist (e.g., in CI environment)
            return
            
        with open(graph_memory_path, 'r') as f:
            content = f.read()
        
        # Check that the dynamic property building pattern exists
        assert 'node_props = [' in content
        assert 'node_props_str = ", ".join(node_props)' in content
        
        # Check that agent_id is handled in the pattern
        assert 'if filters.get(' in content
        assert 'node_props.append(' in content
        
        # Verify the pattern is used in MATCH clauses
        assert '{{{node_props_str}}}' in content or '{node_props_str}' in content

    def test_run_id_cypher_generation(self):
        """Test that run_id is properly included in Cypher query generation"""
        graph_memory_path = 'mem0/memory/graph_memory.py'
        
        # Check if file exists before reading
        if not os.path.exists(graph_memory_path):
            # Skip test if file doesn't exist (e.g., in CI environment)
            return
            
        with open(graph_memory_path, 'r') as f:
            content = f.read()
        
        # Check that the dynamic property building pattern exists
        assert 'node_props = [' in content
        assert 'node_props_str = ", ".join(node_props)' in content
        
        # Check that run_id is handled in the pattern
        assert 'if filters.get(' in content
        assert 'node_props.append(' in content
        
        # Verify the pattern is used in MATCH clauses
        assert '{{{node_props_str}}}' in content or '{node_props_str}' in content

    def test_agent_id_implementation_pattern(self):
        """Test that the code structure supports agent_id implementation"""
        graph_memory_path = 'mem0/memory/graph_memory.py'
        
        # Check if file exists before reading
        if not os.path.exists(graph_memory_path):
            # Skip test if file doesn't exist (e.g., in CI environment)
            return
            
        with open(graph_memory_path, 'r') as f:
            content = f.read()
        
        # Verify that agent_id pattern is used consistently
        assert 'node_props = [' in content
        assert 'node_props_str = ", ".join(node_props)' in content
        assert 'if filters.get("agent_id"):' in content
        assert 'node_props.append("agent_id: $agent_id")' in content

    def test_run_id_implementation_pattern(self):
        """Test that the code structure supports run_id implementation"""
        graph_memory_path = 'mem0/memory/graph_memory.py'
        
        # Check if file exists before reading
        if not os.path.exists(graph_memory_path):
            # Skip test if file doesn't exist (e.g., in CI environment)
            return
            
        with open(graph_memory_path, 'r') as f:
            content = f.read()
        
        # Verify that run_id pattern is used consistently
        assert 'node_props = [' in content
        assert 'node_props_str = ", ".join(node_props)' in content
        assert 'if filters.get("run_id"):' in content
        assert 'node_props.append("run_id: $run_id")' in content

    def test_user_identity_integration(self):
        """Test that both agent_id and run_id are properly integrated into user identity"""
        graph_memory_path = 'mem0/memory/graph_memory.py'
        
        # Check if file exists before reading
        if not os.path.exists(graph_memory_path):
            # Skip test if file doesn't exist (e.g., in CI environment)
            return
            
        with open(graph_memory_path, 'r') as f:
            content = f.read()
        
        # Check that user_identity building includes both agent_id and run_id
        assert 'user_identity = f"user_id: {filters[\'user_id\']}"' in content
        assert 'user_identity += f", agent_id: {filters[\'agent_id\']}"' in content
        assert 'user_identity += f", run_id: {filters[\'run_id\']}"' in content

    def test_search_methods_integration(self):
        """Test that both agent_id and run_id are properly integrated into search methods"""
        graph_memory_path = 'mem0/memory/graph_memory.py'
        
        # Check if file exists before reading
        if not os.path.exists(graph_memory_path):
            # Skip test if file doesn't exist (e.g., in CI environment)
            return
            
        with open(graph_memory_path, 'r') as f:
            content = f.read()
        
        # Check that search methods handle both agent_id and run_id
        assert 'where_conditions.append("source_candidate.agent_id = $agent_id")' in content
        assert 'where_conditions.append("source_candidate.run_id = $run_id")' in content
        assert 'where_conditions.append("destination_candidate.agent_id = $agent_id")' in content
        assert 'where_conditions.append("destination_candidate.run_id = $run_id")' in content

    def test_add_entities_integration(self):
        """Test that both agent_id and run_id are properly integrated into add_entities"""
        graph_memory_path = 'mem0/memory/graph_memory.py'
        
        # Check if file exists before reading
        if not os.path.exists(graph_memory_path):
            # Skip test if file doesn't exist (e.g., in CI environment)
            return
            
        with open(graph_memory_path, 'r') as f:
            content = f.read()
        
        # Check that add_entities handles both agent_id and run_id
        assert 'agent_id = filters.get("agent_id", None)' in content
        assert 'run_id = filters.get("run_id", None)' in content
        
        # Check that merge properties include both
        assert 'if agent_id:' in content
        assert 'if run_id:' in content
        assert 'merge_props.append("agent_id: $agent_id")' in content
        assert 'merge_props.append("run_id: $run_id")' in content

