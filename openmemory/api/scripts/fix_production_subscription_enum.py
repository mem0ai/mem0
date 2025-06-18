#!/usr/bin/env python3
"""
Script to fix the subscription tier enum issue in production.

This script will:
1. Check the current state of the database
2. Fix any lowercase subscription tier values
3. Apply the missing migration
4. Verify the fix worked

Usage:
    python scripts/fix_production_subscription_enum.py
"""

import os
import sys
import subprocess
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.database import SessionLocal, engine
from app.models import User
from sqlalchemy import text, inspect
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_database_state():
    """Check current state of users table and subscription_tier column"""
    logger.info("Checking current database state...")
    
    with engine.connect() as connection:
        inspector = inspect(connection)
        
        # Check if users table exists
        if 'users' not in inspector.get_table_names():
            logger.error("Users table does not exist!")
            return False
        
        # Check columns in users table
        columns = inspector.get_columns('users')
        column_names = [col['name'] for col in columns]
        
        logger.info(f"Existing columns in users table: {column_names}")
        
        # Check if subscription_tier column exists
        if 'subscription_tier' in column_names:
            logger.info("subscription_tier column exists")
            
            # Check current values
            result = connection.execute(text("SELECT subscription_tier, COUNT(*) FROM users WHERE subscription_tier IS NOT NULL GROUP BY subscription_tier"))
            values = result.fetchall()
            logger.info(f"Current subscription_tier values: {values}")
            
        else:
            logger.info("subscription_tier column does not exist")
        
        return True

def fix_enum_values():
    """Fix any lowercase enum values in the database"""
    logger.info("Fixing lowercase subscription tier values...")
    
    with engine.connect() as connection:
        # Check if column exists and has data
        try:
            result = connection.execute(text("SELECT COUNT(*) FROM users WHERE subscription_tier IN ('free', 'pro', 'enterprise')"))
            count = result.scalar()
            
            if count > 0:
                logger.info(f"Found {count} records with lowercase subscription tier values")
                
                # Fix the values
                connection.execute(text("UPDATE users SET subscription_tier = 'FREE' WHERE subscription_tier = 'free'"))
                connection.execute(text("UPDATE users SET subscription_tier = 'PRO' WHERE subscription_tier = 'pro'"))
                connection.execute(text("UPDATE users SET subscription_tier = 'ENTERPRISE' WHERE subscription_tier = 'enterprise'"))
                connection.commit()
                
                logger.info("Fixed lowercase subscription tier values")
            else:
                logger.info("No lowercase subscription tier values found")
                
        except Exception as e:
            logger.info(f"Could not check/fix enum values (column might not exist yet): {e}")

def run_migration():
    """Run the alembic migration"""
    logger.info("Running Alembic migration...")
    
    try:
        # Change to the API directory
        api_dir = Path(__file__).parent.parent
        os.chdir(api_dir)
        
        # Run alembic upgrade
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=api_dir
        )
        
        if result.returncode == 0:
            logger.info("Migration completed successfully!")
            logger.info(result.stdout)
        else:
            logger.error(f"Migration failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error running migration: {e}")
        return False
    
    return True

def verify_fix():
    """Verify that the fix worked"""
    logger.info("Verifying the fix...")
    
    try:
        with SessionLocal() as db:
            # Try to query users - this should work now
            users = db.query(User).limit(5).all()
            logger.info(f"Successfully queried {len(users)} users")
            
            for user in users:
                logger.info(f"User {user.user_id}: subscription_tier = {user.subscription_tier}")
        
        logger.info("✅ Fix verified successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Fix verification failed: {e}")
        return False

def main():
    """Main function to orchestrate the fix"""
    logger.info("🔧 Starting production subscription enum fix...")
    
    # Step 1: Check current state
    if not check_database_state():
        logger.error("Failed to check database state")
        return False
    
    # Step 2: Fix any lowercase values first
    fix_enum_values()
    
    # Step 3: Run migration
    if not run_migration():
        logger.error("Migration failed")
        return False
    
    # Step 4: Verify fix
    if not verify_fix():
        logger.error("Fix verification failed")
        return False
    
    logger.info("🎉 Production subscription enum fix completed successfully!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 