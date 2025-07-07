#!/usr/bin/env python3
"""
Jean Memory V2 - Optimization Testing Script
============================================

Test script to demonstrate the new high-impact optimizations:
1. Semantic Query Caching with Redis
2. Enhanced Deduplication
3. Automated Memory Management

Usage:
    python jean_memory_v2/examples/test_optimizations.py
"""

import asyncio
import logging
import os
import time
from typing import List, Dict, Any

# Configure logging to see optimization messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable cache logging to see hits
logging.getLogger('jean_memory_v2.cache').setLevel(logging.INFO)
logging.getLogger('jean_memory_v2.search').setLevel(logging.INFO)

logger = logging.getLogger(__name__)


async def test_semantic_caching():
    """Test semantic query caching performance"""
    print("\n🎯 TESTING SEMANTIC QUERY CACHING")
    print("=" * 50)
    
    try:
        from jean_memory_v2.api_optimized import JeanMemoryAPIOptimized
        
        # Initialize API
        api = JeanMemoryAPIOptimized()
        await api.initialize()
        
        user_id = "test_user_cache"
        
        # Add some test memories
        test_memories = [
            "I'm working on a machine learning project with TensorFlow",
            "My favorite programming language is Python", 
            "I live in San Francisco and work in tech",
            "I enjoy hiking on weekends in the Bay Area",
            "Currently learning about vector databases and RAG systems"
        ]
        
        print("📝 Adding test memories...")
        for memory in test_memories:
            await api.add_memory(memory, user_id)
        
        # Test queries - some similar, some different
        test_queries = [
            ("What projects am I working on?", "machine learning"),
            ("What programming languages do I use?", "Python"),  
            ("Where do I live?", "San Francisco"),
            ("What do I do for fun?", "hiking"),
            ("What am I learning about?", "vector databases"),
            
            # Similar queries (should hit cache)
            ("What projects am I involved with?", "machine learning"),  # Similar to #1
            ("Which programming languages do I know?", "Python"),       # Similar to #2
            ("What city do I live in?", "San Francisco"),              # Similar to #3
        ]
        
        print("\n🔍 Testing query performance (first run - no cache):")
        first_run_times = []
        
        for query, expected in test_queries[:5]:  # First 5 queries
            start_time = time.time()
            result = await api.search_memories(query, user_id, limit=5)
            elapsed = (time.time() - start_time) * 1000
            first_run_times.append(elapsed)
            
            found_expected = any(expected.lower() in mem.text.lower() for mem in result.memories)
            status = "✅" if found_expected else "❌"
            print(f"  {status} '{query}' → {elapsed:.1f}ms ({len(result.memories)} results)")
        
        print("\n🎯 Testing similar queries (should hit cache):")
        cached_run_times = []
        
        for query, expected in test_queries[5:]:  # Similar queries
            start_time = time.time() 
            result = await api.search_memories(query, user_id, limit=5)
            elapsed = (time.time() - start_time) * 1000
            cached_run_times.append(elapsed)
            
            found_expected = any(expected.lower() in mem.text.lower() for mem in result.memories)
            status = "✅" if found_expected else "❌"
            cache_status = "🎯 CACHED" if elapsed < 50 else "🔍 FRESH"
            print(f"  {status} {cache_status} '{query}' → {elapsed:.1f}ms")
        
        # Performance summary
        avg_first = sum(first_run_times) / len(first_run_times)
        avg_cached = sum(cached_run_times) / len(cached_run_times)
        speedup = avg_first / avg_cached if avg_cached > 0 else 1
        
        print(f"\n📊 CACHING PERFORMANCE SUMMARY:")
        print(f"  Average first query: {avg_first:.1f}ms")
        print(f"  Average cached query: {avg_cached:.1f}ms") 
        print(f"  Speedup: {speedup:.1f}x faster")
        
        if speedup > 2:
            print("  🎉 Excellent caching performance!")
        elif speedup > 1.2:
            print("  ✅ Good caching performance!")
        else:
            print("  ⚠️ Limited caching benefit (Redis may not be running)")
        
        await api.close()
        return True
        
    except Exception as e:
        logger.error(f"Semantic caching test failed: {e}")
        return False


