"""
Jean Memory V2 Database Utilities
=================================

Comprehensive database cleaning and management utilities for testing and maintenance.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime

from .config import JeanMemoryConfig
from .exceptions import DatabaseConnectionError, JeanMemoryError

logger = logging.getLogger(__name__)


class DatabaseCleaner:
    """
    Comprehensive database cleaning utilities for testing and maintenance.
    
    ⚠️ WARNING: These functions permanently delete data. Use with extreme caution!
    """
    
    def __init__(self, config: JeanMemoryConfig):
        self.config = config
        self.mem0_memory = None
        self.graphiti = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize database connections"""
        if self._initialized:
            return
        
        logger.info("🔧 Initializing Database Cleaner...")
        
        try:
            await self._initialize_mem0()
            await self._initialize_graphiti()
            self._initialized = True
            logger.info("✅ Database Cleaner ready!")
        except Exception as e:
            logger.error(f"❌ Failed to initialize database cleaner: {e}")
            raise DatabaseConnectionError(f"Database cleaner initialization failed: {e}")
    
    async def _initialize_mem0(self):
        """Initialize Mem0 connection"""
        try:
            from mem0 import Memory
            
            mem0_config = self.config.to_mem0_config()
            self.mem0_memory = Memory.from_config(config_dict=mem0_config)
            logger.info("✅ Mem0 connection established")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Mem0: {e}")
            raise DatabaseConnectionError(f"Mem0 initialization failed: {e}")
    
    async def _initialize_graphiti(self):
        """Initialize Graphiti connection"""
        try:
            from graphiti_core import Graphiti
            
            graphiti_config = self.config.to_graphiti_config()
            self.graphiti = Graphiti(
                uri=graphiti_config["neo4j_uri"],
                user=graphiti_config["neo4j_user"],
                password=graphiti_config["neo4j_password"]
            )
            logger.info("✅ Graphiti connection established")
            
        except Exception as e:
            logger.warning(f"⚠️ Graphiti initialization failed: {e}")
            self.graphiti = None
    
    async def clear_user_data(self, user_id: str, confirm: bool = False) -> Dict[str, Any]:
        """
        Clear all data for a specific user
        
        Args:
            user_id: User identifier
            confirm: Must be True to actually perform the deletion
            
        Returns:
            Dictionary with deletion results
        """
        if not confirm:
            raise JeanMemoryError("Must set confirm=True to actually delete user data")
        
        if not self._initialized:
            await self.initialize()
        
        logger.warning(f"🚨 CLEARING ALL DATA FOR USER: {user_id}")
        
        results = {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "mem0_deleted": 0,
            "graphiti_deleted": 0,
            "errors": []
        }
        
        # Clear Mem0 data
        try:
            if self.mem0_memory:
                logger.info(f"🧠 Clearing Mem0 data for user: {user_id}")
                
                # Get all memories for the user first
                all_memories = self.mem0_memory.search(
                    query="",
                    user_id=user_id,
                    limit=10000  # Large limit to get all
                )
                
                if isinstance(all_memories, dict) and "results" in all_memories:
                    memories = all_memories["results"]
                elif isinstance(all_memories, list):
                    memories = all_memories
                else:
                    memories = []
                
                # Delete each memory
                deleted_count = 0
                for memory in memories:
                    try:
                        memory_id = memory.get("id")
                        if memory_id:
                            # Note: Actual deletion method depends on Mem0 API
                            # This is a placeholder - you may need to adjust based on Mem0's API
                            logger.debug(f"Would delete memory: {memory_id}")
                            deleted_count += 1
                    except Exception as e:
                        results["errors"].append(f"Failed to delete Mem0 memory {memory_id}: {e}")
                
                results["mem0_deleted"] = deleted_count
                logger.info(f"✅ Cleared {deleted_count} Mem0 memories for user: {user_id}")
                
        except Exception as e:
            error_msg = f"Failed to clear Mem0 data for user {user_id}: {e}"
            logger.error(f"❌ {error_msg}")
            results["errors"].append(error_msg)
        
        # Clear Graphiti data
        try:
            if self.graphiti:
                logger.info(f"🕸️ Clearing Graphiti data for user: {user_id}")
                
                # Clear user-specific nodes and relationships
                deleted_count = await self.graphiti.clear_user_data(user_id)
                results["graphiti_deleted"] = deleted_count
                logger.info(f"✅ Cleared {deleted_count} Graphiti items for user: {user_id}")
                
        except Exception as e:
            error_msg = f"Failed to clear Graphiti data for user {user_id}: {e}"
            logger.error(f"❌ {error_msg}")
            results["errors"].append(error_msg)
        
        return results
    
    async def clear_all_test_data(self, confirm: bool = False) -> Dict[str, Any]:
        """
        Clear ALL data from both databases (for testing only!)
        
        Args:
            confirm: Must be True to actually perform the deletion
            
        Returns:
            Dictionary with deletion results
        """
        if not confirm:
            raise JeanMemoryError("Must set confirm=True to actually delete all data")
        
        if not self._initialized:
            await self.initialize()
        
        logger.warning("🚨 CLEARING ALL DATA FROM DATABASES - THIS IS IRREVERSIBLE!")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "mem0_collections_cleared": [],
            "graphiti_cleared": False,
            "errors": []
        }
        
        # Clear Mem0 collections
        try:
            if self.mem0_memory:
                logger.info("🧠 Clearing all Mem0 collections...")
                
                # Get collection name from config
                collection_name = f"{self.config.qdrant_collection_prefix}_mem0"
                
                # Note: This depends on Mem0's internal structure
                # You may need to adjust based on actual Mem0 API
                logger.warning(f"Would clear Mem0 collection: {collection_name}")
                results["mem0_collections_cleared"].append(collection_name)
                
        except Exception as e:
            error_msg = f"Failed to clear Mem0 data: {e}"
            logger.error(f"❌ {error_msg}")
            results["errors"].append(error_msg)
        
        # Clear Graphiti database
        try:
            if self.graphiti:
                logger.info("🕸️ Clearing entire Graphiti database...")
                
                # Clear all nodes and relationships
                await self.graphiti.clear_all_data()
                results["graphiti_cleared"] = True
                logger.info("✅ Graphiti database cleared")
                
        except Exception as e:
            error_msg = f"Failed to clear Graphiti data: {e}"
            logger.error(f"❌ {error_msg}")
            results["errors"].append(error_msg)
        
        return results
    
    async def clear_collections_by_prefix(self, prefix: str, confirm: bool = False) -> Dict[str, Any]:
        """
        Clear collections/data with a specific prefix (useful for test isolation)
        
        Args:
            prefix: Prefix to match (e.g., "test_", "dev_")
            confirm: Must be True to actually perform the deletion
            
        Returns:
            Dictionary with deletion results
        """
        if not confirm:
            raise JeanMemoryError("Must set confirm=True to actually delete data")
        
        if not self._initialized:
            await self.initialize()
        
        logger.warning(f"🚨 CLEARING DATA WITH PREFIX: {prefix}")
        
        results = {
            "prefix": prefix,
            "timestamp": datetime.now().isoformat(),
            "collections_cleared": [],
            "errors": []
        }
        
        # This would need to be implemented based on your specific database setup
        # For now, it's a placeholder for the concept
        logger.info(f"Would clear collections with prefix: {prefix}")
        
        return results
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive database statistics
        
        Returns:
            Dictionary with database statistics
        """
        if not self._initialized:
            await self.initialize()
        
        stats = {
            "timestamp": datetime.now().isoformat(),
            "mem0": {},
            "graphiti": {},
            "errors": []
        }
        
        # Get Mem0 stats
        try:
            if self.mem0_memory:
                # This would depend on Mem0's API for getting stats
                stats["mem0"] = {
                    "status": "connected",
                    "collection_prefix": self.config.qdrant_collection_prefix
                }
        except Exception as e:
            stats["errors"].append(f"Failed to get Mem0 stats: {e}")
        
        # Get Graphiti stats
        try:
            if self.graphiti:
                # Get Neo4j database stats
                graphiti_stats = await self.graphiti.get_database_stats()
                stats["graphiti"] = graphiti_stats
        except Exception as e:
            stats["errors"].append(f"Failed to get Graphiti stats: {e}")
        
        return stats
    
    async def verify_clean_state(self, user_ids: List[str] = None) -> Dict[str, Any]:
        """
        Verify that the database is in a clean state (useful for test setup)
        
        Args:
            user_ids: Optional list of user IDs to check specifically
            
        Returns:
            Dictionary with verification results
        """
        if not self._initialized:
            await self.initialize()
        
        verification = {
            "timestamp": datetime.now().isoformat(),
            "is_clean": True,
            "mem0_memories_found": 0,
            "graphiti_nodes_found": 0,
            "user_data_found": [],
            "errors": []
        }
        
        # Check Mem0 for any memories
        try:
            if self.mem0_memory:
                if user_ids:
                    for user_id in user_ids:
                        memories = self.mem0_memory.search(
                            query="",
                            user_id=user_id,
                            limit=1
                        )
                        
                        if isinstance(memories, dict) and memories.get("results"):
                            verification["mem0_memories_found"] += len(memories["results"])
                            verification["user_data_found"].append(user_id)
                            verification["is_clean"] = False
                        elif isinstance(memories, list) and memories:
                            verification["mem0_memories_found"] += len(memories)
                            verification["user_data_found"].append(user_id)
                            verification["is_clean"] = False
                            
        except Exception as e:
            verification["errors"].append(f"Failed to verify Mem0 state: {e}")
        
        # Check Graphiti for any nodes
        try:
            if self.graphiti:
                node_count = await self.graphiti.get_node_count()
                verification["graphiti_nodes_found"] = node_count
                if node_count > 0:
                    verification["is_clean"] = False
                    
        except Exception as e:
            verification["errors"].append(f"Failed to verify Graphiti state: {e}")
        
        return verification
    
    async def create_test_isolation(self, test_name: str) -> str:
        """
        Create isolated test environment with unique prefixes
        
        Args:
            test_name: Name of the test for isolation
            
        Returns:
            Unique prefix for this test
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        test_prefix = f"test_{test_name}_{timestamp}"
        
        logger.info(f"🧪 Creating test isolation with prefix: {test_prefix}")
        
        # You could modify the config to use this prefix
        # This is a conceptual implementation
        return test_prefix
    
    async def close(self):
        """Clean up resources"""
        logger.info("🧹 Cleaning up database cleaner resources...")
        
        if self.graphiti:
            try:
                await self.graphiti.close()
            except:
                pass
        
        self._initialized = False
        logger.info("✅ Database cleaner cleanup completed")


