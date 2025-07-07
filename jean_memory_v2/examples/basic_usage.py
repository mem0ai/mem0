#!/usr/bin/env python3
"""
Jean Memory V2 - Basic Usage Example
====================================

This example demonstrates the basic functionality of the Jean Memory V2 library.
"""

import asyncio
import os
from jean_memory_v2 import JeanMemoryV2, setup_logging


async def main():
    # Setup logging
    setup_logging(level="INFO")
    
    # Initialize Jean Memory V2 with API keys
    jm = JeanMemoryV2(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        qdrant_host=os.getenv("QDRANT_HOST"),
        qdrant_port=os.getenv("QDRANT_PORT"),
        neo4j_uri=os.getenv("NEO4J_URI"),
        neo4j_user=os.getenv("NEO4J_USER"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        gemini_api_key=os.getenv("GEMINI_API_KEY")  # Optional for AI synthesis
    )
    
    user_id = "example_user_123"
    
    try:
        # Initialize the system
        print("🚀 Initializing Jean Memory V2...")
        await jm.initialize()
        
        # Health check
        print("\n🏥 Performing health check...")
        health = await jm.health_check()
        print(f"System status: {health['jean_memory_v2']}")
        
        # Ingest some example memories
        print("\n📝 Ingesting memories...")
        memories = [
            "I love hiking in the mountains on weekends",
            "My favorite programming language is Python",
            "I graduated from Stanford University in 2020",
            "I work as a software engineer at a tech startup",
            "I enjoy reading science fiction novels",
            "My cat's name is Whiskers and she's very playful"
        ]
        
        ingestion_result = await jm.ingest_memories(
            memories=memories,
            user_id=user_id
        )
        
        print(f"✅ Ingested {ingestion_result.successful_ingestions}/{ingestion_result.total_memories} memories")
        print(f"   Processing time: {ingestion_result.processing_time:.2f}s")
        print(f"   Success rate: {ingestion_result.success_rate:.1f}%")
        
        # Search for memories
        print("\n🔍 Searching memories...")
        search_queries = [
            "What do I like to do for fun?",
            "Tell me about my education",
            "What pets do I have?",
            "What's my job?"
        ]
        
        for query in search_queries:
            print(f"\nQuery: '{query}'")
            search_result = await jm.search(query, user_id=user_id)
            
            print(f"📊 Found {search_result.total_results} relevant memories")
            print(f"⏱️  Processing time: {search_result.processing_time:.2f}s")
            print(f"🤖 AI Synthesis:")
            print(f"   {search_result.synthesis}")
            print(f"   Confidence: {search_result.confidence_score:.2%}")
        
        # Get user statistics
        print("\n📈 User Statistics:")
        stats = await jm.get_user_stats(user_id)
        print(f"   User ID: {stats['user_id']}")
        if 'mem0_memory_count' in stats:
            print(f"   Mem0 memories: {stats['mem0_memory_count']}")
        if 'graphiti_node_count' in stats:
            print(f"   Graphiti nodes: {stats['graphiti_node_count']}")
        
        # Test individual engines
        print("\n🧠 Testing Mem0 search...")
        mem0_results = await jm.search_mem0_only("programming", user_id=user_id)
        print(f"   Found {len(mem0_results)} results from Mem0")
        
        print("\n🕸️ Testing Graphiti search...")
        graphiti_results = await jm.search_graphiti_only("education", user_id=user_id)
        print(f"   Found {len(graphiti_results)} results from Graphiti")
        
        print("\n✅ Example completed successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        # Clean up resources
        print("\n🧹 Cleaning up...")
        await jm.close()


if __name__ == "__main__":
    asyncio.run(main()) 