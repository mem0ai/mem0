"""
Jean Memory V2 API Adapter
===========================

Adapter layer to integrate V2 capabilities with existing V1 API endpoints.
This allows gradual migration from V1 to V2 while maintaining backward compatibility.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from .core import JeanMemoryV2
from .config import JeanMemoryConfig
from .exceptions import JeanMemoryError, SearchError, IngestionError
from .utils import validate_user_id, sanitize_memory_content, format_search_results

logger = logging.getLogger(__name__)


class JeanMemoryV2ApiAdapter:
    """
    API adapter that provides V1-compatible interfaces while using V2 capabilities under the hood.
    
    This adapter can be integrated into existing FastAPI routes to enhance them with V2 features:
    - Enhanced search with Gemini AI synthesis
    - Multi-engine ingestion (Mem0 + Graphiti)
    - Advanced safety checks and deduplication
    - Backward compatibility with V1 response formats
    """
    
    def __init__(self, config: JeanMemoryConfig):
        self.config = config
        self.jean_memory = JeanMemoryV2.from_config(config)
        self._initialized = False
    
    async def initialize(self):
        """Initialize the V2 engine"""
        if not self._initialized:
            await self.jean_memory.initialize()
            self._initialized = True
            logger.info("🔌 V2 API Adapter initialized")
    
    async def create_memory_v2(
        self,
        user_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        app_name: str = "jean_memory_v2"
    ) -> Dict[str, Any]:
        """
        Enhanced memory creation using V2 ingestion pipeline
        
        Args:
            user_id: User identifier
            text: Memory content
            metadata: Optional metadata
            app_name: Application name
            
        Returns:
            V1-compatible response with V2 enhancements
        """
        if not self._initialized:
            await self.initialize()
        
        if not validate_user_id(user_id):
            raise IngestionError("Invalid user ID")
        
        text = sanitize_memory_content(text)
        if not text:
            raise IngestionError("Empty or invalid memory content")
        
        try:
            # Use V2 ingestion with safety checks
            result = await self.jean_memory.ingest_memories(
                memories=[text],
                user_id=user_id,
                metadata=metadata
            )
            
            # Return V1-compatible response
            if result.successful_ingestions > 0 and result.mem0_results:
                memory_id = result.mem0_results[0].get("id", "unknown")
                return {
                    "status": "success",
                    "memory_id": memory_id,
                    "message": "Memory created successfully",
                    "v2_stats": {
                        "processing_time": result.processing_time,
                        "engines_used": ["mem0"] + (["graphiti"] if result.graphiti_results else []),
                        "safety_checks": self.config.enable_safety_checks,
                        "deduplication": self.config.enable_deduplication
                    }
                }
            else:
                raise IngestionError("Failed to create memory: " + "; ".join(result.errors))
                
        except Exception as e:
            logger.error(f"❌ V2 memory creation failed: {e}")
            raise IngestionError(f"Memory creation failed: {e}")
    
    async def search_memories_v2(
        self,
        user_id: str,
        query: str,
        limit: Optional[int] = None,
        include_synthesis: bool = True
    ) -> Dict[str, Any]:
        """
        Enhanced memory search using V2 hybrid search
        
        Args:
            user_id: User identifier
            query: Search query
            limit: Maximum number of results
            include_synthesis: Whether to include AI synthesis
            
        Returns:
            Enhanced search results with V1 compatibility
        """
        if not self._initialized:
            await self.initialize()
        
        if not validate_user_id(user_id):
            raise SearchError("Invalid user ID")
        
        if not query or not query.strip():
            raise SearchError("Empty search query")
        
        try:
            if include_synthesis:
                # Full V2 hybrid search with synthesis
                result = await self.jean_memory.search(
                    query=query,
                    user_id=user_id,
                    limit=limit
                )
                
                # Format for V1 compatibility with V2 enhancements
                return {
                    "results": format_search_results(
                        result.mem0_results + result.graphiti_results,
                        max_results=limit or 50
                    ),
                    "total": result.total_results,
                    "query": query,
                    "processing_time": result.processing_time,
                    "v2_enhancements": {
                        "synthesis": result.synthesis,
                        "confidence_score": result.confidence_score,
                        "search_method": result.search_method,
                        "engines_used": {
                            "mem0_results": len(result.mem0_results),
                            "graphiti_results": len(result.graphiti_results)
                        }
                    }
                }
            else:
                # Mem0-only search for faster response
                mem0_results = await self.jean_memory.search_mem0_only(
                    query=query,
                    user_id=user_id,
                    limit=limit
                )
                
                return {
                    "results": format_search_results(mem0_results, max_results=limit or 50),
                    "total": len(mem0_results),
                    "query": query,
                    "v2_enhancements": {
                        "engines_used": {"mem0_results": len(mem0_results)},
                        "synthesis_available": False
                    }
                }
                
        except Exception as e:
            logger.error(f"❌ V2 search failed: {e}")
            raise SearchError(f"Search failed: {e}")
    
    async def deep_life_query_v2(
        self,
        user_id: str,
        query: str,
        context_limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Enhanced deep life query using V2 capabilities
        
        Args:
            user_id: User identifier
            query: Deep query about user's life/memories
            context_limit: Maximum context items to include
            
        Returns:
            Deep analysis with AI synthesis
        """
        if not self._initialized:
            await self.initialize()
        
        if not validate_user_id(user_id):
            raise SearchError("Invalid user ID")
        
        try:
            # Use V2 hybrid search with higher limits for deep analysis
            search_limit = context_limit or 50
            result = await self.jean_memory.search(
                query=query,
                user_id=user_id,
                limit=search_limit
            )
            
            # Enhanced response for deep queries
            return {
                "query": query,
                "analysis": result.synthesis,
                "confidence": result.confidence_score,
                "processing_time": result.processing_time,
                "context_sources": {
                    "mem0_memories": len(result.mem0_results),
                    "graphiti_insights": len(result.graphiti_results),
                    "total_context_items": result.total_results
                },
                "detailed_sources": format_search_results(
                    result.mem0_results + result.graphiti_results,
                    max_results=10  # Limit detailed sources for readability
                ),
                "v2_capabilities": {
                    "ai_synthesis": result.search_method == "gemini_ai",
                    "temporal_reasoning": len(result.graphiti_results) > 0,
                    "semantic_search": len(result.mem0_results) > 0
                }
            }
            
        except Exception as e:
            logger.error(f"❌ V2 deep query failed: {e}")
            raise SearchError(f"Deep query failed: {e}")
    
    async def get_life_narrative_v2(self, user_id: str) -> Dict[str, Any]:
        """
        Generate comprehensive life narrative using V2 capabilities
        
        Args:
            user_id: User identifier
            
        Returns:
            Generated life narrative with metadata
        """
        if not self._initialized:
            await self.initialize()
        
        if not validate_user_id(user_id):
            raise SearchError("Invalid user ID")
        
        try:
            # Use broad search to gather comprehensive context
            result = await self.jean_memory.search(
                query="life story personality experiences growth journey",
                user_id=user_id,
                limit=100  # Large limit for comprehensive narrative
            )
            
            # If we have results, the synthesis will be comprehensive
            if result.total_results > 0:
                return {
                    "narrative": result.synthesis,
                    "confidence": result.confidence_score,
                    "generation_time": result.processing_time,
                    "source_count": result.total_results,
                    "narrative_metadata": {
                        "generated_at": datetime.now().isoformat(),
                        "user_id": user_id,
                        "v2_powered": True,
                        "engines_used": {
                            "mem0": len(result.mem0_results) > 0,
                            "graphiti": len(result.graphiti_results) > 0,
                            "gemini_synthesis": result.search_method == "gemini_ai"
                        }
                    }
                }
            else:
                return {
                    "narrative": "I don't have enough information about you yet to create a comprehensive life narrative. Please add more memories to help me understand your experiences, interests, and journey.",
                    "confidence": 0.0,
                    "source_count": 0,
                    "message": "Insufficient data for narrative generation"
                }
                
        except Exception as e:
            logger.error(f"❌ V2 narrative generation failed: {e}")
            raise SearchError(f"Narrative generation failed: {e}")
    
    async def get_user_stats_v2(self, user_id: str) -> Dict[str, Any]:
        """
        Get comprehensive user statistics using V2 capabilities
        
        Args:
            user_id: User identifier
            
        Returns:
            Enhanced user statistics
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            stats = await self.jean_memory.get_user_stats(user_id)
            
            # Add V2-specific enhancements
            stats["v2_capabilities"] = {
                "hybrid_search": True,
                "ai_synthesis": self.config.enable_gemini_synthesis,
                "graph_memory": self.config.enable_graph_memory,
                "safety_checks": self.config.enable_safety_checks,
                "deduplication": self.config.enable_deduplication
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"❌ V2 stats retrieval failed: {e}")
            return {"user_id": user_id, "error": str(e)}
    
    async def health_check_v2(self) -> Dict[str, Any]:
        """
        Comprehensive health check including V2 systems
        
        Returns:
            Health status of all V2 components
        """
        try:
            if not self._initialized:
                await self.initialize()
            
            health = await self.jean_memory.health_check()
            
            # Add adapter-specific information
            health["api_adapter"] = {
                "status": "healthy",
                "v1_compatibility": True,
                "v2_enhancements": True,
                "initialized": self._initialized
            }
            
            return health
            
        except Exception as e:
            logger.error(f"❌ V2 health check failed: {e}")
            return {
                "jean_memory_v2": "error",
                "api_adapter": {"status": "error", "error": str(e)},
                "timestamp": datetime.now().isoformat()
            }
    
    async def close(self):
        """Clean up resources"""
        if self.jean_memory:
            await self.jean_memory.close()
        self._initialized = False
        logger.info("🔌 V2 API Adapter closed")


# Factory function for easy integration
def create_v2_adapter_from_env(env_file: str) -> JeanMemoryV2ApiAdapter:
    """
    Create V2 API adapter from environment file
    
    Args:
        env_file: Path to environment configuration file
        
    Returns:
        Configured V2 API adapter
    """
    config = JeanMemoryConfig.from_env_file(env_file)
    return JeanMemoryV2ApiAdapter(config)


# Integration helper for FastAPI routes
class V2RouteEnhancer:
    """
    Helper class to enhance existing FastAPI routes with V2 capabilities
    """
    
    def __init__(self, adapter: JeanMemoryV2ApiAdapter):
        self.adapter = adapter
    
    async def enhance_create_memory(self, user_id: str, text: str, **kwargs) -> Dict[str, Any]:
        """Enhance memory creation route"""
        return await self.adapter.create_memory_v2(user_id, text, **kwargs)
    
    async def enhance_search_memories(self, user_id: str, query: str, **kwargs) -> Dict[str, Any]:
        """Enhance memory search route"""
        return await self.adapter.search_memories_v2(user_id, query, **kwargs)
    
    async def enhance_deep_query(self, user_id: str, query: str, **kwargs) -> Dict[str, Any]:
        """Enhance deep query route"""
        return await self.adapter.deep_life_query_v2(user_id, query, **kwargs)
    
    async def enhance_life_narrative(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """Enhance life narrative route"""
        return await self.adapter.get_life_narrative_v2(user_id, **kwargs) 