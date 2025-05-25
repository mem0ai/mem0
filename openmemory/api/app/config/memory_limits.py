"""
Memory search and retrieval limits configuration.

These limits help prevent excessive context retrieval and improve performance.
"""

from pydantic import BaseModel


class MemoryLimits(BaseModel):
    """Configuration for memory search and retrieval limits"""
    
    # Regular search limits
    search_default: int = 10
    search_max: int = 50
    
    # List/get_all limits
    list_default: int = 20
    list_max: int = 100
    
    # Deep memory query limits
    deep_memory_default: int = 20
    deep_memory_max: int = 50
    deep_chunk_default: int = 10
    deep_chunk_max: int = 20
    
    # UI pagination defaults
    ui_page_size_default: int = 10
    ui_page_size_options: list[int] = [5, 10, 20, 50]
    
    # Vector search score thresholds
    min_relevance_score: float = 0.7  # Minimum score to consider a memory relevant
    
    @classmethod
    def get_defaults(cls) -> "MemoryLimits":
        """Get default memory limits"""
        return cls()


# Global instance
MEMORY_LIMITS = MemoryLimits.get_defaults() 