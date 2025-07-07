"""
Substack integration service for OpenMemory.
Handles syncing Substack posts to documents and memories.
"""
import asyncio
import re
import gc  # Add garbage collection for memory optimization
import psutil  # Add memory monitoring
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import time

from app.models import Document, Memory, User, App, document_memories, MemoryState
from app.integrations.substack_scraper import SubstackScraper, Post
from app.utils.db import get_user_and_app
from app.utils.memory import get_memory_client
from app.services.chunking_service import ChunkingService
import logging

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds
MEMORY_LIMIT_MB = 1500  # 1.5GB limit for 2GB container

async def retry_with_exponential_backoff(func, *args, max_retries=MAX_RETRIES, **kwargs):
    """Retry function with exponential backoff and memory checks"""
    for attempt in range(max_retries):
        try:
            # Check memory before each attempt
            memory_usage = psutil.Process().memory_info().rss / 1024 / 1024  # MB
            if memory_usage > MEMORY_LIMIT_MB:
                logger.warning(f"Memory usage high: {memory_usage:.1f}MB, forcing garbage collection")
                gc.collect()
                await asyncio.sleep(1)  # Give GC time to work
                
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
            
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Final attempt failed for {func.__name__}: {e}")
                raise
            
            delay = RETRY_DELAY * (2 ** attempt)  # Exponential backoff
            logger.warning(f"Attempt {attempt + 1} failed for {func.__name__}: {e}. Retrying in {delay}s...")
            await asyncio.sleep(delay)
            
            # Force garbage collection on retry
            gc.collect()

