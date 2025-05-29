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
    smart_content_preview: int = 1000  # Chars to preview per document
    smart_max_docs_analysis: int = 3  # Max docs to send to analyst
    smart_doc_content_limit: int = 5000  # Max chars per doc for analyst
    smart_max_memories_analysis: int = 10  # Max memories for analyst
    
    @classmethod
    def get_defaults(cls) -> "MemoryLimits":
        """Get default memory limits"""
        return cls()


# Global instance
MEMORY_LIMITS = MemoryLimits.get_defaults() 