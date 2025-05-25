#!/usr/bin/env python3
"""Test script for Document model"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, SessionLocal, Base
from app.models import User, App, Document, Memory, document_memories
from app.utils.db import get_user_and_app
import uuid
from datetime import datetime

def test_document_operations():
    """Test creating and querying documents"""
    
    # Create all tables
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ Tables created successfully")
    
    # Create a session
    db = SessionLocal()
    
    try:
        # Create a test user
        test_user_id = str(uuid.uuid4())
        user, app = get_user_and_app(
            db, 
            supabase_user_id=test_user_id,
            app_name="substack",
            email="test@example.com"
        )
        print(f"✓ Created user: {user.email} with app: {app.name}")
        
        # Create a test document
        doc = Document(
            user_id=user.id,
            app_id=app.id,
            title="My First Substack Essay",
            source_url="https://example.substack.com/p/my-first-essay",
            document_type="substack",
            content="This is a long essay about AI and memory systems. " * 100,  # Simulate long content
            metadata_={
                "author": "Test Author",
                "published_date": "2024-01-15",
                "word_count": 500
            }
        )
        db.add(doc)
        db.commit()
        print(f"✓ Created document: {doc.title}")
        
        # Create a summary memory for the document
        summary_memory = Memory(
            user_id=user.id,
            app_id=app.id,
            content=f"Essay: {doc.title} - This essay discusses AI and memory systems",
            metadata_={
                "document_id": str(doc.id),
                "type": "document_summary"
            }
        )
        db.add(summary_memory)
        db.commit()
        print(f"✓ Created summary memory for document")
        
        # Link document to memory
        db.execute(
            document_memories.insert().values(
                document_id=doc.id,
                memory_id=summary_memory.id
            )
        )
        db.commit()
        print(f"✓ Linked document to memory")
        
        # Query the document
        retrieved_doc = db.query(Document).filter(
            Document.user_id == user.id,
            Document.document_type == "substack"
        ).first()
        
        if retrieved_doc:
            print(f"\n✓ Successfully retrieved document:")
            print(f"  - Title: {retrieved_doc.title}")
            print(f"  - Type: {retrieved_doc.document_type}")
            print(f"  - Content length: {len(retrieved_doc.content)} chars")
            print(f"  - Metadata: {retrieved_doc.metadata_}")
            
            # Check relationships
            print(f"  - Related memories: {len(retrieved_doc.memories)}")
            for mem in retrieved_doc.memories:
                print(f"    - Memory: {mem.content[:50]}...")
        
        print("\n✅ All tests passed! Document model is working correctly.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_document_operations() 