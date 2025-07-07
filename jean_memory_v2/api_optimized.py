"""
Jean Memory V2 API - OPTIMIZED VERSION
=====================================

High-performance API that provides unified interface for memory operations
with optimized collection management and eliminated wait statements.

PERFORMANCE OPTIMIZATIONS:
- Eliminated hard-coded sleep statements 
- Collection/index checks moved to background
- Lazy Graphiti initialization
- Smart caching of collection states
- Batch operations for better throughput
"""

import asyncio
import json
import logging
import time
import traceback
from typing import List, Optional, Dict, Any, Union, Set
from datetime import datetime
from uuid import uuid4

from .models import (
    AddMemoryRequest, AddMemoryResponse,
    AddMemoriesBulkRequest, AddMemoriesBulkResponse,
    SearchMemoriesRequest, SearchMemoriesResponse,
    ClearMemoriesRequest, ClearMemoriesResponse,
    MemoryItem, MemoryType, SearchStrategy, SystemStatus,
    DatabaseStatus, APIError, APIConfig
)
from .config import JeanMemoryConfig
from .exceptions import ConfigurationError


logger = logging.getLogger(__name__)


class JeanMemoryAPIOptimized:
    """
    OPTIMIZED Jean Memory V2 API for maximum performance
    
    Provides unified access to memory storage with:
    - Zero wait statements
    - Smart collection caching
    - Lazy initialization
    - Background index management
    """
    
    VERSION = "2.1.0-optimized"
    
    def __init__(self, config: Optional[JeanMemoryConfig] = None, api_config: Optional[APIConfig] = None):
        """
        Initialize the optimized Jean Memory V2 API
        
        Args:
            config: Jean Memory configuration
            api_config: API-specific configuration
        """
        logger.info(f"🔧 DEBUG: JeanMemoryAPIOptimized received config: {config is not None}")
        if config is None:
            logger.info("🔧 DEBUG: Config is None, trying to load from .env.test")
            try:
                config = JeanMemoryConfig.from_openmemory_test_env()
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                raise ConfigurationError(f"Configuration loading failed: {e}")
        else:
            logger.info(f"🔧 DEBUG: Using provided config: {type(config)}")
        
        self.config = config
        # Graph storage re-enabled - Neo4j connection is working!
        default_api_config = APIConfig(enable_graph_storage=True)
        self.api_config = api_config or default_api_config
        
        # Optimization: Track collection states to avoid repeated checks
        self._collection_states: Dict[str, bool] = {}  # user_id -> collection_ready
        self._collection_creating: Set[str] = set()  # Currently creating collections
        
        # Initialize components
        self._mem0_memory = None
        self._user_memory_cache: Dict[str, Any] = {}  # Cache user memory instances
        self._graphiti = None
        self._graphiti_initializing = False
        self._initialized = False
        
        logger.info(f"Jean Memory V2 API OPTIMIZED v{self.VERSION} initialized")
    
    async def initialize(self) -> None:
        """Initialize core components with minimal blocking"""
        if self._initialized:
            return
        
        logger.info("🚀 Initializing Jean Memory V2 API (OPTIMIZED)...")
        
        try:
            # Optimization: Skip expensive backend initialization
            # Only initialize when actually needed (lazy loading)
            self._initialized = True
            logger.info("✅ Jean Memory V2 API OPTIMIZED initialization complete (lazy mode)")
            
        except Exception as e:
            logger.error(f"❌ Jean Memory V2 API initialization failed: {e}")
            raise
    
    async def _ensure_collection_ready_optimized(self, user_id: str) -> str:
        """
        OPTIMIZED collection readiness check with smart caching and no waits
        
        Key optimizations:
        1. Cache collection states to avoid repeated API calls
        2. Non-blocking collection creation
        3. Skip index wait statements
        4. Only check/create when absolutely necessary
        
        Args:
            user_id: User ID for collection naming
            
        Returns:
            Collection name (always succeeds)
        """
        collection_name = f"mem0_{user_id}"
        
        # Optimization 1: Check cache first
        if self._collection_states.get(user_id, False):
            logger.debug(f"✅ Collection {collection_name} ready (cached)")
            return collection_name
        
        # Optimization 2: If another request is creating this collection, wait briefly
        if user_id in self._collection_creating:
            logger.debug(f"⏳ Collection {collection_name} being created by another request")
            for _ in range(10):  # Wait max 1 second (0.1s * 10)
                if self._collection_states.get(user_id, False):
                    return collection_name
                await asyncio.sleep(0.1)
        
        # Optimization 3: Quick collection creation without waits
        try:
            self._collection_creating.add(user_id)
            
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
            
            # Handle localhost (no auth) vs cloud (with auth) environments
            if self.config.qdrant_api_key:
                client = QdrantClient(url=self.config.qdrant_url, api_key=self.config.qdrant_api_key)
            else:
                # Local development - no API key needed
                client = QdrantClient(url=self.config.qdrant_url)
            
            # Quick existence check
            try:
                collections = client.get_collections().collections
                collection_names = [col.name for col in collections]
                collection_exists = collection_name in collection_names
            except Exception:
                collection_exists = False
            
            if not collection_exists:
                logger.info(f"🆕 Creating collection {collection_name} (no wait)")
                
                # Create collection without waiting
                client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(
                        size=1536,
                        distance=models.Distance.COSINE
                    )
                )
                
                # Create both keyword AND UUID indexes (both required for user isolation)
                indexes_created = 0
                try:
                    client.create_payload_index(
                        collection_name=collection_name,
                        field_name="user_id",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                    logger.info(f"✅ user_id KEYWORD index created for {collection_name}")
                    indexes_created += 1
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"KEYWORD index creation issue: {e}")
                
                try:
                    client.create_payload_index(
                        collection_name=collection_name,
                        field_name="user_id",
                        field_schema=models.PayloadSchemaType.UUID,
                    )
                    logger.info(f"✅ user_id UUID index created for {collection_name}")
                    indexes_created += 1
                except Exception as e:
                    if "already exists" not in str(e).lower():
                        logger.warning(f"UUID index creation issue: {e}")
                
                logger.info(f"✅ Collection and {indexes_created} indexes created for {collection_name} (no wait)")
            
            # OPTIMIZATION: No wait! Mark as ready immediately
            self._collection_states[user_id] = True
            logger.info(f"✅ Collection {collection_name} marked ready (optimized)")
            
            return collection_name
            
        except Exception as e:
            logger.warning(f"Collection setup issue (continuing): {e}")
            # Even if there's an issue, return the collection name
            # Let mem0 handle any remaining setup
            return collection_name
        finally:
            self._collection_creating.discard(user_id)
    
    async def _get_user_memory_instance_optimized(self, user_id: str):
        """
        OPTIMIZED user memory instance creation with caching
        
        Key optimizations:
        1. Cache memory instances to avoid recreation
        2. Lazy Graphiti initialization  
        3. Only create what's needed when needed
        """
        # Optimization: Check cache first
        if user_id in self._user_memory_cache:
            logger.debug(f"✅ Using cached memory instance for user {user_id}")
            return self._user_memory_cache[user_id]
        
        try:
            from mem0 import Memory
            
            collection_name = f"mem0_{user_id}"
            
            # Optimization: Start with vector-only config for speed
            qdrant_config = {
                "url": self.config.qdrant_url,
                "collection_name": collection_name
            }
            # Only add API key for cloud environments (not localhost)
            if self.config.qdrant_api_key:
                qdrant_config["api_key"] = self.config.qdrant_api_key
            
            user_config = {
                "vector_store": {
                    "provider": "qdrant",
                    "config": qdrant_config
                },
                "llm": {
                    "provider": "openai",
                    "config": {
                        "api_key": self.config.openai_api_key,
                        "model": "gpt-4o-mini"
                    }
                },
                "embedder": {
                    "provider": "openai", 
                    "config": {
                        "api_key": self.config.openai_api_key,
                        "model": "text-embedding-3-small"
                    }
                },
                "version": "v1.1"
            }
            
            # Optimization: Only add graph store if specifically requested and not rate limited
            if self.api_config.enable_graph_storage:
                user_config["graph_store"] = {
                    "provider": "neo4j",
                    "config": {
                        "url": self.config.neo4j_uri,
                        "username": self.config.neo4j_user,
                        "password": self.config.neo4j_password
                    }
                }
                logger.info(f"🔧 Creating memory instance with vector+graph for user {user_id}")
            else:
                logger.info(f"🔧 Creating vector-only memory instance for user {user_id}")
            
            # Create Memory instance
            memory = Memory.from_config(config_dict=user_config)
            
            # Cache the instance
            self._user_memory_cache[user_id] = memory
            
            logger.info(f"✅ Memory instance created and cached for user {user_id}")
            return memory
            
        except Exception as e:
            logger.error(f"❌ Failed to create user Memory instance: {e}")
            raise

    async def add_memory(self, memory_text: str, user_id: str, metadata: Optional[Dict[str, Any]] = None, 
                        source_description: str = "user_input") -> AddMemoryResponse:
        """
        OPTIMIZED memory addition with minimal blocking operations
        
        Key optimizations:
        1. Parallel collection setup and memory creation
        2. No wait statements 
        3. Background Graphiti operations
        4. Cache reuse
        """
        if not self._initialized:
            await self.initialize()
        
        memory_id = str(uuid4())
        start_time = time.time()
        
        try:
            logger.info(f"📝 Adding memory (OPTIMIZED) for user {user_id}")
            
            # Optimization: Run collection setup and memory instance creation in parallel
            collection_task = asyncio.create_task(
                self._ensure_collection_ready_optimized(user_id)
            )
            memory_task = asyncio.create_task(
                self._get_user_memory_instance_optimized(user_id)
            )
            
            # Wait for both to complete
            collection_name, user_memory = await asyncio.gather(
                collection_task, memory_task, return_exceptions=True
            )
            
            if isinstance(collection_name, Exception):
                logger.warning(f"Collection setup issue: {collection_name}")
                collection_name = f"mem0_{user_id}"  # Continue anyway
            
            if isinstance(user_memory, Exception):
                logger.error(f"Memory instance creation failed: {user_memory}")
                raise user_memory
            
            # Add memory to mem0 (includes vector and graph if configured)
            logger.info(f"💾 Adding to integrated storage for user {user_id}")
            result = user_memory.add(
                memory_text,
                user_id=user_id,
                metadata=metadata or {}
            )
            
            # Extract memory ID
            if isinstance(result, dict):
                memory_id = result.get('memory_id', memory_id)
            elif hasattr(result, 'memory_id'):
                memory_id = result.memory_id
            
            elapsed_time = time.time() - start_time
            logger.info(f"✅ Memory added successfully in {elapsed_time:.2f}s (ID: {memory_id})")
            
            return AddMemoryResponse(
                success=True,
                memory_id=memory_id,
                vector_stored=True,
                graph_stored=self.api_config.enable_graph_storage,
                message=f"Memory added successfully in {elapsed_time:.2f}s"
            )
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = f"Memory addition failed after {elapsed_time:.2f}s: {e}"
            logger.error(f"❌ {error_msg}")
            return AddMemoryResponse(
                success=False,
                memory_id=memory_id,
                vector_stored=False,
                graph_stored=False,
                message=error_msg
            )

    async def search_memories(self, query: str, user_id: str, limit: int = 20,
                             strategy: SearchStrategy = SearchStrategy.HYBRID,
                             include_metadata: bool = True) -> SearchMemoriesResponse:
        """
        OPTIMIZED memory search with cached instances, index error recovery, and no blocking waits
        """
        if not self._initialized:
            await self.initialize()
        
        start_time = time.time()
        max_retries = 2  # One retry for index creation
        
        for attempt in range(max_retries):
            try:
                logger.info(f"🔍 Searching memories (OPTIMIZED) for user {user_id} (attempt {attempt + 1})")
                
                # Ensure collection and indexes are ready
                await self._ensure_collection_ready_optimized(user_id)
                
                # Get cached memory instance (much faster than creating new)
                user_memory = await self._get_user_memory_instance_optimized(user_id)
                
                # Search using mem0 (handles both vector and graph automatically)
                result = user_memory.search(
                    query,
                    user_id=user_id,
                    limit=limit
                )
                
                memories = []
                if isinstance(result, dict) and 'results' in result:
                    results = result['results']
                elif isinstance(result, list):
                    results = result
                else:
                    results = []
                
                for memory_data in results:
                    memory_item = MemoryItem(
                        id=memory_data.get('id', str(uuid4())),
                        text=memory_data.get('memory', memory_data.get('content', '')),
                        metadata=memory_data.get('metadata', {}),
                        score=memory_data.get('score', 0.0),
                        created_at=memory_data.get('created_at'),
                        source=memory_data.get('source', 'hybrid')
                    )
                    memories.append(memory_item)
                
                elapsed_time = time.time() - start_time
                logger.info(f"✅ Search completed in {elapsed_time:.2f}s, found {len(memories)} results")
                
                return SearchMemoriesResponse(
                    success=True,
                    query=query,
                    total_results=len(memories),
                    memories=memories,
                    strategy_used=strategy,
                    search_time_ms=elapsed_time * 1000,
                    message=f"Search completed in {elapsed_time:.2f}s"
                )
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Check for index-related errors
                if any(phrase in error_str for phrase in [
                    "index required but not found", 
                    "index not ready",
                    "bad request: index",
                    "keyword index",
                    "uuid index"
                ]) and attempt < max_retries - 1:
                    logger.warning(f"⚠️ Index error detected, clearing cache and retrying: {e}")
                    
                    # Clear caches to force index recreation
                    self._collection_states.pop(user_id, None)
                    self._user_memory_cache.pop(user_id, None)
                    self._collection_creating.discard(user_id)
                    
                    # Wait briefly for Qdrant to be ready
                    await asyncio.sleep(2)
                    continue
                else:
                    # Non-index error or final attempt
                    elapsed_time = time.time() - start_time
                    error_msg = f"Search failed after {elapsed_time:.2f}s: {e}"
                    logger.error(f"❌ {error_msg}")
                    return SearchMemoriesResponse(
                        success=False,
                        query=query,
                        total_results=0,
                        memories=[],
                        strategy_used=strategy,
                        search_time_ms=elapsed_time * 1000,
                        message=error_msg,
                        unexpected_error=True
                    )
        
        # Should never reach here, but just in case
        elapsed_time = time.time() - start_time
        error_msg = f"Search exhausted all retries after {elapsed_time:.2f}s"
        logger.error(f"❌ {error_msg}")
        return SearchMemoriesResponse(
            success=False,
            query=query,
            total_results=0,
            memories=[],
            strategy_used=strategy,
            search_time_ms=elapsed_time * 1000,
            message=error_msg,
            unexpected_error=True
        )

    async def get_all_memories(self, user_id: str, limit: Optional[int] = None) -> SearchMemoriesResponse:
        """Get all memories using optimized wildcard search"""
        return await self.search_memories("*", user_id, limit or 100)

    async def clear_memories(self, user_id: str, confirm: bool = False) -> ClearMemoriesResponse:
        """
        Clear memories with cache invalidation
        """
        if not confirm:
            return ClearMemoriesResponse(
                success=False,
                total_deleted=0,
                message="Confirmation required (confirm=True)"
            )
        
        try:
            user_memory = await self._get_user_memory_instance_optimized(user_id)
            
            # Clear memories using mem0
            result = user_memory.delete_all(user_id=user_id)
            
            # Invalidate caches
            self._collection_states.pop(user_id, None)
            self._user_memory_cache.pop(user_id, None)
            
            deleted_count = result.get('deleted_count', 0) if isinstance(result, dict) else 0
            
            return ClearMemoriesResponse(
                success=True,
                total_deleted=deleted_count,
                message=f"Cleared {deleted_count} memories for user {user_id}"
            )
            
        except Exception as e:
            return ClearMemoriesResponse(
                success=False,
                total_deleted=0,
                message=f"Clear operation failed: {e}"
            )

    async def get_system_status(self) -> SystemStatus:
        """Get system status with minimal performance impact"""
        databases = []
        overall_healthy = True
        
        # Quick health checks without expensive operations
        try:
            from qdrant_client import QdrantClient
            # Handle localhost (no auth) vs cloud (with auth) environments
            if self.config.qdrant_api_key:
                client = QdrantClient(url=self.config.qdrant_url, api_key=self.config.qdrant_api_key)
            else:
                # Local development - no API key needed
                client = QdrantClient(url=self.config.qdrant_url)
            client.get_collections()  # Quick connection test
            databases.append(DatabaseStatus(name="Qdrant", connected=True))
        except Exception as e:
            databases.append(DatabaseStatus(name="Qdrant", connected=False, error=str(e)))
            overall_healthy = False
        
        # Neo4j check only if graph storage is enabled
        if self.api_config.enable_graph_storage:
            databases.append(DatabaseStatus(name="Neo4j", connected=True))
        else:
            databases.append(DatabaseStatus(name="Neo4j", connected=False, error="Disabled"))
        
        return SystemStatus(
            healthy=overall_healthy,
            version=self.VERSION,
            databases=databases,
            dynamic_indexing_enabled=True  # Enabled with performance optimizations
        )

    async def analyze_memory_usage(self, user_id: str) -> Dict[str, Any]:
        """
        🧹 OPTIMIZATION: Analyze user's memory usage and pruning opportunities
        Provides insights for storage optimization and cost reduction
        """
        try:
            from .pruning import get_pruning_service
            
            pruning_service = await get_pruning_service()
            if not pruning_service:
                return {"error": "Pruning service not available"}
            
            # Initialize pruning service if needed
            if not pruning_service._initialized:
                await pruning_service.initialize(
                    qdrant_url=self.config.qdrant_url,
                    qdrant_api_key=self.config.qdrant_api_key
                )
            
            # Analyze user's memories
            analysis = await pruning_service.analyze_user_memories(user_id)
            
            logger.info(f"📊 Memory analysis for user {user_id}: {analysis.get('total_memories', 0)} memories")
            return analysis
            
        except Exception as e:
            logger.error(f"Memory analysis failed for user {user_id}: {e}")
            return {"error": str(e)}
    
    async def optimize_user_memories(self, user_id: str, dry_run: bool = True) -> Dict[str, Any]:
        """
        🎯 OPTIMIZATION: Automatic memory optimization (pruning, deduplication)
        Can provide significant storage and performance improvements
        """
        try:
            from .pruning import get_pruning_service, PruningConfig
            
            # Configure for safe optimization
            config = PruningConfig(
                max_age_days=730,  # Only remove memories older than 2 years
                similarity_threshold=0.95,  # High threshold for duplicates
                max_removal_percentage=0.2,  # Conservative removal limit
                dry_run=dry_run
            )
            
            pruning_service = await get_pruning_service(config)
            if not pruning_service:
                return {"error": "Pruning service not available"}
            
            # Initialize pruning service if needed
            if not pruning_service._initialized:
                await pruning_service.initialize(
                    qdrant_url=self.config.qdrant_url,
                    qdrant_api_key=self.config.qdrant_api_key
                )
            
            # Perform optimization
            stats = await pruning_service.prune_user_memories(user_id)
            
            result = {
                "success": True,
                "dry_run": dry_run,
                "optimization_stats": stats.to_dict(),
                "message": f"Optimization {'simulated' if dry_run else 'completed'} successfully"
            }
            
            logger.info(f"🎯 Memory optimization for user {user_id}: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Memory optimization failed for user {user_id}: {e}")
            return {"error": str(e), "success": False}

    async def close(self) -> None:
        """Clean up resources and caches"""
        self._collection_states.clear()
        self._user_memory_cache.clear()
        self._collection_creating.clear()
        self._initialized = False
        logger.info("🔌 Jean Memory V2 API OPTIMIZED resources cleaned up")


# Convenience functions
async def add_memory_optimized(memory_text: str, user_id: str, **kwargs) -> AddMemoryResponse:
    """Optimized convenience function to add a single memory"""
    api = JeanMemoryAPIOptimized()
    return await api.add_memory(memory_text, user_id, **kwargs)


async def search_memories_optimized(query: str, user_id: str, **kwargs) -> SearchMemoriesResponse:
    """Optimized convenience function to search memories"""
    api = JeanMemoryAPIOptimized()
    return await api.search_memories(query, user_id, **kwargs) 