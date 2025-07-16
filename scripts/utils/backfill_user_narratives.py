import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, UTC
from typing import List, Optional
import traceback

from dotenv import load_dotenv
from sqlalchemy import func, text
from sqlalchemy.orm import sessionmaker, Session

# Add the project root and openmemory/api to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
api_path = os.path.join(project_root, 'openmemory', 'api')
sys.path.insert(0, project_root)
sys.path.insert(0, api_path)

# Now import from our own codebase
try:
    from openmemory.api.app.database import engine, Base
    from openmemory.api.app.models import User, Memory, UserNarrative
    from openmemory.api.app.utils.gemini import GeminiService
except ImportError:
    # Fallback for different path configurations
    os.chdir(api_path)
    sys.path.insert(0, '.')
    from app.database import engine, Base
    from app.models import User, Memory, UserNarrative
    from app.utils.gemini import GeminiService

# Load environment variables
env_files = [
    os.path.join(project_root, '.env'),
    os.path.join(project_root, 'openmemory', '.env'),
    os.path.join(project_root, 'openmemory', 'api', '.env'),
    os.path.join(project_root, 'openmemory', '.env.local'),
]

for env_file in env_files:
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"Loaded environment from: {env_file}")

# --- Configuration ---
BATCH_SIZE = 10  # Reduced from 50 for more careful processing
CONCURRENT_USERS = 3  # Reduced from 10 to respect API limits
MEMORY_THRESHOLD = 5
NARRATIVE_TTL_DAYS = 7
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds

