"""
Jean Memory V2 - Database Cleaning for Testing Example
======================================================

This example demonstrates how to use the comprehensive database cleaning
utilities for testing scenarios. These functions help ensure clean test
environments and proper test isolation.
"""

import asyncio
import os
from jean_memory_v2 import (
    JeanMemoryV2,
    JeanMemoryConfig,
    DatabaseCleaner,
    clear_user_for_testing,
    clear_all_for_testing,
    verify_clean_database
)


async def basic_database_cleaning_example():
    """Basic example of database cleaning for testing"""
    
    print("🧪 Basic Database Cleaning Example")
    print("=" * 50)
    
    # Initialize Jean Memory V2
    jm = JeanMemoryV2(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        neo4j_uri=os.getenv("NEO4J_URI"),
        neo4j_user=os.getenv("NEO4J_USER"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        gemini_api_key=os.getenv("GEMINI_API_KEY")
    )
    
    try:
        await jm.initialize()
        
        # 1. Clear user data before test
        print("\n1. Clearing test user data before starting...")
        clear_result = await jm.clear_user_data_for_testing("test_user", confirm=True)
        print(f"   Cleared: {clear_result}")
        
        # 2. Verify clean state
        print("\n2. Verifying clean state...")
        verification = await jm.verify_clean_state_for_testing(["test_user"])
        print(f"   Clean state: {verification['is_clean']}")
        
        # 3. Add some test data
        print("\n3. Adding test data...")
        result = await jm.ingest_memories([
            "I love testing code",
            "Unit tests are important",
            "Clean databases make testing easier"
        ], user_id="test_user")
        print(f"   Ingested: {result.total_processed} memories")
        
        # 4. Verify data exists
        print("\n4. Verifying data exists...")
        search_result = await jm.search("What do I think about testing?", user_id="test_user")
        print(f"   Found memories: {len(search_result.mem0_results)}")
        
        # 5. Get database stats
        print("\n5. Getting database statistics...")
        stats = await jm.get_database_stats_for_testing()
        print(f"   Database stats: {stats}")
        
        # 6. Clean up after test
        print("\n6. Cleaning up after test...")
        final_clear = await jm.clear_user_data_for_testing("test_user", confirm=True)
        print(f"   Final cleanup: {final_clear}")
        
    finally:
        await jm.close()


async def advanced_database_cleaner_example():
    """Advanced example using DatabaseCleaner directly"""
    
    print("\n\n🔧 Advanced Database Cleaner Example")
    print("=" * 50)
    
    # Create configuration
    config = JeanMemoryConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        neo4j_uri=os.getenv("NEO4J_URI"),
        neo4j_user=os.getenv("NEO4J_USER"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        gemini_api_key=os.getenv("GEMINI_API_KEY")
    )
    
    # Initialize database cleaner
    cleaner = DatabaseCleaner(config)
    
    try:
        await cleaner.initialize()
        
        # 1. Get comprehensive database stats
        print("\n1. Getting comprehensive database statistics...")
        stats = await cleaner.get_database_stats()
        print(f"   Stats: {stats}")
        
        # 2. Verify clean state for multiple users
        print("\n2. Verifying clean state for multiple test users...")
        test_users = ["test_user_1", "test_user_2", "test_user_3"]
        verification = await cleaner.verify_clean_state(test_users)
        print(f"   Verification: {verification}")
        
        # 3. Create test isolation
        print("\n3. Creating test isolation...")
        test_prefix = await cleaner.create_test_isolation("memory_ingestion_test")
        print(f"   Test prefix: {test_prefix}")
        
        # 4. Clear data by prefix (conceptual - would need implementation)
        print("\n4. Clearing data by prefix (if implemented)...")
        try:
            prefix_result = await cleaner.clear_collections_by_prefix("test_", confirm=True)
            print(f"   Prefix clear result: {prefix_result}")
        except Exception as e:
            print(f"   Prefix clearing not fully implemented: {e}")
        
    finally:
        await cleaner.close()


async def convenience_functions_example():
    """Example using convenience functions"""
    
    print("\n\n⚡ Convenience Functions Example")
    print("=" * 50)
    
    # Create configuration
    config = JeanMemoryConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        qdrant_api_key=os.getenv("QDRANT_API_KEY"),
        neo4j_uri=os.getenv("NEO4J_URI"),
        neo4j_user=os.getenv("NEO4J_USER"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),
        gemini_api_key=os.getenv("GEMINI_API_KEY")
    )
    
    # 1. Clear specific user using convenience function
    print("\n1. Clearing specific user with convenience function...")
    user_clear_result = await clear_user_for_testing(config, "test_user")
    print(f"   User clear result: {user_clear_result}")
    
    # 2. Verify clean database
    print("\n2. Verifying clean database...")
    is_clean = await verify_clean_database(config, ["test_user"])
    print(f"   Database is clean: {is_clean}")
    
    # 3. Clear all data (DANGEROUS - use only in isolated test environments)
    print("\n3. Clearing all data (use with extreme caution!)...")
    try:
        # Uncomment the line below ONLY if you want to clear everything
        # all_clear_result = await clear_all_for_testing(config)
        # print(f"   All clear result: {all_clear_result}")
        print("   Skipping full database clear for safety")
    except Exception as e:
        print(f"   Error clearing all data: {e}")


