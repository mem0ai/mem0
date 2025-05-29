"""
Substack integration service for OpenMemory.
Handles syncing Substack posts to documents and memories.
"""
import asyncio
import re
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.models import Document, Memory, User, App, document_memories, MemoryState
from app.integrations.substack_scraper import SubstackScraper, Post
from app.utils.db import get_user_and_app
from app.utils.memory import get_memory_client
from app.services.chunking_service import ChunkingService
import logging

logger = logging.getLogger(__name__)


class SubstackService:
    """Service for syncing Substack posts to OpenMemory"""
    
    @staticmethod
    def normalize_substack_url(url: str) -> str:
        """Normalize Substack URL by adding protocol if missing"""
        url = url.strip()
        
        # If no protocol, add https://
        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"
        
        # Remove trailing slash
        url = url.rstrip('/')
        
        return url
    
    @staticmethod
    def extract_username_from_url(url: str) -> Optional[str]:
        """Extract username from Substack URL"""
        # First normalize the URL
        url = SubstackService.normalize_substack_url(url)
        
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
            return 0, "Error: Invalid Substack URL format. Expected: https://username.substack.com or username.substack.com"
        
        # Use normalized URL for scraping
        normalized_url = self.normalize_substack_url(substack_url)
        
        # Get or create user and app
        user, app = get_user_and_app(
            db,
            supabase_user_id=supabase_user_id,
            app_name="substack",
            email=None
        )
        
        if not app.is_active:
            return 0, "Error: Substack app is paused. Cannot sync posts."
        
        # Initialize scraper with normalized URL
        scraper = SubstackScraper(normalized_url, max_posts=max_posts)
        
        try:
            # Scrape posts
            logger.info(f"Starting to scrape posts from {normalized_url} (max: {max_posts})")
            posts = await scraper.scrape()
            if not posts:
                # More informative error message
                error_msg = f"No posts found at {normalized_url}. This could mean:\n"
                error_msg += f"1. The blog has no published posts\n"
                error_msg += f"2. The RSS feed is disabled\n" 
                error_msg += f"3. The blog URL format is incorrect\n"
                error_msg += f"4. The blog might be private or require authentication\n"
                error_msg += f"Please verify the URL and try again."
                return 0, error_msg
            
            logger.info(f"Found {len(posts)} posts to process")
            
            # Initialize memory client if needed
            memory_client = None
            if use_mem0:
                try:
                    memory_client = get_memory_client()
                    logger.info("Memory client initialized successfully")
                except Exception as e:
                    logger.warning(f"Could not initialize memory client: {e}. Continuing without mem0.")
                    use_mem0 = False
            
            synced_count = 0
            
            for i, post in enumerate(posts, 1):
                logger.info(f"Processing post {i}/{len(posts)}: {post.title}")
                
                # Check if document already exists and has active content
                existing_doc = db.query(Document).filter(
                    Document.source_url == post.url,
                    Document.user_id == user.id
                ).first()
                
                should_skip = False
                if existing_doc:
                    # Check if this document has any active memories
                    active_memories = db.query(Memory).filter(
                        Memory.user_id == user.id,
                        Memory.state == MemoryState.active,
                        text("metadata->>'document_id' = :doc_id")
                    ).params(doc_id=str(existing_doc.id)).count()
                    
                    if active_memories > 0:
                        logger.info(f"Skipping existing post with active memories: {post.title}")
                        should_skip = True
                    else:
                        # Document exists but no active memories - allow re-import by removing old document
                        logger.info(f"Re-importing post (no active memories found): {post.title}")
                        db.delete(existing_doc)
                        db.flush()
                
                if should_skip:
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
                
                # Create a more comprehensive summary that captures key sections
                summary_text = f"Essay: {post.title}"
                
                # Extract meaningful sections from the essay
                content_length = len(post.content)
                if content_length > 1500:
                    # For longer essays, sample from beginning, middle, and end
                    intro = post.content[:500].strip()
                    middle_start = content_length // 2 - 250
                    middle = post.content[middle_start:middle_start + 500].strip()
                    conclusion = post.content[-500:].strip()
                    
                    summary_text += f"\n\n[Beginning]: {intro}...\n\n[Middle]: ...{middle}...\n\n[End]: ...{conclusion}"
                elif content_length > 500:
                    # For medium essays, take more content
                    summary_text += f" - {post.content[:1000]}..."
                else:
                    # For short content, include everything
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
            
            # NEW: Automatically chunk all newly synced documents
            if synced_count > 0:
                logger.info(f"Starting automatic chunking for {synced_count} new documents...")
                try:
                    chunking_service = ChunkingService()
                    # Chunk all documents for this user
                    chunked_count = chunking_service.chunk_all_documents(db, str(user.id))
                    logger.info(f"Successfully chunked {chunked_count} documents")
                except Exception as chunk_error:
                    logger.error(f"Error during automatic chunking: {chunk_error}")
                    # Don't fail the sync if chunking fails
            
            return synced_count, f"Successfully synced {synced_count} posts from {username}'s Substack"
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error syncing Substack: {e}")
            return 0, f"Error syncing Substack: {str(e)}" 