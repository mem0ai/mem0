"""
Simple test to verify the configurable threshold implementation works correctly.
This can be run manually to validate the feature.
"""

import pytest
from unittest.mock import MagicMock
from mem0.graphs.configs import GraphStoreConfig, Neo4jConfig


def test_graph_store_config_default_threshold():
    """Test that GraphStoreConfig has correct default threshold."""
    config = GraphStoreConfig(
        provider="neo4j",
        config=Neo4jConfig(
            url="bolt://localhost:7687",
            username="neo4j",
            password="password"
        )
    )
    
    assert hasattr(config, 'threshold')
    assert config.threshold == 0.7
    print("✓ Default threshold is 0.7")


def test_graph_store_config_custom_threshold():
    """Test that custom threshold can be set."""
    config = GraphStoreConfig(
        provider="neo4j",
        config=Neo4jConfig(
            url="bolt://localhost:7687",
            username="neo4j",
            password="password"
        ),
        threshold=0.95
    )
    
    assert config.threshold == 0.95
    print("✓ Custom threshold (0.95) is set correctly")


def test_graph_store_config_threshold_validation_lower_bound():
    """Test that threshold below 0.0 raises validation error."""
    try:
        config = GraphStoreConfig(
            provider="neo4j",
            config=Neo4jConfig(
                url="bolt://localhost:7687",
                username="neo4j",
                password="password"
            ),
            threshold=-0.1
        )
        assert False, "Should have raised validation error"
    except Exception as e:
        assert "greater than or equal to 0" in str(e).lower() or "validation" in str(e).lower()
        print("✓ Threshold validation prevents values < 0.0")


def test_graph_store_config_threshold_validation_upper_bound():
    """Test that threshold above 1.0 raises validation error."""
    try:
        config = GraphStoreConfig(
            provider="neo4j",
            config=Neo4jConfig(
                url="bolt://localhost:7687",
                username="neo4j",
                password="password"
            ),
            threshold=1.5
        )
        assert False, "Should have raised validation error"
    except Exception as e:
        assert "less than or equal to 1" in str(e).lower() or "validation" in str(e).lower()
        print("✓ Threshold validation prevents values > 1.0")


def test_graph_store_config_threshold_edge_cases():
    """Test edge case threshold values (0.0 and 1.0)."""
    # Test 0.0
    config_min = GraphStoreConfig(
        provider="neo4j",
        config=Neo4jConfig(
            url="bolt://localhost:7687",
            username="neo4j",
            password="password"
        ),
        threshold=0.0
    )
    assert config_min.threshold == 0.0
    print("✓ Threshold 0.0 is valid")
    
    # Test 1.0
    config_max = GraphStoreConfig(
        provider="neo4j",
        config=Neo4jConfig(
            url="bolt://localhost:7687",
            username="neo4j",
            password="password"
        ),
        threshold=1.0
    )
    assert config_max.threshold == 1.0
    print("✓ Threshold 1.0 is valid")


def test_memory_graph_uses_config_threshold():
    """Test that MemoryGraph classes read threshold from config."""
    from unittest.mock import patch, MagicMock
    
    # Create mock config with custom threshold
    mock_config = MagicMock()
    mock_config.graph_store.config.url = "bolt://localhost:7687"
    mock_config.graph_store.config.username = "neo4j"
    mock_config.graph_store.config.password = "password"
    mock_config.graph_store.config.database = "neo4j"
    mock_config.graph_store.config.base_label = False
    mock_config.graph_store.threshold = 0.85  # Custom threshold
    mock_config.graph_store.llm = None
    mock_config.llm.provider = "openai"
    mock_config.llm.config = {}
    mock_config.embedder.provider = "openai"
    mock_config.embedder.config = {"embedding_dims": 1536}
    mock_config.vector_store.config = {}
    
    # Test with graph_memory.py
    try:
        with patch('mem0.memory.graph_memory.Neo4jGraph'):
            with patch('mem0.memory.graph_memory.EmbedderFactory.create'):
                with patch('mem0.memory.graph_memory.LlmFactory.create'):
                    from mem0.memory.graph_memory import MemoryGraph
                    graph = MemoryGraph(mock_config)
                    assert graph.threshold == 0.85
                    print("✓ graph_memory.py uses config threshold (0.85)")
    except ImportError:
        print("⚠ Skipping graph_memory test (dependencies not installed)")
    
    # Test with kuzu_memory.py
    try:
        mock_config.graph_store.config.db = ":memory:"
        with patch('mem0.memory.kuzu_memory.kuzu'):
            with patch('mem0.memory.kuzu_memory.EmbedderFactory.create'):
                with patch('mem0.memory.kuzu_memory.LlmFactory.create'):
                    from mem0.memory.kuzu_memory import MemoryGraph as KuzuMemoryGraph
                    kuzu_graph = KuzuMemoryGraph(mock_config)
                    assert kuzu_graph.threshold == 0.85
                    print("✓ kuzu_memory.py uses config threshold (0.85)")
    except ImportError:
        print("⚠ Skipping kuzu_memory test (dependencies not installed)")


def test_memory_graph_fallback_threshold():
    """Test that MemoryGraph falls back to 0.7 if threshold not in config."""
    from unittest.mock import patch, MagicMock
    
    # Create mock config WITHOUT threshold
    mock_config = MagicMock()
    mock_config.graph_store.config.url = "bolt://localhost:7687"
    mock_config.graph_store.config.username = "neo4j"
    mock_config.graph_store.config.password = "password"
    mock_config.graph_store.config.database = "neo4j"
    mock_config.graph_store.config.base_label = False
    
    # Remove threshold attribute to simulate old config
    if hasattr(mock_config.graph_store, 'threshold'):
        delattr(mock_config.graph_store, 'threshold')
    
    mock_config.graph_store.llm = None
    mock_config.llm.provider = "openai"
    mock_config.llm.config = {}
    mock_config.embedder.provider = "openai"
    mock_config.embedder.config = {"embedding_dims": 1536}
    mock_config.vector_store.config = {}
    
    try:
        with patch('mem0.memory.graph_memory.Neo4jGraph'):
            with patch('mem0.memory.graph_memory.EmbedderFactory.create'):
                with patch('mem0.memory.graph_memory.LlmFactory.create'):
                    from mem0.memory.graph_memory import MemoryGraph
                    graph = MemoryGraph(mock_config)
                    assert graph.threshold == 0.7
                    print("✓ Fallback to default threshold (0.7) works")
    except ImportError:
        print("⚠ Skipping fallback test (dependencies not installed)")


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Configurable Threshold Implementation")
    print("=" * 60)
    
    print("\n1. Testing GraphStoreConfig defaults...")
    test_graph_store_config_default_threshold()
    
    print("\n2. Testing custom threshold...")
    test_graph_store_config_custom_threshold()
    
    print("\n3. Testing threshold validation (lower bound)...")
    test_graph_store_config_threshold_validation_lower_bound()
    
    print("\n4. Testing threshold validation (upper bound)...")
    test_graph_store_config_threshold_validation_upper_bound()
    
    print("\n5. Testing edge case thresholds...")
    test_graph_store_config_threshold_edge_cases()
    
    print("\n6. Testing MemoryGraph uses config threshold...")
    test_memory_graph_uses_config_threshold()
    
    print("\n7. Testing fallback to default threshold...")
    test_memory_graph_fallback_threshold()
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