async def test_isolation_pattern():
    """Example of proper test isolation pattern"""
    
    print("\n\n🧪 Test Isolation Pattern Example")
    print("=" * 50)
    
    async def run_isolated_test(test_name: str, user_id: str):
        """Run a test in isolation with proper cleanup"""
        
        print(f"\n--- Running test: {test_name} ---")
        
        # Initialize Jean Memory V2
        jm = JeanMemoryV2(
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY"),
            neo4j_uri=os.getenv("NEO4J_URI"),
            neo4j_user=os.getenv("NEO4J_USER"),
            neo4j_password=os.getenv("NEO4J_PASSWORD"),
            gemini_api_key=os.getenv("GEMINI_API_KEY")
        )
        
        try:
            await jm.initialize()
            
            # 1. Clean state before test
            print("   1. Ensuring clean state...")
            await jm.clear_user_data_for_testing(user_id, confirm=True)
            
            # 2. Verify clean
            verification = await jm.verify_clean_state_for_testing([user_id])
            assert verification["is_clean"], "Database not clean before test!"
            print("   ✅ Clean state verified")
            
            # 3. Run test operations
            print("   2. Running test operations...")
            await jm.ingest_memories([
                f"Test data for {test_name}",
                f"This is test {test_name} running"
            ], user_id=user_id)
            
            search_result = await jm.search(f"What is {test_name}?", user_id=user_id)
            print(f"   ✅ Test completed, found {len(search_result.mem0_results)} results")
            
            # 4. Clean up after test
            print("   3. Cleaning up...")
            await jm.clear_user_data_for_testing(user_id, confirm=True)
            
            # 5. Verify cleanup
            final_verification = await jm.verify_clean_state_for_testing([user_id])
            assert final_verification["is_clean"], "Database not clean after test!"
            print("   ✅ Cleanup verified")
            
        finally:
            await jm.close()
    
    # Run multiple isolated tests
    await run_isolated_test("memory_ingestion", "test_user_ingestion")
    await run_isolated_test("search_functionality", "test_user_search")
    await run_isolated_test("hybrid_search", "test_user_hybrid")


async def main():
    """Run all database cleaning examples"""
    
    print("🚀 Jean Memory V2 Database Cleaning Examples")
    print("=" * 60)
    
    # Check for required environment variables
    required_vars = [
        "OPENAI_API_KEY", 
        "QDRANT_API_KEY", 
        "NEO4J_URI", 
        "NEO4J_USER", 
        "NEO4J_PASSWORD"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ Missing required environment variables: {missing_vars}")
        print("Please set these variables before running the examples.")
        return
    
    try:
        # Run all examples
        await basic_database_cleaning_example()
        await advanced_database_cleaner_example()
        await convenience_functions_example()
        await test_isolation_pattern()
        
        print("\n\n✅ All database cleaning examples completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main()) 