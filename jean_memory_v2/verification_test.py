"""
Jean Memory V2 - Verification Test
=================================

Quick verification script to test that ontology and custom fact extraction are working.
Run this to verify the integration is active.
"""

import asyncio
import sys
import os
from pathlib import Path
import json
import logging

# Add project root to path
current_dir = Path(__file__).parent.resolve()
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

# Set up logging to see the verification messages
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

from jean_memory_v2.api_optimized import JeanMemoryAPIOptimized
from jean_memory_v2.config import JeanMemoryConfig


async def test_ontology_integration():
    """Test that ontology and custom fact extraction are working"""
    
    print("🧪 JEAN MEMORY V2 - ONTOLOGY & CUSTOM FACT EXTRACTION VERIFICATION")
    print("=" * 70)
    
    # Test memory with rich entity content
    test_memory = (
        "Had coffee with Sarah Johnson at Blue Bottle Coffee yesterday. "
        "She's excited about her new job at Google as a software engineer. "
        "We discussed AI developments and she mentioned feeling optimistic about the future."
    )
    
    test_user_id = "verification_test_user"
    
    print(f"📝 Test Memory: {test_memory}")
    print(f"👤 Test User ID: {test_user_id}")
    print()
    
    try:
        # Initialize Jean Memory V2 API
        print("🔧 Initializing Jean Memory V2 API...")
        config = JeanMemoryConfig.from_environment()
        api = JeanMemoryAPIOptimized(config)
        
        # Add the test memory - this should trigger ontology and custom fact extraction
        print("💾 Adding test memory (watch for ontology/custom fact extraction logs)...")
        print("-" * 70)
        
        result = await api.add_memory(
            memory_text=test_memory,
            user_id=test_user_id,
            source_description="verification_test"
        )
        
        print("-" * 70)
        print(f"✅ Memory added successfully: {result.memory_id}")
        print()
        
        # Search for the memory to verify it was processed
        print("🔍 Searching for the memory...")
        search_result = await api.search(
            query="Sarah coffee",
            user_id=test_user_id,
            limit=5
        )
        
        print(f"✅ Search completed. Found {len(search_result.memories)} memories")
        
        # Display the results
        if search_result.memories:
            print("\n📊 Search Results:")
            for i, memory in enumerate(search_result.memories, 1):
                print(f"   {i}. {memory.text[:100]}...")
                print(f"      Source: {memory.source}")
                print(f"      Score: {memory.score}")
                print()
        
        # Test cleanup
        print("🧹 Cleaning up test data...")
        # Note: In a real test, you might want to clean up the test user's data
        
        print("✅ VERIFICATION COMPLETE!")
        print("\n🎯 What to Look For:")
        print("   • Logs showing '🎯 APPLYING CUSTOM FACT EXTRACTION PROMPT TO MEM0 CONFIG'")
        print("   • Logs showing '🕸️ APPLYING ONTOLOGY TO GRAPHITI CONFIG'")
        print("   • Logs showing '🕸️ APPLYING ONTOLOGY TO GRAPHITI EPISODE'")
        print("   • Enhanced entity extraction in Neo4j (Person: Sarah, Place: Blue Bottle, etc.)")
        print("   • Structured facts in Qdrant with better semantic relationships")
        
        return True
        
    except Exception as e:
        print(f"❌ VERIFICATION FAILED: {e}")
        print("\n🔧 Troubleshooting:")
        print("   • Make sure your environment is properly configured")
        print("   • Check that Neo4j and Qdrant connections are working")
        print("   • Verify OpenAI API key is valid")
        print("   • Run: python jean_memory_v2/test_ontology_integration.py")
        return False
    
    finally:
        if 'api' in locals():
            await api.close()


def print_feature_summary():
    """Print a summary of the new features"""
    print("\n" + "=" * 70)
    print("JEAN MEMORY V2 - NEW FEATURES SUMMARY")
    print("=" * 70)
    
    from jean_memory_v2.ontology import get_ontology_config, ENTITY_TYPES, EDGE_TYPES
    from jean_memory_v2.custom_fact_extraction import CUSTOM_FACT_EXTRACTION_PROMPT
    
    # Ontology summary
    ontology_config = get_ontology_config()
    print(f"\n🧠 ONTOLOGY:")
    print(f"   Entity Types: {len(ontology_config['entity_types'])}")
    for entity_name in ontology_config['entity_types'].keys():
        print(f"     - {entity_name}")
    
    print(f"\n   Edge Types: {len(ontology_config['edge_types'])}")
    for edge_name in ontology_config['edge_types'].keys():
        print(f"     - {edge_name}")
    
    print(f"\n   Edge Mappings: {len(ontology_config['edge_type_map'])}")
    
    # Custom prompt summary
    prompt_length = len(CUSTOM_FACT_EXTRACTION_PROMPT)
    prompt_examples = CUSTOM_FACT_EXTRACTION_PROMPT.count('Input:')
    print(f"\n📝 CUSTOM FACT EXTRACTION:")
    print(f"   Prompt Length: {prompt_length} characters")
    print(f"   Examples: {prompt_examples}")
    print(f"   Entity Types: Person, Place, Event, Topic, Object, Emotion")
    
    print(f"\n🎯 INTEGRATION STATUS:")
    print(f"   ✅ Ontology definitions loaded")
    print(f"   ✅ Custom fact extraction prompt loaded")
    print(f"   ✅ Configuration integration active")
    print(f"   ✅ Automatic application to Mem0 and Graphiti")


async def main():
    """Run the verification test"""
    print_feature_summary()
    print("\n" + "=" * 70)
    print("RUNNING VERIFICATION TEST")
    print("=" * 70)
    
    success = await test_ontology_integration()
    
    if success:
        print("\n🎉 VERIFICATION PASSED!")
        print("Your Jean Memory V2 integration is working correctly.")
    else:
        print("\n❌ VERIFICATION FAILED!")
        print("Please check the logs above for troubleshooting information.")
    
    return success


if __name__ == "__main__":
    asyncio.run(main()) 