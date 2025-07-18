"""
Cache management utilities for MCP orchestration.
Handles session-based context caching and TTL management.
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Session-based context cache - stores user context profiles
_context_cache: Dict[str, Dict] = {}
_cache_ttl_minutes = 30  # Context cache TTL


class ContextCacheManager:
    """Manages context caching for MCP orchestration."""
    
    @staticmethod
    def get_cached_context(cache_key: str) -> Optional[Dict]:
        """Get cached context if it exists and is still valid"""
        if cache_key not in _context_cache:
            return None
        
        cached = _context_cache[cache_key]
        cache_time = cached.get('timestamp')
        if not cache_time:
            return None
        
        # Check if cache is still valid
        if datetime.now() - cache_time > timedelta(minutes=_cache_ttl_minutes):
            del _context_cache[cache_key]
            return None
        
        return cached
    
    @staticmethod
    def update_context_cache(cache_key: str, context_data: Dict, user_id: str):
        """Update the session cache with new context data"""
        try:
            _context_cache[cache_key] = {
                'timestamp': datetime.now(),
                'user_id': user_id,
                'context_data': context_data
            }
            
            # Cleanup old cache entries (keep only 100 most recent)
            if len(_context_cache) > 100:
                oldest_keys = sorted(_context_cache.keys(), 
                                   key=lambda k: _context_cache[k]['timestamp'])[:50]
                for old_key in oldest_keys:
                    del _context_cache[old_key]
                    
        except Exception as e:
            logger.error(f"Error updating context cache: {e}")
    
    @staticmethod
    def clear_cache():
        """Clear the context cache (useful for testing)"""
        global _context_cache
        _context_cache.clear()
    
    @staticmethod
    def get_cache_stats() -> Dict:
        """Get context cache statistics"""
        return {
            "cache_size": len(_context_cache),
            "cache_keys": list(_context_cache.keys()),
            "ttl_minutes": _cache_ttl_minutes
        }


# Convenience functions for backward compatibility
def get_cached_context(cache_key: str) -> Optional[Dict]:
    """Get cached context if it exists and is still valid"""
    return ContextCacheManager.get_cached_context(cache_key)


def update_context_cache(cache_key: str, context_data: Dict, user_id: str):
    """Update the session cache with new context data"""
    return ContextCacheManager.update_context_cache(cache_key, context_data, user_id)


def clear_context_cache():
    """Clear the context cache (useful for testing)"""
    return ContextCacheManager.clear_cache()


def get_cache_stats() -> Dict:
    """Get context cache statistics"""
    return ContextCacheManager.get_cache_stats()