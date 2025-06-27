#!/usr/bin/env python3
"""
Standalone narrative backfill script for production.
Avoids import conflicts by using direct database operations.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timedelta, UTC
import traceback

# Minimal imports to avoid conflicts
import google.generativeai as genai
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configuration
MEMORY_THRESHOLD = 5
NARRATIVE_TTL_DAYS = 7
BATCH_SIZE = 10
CONCURRENT_USERS = 3
MAX_RETRIES = 3

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found")
        
        genai.configure(api_key=api_key)
        self.model_pro = genai.GenerativeModel('gemini-2.5-pro')
    
    async def generate_narrative_pro(self, memories_text: str) -> str:
        prompt = f"""You are providing context for a conversation with this user. Analyze their memories and create a rich, synthesized understanding.

USER'S MEMORIES:
{memories_text}

Create a comprehensive but concise 'life narrative' for this person to be used as a primer for new conversations. Focus on:
1. Who they are (personality, background, values)
2. What they're working on (projects, goals, interests)  
3. How to best interact with them (preferences, communication style)
4. Key themes or recurring patterns in their life.

Provide a well-written, paragraph-based narrative that captures the essence of the user."""
        
        response = await self.model_pro.generate_content_async(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=2048,
            )
        )
        
        return response.text.strip()

def get_db_connection():
    """Get direct PostgreSQL connection"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        # Try Supabase format
        supabase_url = os.getenv("SUPABASE_URL")
        service_key = os.getenv("SUPABASE_SERVICE_KEY")
        if supabase_url and service_key:
            # Extract connection details from Supabase URL
            host = supabase_url.replace("https://", "").replace("http://", "")
            database_url = f"postgresql://postgres.{host.split('.')[0]}:{service_key}@aws-0-us-west-1.pooler.supabase.com:6543/postgres"
    
    if not database_url:
        raise ValueError("No database connection URL found")
    
    return psycopg2.connect(database_url)

def get_eligible_users():
    """Get users with 5+ memories who need narratives"""
    logger.info("🔍 Finding eligible users...")
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            seven_days_ago = datetime.now(UTC) - timedelta(days=NARRATIVE_TTL_DAYS)
            
            query = """
            SELECT DISTINCT u.user_id, u.name, COUNT(m.id) as memory_count
            FROM users u
            INNER JOIN memories m ON u.id = m.user_id AND m.state = 'active'
            LEFT JOIN user_narratives un ON u.id = un.user_id 
                AND un.generated_at >= %s
            WHERE un.user_id IS NULL
            GROUP BY u.user_id, u.name
            HAVING COUNT(m.id) > %s
            ORDER BY COUNT(m.id) DESC
            """
            
            cur.execute(query, (seven_days_ago, MEMORY_THRESHOLD))
            users = cur.fetchall()
            
            logger.info(f"✅ Found {len(users)} eligible users")
            for i, user in enumerate(users[:5]):  # Log first 5
                logger.info(f"  {i+1}. {user['name'] or 'Unknown'} ({user['user_id']}) - {user['memory_count']} memories")
            
            return [user['user_id'] for user in users]
    finally:
        conn.close()

def get_user_memories(user_id: str):
    """Get memories for a specific user"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
            SELECT m.content
            FROM users u
            INNER JOIN memories m ON u.id = m.user_id
            WHERE u.user_id = %s AND m.state = 'active'
            ORDER BY m.created_at DESC
            LIMIT 50
            """
            
            cur.execute(query, (user_id,))
            memories = cur.fetchall()
            
            return [mem['content'] for mem in memories]
    finally:
        conn.close()

async def generate_narrative_for_user(user_id: str, gemini: GeminiService):
    """Generate narrative for a user"""
    logger.info(f"🤖 [User {user_id}] Generating narrative...")
    
    try:
        # Get memories
        memories = get_user_memories(user_id)
        if len(memories) < MEMORY_THRESHOLD:
            logger.warning(f"⚠️ [User {user_id}] Insufficient memories: {len(memories)}")
            return None
        
        # Create memories text
        memories_text = "\n".join([f"• {mem}" for mem in memories])
        logger.info(f"📊 [User {user_id}] Processing {len(memories)} memories")
        
        # Generate narrative
        start_time = datetime.now()
        narrative = await gemini.generate_narrative_pro(memories_text)
        duration = (datetime.now() - start_time).total_seconds()
        
        if narrative and narrative.strip():
            logger.info(f"✅ [User {user_id}] Generated narrative (duration: {duration:.2f}s, length: {len(narrative)} chars)")
            return narrative.strip()
        else:
            logger.error(f"❌ [User {user_id}] Empty narrative response")
            return None
            
    except Exception as e:
        logger.error(f"💥 [User {user_id}] Generation failed: {str(e)}")
        return None

