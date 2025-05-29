"""
Substack integration service for OpenMemory.
Handles syncing Substack posts to documents and memories.
"""
import asyncio
import re
import gc  # Add garbage collection for memory optimization
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime

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
        use_mem0: bool = True,
        progress_callback=None
    ) -> Tuple[int, str]:
        """
        Sync Substack posts for a user - PHASE 1 ONLY (documents + basic memories).
        Chunking happens separately in background.
        
        Args:
            progress_callback: Optional callback function(progress: int, message: str, documents_synced: int)
        
        Returns:
            Tuple of (synced_count, status_message)
        """
        # Report progress
        if progress_callback:
            progress_callback(0, "Starting Substack sync...", 0)
            
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
            if progress_callback:
                progress_callback(10, f"Fetching posts from {username}'s Substack...", 0)
                
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
            if progress_callback:
                progress_callback(20, f"Found {len(posts)} posts to process", 0)

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

            # PHASE 1: Process posts ONE BY ONE for memory efficiency
            for i, post in enumerate(posts, 1):
                logger.info(f"Processing post {i}/{len(posts)}: {post.title}")
                
                # Calculate progress (20-90% range for post processing)
                post_progress = 20 + int((i / len(posts)) * 70)
                if progress_callback:
                    progress_callback(post_progress, f"Syncing essay: {post.title}", synced_count)

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

                # Create document (STORE FULL CONTENT in PostgreSQL)
                doc = Document(
                    user_id=user.id,
                    app_id=app.id,
                    title=post.title,
                    source_url=post.url,
                    document_type="substack",
                    content=post.content,  # Keep full content in PostgreSQL
                    metadata_={
                        "author": username,
                        "published_date": post.date.isoformat() if post.date else None,
                        "word_count": len(post.content.split()),
                        "char_count": len(post.content),
                        "substack_username": username,
                        "needs_chunking": True  # Mark for Phase 2 processing
                    }
                )
                db.add(doc)
                db.flush()  # Get the ID immediately

                # Create LIGHTWEIGHT summary for memory systems (LIMIT SIZE for vector DB)
                summary_text = f"Essay: {post.title}"
                # For large posts, create a meaningful but limited summary
                if len(post.content) > 1000:
                    # Take first 800 chars for better context than just 500
                    summary_text += f" - {post.content[:800]}..."
                else:
                    summary_text += f" - {post.content}"

                # Add to mem0 if available (HEAVILY LIMIT SIZE for vector DB memory efficiency)
                if use_mem0 and memory_client:
                    try:
                        # Strict limit for vector DB to prevent memory issues
                        mem0_content = summary_text[:1200] if len(summary_text) > 1200 else summary_text
                        mem0_response = memory_client.add(
                            messages=mem0_content,
                            user_id=supabase_user_id,
                            metadata={
                                "source_app": "substack",
                                "document_id": str(doc.id),
                                "type": "document_summary",
                                "app_db_id": str(app.id),
                                "processing_phase": "phase1"  # Mark as basic processing
                            }
                        )
                        logger.info(f"Added to mem0: {post.title}")
                    except Exception as e:
                        logger.error(f"Error adding to mem0: {e}")

                # Create SQL memory record (can be longer than vector DB version)
                summary_memory = Memory(
                    user_id=user.id,
                    app_id=app.id,
                    content=summary_text,  # Use the same summary (PostgreSQL can handle it)
                    metadata_={
                        "document_id": str(doc.id),
                        "type": "document_summary",
                        "source_url": post.url,
                        "title": post.title,
                        "processing_phase": "phase1"
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

                # COMMIT IMMEDIATELY for each post (memory efficient)
                db.commit()
                
                synced_count += 1
                logger.info(f"Synced: {post.title} ({len(post.content)} chars)")
                
                # MEMORY OPTIMIZATION: Force garbage collection periodically
                if i % 3 == 0:  # Every 3 posts, more frequent for large posts
                    gc.collect()
                    logger.info(f"Performed garbage collection after {i} posts")
                
                # Update progress after each successful sync
                if progress_callback:
                    progress_callback(post_progress, f"Synced: {post.title}", synced_count)

                # Small delay to prevent overwhelming the system
                await asyncio.sleep(0.2)  # Slightly longer delay for stability

            if progress_callback:
                progress_callback(100, f"Completed! Synced {synced_count} posts", synced_count)

            # NOTE: Chunking is now handled separately by background service
            return synced_count, f"Successfully synced {synced_count} posts from {username}'s Substack. Advanced processing will continue in background."

        except Exception as e:
            db.rollback()
            logger.error(f"Error syncing Substack: {e}")
            return 0, f"Error syncing Substack: {str(e)}" 