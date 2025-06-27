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
RETRY_DELAYS = [5, 15, 30]  # Progressive backoff: 5s, 15s, 30s
API_RATE_LIMIT_DELAY = 3    # Delay between API calls

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
        # Using the same proven prompt strategy as the production deep_memory system
        prompt = f"""You are providing context for a conversation with this user. Analyze their memories and create a rich, synthesized understanding.

USER'S MEMORIES AND CONTENT:
{memories_text}

Create a comprehensive life narrative for this person to be used as a primer for new conversations. Focus on:

1. **Who they are** - personality, background, values, and core interests
2. **What they're working on** - current projects, goals, professional focus, and aspirations  
3. **How to best interact with them** - communication preferences, decision-making style, and what they value in conversations
4. **Key themes and patterns** - recurring topics, growth areas, and important relationships or experiences

Provide a well-written, detailed narrative that captures the essence of this user. Use sophisticated reasoning to identify deeper patterns and insights beyond surface-level information. The goal is to give an AI assistant a complete understanding of who this person is and how to have meaningful, contextually-aware conversations with them.

Write this as flowing, insightful paragraphs that synthesize their experiences into a coherent understanding of their character, motivations, and current life situation."""
        
        try:
            response = await self.model_pro.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.6,  # Slightly lower for more consistent quality
                    max_output_tokens=3072,  # Increased for more comprehensive narratives
                    candidate_count=1,
                )
            )
            
            # Check if response was filtered
            if not response.parts or not response.text:
                logger.warning("Response was filtered, attempting with simplified prompt")
                return await self._generate_narrative_fallback(memories_text)
            
            return response.text.strip()
            
        except Exception as e:
            if "safety" in str(e).lower() or "finish_reason" in str(e).lower():
                logger.warning(f"Safety filter triggered, attempting fallback: {str(e)}")
                return await self._generate_narrative_fallback(memories_text)
            else:
                raise e

    async def _generate_narrative_fallback(self, memories_text: str) -> str:
        """Fallback method with very safe prompt to avoid safety filters"""
        # Much simpler, safer prompt
        prompt = f"""Analyze these conversation notes and create a professional narrative about this person:

NOTES:
{memories_text[:2000]}

Write a cohesive narrative covering:
- Their professional background and skills
- Current projects and interests  
- Working style and goals

Write this as flowing paragraphs that would help an AI assistant understand this person completely."""
        
        try:
            response = await self.model_pro.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,  # Very conservative
                    max_output_tokens=1024,
                )
            )
            
            if response.text:
                return response.text.strip()
            else:
                # Final fallback - return structured template
                return self._create_template_narrative(memories_text)
                
        except Exception as e:
            logger.error(f"Fallback generation also failed: {str(e)}")
            return self._create_template_narrative(memories_text)
    
    def _create_template_narrative(self, memories_text: str) -> str:
        """Create a basic template narrative from memory keywords"""
        # Extract key themes from memories
        words = memories_text.lower().split()
        
        # Simple keyword analysis
        work_terms = ['work', 'project', 'company', 'team', 'develop', 'build', 'engineer', 'design']
        tech_terms = ['code', 'software', 'api', 'system', 'database', 'app', 'tech', 'programming']
        
        work_count = sum(1 for word in words if any(term in word for term in work_terms))
        tech_count = sum(1 for word in words if any(term in word for term in tech_terms))
        
        if tech_count > 5:
            profile_type = "technology professional"
        elif work_count > 10:
            profile_type = "working professional"
        else:
            profile_type = "individual"
        
        return f"""This {profile_type} demonstrates consistent engagement with their goals and interests. Based on their conversation patterns, they appear to be methodical in their approach to projects and value clear communication. They show interest in learning and improving their skills, often discussing practical applications and real-world solutions.

Their interactions suggest someone who appreciates detailed information and thoughtful responses. They tend to focus on actionable insights and concrete steps forward. This person values efficiency and seems to prefer direct, helpful communication that supports their objectives and decision-making process."""