def check_memory_and_cleanup():
    """Check memory usage and cleanup if needed"""
    try:
        memory_usage = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        if memory_usage > MEMORY_LIMIT_MB:
            logger.warning(f"Memory usage: {memory_usage:.1f}MB exceeds limit, forcing cleanup")
            gc.collect()
            return True
        return False
    except Exception as e:
        logger.error(f"Error checking memory: {e}")
        return False

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

            # PHASE 1: Process posts ONE BY ONE for memory efficiency with retries
            for i, post in enumerate(posts, 1):
                logger.info(f"Processing post {i}/{len(posts)}: {post.title}")
                
                # Calculate progress (20-90% range for post processing)
                post_progress = 20 + int((i / len(posts)) * 70)
                if progress_callback:
                    progress_callback(post_progress, f"Syncing essay: {post.title}", synced_count)

                # Check memory before processing each post
                check_memory_and_cleanup()

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

                # Process this post with retry logic
                try:
                    await self._process_single_post_with_retries(
                        db, user, app, post, username, supabase_user_id, 
                        use_mem0, memory_client, i
                    )
                    synced_count += 1
                    
                    # Update progress after each successful sync
                    if progress_callback:
                        progress_callback(post_progress, f"Synced: {post.title}", synced_count)
                    
                except Exception as e:
                    logger.error(f"Failed to process post {post.title} after retries: {e}")
                    # Continue with next post instead of failing entire sync
                    continue

                # MEMORY OPTIMIZATION: Force garbage collection every 5 posts with 2GB
                if i % 5 == 0:
                    gc.collect()
                    logger.info(f"Performed garbage collection after {i} posts")
                
                # Shorter delay with more memory available
                await asyncio.sleep(0.1)

            if progress_callback:
                progress_callback(100, f"Completed! Synced {synced_count} posts", synced_count)

            # NOTE: Chunking is now handled separately by background service
            return synced_count, f"Successfully synced {synced_count} posts from {username}'s Substack. Advanced processing will continue in background."

        except Exception as e:
            db.rollback()
            logger.error(f"Error syncing Substack: {e}")
            return 0, f"Error syncing Substack: {str(e)}" 

    async def _process_single_post_with_retries(
        self, db: Session, user: User, app: App, post: Post, username: str,
        supabase_user_id: str, use_mem0: bool, memory_client, post_index: int
    ):
        """Process a single post with retry logic and memory monitoring"""
        
        async def process_post():
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
                    mem0_response = await retry_with_exponential_backoff(
                        memory_client.add,
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
                    logger.error(f"Error adding to mem0 (after retries): {e}")

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
            
            logger.info(f"Synced: {post.title} ({len(post.content)} chars)")
            return doc

        # Execute with retry logic
        return await retry_with_exponential_backoff(process_post)


# Jean Memory V2 Integration Function - follows Twitter pattern exactly
async def sync_substack_to_memory(
    substack_url: str,
    user_id: str, 
    app_id: str, 
    db_session,
    max_posts: int = 20,
    progress_callback: Optional[callable] = None
):
    """
    Sync Substack posts to memory using Jean Memory V2.
    Adapts existing infrastructure to follow Twitter integration pattern.
    """
    from app.models import Memory, App, User
    from app.utils.memory import get_async_memory_client
    from sqlalchemy.sql import exists
    from uuid import UUID
    import re
    
    def safe_uuid(id_str):
        """Convert string to UUID, handling local development IDs"""
        try:
            return UUID(id_str)
        except ValueError:
            if id_str == 'default_user':
                return UUID('00000000-0000-0000-0000-000000000001')
            if id_str == 'substack':
                return UUID('00000000-0000-0000-0000-000000000003')
            return UUID('00000000-0000-0000-0000-000000000099')

    def report_progress(progress: int, message: str, count: int = 0):
        if progress_callback:
            progress_callback(progress, message, count)

    # Get Jean Memory V2 client
    memory_client = await get_async_memory_client()
    
    # Validate and extract username from URL
    normalized_url = SubstackService.normalize_substack_url(substack_url)
    username = SubstackService.extract_username_from_url(normalized_url)
    if not username:
        report_progress(100, "Error: Invalid Substack URL format", 0)
        return 0
    
    # For local development, ensure the user and app exist
    user_uuid = safe_uuid(user_id)
    app_uuid = safe_uuid(app_id)
    
    # Check if this is local development mode
    if user_id == 'default_user' or app_id == 'substack':
        logger.info("Local development mode detected, ensuring user and app exist in database")
        
        # Check if the user exists, create if not
        user_exists = db_session.query(exists().where(User.id == user_uuid)).scalar()
        if not user_exists:
            logger.info(f"Creating mock user for local development with id {user_uuid}")
            mock_user = User(
                id=user_uuid,
                email='local-dev@example.com',
                display_name='Local Dev User',
                is_active=True
            )
            db_session.add(mock_user)
        
        # Check if the Substack app exists, create if not
        app_exists = db_session.query(exists().where(App.id == app_uuid)).scalar()
        if not app_exists:
            logger.info(f"Creating Substack app for local development with id {app_uuid}")
            substack_app = App(
                id=app_uuid,
                name='Substack',
                description='Substack Integration',
                owner_id=user_uuid,
                is_active=True
            )
            db_session.add(substack_app)
            
        # Commit these changes before proceeding
        db_session.commit()
        logger.info("Ensured user and app exist in database for local development")
    
    try:
        report_progress(5, "Starting Substack sync...", 0)
        
        # Use existing scraper infrastructure
        scraper = SubstackScraper(normalized_url, max_posts=max_posts)
        posts = await scraper.scrape()
        
        if not posts:
            report_progress(100, f"No posts found at {normalized_url}. The blog might be private or have no published posts.", 0)
            return 0
        
        logger.info(f"Found {len(posts)} posts to process")
        report_progress(20, f"Found {len(posts)} posts. Formatting for memory...", len(posts))
        
        # Format posts for memory - following Twitter pattern
        memory_contents = []
        for post in posts:
            # Create memory-friendly content similar to Twitter format
            memory_text = f"Substack post by {username}: {post.title}"
            
            # Add content summary (limit length for memory efficiency)
            if post.content:
                # Take first 800 characters for context (more than tweets but manageable)
                summary = post.content[:800] + "..." if len(post.content) > 800 else post.content
                memory_text += f" - {summary}"
            
            # Add date if available
            if post.date:
                if isinstance(post.date, datetime):
                    date_str = post.date.strftime('%Y-%m-%d')
                else:
                    date_str = str(post.date)
                memory_text += f" (published on {date_str})"
                
            memory_contents.append(memory_text)
        
        # Store posts using memory client - following Twitter pattern exactly
        synced_count = 0
        failed_count = 0
        
        # Process posts in smaller batches (posts are longer than tweets)
        batch_size = 3  # Process 3 posts at a time
        
        for i in range(0, len(memory_contents), batch_size):
            batch = memory_contents[i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(memory_contents) + batch_size - 1)//batch_size} ({len(batch)} posts)")
            
            for j, content in enumerate(batch):
                try:
                    post_index = i + j
                    logger.debug(f"Adding post {post_index+1} to memory: {posts[post_index].title}")
                    
                    # Create memory metadata - following Twitter pattern
                    memory_metadata = {
                        'source': 'substack',
                        'source_app': 'substack',
                        'username': username,
                        'type': 'post',
                        'post_index': post_index,
                        'post_data': {
                            'title': posts[post_index].title,
                            'url': posts[post_index].url,
                            'date': posts[post_index].date.isoformat() if posts[post_index].date else None
                        }
                    }
                    
                    # Create database record - following Twitter pattern
                    db_memory = Memory(
                        user_id=safe_uuid(user_id),
                        app_id=safe_uuid(app_id),
                        content=content,
                        metadata_=memory_metadata
                    )
                    db_session.add(db_memory)
                    db_session.flush()  # Get the ID without committing
                    
                    # Add to vector store using Jean Memory V2 async client - EXACTLY like Twitter
                    try:
                        response = await memory_client.add(
                            messages=content,
                            user_id=user_id,  # This should be the Supabase user ID
                            metadata={
                                **memory_metadata,
                                'db_memory_id': str(db_memory.id),  # Link to database record
                                'app_id': app_id,
                                'app_db_id': app_id
                            }
                        )
                    except Exception as mem_error:
                        logger.warning(f"Failed to add to Jean Memory V2: {mem_error}. Continuing with database storage only.")
                        response = None
                    
                    logger.debug(f"Memory client response: {response}")
                    synced_count += 1
                    
                    # Small delay to prevent overwhelming the system
                    await asyncio.sleep(0.2)
                    
                except Exception as e:
                    logger.error(f"Failed to add post {post_index+1} to memory: {e}")
                    failed_count += 1
                    db_session.rollback()
                    continue
            
            # Commit the batch - following Twitter pattern
            try:
                db_session.commit()
                logger.info(f"Committed batch {i//batch_size + 1} to database")
                
                # Update progress after each successful batch
                batch_progress = 20 + int(((i + len(batch)) / len(memory_contents)) * 70)
                report_progress(batch_progress, f"Synced batch {i//batch_size + 1}", synced_count)
                
            except Exception as e:
                logger.error(f"Failed to commit batch: {e}")
                db_session.rollback()
                failed_count += len(batch)
                synced_count -= len(batch)
            
            # Longer delay between batches (posts are more substantial than tweets)
            if i + batch_size < len(memory_contents):
                logger.info(f"Batch complete. Waiting 3 seconds before next batch...")
                await asyncio.sleep(3)
        
        report_progress(100, f"Sync complete. Added {synced_count} new posts.", synced_count)
        return synced_count
        
    except Exception as e:
        logger.error(f"An error occurred during Substack sync for {normalized_url}: {e}", exc_info=True)
        report_progress(100, f"An error occurred: {e}", 0)
        return 0 