# --- Enhanced Logging Setup ---
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('narrative_backfill.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

# Add specific logger for tracking progress
progress_logger = logging.getLogger('backfill_progress')
progress_logger.setLevel(logging.INFO)

# --- Database Setup ---
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Service Initialization ---
try:
    gemini_service = GeminiService()
    logger.info("✅ Gemini service initialized successfully")
except Exception as e:
    logger.error(f"❌ Failed to initialize Gemini service: {e}")
    sys.exit(1)

async def generate_narrative_for_user(user_id: str, retry_count: int = 0) -> Optional[str]:
    """
    Generates a user narrative with enhanced error handling and retries.
    """
    logger.info(f"🤖 [User {user_id}] Starting narrative generation (attempt {retry_count + 1}/{MAX_RETRIES})")

    try:
        # Get user's memories directly from database
        db = SessionLocal()
        try:
            # Get user by user_id string
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                logger.warning(f"⚠️ [User {user_id}] User not found in database")
                return None
            
            # Get user's full name for personalized narrative
            user_full_name = ""
            if user.firstname and user.lastname:
                user_full_name = f"{user.firstname.strip()} {user.lastname.strip()}".strip()
            elif user.firstname:
                user_full_name = user.firstname.strip()
            elif user.lastname:
                user_full_name = user.lastname.strip()
            
            logger.info(f"📝 [User {user_id}] Found user: {user_full_name or user.name or 'Unknown'}")
            
            # Use Jean Memory V2 instead of direct database query
            logger.info(f"🔍 [User {user_id}] Searching Jean Memory V2...")
            from app.utils.memory import get_async_memory_client
            memory_client = await get_async_memory_client()
            
            # Search for memories using enhanced query (same as API endpoint)
            memory_results = await memory_client.search(
                query="recent experiences recent memories current projects goals values personality growth life patterns recent reflections recent decisions recent insights recent challenges recent achievements how experiences align with values core beliefs life direction personal development recent learning recent relationships recent work recent thoughts",
                user_id=user_id,
                limit=50
            )
            
            logger.info(f"📊 [User {user_id}] Retrieved memory results: {type(memory_results)}")
            
            # Process memory results (same logic as API endpoint)
            memories_text_list = []
            if isinstance(memory_results, dict) and 'results' in memory_results:
                memories = memory_results['results']
                logger.info(f"📝 [User {user_id}] Extracted {len(memories)} memories from dict results")
            elif isinstance(memory_results, list):
                memories = memory_results
                logger.info(f"📝 [User {user_id}] Using list of {len(memories)} memories directly")
            else:
                memories = []
                logger.warning(f"⚠️ [User {user_id}] No memories found - unexpected result type")
            
            # Filter memories for narrative generation (same as API)
            for mem in memories[:25]:  # Limit for narrative generation
                content = mem.get('memory', mem.get('content', ''))
                
                if not content or not isinstance(content, str):
                    continue
                
                content = content.strip()
                
                # Skip empty or very short content
                if not content.strip() or len(content) < 5:
                    continue
                
                memories_text_list.append(content)
            
            memory_count = len(memories_text_list)
            logger.info(f"📊 [User {user_id}] Found {memory_count} valid memories from Jean Memory V2")
            
            if memory_count < MEMORY_THRESHOLD:
                logger.warning(f"⚠️ [User {user_id}] Insufficient memories ({memory_count} < {MEMORY_THRESHOLD}), skipping")
                return None
            
            # Prepare memories text for generation
            memories_text = "\n".join(memories_text_list)
            
            logger.info(f"📄 [User {user_id}] Prepared {memory_count} memories for generation (text length: {len(memories_text)} chars)")

        finally:
            db.close()

        if not memories_text_list:
            logger.warning(f"⚠️ [User {user_id}] No memory texts found")
            return None

        # Use Gemini Pro for high-quality generation with detailed logging
        logger.info(f"🤖 [User {user_id}] Calling Gemini 2.5 Pro API with personalized name: '{user_full_name}'...")
        start_time = datetime.now()
        
        try:
            analysis_response = await gemini_service.generate_narrative_pro(memories_text, user_full_name)
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            if analysis_response and analysis_response.strip():
                logger.info(f"✅ [User {user_id}] Generated narrative successfully (duration: {duration:.2f}s, length: {len(analysis_response)} chars)")
                return analysis_response.strip()
            else:
                logger.error(f"❌ [User {user_id}] Gemini returned empty response")
                return None
                
        except Exception as api_error:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ [User {user_id}] Gemini API call failed after {duration:.2f}s: {str(api_error)}")
            
            # Retry logic for API failures
            if retry_count < MAX_RETRIES - 1:
                logger.info(f"🔄 [User {user_id}] Retrying in {RETRY_DELAY} seconds...")
                await asyncio.sleep(RETRY_DELAY)
                return await generate_narrative_for_user(user_id, retry_count + 1)
            else:
                logger.error(f"💥 [User {user_id}] Max retries exceeded, giving up")
                return None

    except Exception as e:
        logger.error(f"💥 [User {user_id}] Unexpected error during narrative generation: {str(e)}")
        logger.error(f"💥 [User {user_id}] Traceback: {traceback.format_exc()}")
        return None

def get_eligible_users(db: Session) -> List[str]:
    """
    Fetches users who have > 5 memories and need narrative generation.
    Enhanced with better logging and debugging.
    """
    logger.info("🔍 Fetching eligible users for narrative generation...")
    
    try:
        seven_days_ago = datetime.now(UTC) - timedelta(days=NARRATIVE_TTL_DAYS)
        logger.info(f"📅 Considering narratives older than: {seven_days_ago}")

        # Get users with sufficient memories who don't have fresh narratives
        query = """
        SELECT DISTINCT u.user_id 
        FROM users u
        INNER JOIN memories m ON u.id = m.user_id AND m.state = 'active'
        LEFT JOIN user_narratives un ON u.id = un.user_id 
            AND un.generated_at >= %s
        WHERE un.user_id IS NULL
        GROUP BY u.user_id, u.name
        HAVING COUNT(m.id) > %s
        ORDER BY COUNT(m.id) DESC
        """
        
        result = db.execute(text(query), (seven_days_ago, MEMORY_THRESHOLD))
        user_ids = [row[0] for row in result.fetchall()]
        
        logger.info(f"✅ Found {len(user_ids)} eligible users:")
        
        # Log details about eligible users
        for i, user_id in enumerate(user_ids[:10]):  # Log first 10 for debugging
            user = db.query(User).filter(User.user_id == user_id).first()
            memory_count = db.query(Memory).filter(
                Memory.user_id == user.id,
                Memory.state == 'active'
            ).count()
            
            logger.info(f"  {i+1}. User: {user.name or 'Unknown'} ({user_id}) - {memory_count} memories")
        
        if len(user_ids) > 10:
            logger.info(f"  ... and {len(user_ids) - 10} more users")
            
        return user_ids
        
    except Exception as e:
        logger.error(f"❌ Error fetching eligible users: {str(e)}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        return []

async def save_narrative_to_db(user_id_str: str, narrative_content: str) -> bool:
    """
    Saves or updates a user's narrative with enhanced error handling.
    Returns True if successful, False otherwise.
    """
    logger.info(f"💾 [User {user_id_str}] Attempting to save narrative to database...")
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id_str).first()
        if not user:
            logger.error(f"❌ [User {user_id_str}] User not found for narrative save")
            return False

        # Check for existing narrative
        existing_narrative = db.query(UserNarrative).filter(UserNarrative.user_id == user.id).first()
        
        if existing_narrative:
            # Update existing
            existing_narrative.narrative_content = narrative_content
            existing_narrative.version = (existing_narrative.version or 0) + 1
            existing_narrative.generated_at = datetime.now(UTC)
            action = "Updated"
            logger.info(f"🔄 [User {user_id_str}] Updating existing narrative (version {existing_narrative.version})")
        else:
            # Create new
            narrative = UserNarrative(
                user_id=user.id,
                narrative_content=narrative_content,
                generated_at=datetime.now(UTC)
            )
            db.add(narrative)
            action = "Created"
            logger.info(f"✨ [User {user_id_str}] Creating new narrative")
        
        db.commit()
        logger.info(f"✅ [User {user_id_str}] {action} narrative successfully (length: {len(narrative_content)} chars)")
        return True
        
    except Exception as e:
        logger.error(f"❌ [User {user_id_str}] Failed to save narrative: {str(e)}")
        logger.error(f"❌ [User {user_id_str}] Traceback: {traceback.format_exc()}")
        db.rollback()
        return False
    finally:
        db.close()

async def process_user_batch(user_ids: List[str]) -> dict:
    """
    Process a batch of users with detailed progress tracking.
    """
    batch_size = len(user_ids)
    logger.info(f"🔄 Processing batch of {batch_size} users")
    progress_logger.info(f"BATCH_START: {batch_size} users")
    
    results = {
        'total': batch_size,
        'successful': 0,
        'failed': 0,
        'skipped': 0,
        'errors': []
    }
    
    # Process users with controlled concurrency
    semaphore = asyncio.Semaphore(CONCURRENT_USERS)
    
    async def process_single_user(user_id: str) -> dict:
        async with semaphore:
            try:
                # Add delay between requests to respect API limits
                await asyncio.sleep(2)  # 2 second delay between users
                
                logger.info(f"🎯 [User {user_id}] Starting processing...")
                
                # Generate narrative
                narrative = await generate_narrative_for_user(user_id)
                
                if narrative is None:
                    logger.warning(f"⚠️ [User {user_id}] Narrative generation returned None (skipped)")
                    return {'user_id': user_id, 'status': 'skipped', 'reason': 'generation_failed'}
                
                if not narrative.strip():
                    logger.warning(f"⚠️ [User {user_id}] Generated empty narrative (skipped)")
                    return {'user_id': user_id, 'status': 'skipped', 'reason': 'empty_narrative'}
                
                # Save to database
                save_success = await save_narrative_to_db(user_id, narrative)
                
                if save_success:
                    logger.info(f"🎉 [User {user_id}] Processing completed successfully")
                    return {'user_id': user_id, 'status': 'successful', 'narrative_length': len(narrative)}
                else:
                    logger.error(f"❌ [User {user_id}] Processing failed during save")
                    return {'user_id': user_id, 'status': 'failed', 'reason': 'save_failed'}
                    
            except Exception as e:
                logger.error(f"💥 [User {user_id}] Unexpected error during processing: {str(e)}")
                return {'user_id': user_id, 'status': 'failed', 'reason': str(e)}
    
    # Execute all user processing tasks
    logger.info(f"🚀 Starting concurrent processing of {batch_size} users (max concurrent: {CONCURRENT_USERS})")
    user_results = await asyncio.gather(*[process_single_user(uid) for uid in user_ids])
    
    # Aggregate results
    for result in user_results:
        status = result['status']
        if status == 'successful':
            results['successful'] += 1
        elif status == 'failed':
            results['failed'] += 1
            results['errors'].append(f"User {result['user_id']}: {result.get('reason', 'unknown')}")
        elif status == 'skipped':
            results['skipped'] += 1
    
    progress_logger.info(f"BATCH_COMPLETE: {results['successful']}/{batch_size} successful, {results['failed']} failed, {results['skipped']} skipped")
    logger.info(f"✅ Batch processing complete: {results['successful']}/{batch_size} successful")
    
    return results

async def main():
    """
    Enhanced main function with comprehensive logging and error handling.
    """
    logger.info("=" * 80)
    logger.info("🚀 JEAN MEMORY - USER NARRATIVE BACKFILL PROCESS STARTING")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    # Verify database connection
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        logger.info("✅ Database connection verified")
        db.close()
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return
    
    # Verify Gemini API
    try:
        test_response = await gemini_service.generate_response("Test connection")
        logger.info("✅ Gemini API connection verified")
    except Exception as e:
        logger.error(f"❌ Gemini API connection failed: {e}")
        return
    
    # Get eligible users
    db = SessionLocal()
    try:
        eligible_users = get_eligible_users(db)
    finally:
        db.close()

    if not eligible_users:
        logger.info("🎯 No users require narrative backfilling. Process complete.")
        return

    total_users = len(eligible_users)
    logger.info(f"📊 PROCESSING SUMMARY:")
    logger.info(f"   • Total eligible users: {total_users}")
    logger.info(f"   • Memory threshold: {MEMORY_THRESHOLD}+ memories")
    logger.info(f"   • Narrative TTL: {NARRATIVE_TTL_DAYS} days")
    logger.info(f"   • Batch size: {BATCH_SIZE}")
    logger.info(f"   • Concurrent users per batch: {CONCURRENT_USERS}")
    logger.info(f"   • Using: Gemini 2.5 Pro")
    
    # Process in batches
    total_processed = 0
    total_successful = 0
    total_failed = 0
    total_skipped = 0
    all_errors = []
    
    total_batches = (total_users + BATCH_SIZE - 1) // BATCH_SIZE
    
    for i in range(0, total_users, BATCH_SIZE):
        batch_users = eligible_users[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        
        logger.info(f"📦 BATCH {batch_num}/{total_batches}: Processing {len(batch_users)} users")
        logger.info("-" * 60)
        
        batch_results = await process_user_batch(batch_users)
        
        # Update totals
        total_processed += batch_results['total']
        total_successful += batch_results['successful']
        total_failed += batch_results['failed']
        total_skipped += batch_results['skipped']
        all_errors.extend(batch_results['errors'])
        
        # Log batch summary
        logger.info(f"📊 BATCH {batch_num} COMPLETE:")
        logger.info(f"   ✅ Successful: {batch_results['successful']}")
        logger.info(f"   ❌ Failed: {batch_results['failed']}")
        logger.info(f"   ⚠️ Skipped: {batch_results['skipped']}")
        
        # Brief pause between batches
        if i + BATCH_SIZE < total_users:
            logger.info(f"⏸️ Pausing 5 seconds before next batch...")
            await asyncio.sleep(5)

    # Final summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    logger.info("=" * 80)
    logger.info("🎉 JEAN MEMORY - USER NARRATIVE BACKFILL PROCESS COMPLETE")
    logger.info("=" * 80)
    logger.info(f"📊 FINAL RESULTS:")
    logger.info(f"   • Total users processed: {total_processed}")
    logger.info(f"   • ✅ Successful: {total_successful}")
    logger.info(f"   • ❌ Failed: {total_failed}")
    logger.info(f"   • ⚠️ Skipped: {total_skipped}")
    logger.info(f"   • ⏱️ Total duration: {duration}")
    logger.info(f"   • 🤖 Model used: Gemini 2.5 Pro")
    logger.info(f"   • 💾 Success rate: {(total_successful/total_processed*100):.1f}%")
    
    if all_errors:
        logger.info(f"❌ ERRORS ENCOUNTERED ({len(all_errors)}):")
        for error in all_errors[:10]:  # Show first 10 errors
            logger.info(f"   • {error}")
        if len(all_errors) > 10:
            logger.info(f"   • ... and {len(all_errors) - 10} more errors")
    
    progress_logger.info(f"FINAL_SUMMARY: {total_successful}/{total_processed} successful ({(total_successful/total_processed*100):.1f}% success rate)")

if __name__ == "__main__":
    # This allows the script to be run with `python -m scripts.utils.backfill_user_narratives`
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Process interrupted by user")
    except Exception as e:
        logger.error(f"💥 Unexpected error in main process: {str(e)}")
        logger.error(f"💥 Traceback: {traceback.format_exc()}")
        sys.exit(1) 