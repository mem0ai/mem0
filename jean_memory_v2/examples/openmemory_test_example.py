"""
Jean Memory V2 - OpenMemory Test Environment Example
====================================================

This example demonstrates how to use Jean Memory V2 with the 
openmemory test environment configuration for easy testing.
"""

import asyncio
from jean_memory_v2 import JeanMemoryV2


async def main():
    """Example using Jean Memory V2 with openmemory test environment"""
    
    print("🚀 Jean Memory V2 - OpenMemory Test Environment Example")
    print("=" * 60)
    
    # Initialize from openmemory test environment
    # This automatically loads from openmemory/api/.env.test
    jm = JeanMemoryV2.from_openmemory_test_env()
    print("✅ Loaded configuration from openmemory/api/.env.test")
    
    # Test user ID
    test_user_id = "example_test_user"
    
    try:
        # Initialize the system
        await jm.initialize()
        print("✅ Jean Memory V2 initialized successfully")
        
        # Clean any existing test data
        print(f"\n🧹 Cleaning existing data for user: {test_user_id}")
        clear_result = await jm.clear_user_data_for_testing(test_user_id, confirm=True)
        print(f"   Cleared: {clear_result['mem0_deleted']} Mem0 + {clear_result['graphiti_deleted']} Graphiti items")
        
        # Verify clean state
        verification = await jm.verify_clean_state_for_testing([test_user_id])
        print(f"   Clean state: {verification['is_clean']}")
        
        # Ingest some test memories
        print(f"\n📥 Ingesting test memories for user: {test_user_id}")
        test_memories = [
            "I love working with AI and machine learning",
            "My favorite programming language is Python",
            "I enjoy building memory systems and databases",
            "I work on Jean Memory V2 development",
            "Testing database cleaning functionality is important"
        ]
        
        ingestion_result = await jm.ingest_memories(test_memories, user_id=test_user_id)
        print(f"   ✅ Ingested {ingestion_result.successful_ingestions}/{ingestion_result.total_processed} memories")
        print(f"   Processing time: {ingestion_result.processing_time:.2f}s")
        print(f"   Success rate: {ingestion_result.success_rate:.1%}")
        
        # Search for memories
        print(f"\n🔍 Searching memories for user: {test_user_id}")
        search_queries = [
            "What do I like to work on?",
            "What programming languages do I use?",
            "What is important for testing?"
        ]
        
        for query in search_queries:
            print(f"\n   Query: '{query}'")
            search_result = await jm.search(query, user_id=test_user_id)
            
            print(f"   Found {search_result.total_results} results (confidence: {search_result.confidence_score:.2f})")
            print(f"   Processing time: {search_result.processing_time:.2f}s")
            
            if search_result.synthesis:
                print(f"   🤖 AI Synthesis: {search_result.synthesis}")
            
            # Show top result
            if search_result.mem0_results:
                top_result = search_result.mem0_results[0]
                print(f"   📝 Top memory: {top_result.get('content', 'N/A')}")
        
        # Get user statistics
        print(f"\n📊 User Statistics for: {test_user_id}")
        stats = await jm.get_user_stats(test_user_id)
        print(f"   Mem0 memories: {stats.get('mem0_memory_count', 'N/A')}")
        print(f"   Graphiti nodes: {stats.get('graphiti_node_count', 'N/A')}")
        
        # Get database statistics
        print(f"\n🗄️ Database Statistics")
        db_stats = await jm.get_database_stats_for_testing()
        print(f"   Database stats: {db_stats}")
        
        # Health check
        print(f"\n🏥 System Health Check")
        health = await jm.health_check()
        print(f"   Overall status: {health['jean_memory_v2']}")
        print(f"   Components: {health['components']}")
        
        # Clean up after demonstration
        print(f"\n🧹 Cleaning up test data...")
        final_clear = await jm.clear_user_data_for_testing(test_user_id, confirm=True)
        print(f"   Final cleanup: {final_clear}")
        
        # Verify final clean state
        final_verification = await jm.verify_clean_state_for_testing([test_user_id])
        print(f"   Final clean state: {final_verification['is_clean']}")
        
        print("\n✅ Example completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Example failed: {e}")
        raise
        
    finally:
        # Always close the connection
        await jm.close()
        print("🔌 Connection closed")


async def quick_test_example():
    """Quick test pattern for development"""
    
    print("\n🧪 Quick Test Pattern Example")
    print("-" * 40)
    
    # Quick one-liner initialization
    jm = JeanMemoryV2.from_openmemory_test_env()
    
    try:
        # Quick test user
        test_user = "quick_test_user"
        
        # Clean, test, clean pattern
        await jm.clear_user_data_for_testing(test_user, confirm=True)
        
        # Quick ingestion
        await jm.ingest_memories(["Quick test memory"], user_id=test_user)
        
        # Quick search
        result = await jm.search("test", user_id=test_user)
        print(f"   Found {result.total_results} results")
        
        # Quick cleanup
        await jm.clear_user_data_for_testing(test_user, confirm=True)
        
        print("✅ Quick test completed")
        
    finally:
        await jm.close()


if __name__ == "__main__":
    # Run the main example
    asyncio.run(main())
    
    # Run the quick test example
    asyncio.run(quick_test_example()) 