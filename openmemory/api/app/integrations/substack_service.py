"""
Substack integration service for OpenMemory.
Handles syncing Substack posts to documents and memories.
"""
import asyncio
import re
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models import Document, Memory, User, App, document_memories
from app.integrations.substack_scraper import SubstackScraper, Post
from app.utils.db import get_user_and_app
from app.utils.memory import get_memory_client
import logging

logger = logging.getLogger(__name__)


class SubstackService:
    """Service for syncing Substack posts to OpenMemory"""
    
    @staticmethod
    def extract_username_from_url(url: str) -> Optional[str]:
        """Extract username from Substack URL"""
        match = re.match(r'https?://(?:www\.)?([^.]+)\.substack\.com/?', url)
        if match:
            return match.group(1)
        return None
    
    async def sync_substack_posts(
        self, 
        db: Session,
        supabase_user_id: str, 
        substack_url: str, 
        max_posts: int = 20,
        use_mem0: bool = True
    ) -> Tuple[int, str]:
        """
        Sync Substack posts for a user.
        
        Returns:
            Tuple of (synced_count, status_message)
        """
        # Validate URL
        username = self.extract_username_from_url(substack_url)
        if not username:
            return 0, "Error: Invalid Substack URL format. Expected: https://username.substack.com"
        
        # Get or create user and app
        user, app = get_user_and_app(
            db,
            supabase_user_id=supabase_user_id,
            app_name="substack",
            email=None
        )
        
        if not app.is_active:
            return 0, "Error: Substack app is paused. Cannot sync posts."
        
        # Initialize scraper
        scraper = SubstackScraper(substack_url, max_posts=max_posts)
        
        try:
            # Scrape posts
            posts = await scraper.scrape()
            if not posts:
                return 0, f"No posts found at {substack_url}"
            
            # Initialize memory client if needed
            memory_client = None
            if use_mem0:
                try:
                    memory_client = get_memory_client()
                except Exception as e:
                    logger.warning(f"Could not initialize memory client: {e}. Continuing without mem0.")
                    use_mem0 = False
            
            synced_count = 0
            
            for post in posts:
                # Check if document already exists
                existing_doc = db.query(Document).filter(
                    Document.source_url == post.url,
                    Document.user_id == user.id
                ).first()
                
                if existing_doc:
                    logger.info(f"Skipping existing post: {post.title}")
                    continue
                
                # Create document
                doc = Document(
                    user_id=user.id,
                    app_id=app.id,
                    title=post.title,
                    source_url=post.url,
                    document_type="substack",
                    content=post.content,
                    metadata_={
                        "author": username,
                        "published_date": post.date.isoformat() if post.date else None,
                        "word_count": len(post.content.split()),
                        "char_count": len(post.content),
                        "substack_username": username
                    }
                )
                db.add(doc)
                db.flush()  # Get the ID
                
                # Create summary (first 500 chars of content)
                summary_text = f"Essay: {post.title}"
                if len(post.content) > 500:
                    summary_text += f" - {post.content[:500]}..."
                else:
                    summary_text += f" - {post.content}"
                
                # Add to mem0 if available
                if use_mem0 and memory_client:
                    try:
                        mem0_response = memory_client.add(
                            messages=summary_text,
                            user_id=supabase_user_id,
                            metadata={
                                "source_app": "substack",
                                "document_id": str(doc.id),
                                "type": "document_summary",
                                "app_db_id": str(app.id)
                            }
                        )
                        logger.info(f"Added to mem0: {post.title}")
                    except Exception as e:
                        logger.error(f"Error adding to mem0: {e}")
                
                # Create SQL memory record
                summary_memory = Memory(
                    user_id=user.id,
                    app_id=app.id,
                    content=summary_text,
                    metadata_={
                        "document_id": str(doc.id),
                        "type": "document_summary",
                        "source_url": post.url,
                        "title": post.title
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
                
                logger.info(f"Synced: {post.title} ({len(post.content)} chars)")
                synced_count += 1
            
            db.commit()
            
            return synced_count, f"Successfully synced {synced_count} posts from {username}'s Substack"
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error syncing Substack: {e}")
            return 0, f"Error syncing Substack: {str(e)}" 