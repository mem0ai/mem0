#!/usr/bin/env python3
"""
Migration script to move memories from stu_ID to stu user ID.
This script will:
1. Read all memories from Qdrant with user_id 'stu_ID'
2. Add them to Qdrant with user_id 'stu'
3. Import them into the SQL database
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.memory import get_memory_client
from app.database import get_db
from app.models import User, App, Memory, MemoryState
from sqlalchemy.orm import Session
import uuid
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def migrate_user_ids():
    """Migrate memories from stu_ID to stu user ID."""
    try:
        logger.info("=== Starting User ID Migration ===")
        
        # Set up environment variables
        os.environ['QDRANT_HOST'] = 'qdrant.root.svc.cluster.local'
        os.environ['QDRANT_PORT'] = '6333'
        os.environ['NEO4J_URL'] = 'neo4j://neo4j.root.svc.cluster.local:7687'
        os.environ['NEO4J_USERNAME'] = 'neo4j'
        os.environ['NEO4J_PASSWORD'] = 'taketheredpillNe0'
        
        # Get memory client
        logger.info("Initializing memory client...")
        client = await get_memory_client()
        if not client:
            logger.error("Memory client not available")
            return False
            
        # Get all memories for stu_ID
        logger.info("Getting memories for user 'stu_ID'...")
        memories_stu_id = await client.get_all(user_id='stu_ID')
        
        if 'results' not in memories_stu_id or not memories_stu_id['results']:
            logger.info("No memories found for stu_ID")
            return True
            
        logger.info(f"Found {len(memories_stu_id['results'])} memories to migrate")
        
        # Get database session
        db = next(get_db())
        
        # Ensure user 'stu' exists
        user = db.query(User).filter(User.user_id == 'stu').first()
        if not user:
            logger.info("Creating user 'stu'...")
            user = User(user_id='stu', name='stu')
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Ensure default app exists
        app = db.query(App).filter(App.name == 'openmemory').first()
        if not app:
            logger.info("Creating default app 'openmemory'...")
            app = App(
                id=str(uuid.uuid4()),
                name='openmemory',
                description='Default OpenMemory app',
                is_active=True
            )
            db.add(app)
            db.commit()
            db.refresh(app)
        
        # Migrate memories in batches
        batch_size = 10
        migrated_count = 0
        imported_count = 0
        
        for i in range(0, len(memories_stu_id['results']), batch_size):
            batch = memories_stu_id['results'][i:i + batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} memories)")
            
            for memory_data in batch:
                try:
                    # Add to Qdrant with new user_id
                    await client.add(
                        memory_data['memory'],
                        user_id='stu',
                        metadata=memory_data.get('metadata', {})
                    )
                    migrated_count += 1
                    
                    # Import into SQL database
                    memory = Memory(
                        id=str(uuid.uuid4()),
                        user_id=user.id,
                        app_id=app.id,
                        content=memory_data['memory'],
                        state=MemoryState.active,
                        metadata=memory_data.get('metadata', {}),
                        created_at=datetime.fromisoformat(memory_data['created_at'].replace('Z', '+00:00')) if memory_data.get('created_at') else datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    db.add(memory)
                    imported_count += 1
                    
                except Exception as e:
                    logger.error(f"Error migrating memory {memory_data.get('id', 'unknown')}: {e}")
            
            # Commit batch to database
            try:
                db.commit()
                logger.info(f"Committed batch {i//batch_size + 1} to database")
            except Exception as e:
                logger.error(f"Error committing batch {i//batch_size + 1}: {e}")
                db.rollback()
            
            # Small delay between batches
            await asyncio.sleep(0.5)
        
        logger.info(f"Migration completed successfully!")
        logger.info(f"- Migrated {migrated_count} memories to Qdrant with user_id 'stu'")
        logger.info(f"- Imported {imported_count} memories into SQL database")
        
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    success = asyncio.run(migrate_user_ids())
    sys.exit(0 if success else 1)