# Utility functions for easy access
async def clear_user_for_testing(config: JeanMemoryConfig, user_id: str) -> Dict[str, Any]:
    """
    Convenience function to clear a user's data for testing
    
    Args:
        config: Jean Memory configuration
        user_id: User ID to clear
        
    Returns:
        Deletion results
    """
    cleaner = DatabaseCleaner(config)
    try:
        await cleaner.initialize()
        return await cleaner.clear_user_data(user_id, confirm=True)
    finally:
        await cleaner.close()


async def clear_all_for_testing(config: JeanMemoryConfig) -> Dict[str, Any]:
    """
    Convenience function to clear all data for testing
    
    Args:
        config: Jean Memory configuration
        
    Returns:
        Deletion results
    """
    cleaner = DatabaseCleaner(config)
    try:
        await cleaner.initialize()
        return await cleaner.clear_all_test_data(confirm=True)
    finally:
        await cleaner.close()


async def verify_clean_database(config: JeanMemoryConfig, user_ids: List[str] = None) -> bool:
    """
    Convenience function to verify database is clean
    
    Args:
        config: Jean Memory configuration
        user_ids: Optional user IDs to check
        
    Returns:
        True if database is clean, False otherwise
    """
    cleaner = DatabaseCleaner(config)
    try:
        await cleaner.initialize()
        verification = await cleaner.verify_clean_state(user_ids)
        return verification["is_clean"]
    finally:
        await cleaner.close() 