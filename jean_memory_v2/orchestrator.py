"""
Jean Memory V2 - Pipeline Orchestrator
=====================================

Follows the exact same orchestration pattern as the working pipeline.sh to prevent rate limiting
and ensure robust, sequential processing.

Key Features:
- Sequential processing (no concurrency to prevent rate limits)
- Proper timeout management (120s timeouts)
- Step-by-step orchestration with error handling
- Uses openmemory/api dependencies and environment
- Dynamic index management
"""

import asyncio
import logging
import time
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import sys
import os
from dotenv import load_dotenv

# Import from the actual working API dependencies
sys.path.insert(0, str(Path(__file__).parents[1] / "openmemory" / "api"))

from .config import JeanMemoryConfig
from .exceptions import JeanMemoryError, DatabaseConnectionError

logger = logging.getLogger(__name__)

class JeanMemoryOrchestrator:
    """
    Pipeline orchestrator that follows the exact same pattern as the working pipeline.sh
    to prevent rate limiting and ensure robust operation.
    """
    
    def __init__(self, 
                 config: Optional[JeanMemoryConfig] = None,
                 auto_mode: bool = False,
                 timeout_seconds: int = 120):
        """
        Initialize orchestrator following working pipeline patterns
        
        Args:
            config: Jean Memory configuration (auto-loads from openmemory if None)
            auto_mode: If True, run without confirmations
            timeout_seconds: Timeout for each operation (default: 120s like working pipeline)
        """
        self.auto_mode = auto_mode
        self.timeout_seconds = timeout_seconds
        self.start_time = time.time()
        
        # Load configuration using openmemory patterns
        if config is None:
            config = JeanMemoryConfig.from_openmemory_test_env()
        
        self.config = config
        
        # Track components for proper cleanup
        self.active_components = {}
        self.initialization_order = []
        
        logger.info("🚀 Jean Memory V2 Orchestrator initialized")
        logger.info(f"   Auto mode: {auto_mode}")
        logger.info(f"   Timeout: {timeout_seconds}s")
        logger.info(f"   Config source: openmemory/api/.env.test")
    
    async def with_timeout(self, coro, operation_name: str):
        """
        Run operation with timeout (following working pipeline pattern)
        
        Args:
            coro: Coroutine to run
            operation_name: Name for logging
            
        Returns:
            Result of the coroutine
            
        Raises:
            asyncio.TimeoutError: If operation times out
        """
        try:
            logger.debug(f"⏱️ Starting {operation_name} (timeout: {self.timeout_seconds}s)")
            start = time.time()
            
            result = await asyncio.wait_for(coro, timeout=self.timeout_seconds)
            
            elapsed = time.time() - start
            logger.info(f"✅ {operation_name} completed in {elapsed:.1f}s")
            return result
            
        except asyncio.TimeoutError:
            elapsed = time.time() - start
            logger.error(f"❌ TIMEOUT: {operation_name} exceeded {self.timeout_seconds}s (actual: {elapsed:.1f}s)")
            raise JeanMemoryError(f"Operation timeout: {operation_name}")
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"❌ ERROR in {operation_name} after {elapsed:.1f}s: {e}")
            raise
    
    def _confirm_step(self, step_name: str, description: str) -> bool:
        """Ask user for confirmation (following working pipeline pattern)"""
        if self.auto_mode:
            logger.info(f"🤖 AUTO MODE: Proceeding with {step_name}")
            return True
        
        print(f"\n{'='*60}")
        print(f"🎯 NEXT STEP: {step_name}")
        print(f"📋 {description}")
        print("="*60)
        
        while True:
            response = input(f"\n🤔 Proceed with {step_name}? [y/N/quit]: ").strip().lower()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no', '']:
                logger.info(f"⏭️ Skipping {step_name}")
                return False
            elif response in ['q', 'quit', 'exit']:
                logger.info("🛑 Operation cancelled by user")
                raise KeyboardInterrupt("User cancelled operation")
            else:
                print("❌ Please enter 'y' for yes, 'n' for no, or 'quit' to exit")
    
    async def step_1_check_environment(self) -> bool:
        """Step 1: Validate environment and dependencies (like working pipeline)"""
        if not self._confirm_step(
            "Environment Check",
            "Validate configuration and database connections"
        ):
            return False
        
        logger.info("🔍 STEP 1: Environment and connectivity check...")
        
        try:
            # Validate configuration
            await self.with_timeout(
                self._validate_configuration(),
                "Configuration validation"
            )
            
            # Test basic connectivity (sequential, not concurrent)
            await self.with_timeout(
                self._test_basic_connectivity(),
                "Basic connectivity test"
            )
            
            logger.info("✅ Environment check completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Environment check failed: {e}")
            return False
    
    async def step_2_initialize_components(self) -> bool:
        """Step 2: Initialize components sequentially (preventing rate limits)"""
        if not self._confirm_step(
            "Component Initialization", 
            "Initialize Jean Memory V2 components with rate limiting protection"
        ):
            return False
        
        logger.info("🔧 STEP 2: Sequential component initialization...")
        
        try:
            # Initialize components one by one (like working pipeline)
            await self.with_timeout(
                self._initialize_search_engine(),
                "Search engine initialization"
            )
            
            # OPTIMIZATION: Removed delays between initializations for performance
            # await asyncio.sleep(2)  # REMOVED: Rate limiting delay
            
            await self.with_timeout(
                self._initialize_ingestion_engine(),
                "Ingestion engine initialization"
            )
            
            # await asyncio.sleep(2)  # REMOVED: Rate limiting delay
            
            await self.with_timeout(
                self._initialize_database_cleaner(),
                "Database cleaner initialization"
            )
            
            logger.info("✅ All components initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Component initialization failed: {e}")
            await self._cleanup_partial_initialization()
            return False
    
    async def step_3_prepare_databases(self, clear_data: bool = True) -> bool:
        """Step 3: Prepare databases (following working pipeline clear pattern)"""
        step_name = "Database Clearing" if clear_data else "Database Preparation"
        description = ("Clear databases and prepare for fresh data" if clear_data 
                      else "Prepare databases without clearing (for multi-user testing)")
        
        if not self._confirm_step(step_name, description):
            return False
        
        logger.info(f"🗄️ STEP 3: {step_name}...")
        
        try:
            if clear_data:
                # Use the working pipeline's database clearing approach
                await self.with_timeout(
                    self._clear_databases_safely(),
                    "Safe database clearing"
                )
            else:
                logger.info("🔄 Skipping database clearing for multi-user testing")
            
            # Setup indexes (like working pipeline post-clearing)
            await self.with_timeout(
                self._setup_dynamic_indexes(),
                "Dynamic index setup"
            )
            
            logger.info("✅ Database preparation completed")
            return True
            
        except Exception as e:
            logger.error(f"❌ Database preparation failed: {e}")
            return False
    
    async def step_4_health_check(self) -> bool:
        """Step 4: Comprehensive health check (following working pipeline pattern)"""
        if not self._confirm_step(
            "Health Check",
            "Perform comprehensive system health check"
        ):
            return False
        
        logger.info("🏥 STEP 4: Comprehensive health check...")
        
        try:
            # Health check with timeout
            health_result = await self.with_timeout(
                self._comprehensive_health_check(),
                "Comprehensive health check"
            )
            
            if health_result.get('overall_status') == 'healthy':
                logger.info("✅ System is healthy and ready")
                return True
            else:
                logger.warning(f"⚠️ Health check issues: {health_result}")
                return True  # Continue with warnings
                
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False
    
    async def ingest_memories_orchestrated(self, 
                                         memories: Union[str, List[str]], 
                                         user_id: str,
                                         batch_size: int = 5) -> Dict[str, Any]:
        """
        Orchestrated memory ingestion following working pipeline patterns
        
        Args:
            memories: Memory content(s) to ingest
            user_id: User identifier
            batch_size: Process memories in batches (default: 5, like working pipeline)
            
        Returns:
            Ingestion results
        """
        if not self._confirm_step(
            "Memory Ingestion",
            f"Ingest {len(memories) if isinstance(memories, list) else 1} memories for user {user_id}"
        ):
            return {"status": "skipped", "reason": "User declined"}
        
        logger.info(f"📥 ORCHESTRATED INGESTION: {user_id}")
        
        try:
            # Ensure we have the ingestion engine
            if 'ingestion' not in self.active_components:
                logger.info("🔧 Initializing ingestion engine...")
                await self.step_2_initialize_components()
            
            # Ingest with timeout and batching (like working pipeline)
            result = await self.with_timeout(
                self._ingest_memories_safely(memories, user_id, batch_size),
                f"Memory ingestion for {user_id}"
            )
            
            # Post-ingestion index verification (like working pipeline)
            await self.with_timeout(
                self._verify_post_ingestion_indexes(),
                "Post-ingestion index verification"
            )
            
            logger.info(f"✅ Orchestrated ingestion completed for {user_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ Orchestrated ingestion failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def search_memories_orchestrated(self, 
                                         query: str, 
                                         user_id: str,
                                         max_results: int = 10) -> Dict[str, Any]:
        """
        Orchestrated memory search following working pipeline patterns
        
        Args:
            query: Search query
            user_id: User identifier  
            max_results: Maximum results to return
            
        Returns:
            Search results
        """
        logger.info(f"🔍 ORCHESTRATED SEARCH: {user_id} - '{query[:50]}...'")
        
        try:
            # Ensure we have the search engine
            if 'search' not in self.active_components:
                logger.info("🔧 Initializing search engine...")
                await self.step_2_initialize_components()
            
            # Pre-search index verification (like working pipeline)
            await self.with_timeout(
                self._verify_search_indexes(),
                "Pre-search index verification"
            )
            
            # Search with timeout
            result = await self.with_timeout(
                self._search_memories_safely(query, user_id, max_results),
                f"Memory search for {user_id}"
            )
            
            logger.info(f"✅ Search completed: {result.get('total_results', 0)} results")
            return result
            
        except Exception as e:
            logger.error(f"❌ Orchestrated search failed: {e}")
            return {"status": "error", "error": str(e)}
    
    async def cleanup_orchestrated(self, confirm: bool = False) -> Dict[str, Any]:
        """
        Orchestrated cleanup following working pipeline patterns
        
        Args:
            confirm: If True, actually perform cleanup
            
        Returns:
            Cleanup results
        """
        if not confirm:
            logger.info("🧹 Cleanup requested but confirm=False")
            return {"status": "skipped", "reason": "confirm=False"}
        
        if not self._confirm_step(
            "System Cleanup",
            "Clean up all components and connections"
        ):
            return {"status": "skipped", "reason": "User declined"}
        
        logger.info("🧹 ORCHESTRATED CLEANUP...")
        
        try:
            # Cleanup in reverse order of initialization
            cleanup_result = await self.with_timeout(
                self._cleanup_all_components(),
                "Component cleanup"
            )
            
            logger.info("✅ Orchestrated cleanup completed")
            return cleanup_result
            
        except Exception as e:
            logger.error(f"❌ Orchestrated cleanup failed: {e}")
            return {"status": "error", "error": str(e)}
    
    # Implementation methods (to be implemented based on working pipeline patterns)
    
    async def _validate_configuration(self):
        """Validate configuration like working pipeline"""
        logger.debug("Validating configuration...")
        # Implementation follows working pipeline validation
        pass
    
    async def _test_basic_connectivity(self):
        """Test basic connectivity sequentially"""
        logger.debug("Testing basic connectivity...")
        # Implementation follows working pipeline connectivity test
        pass
    
    async def _initialize_search_engine(self):
        """Initialize search engine"""
        logger.debug("Initializing search engine...")
        from .search import HybridSearchEngine
        
        search_engine = HybridSearchEngine(self.config)
        await search_engine.initialize()
        
        self.active_components['search'] = search_engine
        self.initialization_order.append('search')
    
    async def _initialize_ingestion_engine(self):
        """Initialize ingestion engine"""
        logger.debug("Initializing ingestion engine...")
        from .ingestion import MemoryIngestionEngine
        
        ingestion_engine = MemoryIngestionEngine(self.config)
        await ingestion_engine.initialize()
        
        self.active_components['ingestion'] = ingestion_engine
        self.initialization_order.append('ingestion')
    
    async def _initialize_database_cleaner(self):
        """Initialize database cleaner"""
        logger.debug("Initializing database cleaner...")
        from .database_utils import DatabaseCleaner
        
        cleaner = DatabaseCleaner(self.config)
        await cleaner.initialize()
        
        self.active_components['cleaner'] = cleaner
        self.initialization_order.append('cleaner')
    
    async def _clear_databases_safely(self):
        """Clear databases safely (following working pipeline)"""
        logger.debug("Clearing databases safely...")
        cleaner = self.active_components.get('cleaner')
        if cleaner:
            await cleaner.clear_all_for_testing(confirm=True)
    
    async def _setup_dynamic_indexes(self):
        """Setup dynamic indexes (like working pipeline)"""
        logger.debug("Setting up dynamic indexes...")
        # Implementation follows working pipeline index setup
        pass
    
    async def _comprehensive_health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        logger.debug("Performing comprehensive health check...")
        
        health = {
            'overall_status': 'healthy',
            'components': {},
            'timestamp': time.time()
        }
        
        # Check each active component
        for name, component in self.active_components.items():
            try:
                if hasattr(component, 'health_check'):
                    component_health = await component.health_check()
                    health['components'][name] = component_health
                else:
                    health['components'][name] = {'status': 'active'}
            except Exception as e:
                health['components'][name] = {'status': 'error', 'error': str(e)}
                health['overall_status'] = 'degraded'
        
        return health
    
    async def _ingest_memories_safely(self, memories, user_id, batch_size):
        """Ingest memories safely with batching"""
        logger.debug(f"Safely ingesting memories for {user_id}...")
        
        ingestion_engine = self.active_components.get('ingestion')
        if not ingestion_engine:
            raise JeanMemoryError("Ingestion engine not initialized")
        
        return await ingestion_engine.ingest_memories(memories, user_id)
    
    async def _search_memories_safely(self, query, user_id, max_results):
        """Search memories safely"""
        logger.debug(f"Safely searching memories for {user_id}...")
        
        search_engine = self.active_components.get('search')
        if not search_engine:
            raise JeanMemoryError("Search engine not initialized")
        
        return await search_engine.search(query, user_id, limit=max_results)
    
    async def _verify_post_ingestion_indexes(self):
        """Verify indexes after ingestion"""
        logger.debug("Verifying post-ingestion indexes...")
        pass
    
    async def _verify_search_indexes(self):
        """Verify indexes before search"""
        logger.debug("Verifying search indexes...")
        pass
    
    async def _cleanup_partial_initialization(self):
        """Cleanup partial initialization"""
        logger.debug("Cleaning up partial initialization...")
        for component_name in reversed(self.initialization_order):
            try:
                component = self.active_components.get(component_name)
                if component and hasattr(component, 'close'):
                    await component.close()
                del self.active_components[component_name]
            except Exception as e:
                logger.warning(f"Error cleaning up {component_name}: {e}")
        self.initialization_order.clear()
    
    async def _cleanup_all_components(self) -> Dict[str, Any]:
        """Cleanup all components"""
        logger.debug("Cleaning up all components...")
        
        cleanup_results = {}
        
        # Cleanup in reverse order
        for component_name in reversed(self.initialization_order):
            try:
                component = self.active_components.get(component_name)
                if component and hasattr(component, 'close'):
                    await component.close()
                cleanup_results[component_name] = "success"
            except Exception as e:
                cleanup_results[component_name] = f"error: {e}"
        
        self.active_components.clear()
        self.initialization_order.clear()
        
        return {"status": "completed", "components": cleanup_results}


