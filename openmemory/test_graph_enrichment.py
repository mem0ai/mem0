#!/usr/bin/env python3
"""
Test script to demonstrate graph enrichment

Usage:
    python test_graph_enrichment.py
"""

import asyncio
import json
import os
import sys

# Add api directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'api'))

from app.services.graph_enrichment import GraphEnrichmentService


async def test_enrichment():
    """Test the graph enrichment service"""

    print("=" * 80)
    print("GRAPH ENRICHMENT TEST")
    print("=" * 80)
    print()

    # Initialize service
    service = GraphEnrichmentService()

    if not service.driver:
        print("❌ Neo4j not configured or unavailable")
        print("Set NEO4J_URL, NEO4J_USERNAME, NEO4J_PASSWORD environment variables")
        return

    print("✅ Connected to Neo4j")
    print()

    # Test data: simulated memory without enrichment
    test_memory = {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "memory": "Josephine's birthday is on 20th March",
        "content": "Josephine's birthday is on 20th March",
        "created_at": 1704067200,
        "categories": ["personal", "dates"]
    }

    print("BEFORE ENRICHMENT:")
    print("-" * 80)
    print(json.dumps(test_memory, indent=2))
    print()

    # Enrich the memory
    enriched = await service.enrich_memory(test_memory)

    print("AFTER ENRICHMENT:")
    print("-" * 80)
    print(json.dumps(enriched, indent=2, default=str))
    print()

    # Show what was added
    if enriched.get('graph_enriched'):
        print("✅ Successfully enriched with graph data!")
        print()
        print(f"Found {len(enriched.get('entities', []))} entities:")
        for entity in enriched.get('entities', []):
            print(f"  - {entity['name']} ({entity['type']})")
        print()
        print(f"Found {len(enriched.get('relationships', []))} relationships:")
        for rel in enriched.get('relationships', []):
            print(f"  - {rel['source']} -[{rel['relation']}]-> {rel['target']}")
    else:
        print("⚠️  No graph data found for this memory")
        print("This means the memory hasn't been processed by mem0 yet,")
        print("or the entities haven't been extracted to Neo4j")

    print()

    # Test entity lookup
    print("=" * 80)
    print("ENTITY LOOKUP TEST")
    print("=" * 80)
    print()

    entity_name = "Josephine"
    entity_context = await service.get_entity_context(entity_name)

    if entity_context:
        print(f"✅ Found entity: {entity_name}")
        print(json.dumps(entity_context, indent=2))
    else:
        print(f"⚠️  Entity '{entity_name}' not found in graph")
        print("Create a memory mentioning 'Josephine' first")

    print()

    # Cleanup
    service.close()


async def demo_comparison():
    """Show side-by-side comparison of enriched vs non-enriched"""

    print("=" * 80)
    print("COMPARISON: Regular vs Enriched Memory Response")
    print("=" * 80)
    print()

    regular_response = {
        "content": "Josephine's birthday is on 20th March",
        "categories": ["personal", "dates"],
        "metadata_": {}
    }

    enriched_response = {
        "content": "Josephine's birthday is on 20th March",
        "categories": ["personal", "dates"],
        "metadata_": {},
        "entities": [
            {
                "name": "Josephine",
                "type": "PERSON",
                "label": "Person"
            },
            {
                "name": "20th March",
                "type": "DATE",
                "label": "Date"
            }
        ],
        "relationships": [
            {
                "source": "Josephine",
                "relation": "HAS_BIRTHDAY",
                "target": "20th March",
                "source_type": "PERSON",
                "target_type": "DATE"
            }
        ],
        "graph_enriched": True
    }

    print("📦 REGULAR RESPONSE (Current):")
    print("-" * 80)
    print(json.dumps(regular_response, indent=2))
    print()
    print("❓ LLM sees: 'Josephine' (string) - no context")
    print("❓ LLM sees: '20th March' (string) - no context")
    print("❓ LLM must infer relationship from text")
    print()

    print("✨ ENRICHED RESPONSE (New):")
    print("-" * 80)
    print(json.dumps(enriched_response, indent=2))
    print()
    print("✅ LLM sees: 'Josephine' is a PERSON")
    print("✅ LLM sees: '20th March' is a DATE")
    print("✅ LLM sees: Josephine HAS_BIRTHDAY 20th March (explicit relationship)")
    print()

    print("=" * 80)
    print("IMPACT ON LLM REASONING")
    print("=" * 80)
    print()
    print("Query: 'When is Josephine's birthday?'")
    print()
    print("Without enrichment:")
    print("  1. Search for 'Josephine' + 'birthday'")
    print("  2. Find text: 'Josephine's birthday is on 20th March'")
    print("  3. Parse text to extract date")
    print("  4. Hope the parsing is correct")
    print()
    print("With enrichment:")
    print("  1. Find entity: Josephine (PERSON)")
    print("  2. Find relationship: Josephine -[HAS_BIRTHDAY]-> 20th March (DATE)")
    print("  3. Directly answer: '20th March'")
    print("  4. Confidence: 100% (structured data)")
    print()


if __name__ == "__main__":
    print()
    print("🧪 Testing Graph Enrichment Service")
    print()

    # Run demo comparison first (doesn't need Neo4j)
    asyncio.run(demo_comparison())

    # Run actual enrichment test (needs Neo4j)
    asyncio.run(test_enrichment())

    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("1. Test the enriched endpoint: POST /api/v1/memories/filter/enriched")
    print("2. Test entity lookup: GET /api/v1/memories/entity/Josephine")
    print("3. Use MCP search_memory tool (auto-enriched)")
    print()
