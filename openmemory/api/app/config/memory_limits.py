"""
Memory search and retrieval limits configuration.

These limits help prevent excessive context retrieval and improve performance.
"""

from pydantic import BaseModel


class MemoryLimits(BaseModel):
    """Configuration for memory search and retrieval limits"""
    
    # Regular search limits - SIGNIFICANTLY INCREASED
    search_default: int = 50  # was 10 - much more comprehensive ask_memory
    search_max: int = 100     # was 50 - allow for even larger searches
    
    # List/get_all limits
    list_default: int = 50    # was 20 - more comprehensive listing
    list_max: int = 200       # was 100 - allow much larger lists
    
    # Deep memory query limits - MASSIVELY INCREASED
    deep_memory_default: int = 200  # was 20 - HUNDREDS of memories!
    deep_memory_max: int = 500      # was 50 - allow truly massive deep searches
    deep_chunk_default: int = 50    # was 10 - much more document content
    deep_chunk_max: int = 100       # was 20 - comprehensive document analysis
    
    # UI pagination defaults
    ui_page_size_default: int = 20  # was 10 - show more by default
    ui_page_size_options: list[int] = [10, 20, 50, 100]  # bigger options
    
    # Vector search score thresholds
    min_relevance_score: float = 0.7  # Minimum score to consider a memory relevant
    
    # Smart memory query limits (for performance)
    smart_batch_size: int = 20  # was 10 - bigger batches
    smart_content_preview: int = 10000  # was 5000 - more preview content
    smart_max_docs_analysis: int = 10   # was 5 - more documents
    smart_doc_content_limit: int = 20000  # was 10000 - larger docs
    smart_max_memories_analysis: int = 50  # was 20 - way more memories
    
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