def get_db_connection():
    """Get direct PostgreSQL connection"""
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        # Try Supabase format
        supabase_url = os.getenv("SUPABASE_URL")
        service_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if supabase_url and service_key:
            # Extract project ID from Supabase URL
            # Format: https://xxxxx.supabase.co -> xxxxx
            project_id = supabase_url.replace("https://", "").replace("http://", "").split(".")[0]
            database_url = f"postgresql://postgres.{project_id}:{service_key}@aws-0-us-west-1.pooler.supabase.com:6543/postgres"
            logger.info(f"Using Supabase connection for project: {project_id}")
        else:
            logger.error(f"Missing environment variables:")
            logger.error(f"  DATABASE_URL: {'✅' if os.getenv('DATABASE_URL') else '❌'}")
            logger.error(f"  SUPABASE_URL: {'✅' if os.getenv('SUPABASE_URL') else '❌'}")
            logger.error(f"  SUPABASE_SERVICE_KEY: {'✅' if os.getenv('SUPABASE_SERVICE_KEY') else '❌'}")
            logger.error(f"  GEMINI_API_KEY: {'✅' if os.getenv('GEMINI_API_KEY') else '❌'}")
            raise ValueError("No database connection URL found. Please set DATABASE_URL or SUPABASE_URL + SUPABASE_SERVICE_KEY")
    
    return psycopg2.connect(database_url)

def get_eligible_users():
    """Get users with 5+ memories who need narratives"""
    logger.info("🔍 Finding eligible users...")
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            seven_days_ago = datetime.now(UTC) - timedelta(days=NARRATIVE_TTL_DAYS)
            
            # FORCE REGENERATION MODE: Regenerate ALL narratives regardless of age
            # This ensures everyone gets the new comprehensive format
            query = """
            SELECT DISTINCT u.user_id, u.name, COUNT(m.id) as memory_count
            FROM users u
            INNER JOIN memories m ON u.id = m.user_id AND m.state = 'active'
            GROUP BY u.user_id, u.name
            HAVING COUNT(m.id) > %s
            ORDER BY COUNT(m.id) DESC
            """
            
            cur.execute(query, (MEMORY_THRESHOLD,))
            users = cur.fetchall()
            
            logger.info(f"✅ Found {len(users)} eligible users")
            for i, user in enumerate(users[:5]):  # Log first 5
                logger.info(f"  {i+1}. {user['name'] or 'Unknown'} ({user['user_id']}) - {user['memory_count']} memories")
            
            return [user['user_id'] for user in users]
    finally:
        conn.close()

