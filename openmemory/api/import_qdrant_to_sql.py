#!/usr/bin/env python3
"""
Import memories from Qdrant to SQL database with correct user UUID mapping.
This script fixes the failed SQL import from the previous migration.
"""

import asyncio
import os
import uuid
from datetime import datetime
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue
import sqlite3
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_sql_session():
    """Get SQLAlchemy session for the database."""
    # Database URL for SQLite - use absolute path
    db_url = "sqlite:////data/openmemory.db"
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    return Session()

def import_qdrant_memories_to_sql():
    """Import memories from Qdrant to SQL database with correct user UUID."""
    logger.info("=== Starting Qdrant to SQL import ===")
    
    # Connect to Qdrant
    client = QdrantClient(host='qdrant.root.svc.cluster.local', port=6333)
    
    # Get SQL session
    session = get_sql_session()
    
    try:
        # Get the correct user UUID for 'stu'
        result = session.execute(text("SELECT id FROM users WHERE user_id = 'stu'"))
        user_row = result.fetchone()
        if not user_row:
            logger.error("User 'stu' not found in database")
            return
        
        user_uuid = user_row[0]
        logger.info(f"Found user UUID for 'stu': {user_uuid}")
        
        # Get memories from Qdrant with user_id 'stu'
        stu_filter = Filter(
            must=[
                FieldCondition(
                    key='user_id',
                    match=MatchValue(value='stu')
                )
            ]
        )
        
        # Get all memories in batches
        all_memories = []
        offset = None
        
        while True:
            result = client.scroll(
                collection_name='openmemory',
                scroll_filter=stu_filter,
                limit=100,
                offset=offset
            )
            
            points, next_offset = result
            all_memories.extend(points)
            
            if next_offset is None:
                break
            offset = next_offset
        
        logger.info(f"Found {len(all_memories)} memories in Qdrant for user 'stu'")
        
        # Check which memories are already in SQL database
        existing_memory_ids = set()
        result = session.execute(text("SELECT id FROM memories WHERE user_id = :user_id"), 
                               {"user_id": user_uuid})
        for row in result:
            existing_memory_ids.add(row[0])
        
        logger.info(f"Found {len(existing_memory_ids)} existing memories in SQL database")
        
        # Import new memories
        imported_count = 0
        for point in all_memories:
            memory_id = point.id
            
            # Skip if already exists
            if memory_id in existing_memory_ids:
                continue
            
            payload = point.payload
            memory_content = payload.get('data', '')  # Content is stored in 'data' field
            metadata = {
                'source_app': payload.get('source_app', ''),
                'mcp_client': payload.get('mcp_client', ''),
                'created_at': payload.get('created_at', ''),
                'hash': payload.get('hash', '')
            }
            import json
            metadata_json = json.dumps(metadata)
            
            # Use friend_lite as the default app for imported memories
            app_name = 'friend_lite'
            app_result = session.execute(text("SELECT id FROM apps WHERE name = :name AND is_active = 1"), 
                                       {"name": app_name})
            app_row = app_result.fetchone()
            
            if app_row:
                app_id = app_row[0]
            else:
                # Create the friend_lite app if it doesn't exist
                logger.info(f"Creating app '{app_name}' for imported memories")
                app_id = str(uuid.uuid4())
                session.execute(text("""
                    INSERT INTO apps (id, owner_id, name, description, metadata_, is_active, created_at, updated_at)
                    VALUES (:id, :owner_id, :name, :description, :metadata_, :is_active, :created_at, :updated_at)
                """), {
                    "id": app_id,
                    "owner_id": user_uuid,
                    "name": app_name,
                    "description": "App for imported memories from Qdrant migration",
                    "metadata_": "{}",
                    "is_active": True,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                })
                session.flush()  # Flush to ensure the app is created before using its ID
            
            # Insert memory into SQL database
            try:
                session.execute(text("""
                    INSERT INTO memories (
                        id, user_id, app_id, content, vector, metadata, 
                        state, created_at, updated_at, archived_at, deleted_at
                    ) VALUES (
                        :id, :user_id, :app_id, :content, :vector, :metadata,
                        :state, :created_at, :updated_at, :archived_at, :deleted_at
                    )
                """), {
                    "id": memory_id,
                    "user_id": user_uuid,
                    "app_id": app_id,
                    "content": memory_content,
                    "vector": None,  # Vector data is in Qdrant
                    "metadata": metadata_json,
                    "state": "active",
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "archived_at": None,
                    "deleted_at": None
                })
                
                imported_count += 1
                if imported_count % 10 == 0:
                    logger.info(f"Imported {imported_count} memories...")
                    
            except Exception as e:
                logger.error(f"Error importing memory {memory_id}: {e}")
                continue
        
        # Commit all changes
        session.commit()
        logger.info(f"Successfully imported {imported_count} memories to SQL database")
        
        # Verify final count
        result = session.execute(text("SELECT COUNT(*) FROM memories WHERE user_id = :user_id"), 
                               {"user_id": user_uuid})
        final_count = result.fetchone()[0]
        logger.info(f"Final memory count for user 'stu': {final_count}")
        
    except Exception as e:
        logger.error(f"Error during import: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    import_qdrant_memories_to_sql()
