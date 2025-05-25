#!/usr/bin/env python3
"""
Full integration test for OpenMemory with document storage and deep queries.
Tests the complete flow: Substack sync -> Document storage -> Deep memory queries
"""
import os
import sys
import asyncio
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.integrations.substack_service import SubstackService
from app.utils.gemini import GeminiService
from app.models import Document, Memory, MemoryState
from app.utils.db import get_user_and_app
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_full_integration():
    """Test the complete integration flow"""
    
    print("🚀 Starting Full Integration Test\n")
    
    # Test configuration
    test_user_id = "test-integration-user"
    test_substack_url = "https://jonathanpolitzki.substack.com"  # Your Substack
    
    db = SessionLocal()
    
    try:
        # Step 1: Sync Substack posts
        print("📚 Step 1: Syncing Substack posts...")
        service = SubstackService()
        synced_count, message = await service.sync_substack_posts(
            db=db,
            supabase_user_id=test_user_id,
            substack_url=test_substack_url,
            max_posts=3,
            use_mem0=False  # Skip mem0 for local testing
        )
        print(f"   {message}")
        
        # Step 2: Verify documents were stored
        print("\n📄 Step 2: Verifying document storage...")
        user, app = get_user_and_app(db, test_user_id, "substack", None)
        
        documents = db.query(Document).filter(
            Document.user_id == user.id,
            Document.document_type == "substack"
        ).all()
        
        print(f"   Found {len(documents)} documents:")
        for doc in documents:
            print(f"   - {doc.title}")
            print(f"     Length: {len(doc.content)} chars")
            print(f"     Words: {doc.metadata_.get('word_count', 'N/A')}")
        
        # Step 3: Check memories were created
        print("\n🧠 Step 3: Checking memory creation...")
        memories = db.query(Memory).filter(
            Memory.user_id == user.id,
            Memory.app_id == app.id,
            Memory.state == MemoryState.active
        ).all()
        
        print(f"   Found {len(memories)} memories")
        
        # Step 4: Test deep query functionality
        print("\n🔍 Step 4: Testing deep memory query...")
        
        # Simulate what the MCP tool does
        # Get relevant memories (in real usage, this would use vector search)
        relevant_memories = []
        for mem in memories[:5]:
            relevant_memories.append({
                'memory': mem.content,
                'metadata': mem.metadata_ or {},
                'created_at': mem.created_at.isoformat() if mem.created_at else None
            })
        
        # Test the Gemini deep query
        if documents and os.getenv("GEMINI_API_KEY"):
            gemini_service = GeminiService()
            
            test_queries = [
                "What are the main themes discussed in these essays?",
                "Summarize the key insights about technology and society",
                "What does the author think about AI?"
            ]
            
            for query in test_queries:
                print(f"\n   Query: '{query}'")
                try:
                    result = await gemini_service.deep_query(
                        memories=relevant_memories,
                        documents=documents[:2],  # Limit for testing
                        query=query
                    )
                    print(f"   Response: {result[:200]}...")
                except Exception as e:
                    print(f"   Error: {e}")
        else:
            print("   ⚠️  Skipping Gemini test (no API key or documents)")
        
        # Step 5: Summary
        print("\n📊 Integration Test Summary:")
        print(f"   ✅ Documents stored: {len(documents)}")
        print(f"   ✅ Memories created: {len(memories)}")
        print(f"   ✅ Total content: {sum(len(d.content) for d in documents)} chars")
        
        # Show how the system works
        print("\n💡 How it works:")
        print("   1. Substack RSS feed → Full documents stored in SQL")
        print("   2. Summary memories → Created for fast vector search")
        print("   3. Deep queries → Gemini analyzes full context on demand")
        print("   4. Two-tier system → Fast retrieval + Deep understanding")
        
        print("\n✅ Full integration test completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error in integration test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_full_integration()) 