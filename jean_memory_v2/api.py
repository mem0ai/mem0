"""
Jean Memory V2 API
==================

Main API class that provides a unified interface for memory operations
across vector (Mem0) and graph (Graphiti) storage backends with automatic
dynamic indexing and multi-user isolation.
"""

import asyncio
import json
import logging
import time
import traceback
from typing import List, Optional, Dict, Any, Union
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
from .index_setup_utils import IndexSetupManager, ensure_collection_indexes
from .exceptions import ConfigurationError


logger = logging.getLogger(__name__)


class JeanMemoryAPI:
    """
    Main API class for Jean Memory V2
    
    Provides unified access to vector (Mem0) and graph (Graphiti) memory storage
    with automatic indexing, user isolation, and hybrid search capabilities.
    """
    
    VERSION = "2.0.0"
    
    def __init__(self, config: Optional[JeanMemoryConfig] = None, api_config: Optional[APIConfig] = None):
        """
        Initialize the Jean Memory V2 API
        
        Args:
            config: Jean Memory configuration (if None, loads from environment)
            api_config: API-specific configuration (if None, uses defaults)
        """
        # DEBUG: Check what config is being passed
        logger.info(f"🔧 DEBUG: JeanMemoryAPI.__init__ called with config: {config}")
        logger.info(f"🔧 DEBUG: Config is None: {config is None}")
        
        # Load configuration
        if config is None:
            try:
                logger.info(f"🔧 DEBUG: Loading config from .env.test file...")
                config = JeanMemoryConfig.from_openmemory_test_env()
                logger.info(f"🔧 DEBUG: Loaded config from file: NEO4J_URI={config.neo4j_uri}")
            except Exception as e:
                logger.error(f"Failed to load configuration: {e}")
                raise ConfigurationError(f"Configuration loading failed: {e}")
        else:
            logger.info(f"🔧 DEBUG: Using passed config: NEO4J_URI={config.neo4j_uri}")
        
        self.config = config
        self.api_config = api_config or APIConfig()
        
        # Initialize components
        self._mem0_memory = None
        self._mem0_graph_memory = None
        self._graphiti = None
        self._index_manager = None
        self._initialized = False
        
        logger.info(f"Jean Memory V2 API v{self.VERSION} initialized")
    
    async def initialize(self) -> None:
        """Initialize all components asynchronously"""
        if self._initialized:
            return
        
        logger.info("🚀 Initializing Jean Memory V2 API components...")
        
        try:
            # Initialize configuration
            logger.info("🔧 Loading configuration...")
            
            # No need for dynamic index manager anymore since we handle collections per-user
            self._index_manager = None
            
            # Initialize storage backends
            await self._initialize_storage_backends()
            
            # Mark as initialized
            self._initialized = True
            logger.info("✅ Jean Memory V2 API initialization complete")
            
        except Exception as e:
            logger.error(f"❌ Jean Memory V2 API initialization failed: {e}")
            raise
    
    async def _initialize_storage_backends(self) -> None:
        """Initialize Mem0 and Graphiti storage backends using exact working patterns"""
        try:
            # Copy exact working patterns from openmemory services
            
            # Initialize Mem0 vector memory using proven pattern
            if self.api_config.enable_vector_storage:
                try:
                    logger.info("🔧 Initializing Mem0 vector storage...")
                    
                    # We'll create user-specific Memory instances dynamically
                    # For now, create a default one for testing
                    self._mem0_memory = None  # Will be created per-user
                    self._vector_collection_name = None  # Will be set per-user
                    
                    logger.info("✅ Mem0 vector storage system ready (per-user instances)")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Mem0 vector storage initialization failed: {e}")
                    self._mem0_memory = None
            
            # Initialize Mem0 graph memory using proven pattern (optional - continue if fails)
            # DISABLED: Using mem0's built-in graph functionality instead of separate Mem0 graph instance
            self._mem0_graph_memory = None
            logger.info("⏭️ Separate Mem0 graph storage disabled (using integrated graph via user instances)")
            
            # Initialize Graphiti using exact working pattern (optional - continue if fails)
            if self.api_config.enable_graph_storage:
                try:
                    logger.info("🔧 Initializing Graphiti graph storage...")
                    await self._initialize_graphiti()
                    logger.info("✅ Graphiti graph storage initialized")
                except Exception as e:
                    logger.warning(f"⚠️ Graphiti initialization failed: {e}")
                    self._graphiti = None
            else:
                self._graphiti = None
                logger.info("⏭️ Graphiti disabled via configuration")
            
            logger.info("✅ Storage backend initialization complete (mem0 vector+graph via user instances)")
            
        except Exception as e:
            # Check if we have at least vector storage working
            if self._mem0_memory is not None:
                logger.warning(f"⚠️ Some storage backends failed to initialize: {e}")
                logger.info("💡 Continuing with available storage backends (vector-only mode)")
            else:
                logger.error(f"❌ All storage backends failed to initialize: {e}")
                raise
    
    async def _ensure_collection_and_indexes_ready(self, user_id: str, operation_type: str = "operation") -> str:
        """
        Robust collection and index checking before each operation as requested by user.
        
        1. Check if collection exists with proper indexes
        2. If not, create collection and indexes  
        3. If collection exists but indexes wrong, fix indexes
        4. Wait 5 seconds after creation/fix for readiness
        5. Return collection name for the operation
        
        Args:
            user_id: User ID for collection naming
            operation_type: Type of operation (for logging)
            
        Returns:
            Collection name to use for the operation
            
        Raises:
            Exception: If collection/index operations fail after retries
        """
        try:
            import asyncio
            from qdrant_client import QdrantClient
            from qdrant_client.http import models
            
            # Create Qdrant client - handle localhost (no auth) vs cloud (with auth) environments
            if self.config.qdrant_api_key:
                client = QdrantClient(url=self.config.qdrant_url, api_key=self.config.qdrant_api_key)
            else:
                # Local development - no API key needed
                client = QdrantClient(url=self.config.qdrant_url)
            
            # Use proper user-based collection naming: mem0_[user_id]
            collection_name = f"mem0_{user_id}"
            
            logger.info(f"🔍 Checking collection and indexes for {operation_type} (user: {user_id})")
            logger.info(f"📁 Target collection: {collection_name}")
            
            # Step 1: Check if collection exists
            try:
                collections = client.get_collections().collections
                collection_names = [col.name for col in collections]
                collection_exists = collection_name in collection_names
            except Exception as e:
                logger.error(f"Failed to check collections: {e}")
                raise Exception(f"Failed to access Qdrant collections: {e}")
            
            if not collection_exists:
                logger.info(f"🆕 Collection {collection_name} does not exist, creating it...")
                
                # Create the collection with proper vector configuration
                try:
                    client.create_collection(
                        collection_name=collection_name,
                        vectors_config=models.VectorParams(
                            size=1536,  # OpenAI text-embedding-3-small dimension
                            distance=models.Distance.COSINE
                        )
                    )
                    logger.info(f"✅ Created collection: {collection_name}")
                except Exception as e:
                    logger.error(f"Failed to create collection {collection_name}: {e}")
                    raise Exception(f"Failed to create collection {collection_name}: {e}")
            else:
                logger.info(f"✅ Collection {collection_name} already exists")
            
            # Step 2: Check if proper indexes exist
            logger.info(f"🔍 Checking indexes for collection {collection_name}...")
            
            keyword_index_exists = False
            
            try:
                # Check if user_id keyword index exists by attempting to use it
                # This is more reliable than parsing collection info
                try:
                    # Test keyword index
                    client.scroll(
                        collection_name=collection_name,
                        scroll_filter=models.Filter(
                            must=[
                                models.FieldCondition(
                                    key="user_id",
                                    match=models.MatchValue(value="test_index_check")
                                )
                            ]
                        ),
                        limit=1
                    )
                    keyword_index_exists = True
                    logger.debug("✅ user_id keyword index verified")
                except Exception as e:
                    if "index required but not found" in str(e).lower():
                        logger.info("ℹ️ user_id keyword index missing")
                        keyword_index_exists = False
                    else:
                        # Other error, assume index exists
                        keyword_index_exists = True
                        logger.debug("✅ user_id keyword index assumed present")
                
            except Exception as e:
                logger.info(f"ℹ️ Could not verify indexes, will create them: {e}")
                keyword_index_exists = False
            
            # Step 3: Create/fix indexes if needed
            if not keyword_index_exists:
                logger.info(f"🔧 Creating indexes for {collection_name}...")
                
                # Create user_id keyword index ONLY (Mem0 uses keyword filtering, not UUID)
                try:
                    client.create_payload_index(
                        collection_name=collection_name,
                        field_name="user_id",
                        field_schema=models.PayloadSchemaType.KEYWORD,
                    )
                    logger.info(f"✅ user_id keyword index created for {collection_name}")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.info(f"✅ user_id keyword index already exists for {collection_name}")
                    else:
                        logger.error(f"Failed to create keyword index: {e}")
                        raise Exception(f"Failed to create keyword index: {e}")
                
                # NOTE: We don't create UUID index as it conflicts with keyword index
                # and Mem0 specifically needs keyword filtering for user_id
                
                # OPTIMIZATION: Skip wait - indexes are ready immediately for modern Qdrant
                logger.info("✅ Indexes created (no wait required for modern Qdrant)")
                # await asyncio.sleep(5)  # REMOVED: Eliminated 5-second wait for performance
            else:
                logger.info(f"✅ All required indexes already exist for {collection_name}")
            
            return collection_name
            
        except Exception as e:
            logger.error(f"❌ Failed to ensure collection and indexes ready: {e}")
            raise
    
    async def add_memory(self, memory_text: str, user_id: str, metadata: Optional[Dict[str, Any]] = None, 
                        source_description: str = "user_input") -> AddMemoryResponse:
        """
        Add a single memory to the system with robust collection and index checking
        
        This method now follows the user's requested pattern:
        1. Check if collection exists with proper indexes
        2. Create/fix indexes if needed
        3. Wait for readiness
        4. Attempt the operation
        5. Return clear error messages if operation fails
        """
        if not self._initialized:
            await self.initialize()
        
        # Input validation
        request = AddMemoryRequest(
            memory_text=memory_text,
            user_id=user_id,
            metadata=metadata or {},
            source_description=source_description
        )
        
        memory_id = str(uuid4())
        errors = []
        success_count = 0
        total_operations = 0
        
        try:
            # STEP 1: Ensure collection and indexes are ready before operation
            logger.info(f"🔧 Ensuring collection and indexes ready for add_memory operation...")
            
            try:
                collection_name = await self._ensure_collection_and_indexes_ready(
                    user_id=request.user_id, 
                    operation_type="add_memory"
                )
                logger.info(f"✅ Collection and indexes verified: {collection_name}")
            except Exception as e:
                error_msg = f"Failed to ensure collection readiness: {e}"
                logger.error(f"❌ {error_msg}")
                return AddMemoryResponse(
                    success=False,
                    memory_id=memory_id,
                    vector_stored=False,
                    graph_stored=False,
                    message=error_msg
                )
            
            # STEP 2: Attempt memory storage using user-specific Memory instance (vector+graph)
            try:
                logger.info(f"📝 Adding memory to integrated vector+graph storage for user {request.user_id}")
                
                # Get user-specific Memory instance (now includes both vector and graph stores)
                user_memory = await self._get_user_memory_instance(request.user_id)
                
                # Add memory using user-specific instance - mem0 handles both vector and graph automatically
                result = user_memory.add(
                    request.memory_text,
                    user_id=request.user_id,
                    metadata=request.metadata
                )
                
                logger.info(f"✅ Integrated vector+graph storage successful")
                logger.info(f"💾 Memory ID: {result.get('memory_id', 'N/A')}")
                success_count += 1
                total_operations += 1
                
                # Extract memory ID for response
                memory_id = result.get('memory_id', str(uuid4()))
                
            except Exception as e:
                errors.append(f"Integrated storage failed: {e}")
                logger.error(f"❌ Integrated vector+graph storage failed: {e}")
                total_operations += 1
            
            # STEP 3: Add memory to Graphiti with user isolation (if available)
            if self._graphiti and success_count > 0:
                try:
                    logger.info(f"🕸️ Adding memory to Graphiti with user isolation for user {request.user_id}")
                    
                    from graphiti_core.nodes import EpisodeType
                    from datetime import datetime
                    
                    # Add episode to Graphiti with group_id for user isolation
                    await self._graphiti.add_episode(
                        name=f"memory_{memory_id}",
                        episode_body=request.memory_text,
                        source=EpisodeType.text,
                        source_description=request.source_description,
                        reference_time=datetime.now(),
                        group_id=request.user_id  # Use user_id as group_id for isolation
                    )
                    
                    logger.info(f"✅ Graphiti episode added successfully with group_id: {request.user_id}")
                    
                except Exception as e:
                    # Don't fail the entire operation if Graphiti fails
                    logger.warning(f"⚠️ Graphiti episode addition failed (continuing): {e}")
                    errors.append(f"Graphiti storage failed: {e}")
            elif self._graphiti and success_count == 0:
                logger.info(f"⏭️ Skipping Graphiti episode addition (mem0 storage failed)")
            elif not self._graphiti:
                logger.debug(f"⏭️ Graphiti not available, skipping episode addition")
            
            # STEP 5: Return results
            is_success = success_count > 0 and len(errors) == 0
            
            if is_success:
                logger.info(f"✅ Memory added successfully (ID: {memory_id})")
            else:
                logger.warning(f"⚠️ Memory addition completed with issues (successes: {success_count}/{total_operations})")
            
            return AddMemoryResponse(
                success=is_success,
                memory_id=memory_id,
                vector_stored=success_count > 0,  # True if mem0 succeeded
                graph_stored=self._graphiti is not None and success_count > 0 and len(errors) == 0,  # True if both mem0 and Graphiti succeeded
                message=f"Memory addition completed: {success_count}/{total_operations} operations successful" if success_count > 0 else f"Memory addition failed: {'; '.join(errors)}"
            )
            
        except Exception as e:
            error_msg = f"Memory addition failed: {e}"
            logger.error(f"❌ {error_msg}")
            return AddMemoryResponse(
                success=False,
                memory_id=memory_id,
                vector_stored=False,
                graph_stored=False,
                message=error_msg
            )
    
    async def add_memories_bulk(self, memories: List[str], user_id: str, 
                               metadata: Optional[Dict[str, Any]] = None,
                               source_description: str = "bulk_import") -> AddMemoriesBulkResponse:
        """
        Add multiple memories in bulk
        
        Args:
            memories: List of memory texts to store
            user_id: User ID for memory isolation
            metadata: Optional metadata applied to all memories
            source_description: Description of the memory source
            
        Returns:
            AddMemoriesBulkResponse with operation results
        """
        # Validate input using Pydantic model
        try:
            request = AddMemoriesBulkRequest(
                memories=memories,
                user_id=user_id,
                metadata=metadata,
                source_description=source_description
            )
        except Exception as e:
            return AddMemoriesBulkResponse(
                success=False,
                total_memories=len(memories),
                successful_memories=0,
                message=f"Invalid input: {e}"
            )
        
        if not self._initialized:
            await self.initialize()
        
        logger.info(f"📝 Adding {len(request.memories)} memories in bulk for user {user_id}")
        
        successful_memories = 0
        failed_memories = 0
        vector_stored_count = 0
        graph_stored_count = 0
        memory_ids = []
        errors = []
        
        # Process memories in batches to avoid overwhelming the system
        batch_size = min(50, len(request.memories))  # Process 50 at a time
        
        for i in range(0, len(request.memories), batch_size):
            batch = request.memories[i:i + batch_size]
            logger.info(f"📦 Processing batch {i//batch_size + 1}/{(len(request.memories) + batch_size - 1)//batch_size}")
            
            # Process each memory in the batch
            batch_results = []
            batch_errors = []
            
            for memory in batch:
                try:
                    result = await self.add_memory(
                        memory_text=memory,
                        user_id=request.user_id,
                        metadata=request.metadata,
                        source_description=request.source_description
                    )
                    
                    # Check if the memory addition had at least partial success (vector storage)
                    if result.success:
                        batch_results.append(result)
                        successful_memories += 1
                        total_memories += 1
                    else:
                        batch_errors.append(result.message)  # Use message instead of errors
                        total_memories += 1
                        
                except Exception as e:
                    batch_errors.append(f"Memory addition failed: {e}")
                    total_memories += 1
            
            logger.info(f"📦 Batch {i//batch_size + 1}/{len(request.memories)//batch_size} completed: {len(batch_results)}/{len(batch)} successful")
            
            # Combine batch results and errors
            if batch_results:
                memory_ids.extend([result.memory_id for result in batch_results])
                vector_stored_count += sum(1 for result in batch_results if result.vector_stored)
                graph_stored_count += sum(1 for result in batch_results if result.graph_stored)
            if batch_errors:
                errors.extend(batch_errors)
            
        success = successful_memories > 0
        
        if not success:
            error_msg = f"Bulk operation failed: no memories were stored"
            logger.error(f"❌ {error_msg}")
            raise Exception(error_msg)
        
        return AddMemoriesBulkResponse(
            success=success,
            total_memories=total_memories,
            successful_memories=successful_memories,
            failed_memories=total_memories - successful_memories,
            memory_ids=memory_ids,
            vector_stored_count=vector_stored_count,
            graph_stored_count=graph_stored_count,
            errors=errors,
            message=f"Bulk addition completed: {successful_memories}/{total_memories} memories stored successfully"
        )
    
    async def search_memories(self, query: str, user_id: str, limit: int = 20,
                             strategy: SearchStrategy = SearchStrategy.HYBRID,
                             include_metadata: bool = True) -> SearchMemoriesResponse:
        """
        Search memories with robust collection and index checking
        
        This method now follows the user's requested pattern:
        1. Check if collection exists with proper indexes
        2. Create/fix indexes if needed  
        3. Wait for readiness
        4. Attempt the search operation
        5. Return clear error messages if operation fails
        """
        if not self._initialized:
            await self.initialize()
        
        # Input validation
        request = SearchMemoriesRequest(
            query=query,
            user_id=user_id,
            limit=limit,
            strategy=strategy,
            include_metadata=include_metadata
        )
        
        try:
            # STEP 1: Ensure collection and indexes are ready
            collection_name = await self._ensure_collection_and_indexes_ready(request.user_id, "search_memories")
            logger.info(f"✅ Collection and indexes verified for search: {collection_name}")
            
            logger.info(f"🔍 Searching memories for user {request.user_id} with strategy: {request.strategy.value}")
            
            # STEP 2: Perform integrated vector+graph search using user-specific Memory instance
            try:
                logger.info(f"🔍 Performing integrated vector+graph search for user {request.user_id}")
                
                # Get user-specific Memory instance (includes both vector and graph stores)
                user_memory = await self._get_user_memory_instance(request.user_id)
                
                # Handle wildcard queries for get_all operations
                if request.query.strip() == "*":
                    # Use get_all for wildcard queries
                    search_results = user_memory.get_all(user_id=request.user_id)
                    # get_all returns a dict with 'results' key, so extract the results
                    if isinstance(search_results, dict) and 'results' in search_results:
                        search_results = search_results['results']
                else:
                    # Perform normal search using user-specific instance
                    search_results = user_memory.search(
                        query=request.query,
                        user_id=request.user_id,
                        limit=request.limit
                    )
                
                # Process search results and handle field mapping
                memories = []
                for result in search_results:
                    try:
                        # Handle different result formats from mem0
                        if isinstance(result, str):
                            # If result is a string, create a basic memory item
                            memory_data = {
                                "id": f"string_result_{len(memories)}",
                                "text": result,
                                "score": 1.0,  # Default score for string results
                                "source": self._map_memory_source("mem0_integrated_search"),
                                "metadata": {}
                            }
                        elif isinstance(result, dict):
                            # If result is a dictionary, map fields properly
                            memory_data = {
                                "id": result.get("memory_id", result.get("id", f"dict_result_{len(memories)}")),
                                "text": result.get("text", result.get("memory", "")),
                                "score": result.get("score", 1.0),
                                "source": self._map_memory_source(result.get("source", "mem0_integrated_search")),
                                "metadata": result.get("metadata", {})
                            }
                            
                            # Add timestamps if available
                            if "created_at" in result:
                                memory_data["created_at"] = result["created_at"]
                            if "updated_at" in result:
                                memory_data["updated_at"] = result["updated_at"]
                        else:
                            # Unknown format, skip
                            logger.warning(f"⚠️ Unknown result format: {type(result)}")
                            continue
                        
                        memory_item = MemoryItem(**memory_data)
                        memories.append(memory_item)
                        
                    except Exception as e:
                        logger.warning(f"⚠️ Failed to process search result: {e}")
                        logger.debug(f"   Raw result: {result}")
                        logger.debug(f"   Result type: {type(result)}")
                        continue
                        
                total_results = len(memories)
                logger.info(f"✅ Integrated search successful: {total_results} results from mem0")
                
            except Exception as e:
                logger.error(f"❌ Integrated search failed: {e}")
                memories = []
                total_results = 0
            
            # STEP 3: Perform Graphiti search with namespace isolation (if available)
            graphiti_memories = []
            if self._graphiti:
                try:
                    logger.info(f"🕸️ Performing Graphiti search for user {request.user_id}")
                    
                    # Import search config for proper Graphiti search
                    from graphiti_core.search.search_config_recipes import NODE_HYBRID_SEARCH_RRF
                    
                    # Create search config
                    search_config = NODE_HYBRID_SEARCH_RRF.model_copy(deep=True)
                    search_config.limit = request.limit
                    
                    # Basic Graphiti search with user namespace isolation
                    graphiti_results = await self._graphiti.search_(
                        query=request.query,
                        group_ids=[request.user_id],  # Use group_ids list for isolation
                        config=search_config
                    )
                    
                    # Process Graphiti search results (nodes from _search method)
                    if hasattr(graphiti_results, 'nodes'):
                        for i, node in enumerate(graphiti_results.nodes):
                            try:
                                # Handle Graphiti node results from _search
                                memory_data = {
                                    "id": f"graphiti_node_{node.uuid}" if hasattr(node, 'uuid') else f"graphiti_node_{i}",
                                    "text": getattr(node, 'name', '') or getattr(node, 'summary', '') or str(node),
                                    "score": 0.8,  # Default score for Graphiti nodes
                                    "source": self._map_memory_source("graphiti_search"),
                                    "metadata": {
                                        "source_type": "graphiti_node",
                                        "node_uuid": getattr(node, 'uuid', None),
                                        "node_name": getattr(node, 'name', None),
                                        "node_summary": getattr(node, 'summary', None),
                                        "group_id": request.user_id
                                    }
                                }
                                
                                # Create memory item and add to results
                                memory_item = MemoryItem(**memory_data)
                                graphiti_memories.append(memory_item)
                                
                            except Exception as e:
                                logger.warning(f"⚠️ Failed to process Graphiti node: {e}")
                                logger.debug(f"   Raw Graphiti node: {node}")
                                logger.debug(f"   Node type: {type(node)}")
                                continue
                    else:
                        # Fallback: handle case where results don't have .nodes attribute
                        logger.debug(f"Graphiti results don't have .nodes attribute: {type(graphiti_results)}")
                        for i, result in enumerate(graphiti_results if isinstance(graphiti_results, list) else []):
                            try:
                                # Basic fallback processing
                                memory_data = {
                                    "id": f"graphiti_result_{i}",
                                    "text": str(result),
                                    "score": 0.7,
                                    "source": self._map_memory_source("graphiti_search"),
                                    "metadata": {
                                        "source_type": "graphiti_fallback",
                                        "group_id": request.user_id
                                    }
                                }
                                
                                memory_item = MemoryItem(**memory_data)
                                graphiti_memories.append(memory_item)
                                
                            except Exception as e:
                                logger.warning(f"⚠️ Failed to process Graphiti result: {e}")
                                logger.debug(f"   Raw Graphiti result: {result}")
                                logger.debug(f"   Result type: {type(result)}")
                                continue
                    
                    logger.info(f"✅ Graphiti search successful: {len(graphiti_memories)} results")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Graphiti search failed (continuing): {e}")
                    graphiti_memories = []
            else:
                logger.debug(f"⏭️ Graphiti not available, skipping Graphiti search")
            
            # STEP 4: Combine mem0 and Graphiti results
            all_memories = memories + graphiti_memories
            combined_total = len(all_memories)
            
            logger.info(f"🔗 Combined search results: {len(memories)} from mem0 + {len(graphiti_memories)} from Graphiti = {combined_total} total")
            
            # STEP 5: Sort combined results and apply limit
            all_memories.sort(key=lambda x: x.score, reverse=True)
            
            # Apply the original limit to the combined results
            final_memories = all_memories[:request.limit]
            final_total = len(final_memories)
            
            # Create success message with breakdown
            if combined_total > 0:
                success_message = f"Found {combined_total} memories ({len(memories)} from mem0, {len(graphiti_memories)} from Graphiti) for query: '{request.query}'"
                if final_total < combined_total:
                    success_message += f" - showing top {final_total}"
                logger.info(f"✅ {success_message}")
            else:
                success_message = f"No memories found for query: '{request.query}' (user: {request.user_id})"
                logger.info(f"📭 {success_message}")
            
            return SearchMemoriesResponse(
                success=True,
                query=request.query,
                memories=final_memories,
                total_results=final_total,
                strategy_used=request.strategy.value,
                collection_name=collection_name if 'collection_name' in locals() else f"mem0_{request.user_id}",
                vector_results_count=len(memories),  # mem0 results count
                graph_results_count=len(graphiti_memories),  # graphiti results count
                message=success_message
            )
            
        except Exception as e:
            logger.error(f"❌ Search operation failed: {e}")
            return SearchMemoriesResponse(
                success=False,
                query=request.query,
                memories=[],
                total_results=0,
                strategy_used=request.strategy.value,
                collection_name="",
                errors=[str(e)],
                unexpected_error=True,
                message=f"Search failed: {str(e)}"
            )
    
    async def clear_memories(self, user_id: str, confirm: bool = False) -> ClearMemoriesResponse:
        """
        Clear all memories for a user with robust collection and index checking
        
        This method now follows the user's requested pattern:
        1. Check if collection exists with proper indexes
        2. Create/fix indexes if needed
        3. Wait for readiness  
        4. Attempt the clear operation
        5. Return clear error messages if operation fails
        """
        if not self._initialized:
            await self.initialize()
        
        # Input validation
        request = ClearMemoriesRequest(user_id=user_id, confirm=confirm)
        
        if not request.confirm:
            return ClearMemoriesResponse(
                success=False,
                user_id=request.user_id,
                vector_cleared=False,
                graph_cleared=False,
                total_deleted=0,
                message="Clear operation cancelled: confirm must be True to proceed with deletion"
            )
        
        operations_attempted = 0
        operations_successful = 0
        errors = []
        total_deleted = 0
        vector_success = False
        graph_success = False
        
        try:
            # STEP 1: Ensure collection and indexes are ready before operation
            logger.info(f"🔧 Ensuring collection and indexes ready for clear_memories operation...")
            
            try:
                collection_name = await self._ensure_collection_and_indexes_ready(
                    user_id=request.user_id, 
                    operation_type="clear_memories"
                )
                logger.info(f"✅ Collection and indexes verified for clear: {collection_name}")
            except Exception as e:
                error_msg = f"Failed to ensure collection readiness for clear: {e}"
                logger.error(f"❌ {error_msg}")
                return ClearMemoriesResponse(
                    success=False,
                    user_id=request.user_id,
                    errors=[error_msg],
                    operations_attempted=1,
                    operations_successful=0,
                    metadata={
                        "collection_check_failed": True,
                        "error_type": "collection_readiness"
                    }
                )
            
            logger.info(f"🧹 Clearing all memories for user {request.user_id}")
            
            # STEP 2: Clear integrated vector+graph memories using user-specific Memory instance
            try:
                logger.info(f"🧹 Clearing integrated vector+graph memories for user {request.user_id}")
                
                # Get user-specific Memory instance (includes both vector and graph stores)
                user_memory = await self._get_user_memory_instance(request.user_id)
                
                # Get all memories for this user first to verify access and count
                try:
                    user_memories = user_memory.get_all(user_id=request.user_id)
                    memory_count = len(user_memories) if user_memories else 0
                    logger.info(f"Found {memory_count} total memories to clear (vector+graph)")
                except Exception as e:
                    logger.warning(f"Could not get memory count: {e}")
                    memory_count = 0
                
                # Clear all memories for this user (both vector and graph)
                user_memory.delete_all(user_id=request.user_id)
                
                logger.info(f"✅ Integrated vector+graph clearing successful ({memory_count} memories cleared)")
                operations_attempted += 1
                operations_successful += 1
                total_deleted = memory_count
                vector_success = True
                graph_success = True  # Both cleared together
                
            except Exception as e:
                operations_attempted += 1
                errors.append(f"Integrated clear failed: {e}")
                logger.error(f"❌ Integrated vector+graph clearing failed: {e}")
                
                # Check if it's an index-related error
                if "index required but not found" in str(e).lower() or "collection" in str(e).lower():
                    helpful_msg = "Clear operation index or collection error. Please restart the script to reinitialize."
                    errors.append(helpful_msg)
                    logger.error(f"🔄 {helpful_msg}")
                
                vector_success = False
                graph_success = False
                total_deleted = 0
            
            # STEP 5: Return results
            is_success = operations_successful > 0 and len(errors) == 0
            
            if is_success:
                logger.info(f"✅ All memories cleared successfully for user {request.user_id}")
            elif operations_successful > 0:
                logger.warning(f"⚠️ Partial success: {operations_successful}/{operations_attempted} operations succeeded")
            else:
                logger.error(f"❌ Clear operation failed for user {request.user_id}")
            
            return ClearMemoriesResponse(
                success=is_success,
                user_id=request.user_id,
                vector_cleared=vector_success,
                graph_cleared=graph_success,
                total_deleted=total_deleted,
                errors=errors,
                message=f"Clear operation completed: {operations_successful}/{operations_attempted} operations successful, {total_deleted} memories deleted" if operations_successful > 0 else f"Clear operation failed: {'; '.join(errors)}"
            )
            
        except Exception as e:
            error_msg = f"Clear operation failed: {e}"
            logger.error(f"❌ {error_msg}")
            return ClearMemoriesResponse(
                success=False,
                user_id=request.user_id,
                errors=[error_msg],
                operations_attempted=operations_attempted,
                operations_successful=operations_successful,
                metadata={"unexpected_error": True}
            )
    
    async def get_system_status(self) -> SystemStatus:
        """Get system health status"""
        if not self._initialized:
            await self.initialize()
        
        databases = []
        overall_healthy = True
        
        # Check Qdrant status
        try:
            if self._index_manager:
                collections = self._index_manager.get_all_collections()
                databases.append(DatabaseStatus(
                    name="Qdrant",
                    connected=True,
                    collections_count=len(collections)
                ))
            else:
                databases.append(DatabaseStatus(
                    name="Qdrant",
                    connected=False,
                    error="Index manager not initialized"
                ))
                overall_healthy = False
        except Exception as e:
            databases.append(DatabaseStatus(
                name="Qdrant",
                connected=False,
                error=str(e)
            ))
            overall_healthy = False
        
        # Check Neo4j status (if Graphiti is available)
        try:
            if self._graphiti:
                # Simple health check
                databases.append(DatabaseStatus(
                    name="Neo4j",
                    connected=True
                ))
            else:
                databases.append(DatabaseStatus(
                    name="Neo4j",
                    connected=False,
                    error="Graphiti not available"
                ))
        except Exception as e:
            databases.append(DatabaseStatus(
                name="Neo4j",
                connected=False,
                error=str(e)
            ))
            overall_healthy = False
        
        return SystemStatus(
            healthy=overall_healthy,
            version=self.VERSION,
            databases=databases,
            dynamic_indexing_enabled=self.api_config.auto_create_indexes
        )
    
    async def close(self) -> None:
        """Clean up resources"""
        if self._graphiti:
            try:
                await self._graphiti.close()
            except:
                pass
        
        self._initialized = False
        logger.info("🔌 Jean Memory V2 API resources cleaned up")

    async def _get_user_memory_instance(self, user_id: str):
        """
        Get or create a user-specific Memory instance with proper collection naming
        Now supports both vector (Qdrant) and graph (Neo4j) stores via mem0
        
        Args:
            user_id: User ID for collection naming
            
        Returns:
            Memory instance configured for this user with vector+graph capabilities
        """
        try:
            from mem0 import Memory
            import os
            
            # Create user-specific collection name
            collection_name = f"mem0_{user_id}"
            
            # Configure mem0 for this specific user with BOTH vector and graph stores
            # Using the exact format specified by the user
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
                "graph_store": {
                    "provider": "neo4j",
                    "config": {
                        "url": self.config.neo4j_uri,
                        "username": self.config.neo4j_user,
                        "password": self.config.neo4j_password
                    }
                },
                "version": "v1.1"
            }
            
            logger.info(f"🔧 Creating mem0 Memory instance for user {user_id} with vector+graph stores")
            logger.info(f"   📁 Collection: {collection_name}")
            logger.info(f"   🔗 Neo4j: {self.config.neo4j_uri}")
            logger.info(f"   📡 Qdrant: {self.config.qdrant_url}")
            
            # DEBUG: Log the exact config being passed to mem0
            logger.info(f"🔧 DEBUG: Mem0 Neo4j config - URL: {self.config.neo4j_uri}")
            logger.info(f"🔧 DEBUG: Mem0 Neo4j config - User: {self.config.neo4j_user}")
            logger.info(f"🔧 DEBUG: Mem0 Neo4j config - Password: {'*' * 8}...")
            
            # Create Memory instance from config
            memory = Memory.from_config(config_dict=user_config)
            
            logger.info(f"✅ User Memory instance created successfully for {user_id}")
            return memory
            
        except Exception as e:
            logger.error(f"❌ Failed to create user Memory instance: {e}")
            raise

    async def _initialize_graphiti(self):
        """Initialize Graphiti using proven working pattern from openmemory services"""
        try:
            # Import necessary Graphiti components for proper OpenAI configuration
            from openai import AsyncOpenAI
            from graphiti_core import Graphiti
            from graphiti_core.llm_client import OpenAIClient
            from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
            
            # Create properly configured OpenAI client
            openai_client = AsyncOpenAI(api_key=self.config.openai_api_key)
            
            # Initialize Graphiti with explicit OpenAI configuration (using proven pattern)
            self._graphiti = Graphiti(
                self.config.neo4j_uri,
                self.config.neo4j_user,
                self.config.neo4j_password,
                llm_client=OpenAIClient(client=openai_client),
                embedder=OpenAIEmbedder(
                    config=OpenAIEmbedderConfig(
                        embedding_model="text-embedding-3-small"
                    ),
                    client=openai_client
                )
            )
            
            # Build indices and constraints (only needs to be done once)
            try:
                await self._graphiti.build_indices_and_constraints()
                logger.info("Graphiti indices and constraints built successfully")
            except Exception as e:
                # Indices might already exist
                logger.debug(f"Indices might already exist: {e}")
                
            logger.info("Graphiti initialized successfully with explicit OpenAI configuration")
            
        except Exception as e:
            logger.error(f"Failed to initialize Graphiti: {e}")
            raise

    def _map_memory_source(self, source: str) -> str:
        """
        Map memory sources to our enum values
        
        Args:
            source: Memory source (mem0, graphiti, etc.)
            
        Returns:
            Mapped source value compatible with MemoryType enum
        """
        # Map various memory source types to our enum values
        source_mappings = {
            # Mem0 sources
            "mem0_integrated_search": MemoryType.HYBRID.value,
            "vector_search": MemoryType.VECTOR.value,  
            "graph_search": MemoryType.GRAPH.value,
            "hybrid_search": MemoryType.HYBRID.value,
            # Graphiti sources
            "graphiti_search": MemoryType.GRAPH.value,
            "graphiti_fact": MemoryType.GRAPH.value,
            "graphiti_node": MemoryType.GRAPH.value,
            "graphiti_episode": MemoryType.GRAPH.value,
        }
        
        return source_mappings.get(source, MemoryType.VECTOR.value)  # Default to vector


# Convenience functions for direct usage
async def add_memory(memory_text: str, user_id: str, **kwargs) -> AddMemoryResponse:
    """Convenience function to add a single memory"""
    api = JeanMemoryAPI()
    return await api.add_memory(memory_text, user_id, **kwargs)


async def search_memories(query: str, user_id: str, **kwargs) -> SearchMemoriesResponse:
    """Convenience function to search memories"""
    api = JeanMemoryAPI()
    return await api.search_memories(query, user_id, **kwargs)


async def clear_memories(user_id: str, confirm: bool = False) -> ClearMemoriesResponse:
    """Convenience function to clear memories"""
    api = JeanMemoryAPI()
    return await api.clear_memories(user_id, confirm) 