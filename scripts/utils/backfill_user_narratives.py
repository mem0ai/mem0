import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, UTC
from typing import List

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
BATCH_SIZE = 50
CONCURRENT_USERS = 10
MEMORY_THRESHOLD = 5
NARRATIVE_TTL_DAYS = 7

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Database Setup ---
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Service Initialization ---
gemini_service = GeminiService()

async def generate_narrative_for_user(user_id: str) -> str:
    """
    Generates a user narrative by performing a fast deep analysis.
    This logic is adapted from `_fast_deep_analysis` in the orchestrator.
    """
    logger.info(f"Generating narrative for user_id: {user_id}")

    try:
        # Get user's memories directly from database (much simpler than mem0.client)
        db = SessionLocal()
        try:
            # Get user by user_id string
            user = db.query(User).filter(User.user_id == user_id).first()
            if not user:
                logger.warning(f"User not found for user_id: {user_id}")
                return ""
            
            # Get user's active memories
            memories = db.query(Memory).filter(
                Memory.user_id == user.id,
                Memory.state == 'active'
            ).limit(100).all()  # Limit to 100 most recent for performance
            
            if len(memories) < MEMORY_THRESHOLD:
                logger.warning(f"User {user_id} has only {len(memories)} memories, skipping narrative generation")
                return ""
            
            # Extract memory content
            memory_texts = [memory.content for memory in memories]
            memories_text = "\n".join([f"• {mem}" for mem in memory_texts[:25]])  # Limit for prompt size

        finally:
            db.close()

        if not memory_texts:
            logger.warning(f"No memories found for user {user_id}. Cannot generate narrative.")
            return ""

        # Use the new Pro method for high-quality background generation
        analysis_response = await gemini_service.generate_narrative_pro(memories_text)
        return analysis_response

    except Exception as e:
        logger.error(f"Error generating narrative for user {user_id}: {e}", exc_info=True)
        return ""

def get_eligible_users(db: Session) -> List[str]:
    """
    Fetches users who have > 5 memories and no fresh narrative.
    """
    logger.info("Fetching eligible users...")
    
    seven_days_ago = datetime.now(UTC) - timedelta(days=NARRATIVE_TTL_DAYS)

    # Subquery to find users with stale or no narratives
    subquery = db.query(UserNarrative.user_id).filter(UserNarrative.generated_at >= seven_days_ago).subquery()

    # Main query to find users with enough memories who are not in the subquery
    eligible_users_query = (
        db.query(User.user_id)
        .join(Memory, User.id == Memory.user_id)
        .outerjoin(subquery, User.id == subquery.c.user_id)
        .filter(subquery.c.user_id == None)
        .group_by(User.user_id)
        .having(func.count(Memory.id) > MEMORY_THRESHOLD)
    )
    
    results = eligible_users_query.all()
    user_ids = [row[0] for row in results]
    
    logger.info(f"Found {len(user_ids)} eligible users to process.")
    return user_ids

async def save_narrative_to_db(user_id_str: str, narrative_content: str):
    """Saves or updates a user's narrative in the database."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id_str).first()
        if not user:
            logger.error(f"Cannot save narrative, user not found for user_id: {user_id_str}")
            return

        narrative = db.query(UserNarrative).filter(UserNarrative.user_id == user.id).first()
        if narrative:
            narrative.narrative_content = narrative_content
            narrative.version = (narrative.version or 0) + 1
            narrative.generated_at = datetime.now(UTC)
            logger.info(f"Updating narrative for user {user.id}")
        else:
            narrative = UserNarrative(
                user_id=user.id,
                narrative_content=narrative_content,
                generated_at=datetime.now(UTC)
            )
            db.add(narrative)
            logger.info(f"Creating new narrative for user {user.id}")
        
        db.commit()
    except Exception as e:
        logger.error(f"Failed to save narrative for user {user_id_str}: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

async def process_user_batch(user_ids: List[str]):
    """
    Generates and saves narratives for a batch of users concurrently.
    Uses rate limiting to respect Gemini API limits.
    """
    logger.info(f"🔄 Starting batch processing for {len(user_ids)} users with Gemini 2.5 Pro")
    
    # Process users with small delays to respect API rate limits
    tasks = []
    for i, user_id in enumerate(user_ids):
        # Add small delay between requests to avoid rate limiting
        if i > 0:
            await asyncio.sleep(1)  # 1 second delay between requests
        
        task = generate_narrative_for_user(user_id)
        tasks.append((user_id, task))
    
    # Execute all tasks concurrently but with controlled timing
    narrative_results = []
    for user_id, task in tasks:
        try:
            narrative = await task
            narrative_results.append((user_id, narrative))
        except Exception as e:
            logger.error(f"Failed to generate narrative for user {user_id}: {e}")
            narrative_results.append((user_id, None))

    # Save all successful narratives
    save_tasks = []
    for user_id, narrative in narrative_results:
        if narrative and narrative.strip():
            save_tasks.append(save_narrative_to_db(user_id, narrative))
        else:
            logger.warning(f"Skipping save for user {user_id} due to empty narrative")

    await asyncio.gather(*save_tasks)
    
    successful_saves = len([n for _, n in narrative_results if n and n.strip()])
    logger.info(f"✅ Completed batch processing: {successful_saves}/{len(user_ids)} users processed successfully")

async def main():
    """
    Main function to run the backfill process with Gemini 2.5 Pro.
    """
    logger.info("--- Starting User Narrative Backfill Process (Gemini 2.5 Pro) ---")
    
    db = SessionLocal()
    try:
        eligible_users = get_eligible_users(db)
    finally:
        db.close()

    if not eligible_users:
        logger.info("No users require narrative backfilling. Exiting.")
        return

    logger.info(f"📊 Found {len(eligible_users)} eligible users for narrative generation")
    logger.info(f"🤖 Using Gemini 2.5 Pro for high-quality background processing")
    logger.info(f"⚡ Processing in batches of {BATCH_SIZE} with {CONCURRENT_USERS} concurrent users per batch")
    
    total_processed = 0
    total_batches = (len(eligible_users) + BATCH_SIZE - 1) // BATCH_SIZE
    
    for i in range(0, len(eligible_users), BATCH_SIZE):
        batch = eligible_users[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        
        logger.info(f"--- Processing batch {batch_num}/{total_batches} ({len(batch)} users) ---")
        
        # Process smaller chunks within the batch concurrently
        for j in range(0, len(batch), CONCURRENT_USERS):
            concurrent_chunk = batch[j:j + CONCURRENT_USERS]
            logger.info(f"Processing {len(concurrent_chunk)} users concurrently with Gemini Pro...")
            await process_user_batch(concurrent_chunk)
            total_processed += len(concurrent_chunk)
            
            # Brief pause between chunks to be gentle on API
            if j + CONCURRENT_USERS < len(batch):
                await asyncio.sleep(2)

    logger.info(f"🎉 User Narrative Backfill Process Completed!")
    logger.info(f"📈 Total users processed: {total_processed}")
    logger.info(f"🤖 Model used: Gemini 2.5 Pro (Enhanced reasoning)")
    logger.info(f"💾 Narratives cached for instant conversation startup")

if __name__ == "__main__":
    # This allows the script to be run with `python -m scripts.utils.backfill_user_narratives`
    asyncio.run(main()) 