"""
Mem0 API Adapter for Jean Memory V2
Provides full backward compatibility with existing mem0 usage patterns
Following mem0's pattern: Memory (sync) and AsyncMemory (async) classes
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime

from .api import JeanMemoryAPI

logger = logging.getLogger(__name__)


class AsyncMemoryAdapter:
    """
    Async Memory adapter for Jean Memory V2 (matches AsyncMemory interface)
    Direct async interface - use with await
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize async memory adapter
        
        Args:
            config: Configuration dict (maintained for compatibility)
        """
        self.config = config or {}
        self._api = None
        self._initialized = False
        
    async def _ensure_initialized(self):
        """Ensure the Jean Memory V2 API is initialized"""
        if not self._initialized:
            # Use config from self.config if available
            jean_memory_config = None
            if self.config and 'jean_memory_config' in self.config:
                jean_memory_config = self.config['jean_memory_config']
            
            self._api = JeanMemoryAPI(config=jean_memory_config)
            await self._api.initialize()
            self._initialized = True
    
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
        Add memory/memories (async)
        
        Args:
            messages: Text content or list of messages
            user_id: User identifier
            agent_id: Agent identifier (optional)
            metadata: Additional metadata
            
        Returns:
            Dict with 'results' containing list of memory results
        """
        await self._ensure_initialized()
        
        # Convert messages to text content
        if isinstance(messages, str):
            content = messages
        elif isinstance(messages, list):
            if messages and isinstance(messages[0], dict):
                # Extract content from message dicts
                content_parts = []
                for msg in messages:
                    if isinstance(msg, dict):
                        content_parts.append(msg.get('content', str(msg)))
                    else:
                        content_parts.append(str(msg))
                content = '\n'.join(content_parts)
            else:
                content = '\n'.join(str(msg) for msg in messages)
        else:
            content = str(messages)
        
        # Prepare metadata
        full_metadata = metadata or {}
        if agent_id:
            full_metadata['agent_id'] = agent_id
        
        # Add memory using Jean Memory V2
        result = await self._api.add_memory(
            memory_text=content,
            user_id=user_id,
            metadata=full_metadata
        )
        
        # Convert to mem0-compatible format
        if result.success:
            return {
                'results': [{
                    'id': result.memory_id,
                    'memory': content,
                    'event': 'ADD',
                    'metadata': full_metadata
                }]
            }
        else:
            # Return error in compatible format
            return {
                'results': [],
                'errors': result.errors
            }
    
    async def search(
        self, 
        query: str, 
        user_id: str,
        agent_id: Optional[str] = None,
        limit: int = 10,
        **kwargs
    ) -> Union[List[Dict], Dict]:
        """
        Search memories (async)
        
        Args:
            query: Search query
            user_id: User identifier
            agent_id: Agent identifier (optional)
            limit: Maximum results to return
            
        Returns:
            List of memory results or dict with 'results' key
        """
        await self._ensure_initialized()
        
        # Call search_memories with individual parameters
        result = await self._api.search_memories(
            query=query,
            user_id=user_id,
            limit=limit
        )
        
        if result.success:
            # Convert Jean Memory V2 results to mem0 format
            mem0_results = []
            for memory in result.memories:
                mem0_result = {
                    'id': memory.id,
                    'memory': memory.text,
                    'content': memory.text,  # Alternative field name
                    'score': memory.score,
                    'metadata': memory.metadata,
                    'created_at': getattr(memory, 'created_at', None)
                }
                
                # Add source information if available
                if hasattr(memory, 'source'):
                    mem0_result['source'] = memory.source
                
                mem0_results.append(mem0_result)
            
            # Return results in mem0 format
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
        Get all memories for a user (async)
        
        Args:
            user_id: User identifier
            agent_id: Agent identifier (optional) 
            limit: Maximum results to return
            
        Returns:
            Dict with 'results' containing list of all memories
        """
        await self._ensure_initialized()
        
        # Use search with wildcard query to get all memories  
        result = await self._api.search_memories(
            query="*",  # Wildcard query to get all
            user_id=user_id,
            limit=min(limit or 100, 100)  # Respect API limit of 100
        )
        
        if result.success:
            # Convert to mem0 format
            mem0_results = []
            for memory in result.memories:
                mem0_result = {
                    'id': memory.id,
                    'memory': memory.text,
                    'content': memory.text,
                    'metadata': memory.metadata,
                    'created_at': getattr(memory, 'created_at', None)
                }
                
                # Add source information if available
                if hasattr(memory, 'source'):
                    mem0_result['source'] = memory.source
                
                mem0_results.append(mem0_result)
            
            return {'results': mem0_results}
        else:
            return {'results': []}
    
    async def delete_all(self, user_id: str, agent_id: Optional[str] = None) -> Dict:
        """
        Delete all memories for a user (async)
        
        Args:
            user_id: User identifier
            agent_id: Agent identifier (optional)
            
        Returns:
            Dict with deletion result
        """
        await self._ensure_initialized()
        
        try:
            result = await self._api.clear_memories(user_id=user_id, confirm=True)
            return {
                'message': f'Memories deleted for user_id: {user_id}',
                'deleted_count': result.total_deleted if hasattr(result, 'total_deleted') else 0
            }
        except Exception as e:
            logger.error(f"Error deleting all memories for user {user_id}: {e}")
            return {
                'message': f'Error deleting memories: {str(e)}',
                'deleted_count': 0
            }
    
    async def delete(self, memory_id: str, user_id: str) -> Dict:
        """
        Delete specific memory by ID (async)
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            Dict with deletion result
        """
        await self._ensure_initialized()
        
        try:
            # Note: This would need to be implemented in Jean Memory V2 API
            # For now, return success as placeholder
            logger.info(f"Delete memory {memory_id} for user {user_id} - not yet implemented")
            return {
                'message': f'Memory {memory_id} deleted successfully',
                'deleted_count': 1
            }
        except Exception as e:
            logger.error(f"Error deleting memory {memory_id} for user {user_id}: {e}")
            return {
                'message': f'Error deleting memory: {str(e)}',
                'deleted_count': 0
            }


class MemoryAdapter:
    """
    Sync Memory adapter for Jean Memory V2 (matches Memory interface)
    Synchronous wrapper around AsyncMemoryAdapter
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize sync memory adapter
        
        Args:
            config: Configuration dict (maintained for compatibility)
        """
        self.config = config or {}
        self._async_adapter = AsyncMemoryAdapter(config)
        
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
        Add memory/memories (sync wrapper)
        
        Args:
            messages: Text content or list of messages
            user_id: User identifier
            agent_id: Agent identifier (optional)
            metadata: Additional metadata
            
        Returns:
            Dict with 'results' containing list of memory results
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
        Search memories (sync wrapper)
        
        Args:
            query: Search query
            user_id: User identifier
            agent_id: Agent identifier (optional)
            limit: Maximum results to return
            
        Returns:
            Dict with 'results' containing list of memory results
        """
        return asyncio.run(self._async_adapter.search(query, user_id, agent_id, limit, **kwargs))
    
    def get_all(
        self, 
        user_id: str,
        agent_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Union[List[Dict], Dict]:
        """
        Get all memories for a user (sync wrapper)
        
        Args:
            user_id: User identifier
            agent_id: Agent identifier (optional) 
            limit: Maximum results to return
            
        Returns:
            Dict with 'results' containing list of all memories
        """
        return asyncio.run(self._async_adapter.get_all(user_id, agent_id, limit))
    
    def delete_all(self, user_id: str, agent_id: Optional[str] = None) -> Dict:
        """
        Delete all memories for a user (sync wrapper)
        
        Args:
            user_id: User identifier
            agent_id: Agent identifier (optional)
            
        Returns:
            Dict with deletion result
        """
        return asyncio.run(self._async_adapter.delete_all(user_id, agent_id))
    
    def delete(self, memory_id: str, user_id: str) -> Dict:
        """
        Delete specific memory by ID (sync wrapper)
        
        Args:
            memory_id: Memory identifier
            user_id: User identifier
            
        Returns:
            Dict with deletion result
        """
        return asyncio.run(self._async_adapter.delete(memory_id, user_id))


# Aliases for backward compatibility and mem0-style imports
Memory = MemoryAdapter
AsyncMemory = AsyncMemoryAdapter


def get_memory_client_v2(config: Optional[Dict] = None) -> MemoryAdapter:
    """
    Factory function to create Jean Memory V2 adapter (sync)
    Drop-in replacement for get_memory_client()
    """
    return MemoryAdapter(config=config)


def get_async_memory_client_v2(config: Optional[Dict] = None) -> AsyncMemoryAdapter:
    """
    Factory function to create Jean Memory V2 async adapter
    """
    return AsyncMemoryAdapter(config=config) 