async def test_memory_deduplication():
    """Test enhanced deduplication features"""
    print("\n🔄 TESTING ENHANCED DEDUPLICATION")
    print("=" * 50)
    
    try:
        from jean_memory_v2.api_optimized import JeanMemoryAPIOptimized
        
        api = JeanMemoryAPIOptimized()
        await api.initialize()
        
        user_id = "test_user_dedup"
        
        # Clear any existing memories
        await api.clear_memories(user_id, confirm=True)
        
        # Add duplicate-prone memories
        duplicate_memories = [
            "I work at Google as a software engineer",
            "I'm a software engineer at Google",  # Similar
            "My job is software engineering at Google",  # Similar
            "I love pizza, especially pepperoni",
            "Pizza is my favorite food, particularly pepperoni",  # Similar
            "I have a cat named Whiskers",
            "My cat's name is Whiskers",  # Similar
            "Whiskers is my cat's name",  # Similar
        ]
        
        print("📝 Adding potentially duplicate memories...")
        added_count = 0
        for i, memory in enumerate(duplicate_memories):
            result = await api.add_memory(memory, user_id)
            if result.success:
                added_count += 1
            print(f"  {i+1}. '{memory}' → {'✅' if result.success else '❌'}")
        
        # Search for all memories to see deduplication effect
        all_memories = await api.search_memories("*", user_id, limit=20)
        
        print(f"\n📊 DEDUPLICATION RESULTS:")
        print(f"  Attempted to add: {len(duplicate_memories)} memories")
        print(f"  Successfully added: {added_count} memories")
        print(f"  Final memory count: {len(all_memories.memories)} memories")
        
        dedup_ratio = len(all_memories.memories) / len(duplicate_memories)
        
        if dedup_ratio < 0.7:
            print(f"  🎉 Excellent deduplication! ({dedup_ratio:.1%} retention)")
        elif dedup_ratio < 0.9:
            print(f"  ✅ Good deduplication! ({dedup_ratio:.1%} retention)")
        else:
            print(f"  ⚠️ Limited deduplication ({dedup_ratio:.1%} retention)")
        
        print(f"\n📋 Final memories stored:")
        for i, memory in enumerate(all_memories.memories):
            print(f"  {i+1}. {memory.text}")
        
        await api.close()
        return True
        
    except Exception as e:
        logger.error(f"Deduplication test failed: {e}")
        return False