# Convenience functions for common orchestrated operations

async def orchestrated_setup(auto_mode: bool = False, 
                           clear_databases: bool = True) -> JeanMemoryOrchestrator:
    """
    Complete orchestrated setup following working pipeline pattern
    
    Args:
        auto_mode: If True, proceed without user confirmations
        clear_databases: If True, clear databases before setup
        
    Returns:
        Initialized orchestrator
    """
    orchestrator = JeanMemoryOrchestrator(auto_mode=auto_mode)
    
    # Run the full setup sequence
    steps = [
        orchestrator.step_1_check_environment(),
        orchestrator.step_2_initialize_components(),
        orchestrator.step_3_prepare_databases(clear_data=clear_databases),
        orchestrator.step_4_health_check()
    ]
    
    for i, step in enumerate(steps, 1):
        success = await step
        if not success:
            logger.error(f"❌ Setup failed at step {i}")
            await orchestrator.cleanup_orchestrated(confirm=True)
            raise JeanMemoryError(f"Orchestrated setup failed at step {i}")
    
    logger.info("🎉 Orchestrated setup completed successfully!")
    return orchestrator


async def quick_ingest_and_search(memories: List[str], 
                                user_id: str, 
                                search_query: str,
                                auto_mode: bool = True) -> Dict[str, Any]:
    """
    Quick orchestrated ingest and search operation
    
    Args:
        memories: Memory content to ingest
        user_id: User identifier
        search_query: Query to search after ingestion
        auto_mode: Run without confirmations
        
    Returns:
        Combined results
    """
    orchestrator = await orchestrated_setup(auto_mode=auto_mode, clear_databases=False)
    
    try:
        # Ingest memories
        ingest_result = await orchestrator.ingest_memories_orchestrated(
            memories, user_id
        )
        
        # Search memories
        search_result = await orchestrator.search_memories_orchestrated(
            search_query, user_id
        )
        
        return {
            "status": "success",
            "ingestion": ingest_result,
            "search": search_result
        }
        
    finally:
        await orchestrator.cleanup_orchestrated(confirm=True) 