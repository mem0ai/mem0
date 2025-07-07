"""
Optimized Mem0 Adapter for Jean Memory V2
=========================================

High-performance drop-in replacement for mem0.Memory with:
- Zero wait statements
- Smart caching 
- Parallel operations
- Lazy initialization

PERFORMANCE TARGET: 3-5x faster than original adapter
"""

import asyncio
import logging
from typing import List, Dict, Any, Union, Optional

from .api_optimized import JeanMemoryAPIOptimized
from .models import SearchStrategy


logger = logging.getLogger(__name__)


class AsyncMemoryAdapterOptimized:
    """
    OPTIMIZED Async Memory adapter for Jean Memory V2
    
    Performance optimizations:
    - Shared API instance across operations
    - Smart caching of user states
    - Parallel collection setup
    - Eliminated all wait statements
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize optimized async memory adapter
        
        Args:
            config: Configuration dict (maintained for compatibility)
        """
        self.config = config or {}
        
        # Extract jean_memory_config if provided (like in memory.py)
        jean_memory_config = None
        if 'jean_memory_config' in self.config:
            jean_memory_config = self.config['jean_memory_config']
            logger.info(f"🔧 DEBUG: Extracted jean_memory_config: {type(jean_memory_config)}")
        else:
            logger.info(f"🔧 DEBUG: No jean_memory_config found in: {list(self.config.keys())}")
            # Fallback: Create config from current environment variables (already loaded)
            from jean_memory_v2.config import JeanMemoryConfig
            try:
                jean_memory_config = JeanMemoryConfig.from_environment()
                logger.info("🔧 DEBUG: Created config from environment variables")
            except Exception as e:
                logger.warning(f"🔧 DEBUG: Could not create config from environment: {e}")
        
        # Optimization: Single shared API instance with caching and proper config
        self._api = JeanMemoryAPIOptimized(config=jean_memory_config)
        self._initialized = False
        
        logger.info("✅ AsyncMemoryAdapterOptimized initialized with config")
    
    async def _ensure_initialized(self):
        """Lazy initialization - only when needed"""
        if not self._initialized:
            await self._api.initialize()
            self._initialized = True
            logger.debug("✅ API initialized (lazy)")
    
    @classmethod
    def from_config(cls, config_dict: Dict):
        """Create AsyncMemory instance from config dict (mem0 compatibility)"""
        return cls(config=config_dict)
    
    async def add(
        self, 
        messages: Union[str, List[str], List[Dict]], 
        user_id: str,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        OPTIMIZED Add memory/memories (async)
        
        Key optimizations:
        - Parallel processing for multiple messages
        - Shared API instance
        - No blocking waits
        """
        await self._ensure_initialized()
        
        # Handle different input formats
        if isinstance(messages, str):
            messages_list = [messages]
        elif isinstance(messages, list):
            if messages and isinstance(messages[0], dict):
                # Handle message dicts (extract content/text)
                messages_list = []
                for msg in messages:
                    if isinstance(msg, dict):
                        content = msg.get('content') or msg.get('text') or msg.get('message', str(msg))
                        messages_list.append(content)
                    else:
                        messages_list.append(str(msg))
            else:
                messages_list = [str(msg) for msg in messages]
        else:
            messages_list = [str(messages)]
        
        results = []
        
        # Optimization: Process all messages in parallel for bulk operations
        if len(messages_list) > 1:
            logger.info(f"📝 Adding {len(messages_list)} memories in parallel")
            
            # Create parallel tasks
            tasks = []
            for message_text in messages_list:
                task = self._api.add_memory(
                    memory_text=message_text,
                    user_id=user_id,
                    metadata=metadata
                )
                tasks.append(task)
            
            # Execute all tasks in parallel
            parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(parallel_results):
                if isinstance(result, Exception):
                    logger.error(f"Parallel add failed for message {i}: {result}")
                    results.append({
                        'id': f'error_{i}',
                        'memory': messages_list[i],
                        'content': messages_list[i],
                        'error': str(result),
                        'score': 0.0,
                        'metadata': metadata or {}
                    })
                else:
                    results.append({
                        'id': result.memory_id,
                        'memory': messages_list[i],
                        'content': messages_list[i],
                        'score': 1.0,
                        'metadata': metadata or {},
                        'memory_id': result.memory_id
                    })
            
        else:
            # Single message - direct call
            message_text = messages_list[0]
            logger.info(f"📝 Adding single memory (optimized)")
            
            result = await self._api.add_memory(
                memory_text=message_text,
                user_id=user_id,
                metadata=metadata
            )
            
            if result.success:
                results.append({
                    'id': result.memory_id,
                    'memory': message_text,
                    'content': message_text,
                    'score': 1.0,
                    'metadata': metadata or {},
                    'memory_id': result.memory_id
                })
            else:
                results.append({
                    'id': 'error',
                    'memory': message_text,
                    'content': message_text,
                    'error': result.message,
                    'score': 0.0,
                    'metadata': metadata or {}
                })
        
        return {'results': results}
    
    async def search(
        self, 
        query: str, 
        user_id: str,
        agent_id: Optional[str] = None,
        limit: int = 10,
        **kwargs
    ) -> Union[List[Dict], Dict]:
        """
        OPTIMIZED Search memories (async)
        
        Uses cached API instance for faster performance
        """
        await self._ensure_initialized()
        
        logger.info(f"🔍 Searching memories (optimized) for user {user_id}")
        
        result = await self._api.search_memories(
            query=query,
            user_id=user_id,
            limit=limit,
            strategy=SearchStrategy.HYBRID
        )
        
        if result.success:
            mem0_results = []
            for memory in result.memories:
                mem0_result = {
                    'id': memory.id,
                    'memory': memory.text,
                    'content': memory.text,
                    'score': memory.score,
                    'metadata': memory.metadata,
                    'created_at': memory.created_at
                }
                
                # Add source information if available
                if hasattr(memory, 'source'):
                    mem0_result['source'] = memory.source
                
                mem0_results.append(mem0_result)
            
            return {'results': mem0_results}
        else:
            return {'results': []}
    
    async def get_all(
        self, 
        user_id: str,
        agent_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Union[List[Dict], Dict]:
        """
        OPTIMIZED Get all memories for a user (async)
        
        Uses optimized wildcard search
        """
        await self._ensure_initialized()
        
        result = await self._api.get_all_memories(
            user_id=user_id,
            limit=min(limit or 100, 100)
        )
        
        if result.success:
            mem0_results = []
            for memory in result.memories:
                mem0_result = {
                    'id': memory.id,
                    'memory': memory.text,
                    'content': memory.text,
                    'metadata': memory.metadata,
                    'created_at': memory.created_at
                }
                
                if hasattr(memory, 'source'):
                    mem0_result['source'] = memory.source
                
                mem0_results.append(mem0_result)
            
            return {'results': mem0_results}
        else:
            return {'results': []}
    
    async def delete_all(self, user_id: str, agent_id: Optional[str] = None) -> Dict:
        """
        OPTIMIZED Delete all memories for a user (async)
        """
        await self._ensure_initialized()
        
        try:
            result = await self._api.clear_memories(user_id=user_id, confirm=True)
            return {
                'message': f'Memories deleted for user_id: {user_id}',
                'deleted_count': result.total_deleted if result.success else 0
            }
        except Exception as e:
            logger.error(f"Error deleting all memories for user {user_id}: {e}")
            return {
                'message': f'Error deleting memories: {str(e)}',
                'deleted_count': 0
            }


class MemoryAdapterOptimized:
    """
    OPTIMIZED Sync Memory adapter for Jean Memory V2
    
    Performance optimizations:
    - Shared async adapter instance
    - Optimized asyncio.run usage
    - Smart event loop handling
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize optimized sync memory adapter
        """
        self.config = config or {}
        self._async_adapter = AsyncMemoryAdapterOptimized(config)
        
        logger.info("✅ MemoryAdapterOptimized initialized with config")
    
    @classmethod
    def from_config(cls, config_dict: Dict):
        """Create Memory instance from config dict (mem0 compatibility)"""
        return cls(config=config_dict)
    
    def add(
        self, 
        messages: Union[str, List[str], List[Dict]], 
        user_id: str,
        agent_id: Optional[str] = None,
        metadata: Optional[Dict] = None
    ) -> Dict:
        """
        OPTIMIZED Add memory/memories (sync wrapper)
        """
        return asyncio.run(self._async_adapter.add(messages, user_id, agent_id, metadata))
    
    def search(
        self, 
        query: str, 
        user_id: str,
        agent_id: Optional[str] = None,
        limit: int = 10,
        **kwargs
    ) -> Union[List[Dict], Dict]:
        """
        OPTIMIZED Search memories (sync wrapper)
        """
        return asyncio.run(self._async_adapter.search(query, user_id, agent_id, limit, **kwargs))
    
    def get_all(
        self, 
        user_id: str,
        agent_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Union[List[Dict], Dict]:
        """
        OPTIMIZED Get all memories for a user (sync wrapper)
        """
        return asyncio.run(self._async_adapter.get_all(user_id, agent_id, limit))
    
    def delete_all(self, user_id: str, agent_id: Optional[str] = None) -> Dict:
        """
        OPTIMIZED Delete all memories for a user (sync wrapper)
        """
        return asyncio.run(self._async_adapter.delete_all(user_id, agent_id))


# mem0 compatibility aliases
Memory = MemoryAdapterOptimized
AsyncMemory = AsyncMemoryAdapterOptimized


def get_memory_client_v2_optimized(config: Optional[Dict] = None) -> MemoryAdapterOptimized:
    """
    Get optimized synchronous Memory client for Jean Memory V2
    
    Args:
        config: Optional configuration dict
        
    Returns:
        MemoryAdapterOptimized instance with enhanced performance
    """
    return MemoryAdapterOptimized(config)


def get_async_memory_client_v2_optimized(config: Optional[Dict] = None) -> AsyncMemoryAdapterOptimized:
    """
    Get optimized asynchronous Memory client for Jean Memory V2
    
    Args:
        config: Optional configuration dict
        
    Returns:
        AsyncMemoryAdapterOptimized instance with enhanced performance
    """
    return AsyncMemoryAdapterOptimized(config) 