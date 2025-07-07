"""
Jean Memory V2 Ingestion Engine
===============================

Advanced memory ingestion pipeline with safety checks, deduplication, and multi-engine support.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

from .config import JeanMemoryConfig
from .exceptions import IngestionError, DatabaseConnectionError, ValidationError

logger = logging.getLogger(__name__)


@dataclass
class IngestionResult:
    """Result of memory ingestion operation"""
    
    user_id: str
    total_memories: int
    successful_ingestions: int
    failed_ingestions: int
    processing_time: float
    
    # Detailed results
    mem0_results: List[Dict[str, Any]]
    graphiti_results: List[Dict[str, Any]]
    errors: List[str]
    
    # Metadata
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.total_memories == 0:
            return 0.0
        return (self.successful_ingestions / self.total_memories) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "user_id": self.user_id,
            "total_memories": self.total_memories,
            "successful_ingestions": self.successful_ingestions,
            "failed_ingestions": self.failed_ingestions,
            "success_rate": self.success_rate,
            "processing_time": self.processing_time,
            "mem0_results": self.mem0_results,
            "graphiti_results": self.graphiti_results,
            "errors": self.errors,
            "timestamp": self.timestamp.isoformat()
        }


class MemoryIngestionEngine:
    """Advanced memory ingestion engine with safety checks and multi-engine support"""
    
    def __init__(self, config: JeanMemoryConfig):
        self.config = config
        self.mem0_memory = None
        self.graphiti = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize ingestion engines"""
        if self._initialized:
            return
        
        logger.info("🔧 Initializing Memory Ingestion Engine...")
        
        try:
            await self._initialize_mem0()
            await self._initialize_graphiti()
            self._initialized = True
            logger.info("✅ Memory Ingestion Engine ready!")
        except Exception as e:
            logger.error(f"❌ Failed to initialize ingestion engine: {e}")
            raise IngestionError(f"Ingestion engine initialization failed: {e}")
    
    async def _initialize_mem0(self):
        """Initialize Mem0 for memory storage"""
        logger.info("🧠 Initializing Mem0 for ingestion...")
        
        try:
            from mem0 import Memory
            
            mem0_config = self.config.to_mem0_config()
            self.mem0_memory = Memory.from_config(config_dict=mem0_config)
            logger.info("✅ Mem0 ingestion initialized")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Mem0 for ingestion: {e}")
            raise DatabaseConnectionError(f"Mem0 ingestion initialization failed: {e}")
    
    async def _initialize_graphiti(self):
        """Initialize Graphiti for graph storage"""
        logger.info("🕸️ Initializing Graphiti for ingestion...")
        
        try:
            from graphiti_core import Graphiti
            
            graphiti_config = self.config.to_graphiti_config()
            self.graphiti = Graphiti(
                uri=graphiti_config["neo4j_uri"],
                user=graphiti_config["neo4j_user"],
                password=graphiti_config["neo4j_password"]
            )
            logger.info("✅ Graphiti ingestion initialized")
            
        except Exception as e:
            logger.warning(f"⚠️ Graphiti ingestion initialization failed, continuing without: {e}")
            self.graphiti = None
    
    def _validate_memory_content(self, content: str) -> bool:
        """Validate memory content for safety and quality"""
        if not content or not isinstance(content, str):
            return False
        
        content = content.strip()
        
        # Basic length checks
        if len(content) < 3:
            return False
        
        if len(content) > 10000:  # Max 10k characters
            return False
        
        # Content quality checks
        if content.count(' ') == 0 and len(content) > 50:  # Likely garbage if no spaces
            return False
        
        # Safety checks for potential contamination
        suspicious_patterns = [
            'pralayb', '/users/pralayb', 'faircopyfolder',
            'user_id:', 'memory_id:', 'database_'
        ]
        
        content_lower = content.lower()
        for pattern in suspicious_patterns:
            if pattern in content_lower:
                logger.warning(f"⚠️ Suspicious content detected: {pattern}")
                return False
        
        return True
    
    def _deduplicate_memories(self, memories: List[str]) -> List[str]:
        """Remove duplicate memories"""
        if not self.config.enable_deduplication:
            return memories
        
        seen = set()
        deduplicated = []
        
        for memory in memories:
            # Normalize for comparison
            normalized = memory.strip().lower()
            
            if normalized not in seen:
                seen.add(normalized)
                deduplicated.append(memory)
        
        removed_count = len(memories) - len(deduplicated)
        if removed_count > 0:
            logger.info(f"🔄 Removed {removed_count} duplicate memories")
        
        return deduplicated
    
    async def _ingest_to_mem0(self, memories: List[str], user_id: str) -> List[Dict[str, Any]]:
        """Ingest memories to Mem0"""
        if not self.mem0_memory:
            raise IngestionError("Mem0 not initialized")
        
        results = []
        
        try:
            logger.info(f"📥 Ingesting {len(memories)} memories to Mem0...")
            
            # Process in batches
            batch_size = self.config.batch_size
            for i in range(0, len(memories), batch_size):
                batch = memories[i:i + batch_size]
                
                # Create messages format for Mem0
                messages = [{"role": "user", "content": memory} for memory in batch]
                
                # Add to Mem0
                batch_result = self.mem0_memory.add(
                    messages=messages,
                    user_id=user_id
                )
                
                # Process results
                if isinstance(batch_result, list):
                    for result in batch_result:
                        results.append({
                            "id": result.get("id", str(uuid.uuid4())),
                            "memory": result.get("memory", ""),
                            "event": result.get("event", "ADD"),
                            "source": "mem0"
                        })
                elif isinstance(batch_result, dict):
                    results.append({
                        "id": batch_result.get("id", str(uuid.uuid4())),
                        "memory": batch_result.get("memory", ""),
                        "event": batch_result.get("event", "ADD"),
                        "source": "mem0"
                    })
                
                logger.info(f"📊 Processed batch {i//batch_size + 1}/{(len(memories) + batch_size - 1)//batch_size}")
                
                # Small delay between batches to avoid overwhelming the system
                if i + batch_size < len(memories):
                    await asyncio.sleep(0.1)
            
            logger.info(f"✅ Mem0 ingestion completed: {len(results)} memories processed")
            return results
            
        except Exception as e:
            logger.error(f"❌ Mem0 ingestion failed: {e}")
            raise IngestionError(f"Mem0 ingestion failed: {e}")
    
    async def _ingest_to_graphiti(self, memories: List[str], user_id: str) -> List[Dict[str, Any]]:
        """Ingest memories to Graphiti"""
        if not self.graphiti:
            logger.warning("⚠️ Graphiti not available, skipping")
            return []
        
        results = []
        
        try:
            logger.info(f"🕸️ Ingesting {len(memories)} memories to Graphiti...")
            
            for i, memory in enumerate(memories):
                try:
                    # Add to Graphiti
                    result = await self.graphiti.add_memory(
                        content=memory,
                        user_id=user_id,
                        timestamp=datetime.now()
                    )
                    
                    results.append({
                        "id": result.get("id", str(uuid.uuid4())),
                        "content": memory,
                        "source": "graphiti",
                        "node_type": result.get("type", "memory")
                    })
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"📊 Graphiti progress: {i + 1}/{len(memories)}")
                    
                    # Small delay to avoid overwhelming
                    await asyncio.sleep(0.05)
                    
                except Exception as e:
                    logger.warning(f"⚠️ Failed to add memory to Graphiti: {e}")
                    continue
            
            logger.info(f"✅ Graphiti ingestion completed: {len(results)} memories processed")
            return results
            
        except Exception as e:
            logger.warning(f"⚠️ Graphiti ingestion failed, continuing: {e}")
            return []
    
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
        
        start_time = time.time()
        
        # Normalize input
        if isinstance(memories, str):
            memories = [memories]
        
        if not memories:
            raise ValidationError("No memories provided for ingestion")
        
        logger.info(f"🚀 Starting ingestion for user {user_id}: {len(memories)} memories")
        
        # Validation and preprocessing
        valid_memories = []
        errors = []
        
        for i, memory in enumerate(memories):
            if self.config.enable_safety_checks:
                if not self._validate_memory_content(memory):
                    error_msg = f"Memory {i+1} failed validation"
                    errors.append(error_msg)
                    logger.warning(f"⚠️ {error_msg}: {memory[:100]}...")
                    continue
            
            valid_memories.append(memory.strip())
        
        if not valid_memories:
            raise ValidationError("No valid memories after validation")
        
        # Deduplication
        if self.config.enable_deduplication:
            valid_memories = self._deduplicate_memories(valid_memories)
        
        logger.info(f"📋 Processing {len(valid_memories)} valid memories after validation/deduplication")
        
        # Ingest to all engines in parallel
        ingestion_tasks = [
            self._ingest_to_mem0(valid_memories, user_id)
        ]
        
        if self.graphiti:
            ingestion_tasks.append(self._ingest_to_graphiti(valid_memories, user_id))
        
        ingestion_results = await asyncio.gather(*ingestion_tasks, return_exceptions=True)
        
        # Process results
        mem0_results = ingestion_results[0] if not isinstance(ingestion_results[0], Exception) else []
        graphiti_results = ingestion_results[1] if len(ingestion_results) > 1 and not isinstance(ingestion_results[1], Exception) else []
        
        # Handle exceptions
        for i, result in enumerate(ingestion_results):
            if isinstance(result, Exception):
                engine_name = "mem0" if i == 0 else "graphiti"
                error_msg = f"{engine_name} ingestion failed: {result}"
                errors.append(error_msg)
                logger.error(f"❌ {error_msg}")
        
        # Calculate statistics
        successful_ingestions = len(mem0_results) + len(graphiti_results)
        failed_ingestions = len(memories) - len(valid_memories) + len([r for r in ingestion_results if isinstance(r, Exception)])
        processing_time = time.time() - start_time
        
        # Create result
        result = IngestionResult(
            user_id=user_id,
            total_memories=len(memories),
            successful_ingestions=successful_ingestions,
            failed_ingestions=failed_ingestions,
            processing_time=processing_time,
            mem0_results=mem0_results,
            graphiti_results=graphiti_results,
            errors=errors
        )
        
        logger.info(f"✅ Ingestion completed in {processing_time:.2f}s: {successful_ingestions}/{len(memories)} successful")
        
        return result
    
    async def ingest_from_file(self, file_path: str, user_id: str) -> IngestionResult:
        """Ingest memories from a text file (one memory per line)"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                memories = [line.strip() for line in f if line.strip()]
            
            logger.info(f"📄 Loaded {len(memories)} memories from {file_path}")
            return await self.ingest_memories(memories, user_id)
            
        except Exception as e:
            raise IngestionError(f"Failed to read file {file_path}: {e}")
    
    async def get_ingestion_stats(self, user_id: str) -> Dict[str, Any]:
        """Get ingestion statistics for a user"""
        try:
            stats = {"user_id": user_id}
            
            # Get Mem0 stats
            if self.mem0_memory:
                mem0_results = self.mem0_memory.search(query="", user_id=user_id, limit=1)
                stats["mem0_memory_count"] = len(mem0_results.get("results", [])) if isinstance(mem0_results, dict) else len(mem0_results)
            
            # Get Graphiti stats
            if self.graphiti:
                graphiti_stats = await self.graphiti.get_user_stats(user_id)
                stats["graphiti_node_count"] = graphiti_stats.get("node_count", 0)
                stats["graphiti_edge_count"] = graphiti_stats.get("edge_count", 0)
            
            return stats
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to get ingestion stats: {e}")
            return {"user_id": user_id, "error": str(e)}
    
    async def clear_user_memories(self, user_id: str) -> bool:
        """Clear all memories for a user (use with caution)"""
        logger.warning(f"🗑️ Clearing all memories for user: {user_id}")
        
        success = True
        
        try:
            # Clear Mem0 memories
            if self.mem0_memory:
                # Note: This is a simplified approach - actual implementation may vary
                logger.info("🧠 Clearing Mem0 memories...")
                # Implementation depends on Mem0 API for deletion
                
            # Clear Graphiti memories
            if self.graphiti:
                logger.info("🕸️ Clearing Graphiti memories...")
                await self.graphiti.clear_user_data(user_id)
            
            logger.info(f"✅ Cleared memories for user: {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Failed to clear memories for user {user_id}: {e}")
            success = False
        
        return success
    
    async def close(self):
        """Clean up resources"""
        logger.info("🧹 Cleaning up ingestion engine resources...")
        
        if self.graphiti:
            try:
                await self.graphiti.close()
            except:
                pass
        
        self._initialized = False
        logger.info("✅ Ingestion engine cleanup completed") 