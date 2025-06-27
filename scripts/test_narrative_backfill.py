#!/usr/bin/env python3
"""
Test script for narrative backfill functionality.
This script validates that the backfill system works correctly before deploying the cron job.
"""

import asyncio
import os
import sys
from datetime import datetime
import logging

# Add the project paths
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
api_path = os.path.join(project_root, 'openmemory', 'api')
sys.path.insert(0, project_root)
sys.path.insert(0, api_path)

from dotenv import load_dotenv

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

# Import after environment setup
try:
    # Change to API directory first to avoid import conflicts
    original_cwd = os.getcwd()
    os.chdir(api_path)
    sys.path.insert(0, '.')
    
    from app.database import SessionLocal
    from app.models import User, Memory, UserNarrative
    from app.utils.gemini import GeminiService
    
    # Return to original directory
    os.chdir(original_cwd)
except ImportError as e:
    print(f"Import error: {e}")
    sys.exit(1)

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_database_connection():
    """Test database connectivity"""
    logger.info("🔍 Testing database connection...")
    try:
        db = SessionLocal()
        result = db.execute("SELECT COUNT(*) FROM users").scalar()
        logger.info(f"✅ Database connection successful. Found {result} users.")
        db.close()
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False

async def test_gemini_api():
    """Test Gemini API connectivity"""
    logger.info("🔍 Testing Gemini API connection...")
    try:
        gemini = GeminiService()
        response = await gemini.generate_response("Hello, this is a test.")
        logger.info(f"✅ Gemini API connection successful. Response length: {len(response) if response else 0}")
        return True
    except Exception as e:
        logger.error(f"❌ Gemini API connection failed: {e}")
        return False

async def get_test_user():
    """Get a user with sufficient memories for testing"""
    logger.info("🔍 Finding test user with sufficient memories...")
    db = SessionLocal()
    try:
        # Find user with most memories
        user_with_memories = db.execute("""
            SELECT u.user_id, u.name, COUNT(m.id) as memory_count
            FROM users u
            INNER JOIN memories m ON u.id = m.user_id AND m.state = 'active'
            GROUP BY u.user_id, u.name
            HAVING COUNT(m.id) >= 5
            ORDER BY COUNT(m.id) DESC
            LIMIT 1
        """).fetchone()
        
        if user_with_memories:
            user_id, name, count = user_with_memories
            logger.info(f"✅ Found test user: {name or 'Unknown'} ({user_id}) with {count} memories")
            return user_id
        else:
            logger.warning("⚠️ No users found with 5+ memories for testing")
            return None
    finally:
        db.close()

async def test_narrative_generation(user_id: str):
    """Test narrative generation for a specific user"""
    logger.info(f"🔍 Testing narrative generation for user {user_id}...")
    
    try:
        # Import the backfill function
        from scripts.utils.backfill_user_narratives import generate_narrative_for_user, save_narrative_to_db
        
        # Generate narrative
        start_time = datetime.now()
        narrative = await generate_narrative_for_user(user_id)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        if narrative:
            logger.info(f"✅ Narrative generation successful (duration: {duration:.2f}s, length: {len(narrative)} chars)")
            logger.info(f"📝 First 200 chars: {narrative[:200]}...")
            
            # Test database save
            save_success = await save_narrative_to_db(user_id, narrative)
            if save_success:
                logger.info("✅ Database save successful")
                return True
            else:
                logger.error("❌ Database save failed")
                return False
        else:
            logger.error("❌ Narrative generation failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Test narrative generation failed: {e}")
        return False

async def test_narrative_retrieval(user_id: str):
    """Test retrieval of cached narrative"""
    logger.info(f"🔍 Testing narrative retrieval for user {user_id}...")
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            logger.error(f"❌ User {user_id} not found")
            return False
        
        narrative = db.query(UserNarrative).filter(UserNarrative.user_id == user.id).first()
        if narrative:
            logger.info(f"✅ Narrative found in database (length: {len(narrative.narrative_content)} chars)")
            logger.info(f"📅 Generated at: {narrative.generated_at}")
            return True
        else:
            logger.warning("⚠️ No narrative found in database")
            return False
    finally:
        db.close()

async def cleanup_test_data(user_id: str):
    """Cleanup test narrative data"""
    logger.info(f"🧹 Cleaning up test data for user {user_id}...")
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user:
            narrative = db.query(UserNarrative).filter(UserNarrative.user_id == user.id).first()
            if narrative:
                db.delete(narrative)
                db.commit()
                logger.info("✅ Test narrative cleaned up")
            else:
                logger.info("ℹ️ No test narrative to clean up")
    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")
        db.rollback()
    finally:
        db.close()

async def main():
    """Run comprehensive test suite"""
    logger.info("=" * 60)
    logger.info("🧪 JEAN MEMORY NARRATIVE BACKFILL TEST SUITE")
    logger.info("=" * 60)
    
    test_results = {}
    
    # Test 1: Database Connection
    test_results['database'] = await test_database_connection()
    
    # Test 2: Gemini API
    test_results['gemini_api'] = await test_gemini_api()
    
    if not all([test_results['database'], test_results['gemini_api']]):
        logger.error("❌ Basic connectivity tests failed. Cannot proceed with narrative tests.")
        return False
    
    # Test 3: Find Test User
    test_user_id = await get_test_user()
    if not test_user_id:
        logger.error("❌ No suitable test user found. Cannot proceed with narrative tests.")
        return False
    
    try:
        # Test 4: Narrative Generation
        test_results['generation'] = await test_narrative_generation(test_user_id)
        
        # Test 5: Narrative Retrieval
        test_results['retrieval'] = await test_narrative_retrieval(test_user_id)
        
    finally:
        # Test 6: Cleanup
        await cleanup_test_data(test_user_id)
    
    # Results Summary
    logger.info("=" * 60)
    logger.info("📊 TEST RESULTS SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(test_results.values())
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {test_name.upper()}: {status}")
    
    logger.info(f"\n🎯 OVERALL RESULT: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 ALL TESTS PASSED - System ready for cron job deployment!")
        return True
    else:
        logger.error("❌ SOME TESTS FAILED - Fix issues before deploying cron job!")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Unexpected error during testing: {e}")
        sys.exit(1) 