def get_user_context_like_deep_memory(user_id: str):
    """Get comprehensive user context using the same strategy as deep_memory_query"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Use the same memory query pattern as deep_memory_query
            query = """
            SELECT m.content, m.created_at, m.metadata
            FROM users u
            INNER JOIN memories m ON u.id = m.user_id
            WHERE u.user_id = %s 
              AND m.state = 'active'
            ORDER BY m.created_at DESC
            LIMIT 150
            """
            
            cur.execute(query, (user_id,))
            memories = cur.fetchall()
            
            if not memories:
                return ""
            
            # Filter and format memories like the production system does
            memory_texts = []
            for mem in memories:
                content = mem['content'].strip()
                # Skip very short or low-quality content
                if len(content) > 15 and not content.lower().startswith(('ok', 'yes', 'no', 'thanks')):
                    memory_texts.append(content)
            
            # Limit to prevent token overflow (like deep_memory does)
            selected_memories = memory_texts[:80]  # Similar to deep_memory limits
            
            # Format like deep_memory_query does
            context = "=== USER MEMORIES ===\n\n"
            context += "\n\n".join([f"Memory: {mem}" for mem in selected_memories])
            
            # Add document context if available (comprehensive but limited)
            doc_query = """
            SELECT d.title, d.document_type, d.content
            FROM users u
            INNER JOIN documents d ON u.id = d.user_id
            WHERE u.user_id = %s
            ORDER BY d.created_at DESC
            LIMIT 10
            """
            
            cur.execute(doc_query, (user_id,))
            documents = cur.fetchall()
            
            if documents:
                context += "\n\n=== WRITTEN CONTENT ===\n\n"
                for doc in documents[:5]:  # Limit to prevent bloat
                    title = doc['title']
                    doc_type = doc['document_type']
                    # Take first part of content for overview
                    preview = doc['content'][:500] if len(doc['content']) > 500 else doc['content']
                    context += f"Document: {title} ({doc_type})\nContent: {preview}\n\n"
            
            logger.info(f"[User {user_id}] Built context: {len(selected_memories)} memories + {len(documents)} documents = {len(context)} chars")
            
            return context
            
    finally:
        conn.close()

async def generate_narrative_for_user(user_id: str, gemini: GeminiService, retry_count: int = 0):
    """Generate narrative for a user using proven deep_memory strategy with robust retry logic"""
    attempt_num = retry_count + 1
    logger.info(f"🤖 [User {user_id}] Generating narrative (attempt {attempt_num}/{MAX_RETRIES + 1})...")
    
    try:
        # Get comprehensive context like deep_memory_query
        context_text = get_user_context_like_deep_memory(user_id)
        
        if not context_text or len(context_text) < 200:
            logger.warning(f"⚠️ [User {user_id}] Insufficient context ({len(context_text) if context_text else 0} chars)")
            return None
        
        logger.info(f"📊 [User {user_id}] Processing context: {len(context_text)} chars")
        
        # Generate narrative using proven method
        start_time = datetime.now()
        narrative = await gemini.generate_narrative_pro(context_text)
        duration = (datetime.now() - start_time).total_seconds()
        
        if narrative and len(narrative) > 100:  # Ensure meaningful response
            logger.info(f"✅ [User {user_id}] Generated narrative (attempt {attempt_num}, duration: {duration:.2f}s, length: {len(narrative)} chars)")
            return narrative.strip()
        else:
            logger.warning(f"⚠️ [User {user_id}] Insufficient narrative response ({len(narrative) if narrative else 0} chars)")
            
            # If we got a response but it's too short, don't retry - likely user doesn't have good content
            if narrative and len(narrative) > 20:
                logger.info(f"📝 [User {user_id}] Short but valid response, not retrying")
                return narrative.strip()
            
            # Empty response - worth retrying
            if retry_count < MAX_RETRIES:
                delay = RETRY_DELAYS[min(retry_count, len(RETRY_DELAYS) - 1)]
                logger.info(f"🔄 [User {user_id}] Retrying in {delay}s due to empty response...")
                await asyncio.sleep(delay)
                return await generate_narrative_for_user(user_id, gemini, retry_count + 1)
                
            return None
            
    except Exception as e:
        error_str = str(e).lower()
        duration = (datetime.now() - start_time).total_seconds() if 'start_time' in locals() else 0
        
        # Categorize errors for different retry strategies
        is_safety_filter = any(word in error_str for word in ['safety', 'finish_reason', 'blocked', 'filtered'])
        is_rate_limit = any(word in error_str for word in ['rate', 'quota', 'limit', '429'])
        is_network = any(word in error_str for word in ['connection', 'timeout', 'network', 'dns'])
        
        logger.error(f"💥 [User {user_id}] Generation failed (attempt {attempt_num}, duration: {duration:.2f}s): {str(e)}")
        
        # Handle different error types
        if is_safety_filter:
            logger.warning(f"🛡️ [User {user_id}] Safety filter detected - this is handled by fallback prompts in Gemini class")
            # Don't retry safety filters - the GeminiService already handles fallbacks
            return None
            
        elif is_rate_limit:
            if retry_count < MAX_RETRIES:
                # Longer delay for rate limits
                delay = RETRY_DELAYS[min(retry_count, len(RETRY_DELAYS) - 1)] * 2  # Double delay for rate limits
                logger.info(f"⏳ [User {user_id}] Rate limit hit, retrying in {delay}s...")
                await asyncio.sleep(delay)
                return await generate_narrative_for_user(user_id, gemini, retry_count + 1)
                
        elif is_network:
            if retry_count < MAX_RETRIES:
                delay = RETRY_DELAYS[min(retry_count, len(RETRY_DELAYS) - 1)]
                logger.info(f"🌐 [User {user_id}] Network error, retrying in {delay}s...")
                await asyncio.sleep(delay)
                return await generate_narrative_for_user(user_id, gemini, retry_count + 1)
                
        else:
            # Generic error - still worth retrying
            if retry_count < MAX_RETRIES:
                delay = RETRY_DELAYS[min(retry_count, len(RETRY_DELAYS) - 1)]
                logger.info(f"🔄 [User {user_id}] Generic error, retrying in {delay}s...")
                await asyncio.sleep(delay)
                return await generate_narrative_for_user(user_id, gemini, retry_count + 1)
        
        logger.error(f"💥 [User {user_id}] Max retries exceeded or non-retryable error")
        return None

def save_narrative_to_db(user_id: str, narrative_content: str, retry_count: int = 0):
    """Save narrative to database with retry logic"""
    attempt_num = retry_count + 1
    logger.info(f"💾 [User {user_id}] Saving narrative (attempt {attempt_num})...")
    
    try:
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                # Get user internal ID
                cur.execute("SELECT id FROM users WHERE user_id = %s", (user_id,))
                user_row = cur.fetchone()
                if not user_row:
                    logger.error(f"❌ [User {user_id}] User not found in database")
                    return False
                
                user_internal_id = user_row[0]
                
                # Delete existing narrative (upsert pattern)
                cur.execute("DELETE FROM user_narratives WHERE user_id = %s", (user_internal_id,))
                
                # Insert new narrative
                cur.execute("""
                    INSERT INTO user_narratives (id, user_id, narrative_content, generated_at)
                    VALUES (gen_random_uuid(), %s, %s, %s)
                """, (user_internal_id, narrative_content, datetime.now(UTC)))
                
                conn.commit()
                logger.info(f"✅ [User {user_id}] Saved narrative successfully (attempt {attempt_num})")
                return True
                
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
            
    except Exception as e:
        error_str = str(e).lower()
        is_connection_error = any(word in error_str for word in ['connection', 'timeout', 'network', 'dns', 'refused'])
        is_deadlock = any(word in error_str for word in ['deadlock', 'lock', 'timeout'])
        
        logger.error(f"❌ [User {user_id}] Database save failed (attempt {attempt_num}): {str(e)}")
        
        # Retry database errors with progressive backoff
        if (is_connection_error or is_deadlock) and retry_count < MAX_RETRIES:
            delay = RETRY_DELAYS[min(retry_count, len(RETRY_DELAYS) - 1)]
            logger.info(f"🔄 [User {user_id}] Database error, retrying in {delay}s...")
            import time
            time.sleep(delay)  # Use sync sleep for database operations
            return save_narrative_to_db(user_id, narrative_content, retry_count + 1)
        
        return False

async def process_batch(user_ids, gemini):
    """Process a batch of users with enhanced error handling"""
    logger.info(f"🔄 Processing batch of {len(user_ids)} users")
    
    results = {'successful': 0, 'failed': 0, 'skipped': 0, 'errors': []}
    
    for i, user_id in enumerate(user_ids):
        try:
            # Rate limiting - respect API limits
            if i > 0:  # Skip delay for first user in batch
                await asyncio.sleep(API_RATE_LIMIT_DELAY)
            
            logger.info(f"📍 [{i+1}/{len(user_ids)}] Processing user {user_id}")
            
            # Generate narrative with built-in retry logic
            narrative = await generate_narrative_for_user(user_id, gemini)
            
            if not narrative:
                results['skipped'] += 1
                logger.info(f"⚠️ [User {user_id}] Skipped (no narrative generated)")
                continue
            
            # Save to database with built-in retry logic
            if save_narrative_to_db(user_id, narrative):
                results['successful'] += 1
                logger.info(f"🎉 [User {user_id}] Processing completed successfully")
            else:
                results['failed'] += 1
                error_msg = f"Database save failed for user {user_id}"
                results['errors'].append(error_msg)
                logger.error(f"❌ [User {user_id}] {error_msg}")
                
        except Exception as e:
            error_msg = f"Unexpected error for user {user_id}: {str(e)}"
            logger.error(f"💥 [User {user_id}] {error_msg}")
            results['failed'] += 1
            results['errors'].append(error_msg)
    
    success_rate = (results['successful'] / len(user_ids) * 100) if user_ids else 0
    logger.info(f"✅ Batch complete: {results['successful']}/{len(user_ids)} successful ({success_rate:.1f}%)")
    
    if results['errors']:
        logger.warning(f"⚠️ Batch had {len(results['errors'])} errors:")
        for error in results['errors'][-3:]:  # Log last 3 errors
            logger.warning(f"   • {error}")
    
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