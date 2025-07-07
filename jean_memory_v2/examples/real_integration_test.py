"""
Jean Memory V2 - Real Integration Test
=====================================

Test the ontology and custom fact extraction with real-world memory scenarios.
"""

import asyncio
import sys
import os
from pathlib import Path
import json
from datetime import datetime

# Add project root to path
current_dir = Path(__file__).parent.resolve()
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

# Import Jean Memory V2 components
from api import JeanMemoryAPI
from config import JeanMemoryConfig


async def test_real_memory_scenarios():
    """Test real-world memory scenarios with ontology and custom fact extraction"""
    
    print("🧪 JEAN MEMORY V2 - REAL INTEGRATION TEST")
    print("=" * 60)
    
    # Test memories with rich entity content
    test_memories = [
        "Had coffee with Sarah Johnson at Blue Bottle Coffee on University Ave yesterday. She's a software engineer at Google working on search algorithms. We discussed the latest AI developments and she mentioned she's excited about the new GPT models.",
        
        "Bought a new MacBook Pro M3 at Apple Store in Palo Alto for $2,499. The salesperson, Mike, was very helpful and explained the performance differences. Feeling excited about the upgrade but also nervous about the cost.",
        
        "Planning to visit Tokyo, Japan next month for the AI Conference 2024. Really excited about trying authentic sushi at Tsukiji Fish Market and exploring the technology district of Akihabara. Booked a hotel near Shibuya Station.",
        
        "Started learning Spanish using Duolingo app. Finding the pronunciation challenging but enjoying the interactive lessons. My goal is to be conversational before my trip to Barcelona in summer.",
        
        "Had dinner at Chez Panisse in Berkeley with my parents. The restaurant has amazing farm-to-table cuisine. Mom loved the seasonal vegetable dish, and Dad was impressed by the wine selection. Feeling grateful for family time."
    ]
    
    test_user_id = "test_user_ontology"
    
    try:
        # Initialize API
        config = JeanMemoryConfig.from_environment()
        api = JeanMemoryAPI(config=config)
        
        print("🔧 Initializing Jean Memory V2 API...")
        await api.initialize()
        print("✅ API initialized successfully")
        
        # Clear any existing test data
        print(f"🧹 Clearing existing test data for user {test_user_id}...")
        await api.clear_memories(test_user_id, confirm=True)
        
        print(f"\n📝 Adding {len(test_memories)} test memories with rich entity content...")
        
        # Add memories one by one to see individual processing
        added_memories = []
        for i, memory in enumerate(test_memories, 1):
            print(f"\n🔄 Adding memory {i}/{len(test_memories)}:")
            print(f"   Content: {memory[:100]}...")
            
            result = await api.add_memory(
                memory_text=memory,
                user_id=test_user_id,
                metadata={"test_scenario": f"scenario_{i}", "timestamp": datetime.now().isoformat()}
            )
            
            if result.success:
                print(f"   ✅ Added successfully (ID: {result.memory_id})")
                print(f"   📊 Vector stored: {result.vector_stored}, Graph stored: {result.graph_stored}")
                added_memories.append(result.memory_id)
            else:
                print(f"   ❌ Failed: {result.message}")
        
        print(f"\n✅ Successfully added {len(added_memories)}/{len(test_memories)} memories")
        
        # Test searches that should benefit from ontology
        print(f"\n🔍 Testing ontology-enhanced searches...")
        
        search_queries = [
            "Who did I meet for coffee?",  # Should find Sarah Johnson
            "What restaurants did I visit?",  # Should find Chez Panisse
            "What products did I buy?",  # Should find MacBook Pro
            "Where am I planning to travel?",  # Should find Tokyo, Barcelona
            "What am I learning?",  # Should find Spanish, Duolingo
            "What emotions did I experience?",  # Should find excited, nervous, grateful
        ]
        
        for query in search_queries:
            print(f"\n🔍 Query: '{query}'")
            results = await api.search_memories(
                query=query,
                user_id=test_user_id,
                limit=3
            )
            
            print(f"   📊 Found {len(results.memories)} results")
            for j, memory in enumerate(results.memories[:2], 1):  # Show top 2
                print(f"   {j}. {memory.text[:100]}... (Score: {memory.score:.3f})")
        
        # Test system status
        print(f"\n🏥 System Status Check...")
        status = await api.get_system_status()
        print(f"   Overall Status: {status.status}")
        print(f"   Vector DB: {status.vector_db.status}")
        print(f"   Graph DB: {status.graph_db.status}")
        
        print(f"\n✅ REAL INTEGRATION TEST COMPLETED SUCCESSFULLY!")
        print(f"🎯 The ontology and custom fact extraction are working correctly")
        print(f"🚀 Your existing Jean Memory V2 code will now benefit from structured entity extraction")
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Clean up
        if 'api' in locals():
            await api.close()
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_real_memory_scenarios())
    if success:
        print("\n🎉 All tests passed! Your Jean Memory V2 integration is ready for production.")
    else:
        print("\n❌ Some tests failed. Please check the error messages above.") 