#!/usr/bin/env python3
"""
Integration test for delete_all() bug fix (Issue #3918)

This script uses REAL Qdrant and OpenAI to verify that delete_all() with filters
only deletes the specified user's memories, not ALL memories.

Prerequisites:
- Qdrant running locally (default: http://localhost:6333)
- OPENAI_API_KEY in .env file

Run: python test_delete_all_bug_integration.py
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from mem0 import Memory
from mem0.configs.base import MemoryConfig

def test_delete_all_preserves_other_users_memories():
    """
    Integration test: Verify delete_all(user_id=X) only deletes user X's memories.

    This test would FAIL with the bug (reset() call), because ALL users' data
    would be wiped when deleting user_a's memories.
    """
    print("=" * 70)
    print("Integration Test: delete_all() Bug Fix Verification")
    print("=" * 70)

    # Create a unique collection name for this test
    import uuid
    test_collection = f"test_delete_all_{uuid.uuid4().hex[:8]}"

    print(f"\n1. Setting up Memory with collection: {test_collection}")

    # Configure Memory with Qdrant (local) and OpenAI
    config = MemoryConfig(
        vector_store={
            "provider": "qdrant",
            "config": {
                "collection_name": test_collection,
                "host": "localhost",
                "port": 6333,
            }
        },
        llm={
            "provider": "openai",
            "config": {
                "model": "gpt-4o-mini",
                "temperature": 0,
            }
        },
        embedder={
            "provider": "openai",
            "config": {
                "model": "text-embedding-3-small"
            }
        }
    )

    memory = Memory(config)

    try:
        # Step 2: Add memories for User A
        print("\n2. Adding memories for user_a...")
        memory.add(
            "I love Python programming",
            user_id="user_a"
        )
        memory.add(
            "My favorite framework is FastAPI",
            user_id="user_a"
        )
        print("   ✓ Added 2 memories for user_a")

        # Step 3: Add memories for User B
        print("\n3. Adding memories for user_b...")
        memory.add(
            "I prefer JavaScript",
            user_id="user_b"
        )
        memory.add(
            "React is my go-to library",
            user_id="user_b"
        )
        print("   ✓ Added 2 memories for user_b")

        # Step 4: Add memories for User C
        print("\n4. Adding memories for user_c...")
        memory.add(
            "I work with Go language",
            user_id="user_c"
        )
        print("   ✓ Added 1 memory for user_c")

        # Step 5: Verify all memories exist
        print("\n5. Verifying all memories exist before deletion...")
        user_a_before = memory.get_all(user_id="user_a")
        user_b_before = memory.get_all(user_id="user_b")
        user_c_before = memory.get_all(user_id="user_c")

        print(f"   user_a: {len(user_a_before['results'])} memories")
        print(f"   user_b: {len(user_b_before['results'])} memories")
        print(f"   user_c: {len(user_c_before['results'])} memories")

        assert len(user_a_before['results']) == 2, "user_a should have 2 memories"
        assert len(user_b_before['results']) == 2, "user_b should have 2 memories"
        assert len(user_c_before['results']) == 1, "user_c should have 1 memory"
        print("   ✓ All memories verified")

        # Step 6: Delete ONLY user_a's memories
        print("\n6. Calling delete_all(user_id='user_a')...")
        result = memory.delete_all(user_id="user_a")
        print(f"   Result: {result['message']}")

        # Step 7: THE CRITICAL TEST - Verify other users' data still exists
        print("\n7. Verifying other users' memories are PRESERVED...")
        user_a_after = memory.get_all(user_id="user_a")
        user_b_after = memory.get_all(user_id="user_b")
        user_c_after = memory.get_all(user_id="user_c")

        print(f"   user_a: {len(user_a_after['results'])} memories (should be 0)")
        print(f"   user_b: {len(user_b_after['results'])} memories (should be 2)")
        print(f"   user_c: {len(user_c_after['results'])} memories (should be 1)")

        # These assertions would FAIL with the bug
        assert len(user_a_after['results']) == 0, "❌ user_a memories should be deleted"
        assert len(user_b_after['results']) == 2, "❌ BUG: user_b memories were deleted! reset() was called!"
        assert len(user_c_after['results']) == 1, "❌ BUG: user_c memories were deleted! reset() was called!"

        print("\n" + "=" * 70)
        print("✅ TEST PASSED: Bug fix verified!")
        print("=" * 70)
        print("\n✓ delete_all(user_id='user_a') only deleted user_a's memories")
        print("✓ user_b and user_c memories were preserved")
        print("✓ No reset() call detected")
        print("\nThe bug fix is working correctly! 🎉")

        return True

    except AssertionError as e:
        print("\n" + "=" * 70)
        print("❌ TEST FAILED")
        print("=" * 70)
        print(f"\nAssertion Error: {e}")
        print("\nThis indicates the bug still exists:")
        print("- reset() was likely called, wiping ALL users' memories")
        print("- Only filtered memories should be deleted")
        return False

    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup: Delete the test collection
        print(f"\n8. Cleaning up test collection: {test_collection}...")
        try:
            memory.reset()
            print("   ✓ Test collection cleaned up")
        except Exception as e:
            print(f"   ⚠ Cleanup warning: {e}")


if __name__ == "__main__":
    print("\n🧪 Starting integration test for delete_all() bug fix...")
    print("\nChecking prerequisites...")

    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY not found in environment")
        print("   Make sure .env file exists with OPENAI_API_KEY set")
        sys.exit(1)
    print("✓ OPENAI_API_KEY found")

    # Check if Qdrant is accessible
    print("✓ Assuming Qdrant is running on localhost:6333")
    print("  (If not, start it with: docker run -p 6333:6333 qdrant/qdrant)")

    # Run the test
    success = test_delete_all_preserves_other_users_memories()

    sys.exit(0 if success else 1)
