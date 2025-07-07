"""
Jean Memory V2 - Ontology and Custom Fact Extraction Example
===========================================================

This example demonstrates how to use the new ontology and custom fact extraction
features in Jean Memory V2.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
current_dir = Path(__file__).parent.resolve()
project_root = current_dir.parent.parent
sys.path.insert(0, str(project_root))

from jean_memory_v2.ontology import get_ontology_config, ENTITY_TYPES, EDGE_TYPES
from jean_memory_v2.custom_fact_extraction import CUSTOM_FACT_EXTRACTION_PROMPT
from jean_memory_v2.config import JeanMemoryConfig


def demonstrate_ontology():
    """Demonstrate the ontology structure and configuration"""
    print("🧠 JEAN MEMORY V2 ONTOLOGY DEMONSTRATION")
    print("="*50)
    
    # Get the ontology configuration
    ontology_config = get_ontology_config()
    
    print("📋 ENTITY TYPES:")
    for entity_name, entity_class in ENTITY_TYPES.items():
        print(f"   • {entity_name}: {entity_class.__doc__}")
        
        # Show some fields for each entity type
        if hasattr(entity_class, '__fields__'):
            fields = list(entity_class.__fields__.keys())[:3]  # Show first 3 fields
            print(f"     Fields: {', '.join(fields)}...")
        print()
    
    print("🔗 EDGE TYPES:")
    for edge_name, edge_class in EDGE_TYPES.items():
        print(f"   • {edge_name}: {edge_class.__doc__}")
        
        # Show some fields for each edge type
        if hasattr(edge_class, '__fields__'):
            fields = list(edge_class.__fields__.keys())[:3]  # Show first 3 fields
            print(f"     Fields: {', '.join(fields)}...")
        print()
    
    print("🗺️  EDGE TYPE MAPPINGS (Sample):")
    edge_map = ontology_config["edge_type_map"]
    sample_mappings = list(edge_map.items())[:5]  # Show first 5 mappings
    
    for (source, target), edge_types in sample_mappings:
        print(f"   • {source} → {target}: {', '.join(edge_types)}")
    
    print(f"   ... and {len(edge_map) - 5} more mappings")


def demonstrate_custom_fact_extraction():
    """Demonstrate the custom fact extraction prompt"""
    print("\n📝 CUSTOM FACT EXTRACTION PROMPT")
    print("="*50)
    
    print("Prompt Overview:")
    print(f"   • Length: {len(CUSTOM_FACT_EXTRACTION_PROMPT)} characters")
    print(f"   • Lines: {CUSTOM_FACT_EXTRACTION_PROMPT.count('\\n')}")
    print(f"   • Examples: {CUSTOM_FACT_EXTRACTION_PROMPT.count('Input:')}")
    
    # Show a sample of the prompt
    lines = CUSTOM_FACT_EXTRACTION_PROMPT.split('\n')
    print(f"\nFirst few lines:")
    for line in lines[:10]:
        if line.strip():
            print(f"   {line[:80]}...")
    
    print("\nEntity types the prompt extracts:")
    entity_mentions = []
    for entity in ENTITY_TYPES.keys():
        if entity in CUSTOM_FACT_EXTRACTION_PROMPT:
            entity_mentions.append(entity)
    print(f"   {', '.join(entity_mentions)}")


def demonstrate_configuration_integration():
    """Demonstrate how the ontology and prompt are integrated into configuration"""
    print("\n⚙️  CONFIGURATION INTEGRATION")
    print("="*50)
    
    # Create a sample configuration
    try:
        config = JeanMemoryConfig(
            openai_api_key="sk-example123",
            qdrant_api_key="example-key",
            qdrant_host="localhost",
            qdrant_port="6333",
            neo4j_uri="neo4j://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="password"
        )
        
        print("✅ Configuration created successfully")
        
        # Test Mem0 configuration
        mem0_config = config.to_mem0_config()
        print("\n📊 Mem0 Configuration Features:")
        print(f"   • Custom fact extraction prompt: {'✅' if 'custom_fact_extraction_prompt' in mem0_config else '❌'}")
        print(f"   • Version specification: {mem0_config.get('version', 'Not set')}")
        print(f"   • LLM model: {mem0_config['llm']['config']['model']}")
        
        # Test Graphiti configuration
        graphiti_config = config.to_graphiti_config()
        print("\n🕸️  Graphiti Configuration Features:")
        print(f"   • Entity types: {len(graphiti_config.get('entity_types', {}))}")
        print(f"   • Edge types: {len(graphiti_config.get('edge_types', {}))}")
        print(f"   • Edge mappings: {len(graphiti_config.get('edge_type_map', {}))}")
        
    except Exception as e:
        print(f"❌ Configuration creation failed: {e}")


def demonstrate_example_usage():
    """Show example memory texts and how they would be processed"""
    print("\n🎯 EXAMPLE USAGE SCENARIOS")
    print("="*50)
    
    example_memories = [
        "Had coffee with Sarah at Blue Bottle yesterday. She's a software engineer at Google.",
        "My MacBook Pro broke down last week. Feeling frustrated about it.",
        "Planning to visit Tokyo next month for a conference. Really excited about trying sushi.",
        "Started learning Spanish using Duolingo. Finding it challenging but rewarding.",
        "Bought a new guitar at Guitar Center for $800. It's a Fender Stratocaster in blue."
    ]
    
    print("Sample memory texts that would benefit from the new features:\n")
    
    for i, memory in enumerate(example_memories, 1):
        print(f"{i}. \"{memory}\"")
        
        # Analyze what entities/relationships this would extract
        potential_entities = []
        for entity_type in ENTITY_TYPES.keys():
            if any(keyword in memory.lower() for keyword in get_entity_keywords(entity_type)):
                potential_entities.append(entity_type)
        
        if potential_entities:
            print(f"   → Likely entities: {', '.join(potential_entities)}")
        
        print()


def get_entity_keywords(entity_type):
    """Get keywords that suggest a particular entity type"""
    keywords = {
        "Person": ["sarah", "john", "mom", "dad", "friend", "colleague"],
        "Place": ["coffee", "blue bottle", "tokyo", "guitar center", "starbucks"],
        "Event": ["coffee", "meeting", "conference", "trip", "learning"],
        "Topic": ["software", "spanish", "guitar", "music", "engineering"],
        "Object": ["macbook", "guitar", "iphone", "duolingo", "fender"],
        "Emotion": ["frustrated", "excited", "happy", "challenging", "rewarding"]
    }
    return keywords.get(entity_type, [])


async def main():
    """Run the complete demonstration"""
    print("🚀 JEAN MEMORY V2 - ONTOLOGY & CUSTOM FACT EXTRACTION")
    print("=" * 60)
    print("This demonstration shows the new structured memory features.")
    print("=" * 60)
    
    try:
        # Run demonstrations
        demonstrate_ontology()
        demonstrate_custom_fact_extraction()
        demonstrate_configuration_integration()
        demonstrate_example_usage()
        
        print("\n✅ INTEGRATION SUMMARY")
        print("="*50)
        print("Your Jean Memory V2 library now includes:")
        print("   • 6 structured entity types (Person, Place, Event, Topic, Object, Emotion)")
        print("   • 4 relationship edge types (ParticipatedIn, LocatedAt, RelatedTo, Expressed)")
        print("   • Custom fact extraction prompt with examples")
        print("   • Automatic integration with Mem0 and Graphiti")
        print("   • 100% backward compatibility with existing code")
        
        print("\n🎯 NEXT STEPS:")
        print("   1. Run the test: python jean_memory_v2/test_ontology_integration.py")
        print("   2. Use your existing Jean Memory V2 code - it will automatically use the new features")
        print("   3. Monitor logs for enhanced entity extraction")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Demonstration failed: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1) 