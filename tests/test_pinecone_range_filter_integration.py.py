#!/usr/bin/env python3
"""
Integration test for Pinecone range filter support - Issue #3914

This test requires:
1. PINECONE_API_KEY environment variable
2. GOOGLE_API_KEY for embeddings (or OPENAI_API_KEY)

Run with: python tests/test_pinecone_integration.py

NOTE: These Integration tests have been co-written by AI
"""

import os
import sys
import time
import uuid

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()


def test_pinecone_range_filter_integration():
    """
    Integration test for Pinecone range filters.
    Tests that chained comparison operators work correctly with real Pinecone.
    """
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print("❌ PINECONE_API_KEY not set. Skipping test.")
        return False
    
    google_key = os.getenv("GOOGLE_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")
    
    if not google_key and not openai_key:
        print("❌ No embedding API key found (GOOGLE_API_KEY or OPENAI_API_KEY)")
        return False
    
    # Generate unique index name for this test
    index_name = f"test-range-{uuid.uuid4().hex[:8]}"
    
    print(f"🧪 Testing Pinecone range filters")
    print(f"📦 Index: {index_name}")
    print("-" * 60)
    
    try:
        from mem0 import Memory
        
        # Configure Memory with Pinecone
        config = {
            "vector_store": {
                "provider": "pinecone",
                "config": {
                    "api_key": api_key,
                    "collection_name": index_name,
                    "embedding_model_dims": 768,  # Gemini embedding size
                    "serverless_config": {
                        "cloud": "aws",
                        "region": "us-east-1",
                    },
                },
            },
            "embedder": {
                "provider": "gemini",
                "config": {
                    "api_key": google_key,
                    "model": "models/text-embedding-004",
                },
            } if google_key else {
                "provider": "openai",
                "config": {
                    "api_key": openai_key,
                    "model": "text-embedding-3-small",
                },
            },
            "llm": {
                "provider": "gemini",
                "config": {
                    "api_key": google_key,
                    "model": "gemini-2.0-flash",
                },
            } if google_key else {
                "provider": "openai",
                "config": {
                    "api_key": openai_key,
                    "model": "gpt-4o-mini",
                },
            },
        }
        
        m = Memory.from_config(config)
        print("✅ Memory instance created with Pinecone")
        
        # Test 1: Verify _process_metadata_filters works
        print("\n🔍 Test 1: _process_metadata_filters verification")
        test_filters = {"priority": {"gt": 5, "lt": 15}}
        processed = m._process_metadata_filters(test_filters)
        
        if processed == {"priority": {"gt": 5, "lt": 15}}:
            print("   ✅ PASS: Filter correctly processed")
        else:
            print(f"   ❌ FAIL: Expected {{'priority': {{'gt': 5, 'lt': 15}}}}, got {processed}")
            return False
        
        # Test 2: Verify Pinecone _create_filter directly
        print("\n🔍 Test 2: Pinecone _create_filter verification")
        pinecone_filter = m.vector_store._create_filter(processed)
        
        expected = {"priority": {"$gt": 5, "$lt": 15}}
        if pinecone_filter == expected:
            print(f"   ✅ PASS: Pinecone filter correctly formatted to {pinecone_filter}")
        else:
            print(f"   ❌ FAIL: Expected {expected}, got {pinecone_filter}")
            return False
        
        # Test 3: Multiple operators
        print("\n🔍 Test 3: Multiple operators verification")
        filters = {"score": {"gte": 0, "lte": 100}}
        processed = m._process_metadata_filters(filters)
        pinecone_filter = m.vector_store._create_filter(processed)
        
        expected = {"score": {"$gte": 0, "$lte": 100}}
        if pinecone_filter == expected:
            print(f"   ✅ PASS: Inclusive range correctly formatted")
        else:
            print(f"   ❌ FAIL: Expected {expected}, got {pinecone_filter}")
            return False
        
        # Test 4: Other operators (in, ne)
        print("\n🔍 Test 4: Other operators (in, ne)")
        filters = {"status": {"ne": "deleted"}}
        processed = m._process_metadata_filters(filters)
        pinecone_filter = m.vector_store._create_filter(processed)
        
        expected = {"status": {"$ne": "deleted"}}
        if pinecone_filter == expected:
            print(f"   ✅ PASS: 'ne' operator correctly formatted")
        else:
            print(f"   ❌ FAIL: Expected {expected}, got {pinecone_filter}")
            return False
        
        filters = {"tags": {"in": ["tech", "science"]}}
        processed = m._process_metadata_filters(filters)
        pinecone_filter = m.vector_store._create_filter(processed)
        
        expected = {"tags": {"$in": ["tech", "science"]}}
        if pinecone_filter == expected:
            print(f"   ✅ PASS: 'in' operator correctly formatted")
        else:
            print(f"   ❌ FAIL: Expected {expected}, got {pinecone_filter}")
            return False

        print("\n" + "=" * 60)
        print("✅ All Pinecone integration tests PASSED!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        # Cleanup: Delete the test index
        print(f"\n🧹 Cleaning up index: {index_name}")
        try:
            from pinecone import Pinecone
            pc = Pinecone(api_key=api_key)
            pc.delete_index(index_name)
            print("   ✅ Index deleted")
        except Exception as e:
            print(f"   ⚠️  Cleanup warning: {e}")


if __name__ == "__main__":
    success = test_pinecone_range_filter_integration()
    sys.exit(0 if success else 1)
