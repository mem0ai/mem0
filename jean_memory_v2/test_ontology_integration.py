"""
Test Script for Jean Memory V2 Ontology and Custom Fact Extraction Integration
============================================================================

This script tests the integration of the new ontology and custom fact extraction prompt
with Jean Memory V2.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
current_dir = Path(__file__).parent.resolve()
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from jean_memory_v2.ontology import validate_ontology, get_ontology_config, ENTITY_TYPES, EDGE_TYPES
from jean_memory_v2.custom_fact_extraction import CUSTOM_FACT_EXTRACTION_PROMPT, validate_prompt_format
from jean_memory_v2.config import JeanMemoryConfig


def test_ontology_validation():
    """Test that the ontology is valid"""
    print("🧪 Testing Ontology Validation...")
    
    try:
        # Test ontology validation
        is_valid = validate_ontology()
        assert is_valid, "Ontology validation failed"
        
        # Test ontology config retrieval
        config = get_ontology_config()
        assert "entity_types" in config
        assert "edge_types" in config
        assert "edge_type_map" in config
        
        # Test that we have the expected entity types
        expected_entities = ["Person", "Place", "Event", "Topic", "Object", "Emotion"]
        for entity in expected_entities:
            assert entity in ENTITY_TYPES, f"Missing entity type: {entity}"
        
        # Test that we have the expected edge types
        expected_edges = ["ParticipatedIn", "LocatedAt", "RelatedTo", "Expressed"]
        for edge in expected_edges:
            assert edge in EDGE_TYPES, f"Missing edge type: {edge}"
        
        print("✅ Ontology validation passed!")
        return True
        
    except Exception as e:
        print(f"❌ Ontology validation failed: {e}")
        return False


def test_custom_fact_extraction():
    """Test that the custom fact extraction prompt is valid"""
    print("🧪 Testing Custom Fact Extraction Prompt...")
    
    try:
        # Test prompt validation
        is_valid = validate_prompt_format(CUSTOM_FACT_EXTRACTION_PROMPT)
        assert is_valid, "Custom fact extraction prompt validation failed"
        
        # Test that prompt contains required elements
        required_elements = [
            "Person", "Place", "Event", "Topic", "Object", "Emotion",
            "JSON", "facts", "Input:", "Output:"
        ]
        
        for element in required_elements:
            assert element in CUSTOM_FACT_EXTRACTION_PROMPT, f"Missing element in prompt: {element}"
        
        print("✅ Custom fact extraction prompt validation passed!")
        return True
        
    except Exception as e:
        print(f"❌ Custom fact extraction prompt validation failed: {e}")
        return False


def test_config_integration():
    """Test that the configuration properly integrates ontology and custom prompt"""
    print("🧪 Testing Configuration Integration...")
    
    try:
        # Create a test configuration
        test_config = JeanMemoryConfig(
            openai_api_key="sk-test123",
            qdrant_api_key="test-api-key",
            qdrant_host="localhost",
            qdrant_port="6333",
            neo4j_uri="neo4j://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="password"
        )
        
        # Test Mem0 config includes custom fact extraction prompt
        mem0_config = test_config.to_mem0_config()
        assert "custom_fact_extraction_prompt" in mem0_config
        assert mem0_config["custom_fact_extraction_prompt"] == CUSTOM_FACT_EXTRACTION_PROMPT
        assert "version" in mem0_config
        assert mem0_config["version"] == "v1.1"
        
        # Test Graphiti config includes ontology
        graphiti_config = test_config.to_graphiti_config()
        assert "entity_types" in graphiti_config
        assert "edge_types" in graphiti_config
        assert "edge_type_map" in graphiti_config
        
        print("✅ Configuration integration passed!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration integration failed: {e}")
        return False


async def test_integration_example():
    """Test a complete integration example"""
    print("🧪 Testing Complete Integration Example...")
    
    try:
        # This is a demonstration of how the integration would work
        # (without actually initializing the full system)
        
        # 1. Get ontology configuration
        ontology_config = get_ontology_config()
        
        # 2. Verify ontology has expected structure
        assert len(ontology_config["entity_types"]) == 6
        assert len(ontology_config["edge_types"]) == 4
        
        # 3. Test that edge type mappings work
        edge_map = ontology_config["edge_type_map"]
        assert ("Person", "Event") in edge_map
        assert "ParticipatedIn" in edge_map[("Person", "Event")]
        
        # 4. Test custom fact extraction prompt structure
        assert len(CUSTOM_FACT_EXTRACTION_PROMPT) > 1000  # Should be substantial
        assert "Few-shot examples:" in CUSTOM_FACT_EXTRACTION_PROMPT
        
        print("✅ Complete integration example passed!")
        return True
        
    except Exception as e:
        print(f"❌ Complete integration example failed: {e}")
        return False


def print_integration_summary():
    """Print a summary of the integration"""
    print("\n" + "="*60)
    print("JEAN MEMORY V2 ONTOLOGY & CUSTOM FACT EXTRACTION SUMMARY")
    print("="*60)
    
    # Ontology summary
    ontology_config = get_ontology_config()
    print(f"\n📋 ONTOLOGY:")
    print(f"   Entity Types: {len(ontology_config['entity_types'])}")
    for entity_name in ontology_config['entity_types'].keys():
        print(f"     - {entity_name}")
    
    print(f"\n   Edge Types: {len(ontology_config['edge_types'])}")
    for edge_name in ontology_config['edge_types'].keys():
        print(f"     - {edge_name}")
    
    print(f"\n   Edge Mappings: {len(ontology_config['edge_type_map'])}")
    
    # Custom prompt summary
    prompt_length = len(CUSTOM_FACT_EXTRACTION_PROMPT)
    prompt_lines = CUSTOM_FACT_EXTRACTION_PROMPT.count('\n')
    print(f"\n📝 CUSTOM FACT EXTRACTION PROMPT:")
    print(f"   Length: {prompt_length} characters")
    print(f"   Lines: {prompt_lines}")
    print(f"   Examples: {CUSTOM_FACT_EXTRACTION_PROMPT.count('Input:')}")
    
    print("\n✅ Integration complete and ready for use!")
    print("="*60)


async def main():
    """Run all tests"""
    print("🚀 Jean Memory V2 Ontology & Custom Fact Extraction Tests")
    print("="*60)
    
    tests = [
        test_ontology_validation,
        test_custom_fact_extraction,
        test_config_integration,
        test_integration_example
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if asyncio.iscoroutinefunction(test):
            result = await test()
        else:
            result = test()
        
        if result:
            passed += 1
        print()  # Add spacing between tests
    
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print_integration_summary()
        return True
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return False


if __name__ == "__main__":
    # Run the tests
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 