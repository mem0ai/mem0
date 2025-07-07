"""
Jean Memory V2 Core
===================

Main interface class that combines search and ingestion capabilities into a unified API.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union

from .config import JeanMemoryConfig
from .search import HybridSearchEngine, SearchResult
from .ingestion import MemoryIngestionEngine, IngestionResult
from .exceptions import JeanMemoryError, ConfigurationError
from .database_utils import DatabaseCleaner
from .utils import SearchResult, IngestionResult

logger = logging.getLogger(__name__)


class JeanMemoryV2:
    """
    Main Jean Memory V2 interface combining advanced search and ingestion capabilities.
    
    This class provides a unified API for:
    - Memory ingestion with safety checks and deduplication
    - Hybrid search across Mem0, Graphiti, and Gemini AI
    - Configuration management and resource cleanup
    
    Example:
        # Initialize with API keys
        jm = JeanMemoryV2(
            openai_api_key="sk-...",
            qdrant_api_key="...",
            neo4j_uri="neo4j://...",
            neo4j_user="neo4j",
            neo4j_password="...",
            gemini_api_key="..."
        )
        
        # Ingest memories
        result = await jm.ingest_memories(
            memories=["I love hiking", "My favorite color is blue"],
            user_id="user123"
        )
        
        # Search memories
        search_result = await jm.search("What are my hobbies?", user_id="user123")
        print(search_result.synthesis)
    """
    
    def __init__(
        self,
        openai_api_key: str,
        qdrant_api_key: Optional[str],
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str,
        gemini_api_key: Optional[str] = None,
        qdrant_host: Optional[str] = None,
        qdrant_port: Optional[str] = None,
        qdrant_url: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Jean Memory V2
        
        Args:
            openai_api_key: OpenAI API key (required)
            qdrant_api_key: Qdrant API key (required for cloud, optional for localhost)
            neo4j_uri: Neo4j connection URI (required)
            neo4j_user: Neo4j username (required)
            neo4j_password: Neo4j password (required)
            gemini_api_key: Google Gemini API key (optional, enables AI synthesis)
            qdrant_host: Qdrant host (optional if qdrant_url provided)
            qdrant_port: Qdrant port (optional if qdrant_url provided)
            qdrant_url: Full Qdrant URL (optional if host/port provided)
            **kwargs: Additional configuration options
        """
        # Create configuration
        self.config = JeanMemoryConfig(
            openai_api_key=openai_api_key,
            qdrant_api_key=qdrant_api_key,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            gemini_api_key=gemini_api_key,
            qdrant_host=qdrant_host,
            qdrant_port=qdrant_port,
            qdrant_url=qdrant_url,
            **kwargs
        )
        
        # Initialize engines
        self.search_engine = HybridSearchEngine(self.config)
        self.ingestion_engine = MemoryIngestionEngine(self.config)
        self._database_cleaner = None  # Lazy initialization for testing
        
        self._initialized = False
        
        logger.info("🎯 Jean Memory V2 initialized")
    
    @classmethod
    def from_config(cls, config: JeanMemoryConfig) -> 'JeanMemoryV2':
        """Create instance from existing configuration"""
        instance = cls.__new__(cls)
        instance.config = config
        instance.search_engine = HybridSearchEngine(config)
        instance.ingestion_engine = MemoryIngestionEngine(config)
        instance._database_cleaner = None  # Lazy initialization for testing
        instance._initialized = False
        
        logger.info("🎯 Jean Memory V2 created from config")
        return instance
    
    @classmethod
    def from_env_file(cls, env_file: str) -> 'JeanMemoryV2':
        """
        Create JeanMemoryV2 instance from environment file
        
        Args:
            env_file: Path to .env file
            
        Returns:
            JeanMemoryV2 instance
        """
        config = JeanMemoryConfig.from_env_file(env_file)
        return cls.from_config(config)
    
    @classmethod
    def from_environment(cls) -> 'JeanMemoryV2':
        """
        Create JeanMemoryV2 instance from environment variables
        
        Returns:
            JeanMemoryV2 instance
        """
        config = JeanMemoryConfig.from_environment()
        return cls.from_config(config)
    
    @classmethod
    def from_openmemory_test_env(cls, use_orchestrator: bool = False) -> 'JeanMemoryV2':
        """
        Create JeanMemoryV2 instance from openmemory test environment
        
        This is a convenience method that loads configuration from
        openmemory/api/.env.test with test-optimized settings.
        
        Args:
            use_orchestrator: If True, defer initialization to orchestrator (prevents rate limiting)
        
        Returns:
            JeanMemoryV2 instance configured for testing
        """
        config = JeanMemoryConfig.from_environment()
        
        if use_orchestrator:
            # Create instance without full initialization - orchestrator will handle it
            instance = cls.__new__(cls)
            instance.config = config
            instance.search_engine = None  # Will be set by orchestrator
            instance.ingestion_engine = None  # Will be set by orchestrator
            instance._database_cleaner = None  # Will be set by orchestrator
            instance._initialized = False
            instance._use_orchestrator = True
            logger.info("✅ Jean Memory V2 created with orchestrator support")
            return instance
        else:
            return cls.from_config(config)
    
    async def initialize(self):
        """Initialize all engines and connections"""
        if self._initialized:
            return
        
        logger.info("🚀 Initializing Jean Memory V2 engines...")
        
        try:
            # Initialize both engines in parallel
            await asyncio.gather(
                self.search_engine.initialize(),
                self.ingestion_engine.initialize()
            )
            
            self._initialized = True
            logger.info("✅ Jean Memory V2 fully initialized and ready!")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Jean Memory V2: {e}")
            raise JeanMemoryError(f"Initialization failed: {e}")
    
    async def ingest_memories(
        self,
        memories: Union[List[str], str],
        user_id: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> IngestionResult:
        """
        Ingest memories into the system
        
        Args:
            memories: List of memory strings or single memory string
            user_id: User identifier
            metadata: Optional metadata to attach to memories
            
        Returns:
            IngestionResult with detailed ingestion statistics
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.ingestion_engine.ingest_memories(
            memories=memories,
            user_id=user_id,
            metadata=metadata
        )
    
    async def ingest_from_file(self, file_path: str, user_id: str) -> IngestionResult:
        """
        Ingest memories from a text file (one memory per line)
        
        Args:
            file_path: Path to text file containing memories
            user_id: User identifier
            
        Returns:
            IngestionResult with detailed ingestion statistics
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.ingestion_engine.ingest_from_file(file_path, user_id)
    
    async def search(
        self,
        query: str,
        user_id: str,
        limit: Optional[int] = None
    ) -> SearchResult:
        """
        Search memories using hybrid intelligence
        
        Args:
            query: Search query
            user_id: User identifier
            limit: Maximum number of results (optional)
            
        Returns:
            SearchResult with synthesis and source data
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.search_engine.search(
            query=query,
            user_id=user_id,
            limit=limit
        )
    
    async def search_mem0_only(
        self,
        query: str,
        user_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search using only Mem0 (no synthesis)
        
        Args:
            query: Search query
            user_id: User identifier
            limit: Maximum number of results
            
        Returns:
            List of raw Mem0 search results
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.search_engine.search_mem0(query, user_id, limit)
    
    async def search_graphiti_only(
        self,
        query: str,
        user_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Search using only Graphiti (no synthesis)
        
        Args:
            query: Search query
            user_id: User identifier
            limit: Maximum number of results
            
        Returns:
            List of raw Graphiti search results
        """
        if not self._initialized:
            await self.initialize()
        
        return await self.search_engine.search_graphiti(query, user_id, limit)
    
    async def get_user_stats(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive statistics for a user
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with user statistics from all engines
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # Get stats from ingestion engine
            ingestion_stats = await self.ingestion_engine.get_ingestion_stats(user_id)
            
            # Add configuration info
            stats = {
                **ingestion_stats,
                "config": {
                    "enable_graph_memory": self.config.enable_graph_memory,
                    "enable_gemini_synthesis": self.config.enable_gemini_synthesis,
                    "default_search_limit": self.config.default_search_limit,
                    "batch_size": self.config.batch_size,
                    "enable_safety_checks": self.config.enable_safety_checks,
                    "enable_deduplication": self.config.enable_deduplication
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ Failed to get user stats: {e}")
            return {"user_id": user_id, "error": str(e)}
    
    async def clear_user_memories(self, user_id: str) -> bool:
        """
        Clear all memories for a user (use with extreme caution)
        
        Args:
            user_id: User identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self._initialized:
            await self.initialize()
        
        logger.warning(f"🚨 CLEARING ALL MEMORIES FOR USER: {user_id}")
        return await self.ingestion_engine.clear_user_memories(user_id)
    
    async def clear_user_data_for_testing(self, user_id: str, confirm: bool = False) -> Dict[str, Any]:
        """
        Clear all data for a user across all engines (for testing)
        
        Args:
            user_id: User identifier
            confirm: Must be True to actually perform the deletion
            
        Returns:
            Dictionary with detailed deletion results
        """
        if not confirm:
            raise JeanMemoryError("Must set confirm=True to actually delete user data")
        
        if not self._database_cleaner:
            self._database_cleaner = DatabaseCleaner(self.config)
        
        return await self._database_cleaner.clear_user_data(user_id, confirm=True)
    
    async def clear_all_data_for_testing(self, confirm: bool = False) -> Dict[str, Any]:
        """
        Clear ALL data from all engines (for testing only!)
        
        Args:
            confirm: Must be True to actually perform the deletion
            
        Returns:
            Dictionary with detailed deletion results
        """
        if not confirm:
            raise JeanMemoryError("Must set confirm=True to actually delete all data")
        
        if not self._database_cleaner:
            self._database_cleaner = DatabaseCleaner(self.config)
        
        return await self._database_cleaner.clear_all_test_data(confirm=True)
    
    async def verify_clean_state_for_testing(self, user_ids: List[str] = None) -> Dict[str, Any]:
        """
        Verify that the database is in a clean state (useful for test setup)
        
        Args:
            user_ids: Optional list of user IDs to check specifically
            
        Returns:
            Dictionary with verification results
        """
        if not self._database_cleaner:
            self._database_cleaner = DatabaseCleaner(self.config)
        
        return await self._database_cleaner.verify_clean_state(user_ids)
    
    async def get_database_stats_for_testing(self) -> Dict[str, Any]:
        """
        Get comprehensive database statistics (useful for testing and monitoring)
        
        Returns:
            Dictionary with database statistics
        """
        if not self._database_cleaner:
            self._database_cleaner = DatabaseCleaner(self.config)
        
        return await self._database_cleaner.get_database_stats()
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a comprehensive health check of all systems
        
        Returns:
            Dictionary with health status of all components
        """
        health = {
            "jean_memory_v2": "healthy",
            "timestamp": asyncio.get_event_loop().time(),
            "initialized": self._initialized,
            "components": {}
        }
        
        try:
            if not self._initialized:
                await self.initialize()
            
            # Test Mem0 connection
            try:
                if self.search_engine.mem0_memory:
                    # Simple test search
                    test_result = self.search_engine.mem0_memory.search(
                        query="test", 
                        user_id="health_check", 
                        limit=1
                    )
                    health["components"]["mem0"] = "healthy"
                else:
                    health["components"]["mem0"] = "not_initialized"
            except Exception as e:
                health["components"]["mem0"] = f"error: {e}"
            
            # Test Graphiti connection
            try:
                if self.search_engine.graphiti:
                    health["components"]["graphiti"] = "healthy"
                else:
                    health["components"]["graphiti"] = "not_available"
            except Exception as e:
                health["components"]["graphiti"] = f"error: {e}"
            
            # Test Gemini connection
            try:
                if self.search_engine.gemini_client:
                    health["components"]["gemini"] = "healthy"
                else:
                    health["components"]["gemini"] = "not_available"
            except Exception as e:
                health["components"]["gemini"] = f"error: {e}"
            
            # Overall health assessment
            component_statuses = list(health["components"].values())
            if all("healthy" in status for status in component_statuses):
                health["jean_memory_v2"] = "healthy"
            elif any("error" in status for status in component_statuses):
                health["jean_memory_v2"] = "degraded"
            else:
                health["jean_memory_v2"] = "limited"
            
        except Exception as e:
            health["jean_memory_v2"] = f"error: {e}"
        
        return health
    
    async def close(self):
        """
        Clean up all resources and connections
        """
        logger.info("🧹 Shutting down Jean Memory V2...")
        
        try:
            # Close engines and database cleaner in parallel
            close_tasks = [
                self.search_engine.close(),
                self.ingestion_engine.close(),
            ]
            
            if self._database_cleaner:
                close_tasks.append(self._database_cleaner.close())
            
            await asyncio.gather(*close_tasks, return_exceptions=True)
            
            self._initialized = False
            logger.info("✅ Jean Memory V2 shutdown completed")
            
        except Exception as e:
            logger.error(f"❌ Error during shutdown: {e}")
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
    
    def __repr__(self) -> str:
        return f"JeanMemoryV2(initialized={self._initialized}, config={self.config.qdrant_collection_prefix})" 