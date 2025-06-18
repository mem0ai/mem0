#!/usr/bin/env python3
"""
One-time fix for missing document_chunks metadata column
Run this once in your Render environment, then delete it.

Usage: python run_migration_fix.py
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_schema():
    """Fix the missing metadata column issue"""
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        logger.error("DATABASE_URL not found in environment")
        return False
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            # Check if metadata column exists
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'document_chunks' 
                    AND column_name = 'metadata' 
                    AND table_schema = 'public'
                ) as metadata_exists
            """))
            
            metadata_exists = result.scalar()
            
            if metadata_exists:
                logger.info("✅ metadata column already exists - no fix needed")
                return True
            
            logger.info("🔧 Adding missing metadata column...")
            
            # Add the missing column
            conn.execute(text("ALTER TABLE document_chunks ADD COLUMN metadata JSONB"))
            
            # Update migration state
            conn.execute(text("""
                INSERT INTO alembic_version (version_num) 
                VALUES ('2834f44d4d7d')
                ON CONFLICT (version_num) DO NOTHING
            """))
            
            # Clear stuck documents
            result = conn.execute(text("""
                UPDATE documents 
                SET metadata_ = metadata_ || '{"needs_chunking": false, "schema_fixed": true}'::jsonb
                WHERE metadata_->>'needs_chunking' = 'true'
            """))
            
            fixed_docs = result.rowcount
            conn.commit()
            
            logger.info(f"✅ Schema fixed successfully!")
            logger.info(f"✅ Cleared {fixed_docs} stuck documents")
            logger.info("📋 Next: Restart your web service and delete this file")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Error fixing schema: {e}")
        return False

if __name__ == "__main__":
    success = fix_schema()
    sys.exit(0 if success else 1) 