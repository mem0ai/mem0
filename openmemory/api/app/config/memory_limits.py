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
    
    # Memory monitoring - Updated for 2GB container
    max_memory_usage_mb: int = 1500  # Restart if using more than 1.5GB (plenty of buffer)
    gc_threshold_mb: int = 1000  # Run garbage collection if using more than 1GB
    critical_memory_mb: int = 1200  # Emergency throttling at 1.2GB
    
    # Batch processing for syncs - Can handle larger batches with 2GB
    sync_batch_size: int = 10  # Process more posts at once (was 3)
    sync_batch_delay_seconds: int = 0.5  # Shorter delay (was 2)
    sync_max_post_size: int = 200000  # Allow larger posts up to 200KB (was 50KB)
    
    @classmethod
    def get_defaults(cls) -> "MemoryLimits":
        """Get default memory limits"""
        return cls()


# Global instance
MEMORY_LIMITS = MemoryLimits.get_defaults() 