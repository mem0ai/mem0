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
    
    # Smart memory query limits (for performance)
    smart_batch_size: int = 10  # Process documents in batches
    smart_content_preview: int = 5000  # Characters to preview per document
    smart_max_docs_analysis: int = 5  # Max documents for final analysis
    smart_doc_content_limit: int = 10000  # Max characters per document in analysis
    smart_max_memories_analysis: int = 20  # Max memories for final analysis
    
    # Memory monitoring
    max_memory_usage_mb: int = 400  # Restart if using more than 400MB (Render starter limit is 512MB)
    gc_threshold_mb: int = 300  # Run garbage collection if using more than 300MB
    
    # Batch processing for syncs
    sync_batch_size: int = 5  # Process posts in batches during sync
    sync_batch_delay_seconds: int = 1  # Delay between batches to prevent memory buildup
    
    @classmethod
    def get_defaults(cls) -> "MemoryLimits":
        """Get default memory limits"""
        return cls()


# Global instance
MEMORY_LIMITS = MemoryLimits.get_defaults() 