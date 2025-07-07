"""
Dynamic Index Setup Utilities for Jean Memory V2
=================================================

This module provides utilities to ensure proper Qdrant collection indexes
for user isolation and performance in the Jean Memory V2 system.

Key Features:
- Automatic index creation for new collections
- Fast index verification (skips if already exists)
- Proper error handling and logging
- Support for both KEYWORD and UUID user_id indexes
"""

import asyncio
import logging
from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models

logger = logging.getLogger(__name__)


class IndexSetupManager:
    """Manages dynamic index setup for Qdrant collections"""
    
    def __init__(self, qdrant_url: str, qdrant_api_key: str, wait_time: int = 5):
        """
        Initialize the Index Setup Manager
        
        Args:
            qdrant_url: Qdrant Cloud URL
            qdrant_api_key: Qdrant API key
            wait_time: Seconds to wait after index creation (default: 5)
        """
        self.qdrant_url = qdrant_url
        self.qdrant_api_key = qdrant_api_key
        self.wait_time = wait_time
        self._client = None
    
    @property
    def client(self) -> QdrantClient:
        """Get or create Qdrant client (lazy initialization)"""
        if self._client is None:
            self._client = QdrantClient(url=self.qdrant_url, api_key=self.qdrant_api_key)
        return self._client
    
    def ensure_collection_indexes(self, collection_name: str) -> bool:
        """
        Ensure a collection has proper user_id indexes for isolation
        
        This is a fast operation that skips if indexes already exist.
        
        Args:
            collection_name: Name of the Qdrant collection
            
        Returns:
            True if indexes are ready, False if errors occurred
        """
        logger.info(f"🔧 Ensuring indexes for collection: {collection_name}")
        
        try:
            # Check if collection exists first
            try:
                self.client.get_collection(collection_name)
            except Exception:
                logger.warning(f"Collection {collection_name} does not exist, skipping index setup")
                return False
            
            indexes_created = 0
            
            # Create user_id KEYWORD index (for exact matching)
            try:
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="user_id",
                    field_schema=models.PayloadSchemaType.KEYWORD,
                )
                logger.info(f"  ✅ Created user_id KEYWORD index")
                indexes_created += 1
            except Exception as e:
                error_str = str(e).lower()
                if "already exists" in error_str or "index exists" in error_str:
                    logger.debug(f"  ✅ user_id KEYWORD index already exists")
                else:
                    logger.warning(f"  ⚠️ Could not create KEYWORD index: {e}")
            
            # Create user_id UUID index (for UUID matching)
            try:
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="user_id",
                    field_schema=models.PayloadSchemaType.UUID,
                )
                logger.info(f"  ✅ Created user_id UUID index")
                indexes_created += 1
            except Exception as e:
                error_str = str(e).lower()
                if "already exists" in error_str or "index exists" in error_str:
                    logger.debug(f"  ✅ user_id UUID index already exists")
                else:
                    logger.warning(f"  ⚠️ Could not create UUID index: {e}")
            
            logger.info(f"  📊 Collection {collection_name}: {indexes_created} indexes processed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to ensure indexes for {collection_name}: {e}")
            return False
    
    async def ensure_collection_indexes_async(self, collection_name: str) -> bool:
        """Async version of ensure_collection_indexes"""
        return self.ensure_collection_indexes(collection_name)
    
    def wait_for_indexes(self):
        """Wait for indexes to be fully ready"""
        if self.wait_time > 0:
            logger.info(f"⏳ Waiting {self.wait_time} seconds for indexes to be ready...")
            import time
            time.sleep(self.wait_time)
    
    async def wait_for_indexes_async(self):
        """Async version of wait_for_indexes"""
        if self.wait_time > 0:
            logger.info(f"⏳ Waiting {self.wait_time} seconds for indexes to be ready...")
            await asyncio.sleep(self.wait_time)
    
    def setup_collection_with_indexes(self, collection_name: str, wait: bool = True) -> bool:
        """
        Complete setup: ensure indexes and optionally wait for readiness
        
        Args:
            collection_name: Name of the collection
            wait: Whether to wait for indexes to be ready
            
        Returns:
            True if setup succeeded
        """
        success = self.ensure_collection_indexes(collection_name)
        
        if success and wait:
            self.wait_for_indexes()
        
        return success
    
    async def setup_collection_with_indexes_async(self, collection_name: str, wait: bool = True) -> bool:
        """Async version of setup_collection_with_indexes"""
        success = await self.ensure_collection_indexes_async(collection_name)
        
        if success and wait:
            await self.wait_for_indexes_async()
        
        return success
    
    def get_all_collections(self) -> list:
        """Get list of all collection names"""
        try:
            collections = self.client.get_collections()
            return [col.name for col in collections.collections]
        except Exception as e:
            logger.error(f"Failed to get collections: {e}")
            return []
    
    def setup_all_existing_collections(self) -> bool:
        """Set up indexes for all existing collections"""
        collections = self.get_all_collections()
        
        if not collections:
            logger.info("No collections found")
            return True
        
        logger.info(f"🔧 Setting up indexes for {len(collections)} collections")
        
        success_count = 0
        for collection_name in collections:
            if self.ensure_collection_indexes(collection_name):
                success_count += 1
        
        if self.wait_time > 0:
            self.wait_for_indexes()
        
        logger.info(f"📊 Successfully processed {success_count}/{len(collections)} collections")
        return success_count == len(collections)


# Convenience functions for direct usage
def ensure_collection_indexes(
    collection_name: str, 
    qdrant_url: str, 
    qdrant_api_key: str,
    wait_time: int = 5
) -> bool:
    """
    Convenience function to ensure indexes for a single collection
    
    Args:
        collection_name: Name of the collection
        qdrant_url: Qdrant Cloud URL
        qdrant_api_key: Qdrant API key
        wait_time: Seconds to wait after index creation
        
    Returns:
        True if successful
    """
    manager = IndexSetupManager(qdrant_url, qdrant_api_key, wait_time)
    return manager.setup_collection_with_indexes(collection_name, wait=True)


async def ensure_collection_indexes_async(
    collection_name: str, 
    qdrant_url: str, 
    qdrant_api_key: str,
    wait_time: int = 5
) -> bool:
    """Async convenience function to ensure indexes for a single collection"""
    manager = IndexSetupManager(qdrant_url, qdrant_api_key, wait_time)
    return await manager.setup_collection_with_indexes_async(collection_name, wait=True)


def setup_all_collections(
    qdrant_url: str, 
    qdrant_api_key: str,
    wait_time: int = 5
) -> bool:
    """
    Convenience function to set up indexes for all existing collections
    
    Args:
        qdrant_url: Qdrant Cloud URL
        qdrant_api_key: Qdrant API key
        wait_time: Seconds to wait after index creation
        
    Returns:
        True if all collections were processed successfully
    """
    manager = IndexSetupManager(qdrant_url, qdrant_api_key, wait_time)
    return manager.setup_all_existing_collections() 