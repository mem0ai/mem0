#!/usr/bin/env python3
"""Simple Substack sync test without mem0"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Document, Memory, document_memories
from app.utils.db import get_user_and_app
import feedparser
from datetime import datetime
import re

def extract_username_from_url(url: str) -> str:
    """Extract username from Substack URL"""
    match = re.match(r'https?://(?:www\.)?([^.]+)\.substack\.com/?', url)
    if match:
        return match.group(1)
    return None

def sync_substack_posts_simple(supabase_user_id: str, substack_url: str, max_posts: int = 3):
    """Sync Substack posts for a user (SQL only, no mem0)"""
    
    # Extract username
    username = extract_username_from_url(substack_url)
    if not username:
        return f"Error: Invalid Substack URL format. Expected: https://username.substack.com"
    
    # Get RSS feed URL
    feed_url = f"{substack_url.rstrip('/')}/feed"
    
    print(f"Fetching posts from: {feed_url}")
    
    try:
        # Parse RSS feed
        feed = feedparser.parse(feed_url)
        if not feed.entries:
            return f"Error: No posts found at {feed_url}"
        
        db = SessionLocal()
        
        try:
            # Get or create user and app
            user, app = get_user_and_app(
                db,
                supabase_user_id=supabase_user_id,
                app_name="substack",
                email=f"{username}@substack.test"
            )
            
            print(f"✓ User: {user.email}, App: {app.name}")
            
            synced_count = 0
            
            for entry in feed.entries[:max_posts]:
                # Check if document already exists
                existing_doc = db.query(Document).filter(
                    Document.source_url == entry.link,
                    Document.user_id == user.id
                ).first()
                
                if existing_doc:
                    print(f"  - Skipping (already exists): {entry.title}")
                    continue
                
                # Extract content (limit for display)
                content = entry.content[0].value if 'content' in entry else entry.summary
                
                # Create document
                doc = Document(
                    user_id=user.id,
                    app_id=app.id,
                    title=entry.title,
                    source_url=entry.link,
                    document_type="substack",
                    content=content,
                    metadata_={
                        "author": entry.author if 'author' in entry else username,
                        "published_date": entry.published if 'published' in entry else None,
                        "word_count": len(content.split()),
                        "substack_username": username
                    }
                )
                db.add(doc)
                db.flush()  # Get the ID
                
                # Create summary memory
                summary = f"Essay: {entry.title}"
                if 'summary' in entry:
                    # Clean HTML from summary
                    import re
                    clean_summary = re.sub('<.*?>', '', entry.summary)
                    summary += f" - {clean_summary[:200]}..."
                
                # Create SQL memory record
                summary_memory = Memory(
                    user_id=user.id,
                    app_id=app.id,
                    content=summary,
                    metadata_={
                        "document_id": str(doc.id),
                        "type": "document_summary",
                        "source_url": entry.link
                    }
                )
                db.add(summary_memory)
                db.flush()
                
                # Link document to memory
                db.execute(
                    document_memories.insert().values(
                        document_id=doc.id,
                        memory_id=summary_memory.id
                    )
                )
                
                print(f"  ✓ Synced: {entry.title}")
                print(f"    - Content length: {len(content)} chars")
                print(f"    - Word count: {len(content.split())} words")
                synced_count += 1
            
            db.commit()
            
            # Show what's in the database
            print(f"\n📊 Database Summary:")
            total_docs = db.query(Document).filter(
                Document.user_id == user.id,
                Document.document_type == "substack"
            ).count()
            print(f"  - Total Substack documents: {total_docs}")
            
            total_memories = db.query(Memory).filter(
                Memory.user_id == user.id,
                Memory.app_id == app.id
            ).count()
            print(f"  - Total Substack memories: {total_memories}")
            
            return f"\n✅ Successfully synced {synced_count} new posts from {username}'s Substack"
            
        finally:
            db.close()
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Error syncing Substack: {str(e)}"

if __name__ == "__main__":
    # Test with a real Substack
    test_user_id = "test-user-456"
    test_url = "https://jonathanpolitzki.substack.com/"  # Casey Newton's Platformer
    
    print("🚀 Starting Substack sync test (SQL only)\n")
    result = sync_substack_posts_simple(test_user_id, test_url, max_posts=2)
    print(result) 