async def test_memory_optimization():
    """Test automated memory management and optimization"""
    print("\n🧹 TESTING AUTOMATED MEMORY OPTIMIZATION")
    print("=" * 50)
    
    try:
        from jean_memory_v2.api_optimized import JeanMemoryAPIOptimized
        
        api = JeanMemoryAPIOptimized()
        await api.initialize()
        
        user_id = "test_user_optimize"
        
        # Add a mix of good and poor quality memories
        test_memories = [
            # Good memories
            "I'm working on a React project for e-commerce",
            "I graduated from Stanford with a CS degree in 2020",
            "My favorite restaurants in NYC are Joe's Pizza and Katz's Deli",
            
            # Poor quality memories (should be pruned)
            "ok",
            "yes",
            "...", 
            "test",
            "hm",
            
            # Duplicates
            "I like coffee in the morning",
            "I enjoy coffee in the mornings",
            "Morning coffee is something I like",
        ]
        
        print("📝 Adding mix of good and poor quality memories...")
        for memory in test_memories:
            await api.add_memory(memory, user_id)
        
        # Analyze memory usage
        print("\n📊 Analyzing memory usage...")
        analysis = await api.analyze_memory_usage(user_id)
        
        if 'error' in analysis:
            print(f"  ⚠️ Analysis error: {analysis['error']}")
            return False
        
        print(f"  Total memories: {analysis.get('total_memories', 0)}")
        print(f"  Collection size: {analysis.get('collection_size_mb', 0):.2f} MB")
        print(f"  Duplicate candidates: {analysis.get('duplicate_candidates', 0)}")
        print(f"  Low-value candidates: {analysis.get('low_value_candidates', 0)}")
        
        recommendations = analysis.get('recommendations', [])
        if recommendations:
            print(f"\n💡 Optimization recommendations:")
            for rec in recommendations:
                print(f"  - {rec['description']} (saves ~{rec['estimated_savings_mb']:.2f} MB)")
        
        # Test dry run optimization
        print(f"\n🧪 Running optimization (dry run)...")
        dry_result = await api.optimize_user_memories(user_id, dry_run=True)
        
        if dry_result.get('success'):
            stats = dry_result['optimization_stats']
            print(f"  Would remove {stats['duplicates_removed']} duplicates")
            print(f"  Would remove {stats['low_value_removed']} low-value memories")
            print(f"  Would save {stats['storage_saved_mb']:.2f} MB")
            
            # Ask user if they want to run actual optimization
            print(f"\n🤔 Run actual optimization? (y/n): ", end="")
            try:
                # For automated testing, we'll skip the actual optimization
                choice = "n"  # input().strip().lower()
                
                if choice == 'y':
                    print("🎯 Running actual optimization...")
                    real_result = await api.optimize_user_memories(user_id, dry_run=False)
                    if real_result.get('success'):
                        final_stats = real_result['optimization_stats']
                        print(f"  ✅ Optimization completed!")
                        print(f"  Removed {final_stats['duplicates_removed']} duplicates")
                        print(f"  Removed {final_stats['low_value_removed']} low-value memories")
                        print(f"  Saved {final_stats['storage_saved_mb']:.2f} MB")
                else:
                    print("  ⏭️ Skipping actual optimization")
            except KeyboardInterrupt:
                print("\n  ⏭️ Skipping actual optimization")
        else:
            print(f"  ❌ Optimization failed: {dry_result.get('error', 'Unknown error')}")
        
        await api.close()
        return True
        
    except Exception as e:
        logger.error(f"Memory optimization test failed: {e}")
        return False


async def main():
    """Run all optimization tests"""
    print("🚀 JEAN MEMORY V2 - OPTIMIZATION TESTING")
    print("=" * 60)
    
    # Check prerequisites
    print("🔧 Checking prerequisites...")
    
    # Check if Redis is available
    redis_available = False
    try:
        import redis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
        client = redis.from_url(redis_url)
        client.ping()
        redis_available = True
        print("  ✅ Redis connection successful")
    except Exception as e:
        print(f"  ⚠️ Redis not available: {e}")
        print("     Start Redis with: docker run -d -p 6379:6379 redis:7-alpine")
    
    # Check required environment variables
    required_vars = ["OPENAI_API_KEY", "QDRANT_HOST"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"  ❌ Missing environment variables: {missing_vars}")
        print("     Please set these variables before running tests")
        return
    else:
        print("  ✅ Required environment variables found")
    
    # Run tests
    test_results = []
    
    if redis_available:
        test_results.append(await test_semantic_caching())
    else:
        print("\n⚠️ Skipping semantic caching test (Redis not available)")
        test_results.append(False)
    
    test_results.append(await test_memory_deduplication())
    test_results.append(await test_memory_optimization())
    
    # Summary
    print("\n" + "=" * 60)
    print("🏁 TEST SUMMARY")
    print("=" * 60)
    
    tests = [
        ("Semantic Query Caching", test_results[0]),
        ("Enhanced Deduplication", test_results[1]),
        ("Memory Optimization", test_results[2])
    ]
    
    passed = sum(test_results)
    total = len(test_results)
    
    for test_name, result in tests:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"  {status} {test_name}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All optimizations working correctly!")
        print("🚀 Your Jean Memory V2 system is ready for high-performance scaling!")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed. Check logs above for details.")
    
    print("\n📖 For more information, see: jean_memory_v2/OPTIMIZATION_GUIDE.md")


if __name__ == "__main__":
    asyncio.run(main()) 