def save_narrative_to_db(user_id: str, narrative_content: str):
    """Save narrative to database"""
    logger.info(f"💾 [User {user_id}] Saving narrative...")
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Get user internal ID
            cur.execute("SELECT id FROM users WHERE user_id = %s", (user_id,))
            user_row = cur.fetchone()
            if not user_row:
                logger.error(f"❌ [User {user_id}] User not found")
                return False
            
            user_internal_id = user_row[0]
            
            # Delete existing narrative
            cur.execute("DELETE FROM user_narratives WHERE user_id = %s", (user_internal_id,))
            
            # Insert new narrative
            cur.execute("""
                INSERT INTO user_narratives (id, user_id, narrative_content, generated_at)
                VALUES (gen_random_uuid(), %s, %s, %s)
            """, (user_internal_id, narrative_content, datetime.now(UTC)))
            
            conn.commit()
            logger.info(f"✅ [User {user_id}] Saved narrative successfully")
            return True
            
    except Exception as e:
        logger.error(f"❌ [User {user_id}] Save failed: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()

async def process_batch(user_ids, gemini):
    """Process a batch of users"""
    logger.info(f"🔄 Processing batch of {len(user_ids)} users")
    
    results = {'successful': 0, 'failed': 0, 'skipped': 0}
    
    for user_id in user_ids:
        try:
            # Add delay to respect API limits
            await asyncio.sleep(2)
            
            # Generate narrative
            narrative = await generate_narrative_for_user(user_id, gemini)
            
            if not narrative:
                results['skipped'] += 1
                continue
            
            # Save to database
            if save_narrative_to_db(user_id, narrative):
                results['successful'] += 1
                logger.info(f"🎉 [User {user_id}] Processing completed successfully")
            else:
                results['failed'] += 1
                
        except Exception as e:
            logger.error(f"💥 [User {user_id}] Unexpected error: {str(e)}")
            results['failed'] += 1
    
    logger.info(f"✅ Batch complete: {results['successful']}/{len(user_ids)} successful")
    return results

async def main():
    """Main function"""
    logger.info("🚀 STANDALONE NARRATIVE BACKFILL STARTING")
    start_time = datetime.now()
    
    try:
        # Test connections
        logger.info("🔍 Testing database connection...")
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            user_count = cur.fetchone()[0]
            logger.info(f"✅ Database connected: {user_count} users found")
        conn.close()
        
        logger.info("🔍 Testing Gemini API...")
        gemini = GeminiService()
        test_response = await gemini.generate_narrative_pro("Test connection")
        logger.info(f"✅ Gemini API connected: {len(test_response)} chars response")
        
        # Get eligible users
        eligible_users = get_eligible_users()
        if not eligible_users:
            logger.info("🎯 No users need narrative generation")
            return
        
        total_users = len(eligible_users)
        logger.info(f"📊 Processing {total_users} users in batches of {BATCH_SIZE}")
        
        # Process in batches
        total_successful = 0
        total_failed = 0
        total_skipped = 0
        
        for i in range(0, total_users, BATCH_SIZE):
            batch_users = eligible_users[i:i + BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (total_users + BATCH_SIZE - 1) // BATCH_SIZE
            
            logger.info(f"📦 BATCH {batch_num}/{total_batches}: {len(batch_users)} users")
            
            batch_results = await process_batch(batch_users, gemini)
            
            total_successful += batch_results['successful']
            total_failed += batch_results['failed']
            total_skipped += batch_results['skipped']
            
            # Brief pause between batches
            if i + BATCH_SIZE < total_users:
                logger.info("⏸️ Pausing 5 seconds...")
                await asyncio.sleep(5)
        
        # Final results
        duration = datetime.now() - start_time
        success_rate = (total_successful / total_users * 100) if total_users > 0 else 0
        
        logger.info("🎉 NARRATIVE BACKFILL COMPLETED")
        logger.info(f"📊 RESULTS: {total_successful}/{total_users} successful ({success_rate:.1f}%)")
        logger.info(f"   • ✅ Successful: {total_successful}")
        logger.info(f"   • ❌ Failed: {total_failed}")
        logger.info(f"   • ⚠️ Skipped: {total_skipped}")
        logger.info(f"   • ⏱️ Duration: {duration}")
        
    except Exception as e:
        logger.error(f"💥 Fatal error: {str(e)}")
        logger.error(f"💥 Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Process interrupted")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Unexpected error: {str(e)}")
        sys.exit(1) 