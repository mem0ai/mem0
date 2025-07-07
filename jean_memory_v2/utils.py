"""
Jean Memory V2 Utilities
========================

Utility functions and helpers for the Jean Memory V2 library.
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """
    Structured search result with AI synthesis
    """
    synthesis: str
    confidence_score: float
    total_results: int
    processing_time: float
    mem0_results: List[Dict[str, Any]]
    graphiti_results: List[Dict[str, Any]]
    query: str
    user_id: str
    timestamp: str
    errors: List[str]
    
    def __post_init__(self):
        """Validate and normalize data after initialization"""
        self.confidence_score = max(0.0, min(1.0, self.confidence_score))
        self.total_results = max(0, self.total_results)
        self.processing_time = max(0.0, self.processing_time)
        
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        
        if not isinstance(self.errors, list):
            self.errors = []


@dataclass
class IngestionResult:
    """
    Detailed ingestion result with statistics
    """
    total_processed: int
    successful_ingestions: int
    failed_ingestions: int
    processing_time: float
    success_rate: float
    errors: List[str]
    user_id: str
    timestamp: str
    mem0_stored: int
    graphiti_stored: int
    duplicates_removed: int
    safety_checks_failed: int
    
    def __post_init__(self):
        """Validate and normalize data after initialization"""
        self.total_processed = max(0, self.total_processed)
        self.successful_ingestions = max(0, self.successful_ingestions)
        self.failed_ingestions = max(0, self.failed_ingestions)
        self.processing_time = max(0.0, self.processing_time)
        self.success_rate = max(0.0, min(1.0, self.success_rate))
        
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        
        if not isinstance(self.errors, list):
            self.errors = []
    
    @classmethod
    def create_success(
        cls,
        total_processed: int,
        processing_time: float,
        user_id: str,
        mem0_stored: int = 0,
        graphiti_stored: int = 0,
        duplicates_removed: int = 0
    ) -> 'IngestionResult':
        """Create a successful ingestion result"""
        return cls(
            total_processed=total_processed,
            successful_ingestions=total_processed,
            failed_ingestions=0,
            processing_time=processing_time,
            success_rate=1.0,
            errors=[],
            user_id=user_id,
            timestamp=datetime.now().isoformat(),
            mem0_stored=mem0_stored,
            graphiti_stored=graphiti_stored,
            duplicates_removed=duplicates_removed,
            safety_checks_failed=0
        )
    
    @classmethod
    def create_failure(
        cls,
        total_processed: int,
        failed_count: int,
        processing_time: float,
        user_id: str,
        errors: List[str]
    ) -> 'IngestionResult':
        """Create a failed ingestion result"""
        successful = total_processed - failed_count
        success_rate = successful / total_processed if total_processed > 0 else 0.0
        
        return cls(
            total_processed=total_processed,
            successful_ingestions=successful,
            failed_ingestions=failed_count,
            processing_time=processing_time,
            success_rate=success_rate,
            errors=errors,
            user_id=user_id,
            timestamp=datetime.now().isoformat(),
            mem0_stored=0,
            graphiti_stored=0,
            duplicates_removed=0,
            safety_checks_failed=0
        )


def setup_logging(level: str = "INFO", format_string: Optional[str] = None) -> None:
    """
    Setup logging for Jean Memory V2
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        format_string: Custom format string for log messages
    """
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format_string,
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Set specific loggers
    logging.getLogger('jean_memory_v2').setLevel(getattr(logging, level.upper()))


def validate_user_id(user_id: str) -> bool:
    """
    Validate user ID format
    
    Args:
        user_id: User identifier to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not user_id or not isinstance(user_id, str):
        return False
    
    user_id = user_id.strip()
    
    # Basic length check
    if len(user_id) < 3 or len(user_id) > 100:
        return False
    
    # Check for suspicious patterns
    suspicious_patterns = ['..', '//', 'null', 'undefined', 'admin', 'root']
    user_id_lower = user_id.lower()
    
    for pattern in suspicious_patterns:
        if pattern in user_id_lower:
            return False
    
    return True


def sanitize_memory_content(content: str) -> str:
    """
    Sanitize memory content for safe storage
    
    Args:
        content: Raw memory content
        
    Returns:
        Sanitized content
    """
    if not content or not isinstance(content, str):
        return ""
    
    # Basic cleaning
    content = content.strip()
    
    # Remove null characters and control characters
    content = ''.join(char for char in content if ord(char) >= 32 or char in '\n\r\t')
    
    # Limit length
    if len(content) > 10000:
        content = content[:10000] + "... [truncated]"
    
    return content


def format_search_results(results: List[Dict[str, Any]], max_results: int = 50) -> List[Dict[str, Any]]:
    """
    Format and standardize search results
    
    Args:
        results: Raw search results
        max_results: Maximum number of results to return
        
    Returns:
        Formatted results
    """
    formatted = []
    
    for result in results[:max_results]:
        if not isinstance(result, dict):
            continue
        
        formatted_result = {
            "id": result.get("id", "unknown"),
            "content": sanitize_memory_content(result.get("content", result.get("memory", ""))),
            "score": float(result.get("score", 0.0)),
            "source": result.get("source", "unknown"),
            "metadata": result.get("metadata", {}),
            "user_id": result.get("user_id"),
            "created_at": result.get("created_at"),
        }
        
        # Add source-specific fields
        if result.get("source") == "graphiti":
            formatted_result["node_type"] = result.get("node_type", "unknown")
        
        formatted.append(formatted_result)
    
    return formatted


def calculate_relevance_score(query: str, content: str) -> float:
    """
    Calculate a simple relevance score between query and content
    
    Args:
        query: Search query
        content: Content to score
        
    Returns:
        Relevance score between 0.0 and 1.0
    """
    if not query or not content:
        return 0.0
    
    query_lower = query.lower()
    content_lower = content.lower()
    
    # Exact match bonus
    if query_lower in content_lower:
        return 1.0
    
    # Word overlap scoring
    query_words = set(query_lower.split())
    content_words = set(content_lower.split())
    
    if not query_words:
        return 0.0
    
    overlap = len(query_words.intersection(content_words))
    score = overlap / len(query_words)
    
    return min(score, 1.0)


def merge_search_results(
    results_list: List[List[Dict[str, Any]]], 
    query: str,
    max_results: int = 50
) -> List[Dict[str, Any]]:
    """
    Merge and deduplicate search results from multiple sources
    
    Args:
        results_list: List of result lists from different sources
        query: Original search query
        max_results: Maximum number of results to return
        
    Returns:
        Merged and sorted results
    """
    all_results = []
    seen_content = set()
    
    for results in results_list:
        for result in results:
            if not isinstance(result, dict):
                continue
            
            content = result.get("content", result.get("memory", ""))
            if not content:
                continue
            
            # Simple deduplication based on content
            content_normalized = content.lower().strip()
            if content_normalized in seen_content:
                continue
            
            seen_content.add(content_normalized)
            
            # Ensure score is present
            if "score" not in result:
                result["score"] = calculate_relevance_score(query, content)
            
            all_results.append(result)
    
    # Sort by score (descending)
    all_results.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    
    return format_search_results(all_results, max_results)


def create_memory_batch(memories: List[str], batch_size: int = 100) -> List[List[str]]:
    """
    Split memories into batches for processing
    
    Args:
        memories: List of memory strings
        batch_size: Size of each batch
        
    Returns:
        List of memory batches
    """
    batches = []
    for i in range(0, len(memories), batch_size):
        batch = memories[i:i + batch_size]
        batches.append(batch)
    
    return batches


def export_results_to_json(results: Any, file_path: str) -> bool:
    """
    Export results to JSON file
    
    Args:
        results: Results to export (SearchResult, IngestionResult, or dict)
        file_path: Path to output file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Convert to dict if needed
        if hasattr(results, 'to_dict'):
            data = results.to_dict()
        elif isinstance(results, dict):
            data = results
        else:
            data = {"results": results}
        
        # Ensure directory exists
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Write to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"✅ Results exported to: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to export results: {e}")
        return False


def load_memories_from_file(file_path: str) -> List[str]:
    """
    Load memories from various file formats
    
    Args:
        file_path: Path to file containing memories
        
    Returns:
        List of memory strings
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    memories = []
    
    try:
        if path.suffix.lower() == '.json':
            # JSON format
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, list):
                memories = [str(item) for item in data if item]
            elif isinstance(data, dict) and 'memories' in data:
                memories = [str(item) for item in data['memories'] if item]
            else:
                memories = [str(data)]
        
        else:
            # Text format (one memory per line)
            with open(path, 'r', encoding='utf-8') as f:
                memories = [line.strip() for line in f if line.strip()]
        
        logger.info(f"📄 Loaded {len(memories)} memories from {file_path}")
        return memories
        
    except Exception as e:
        logger.error(f"❌ Failed to load memories from {file_path}: {e}")
        raise


def create_performance_report(
    operation: str,
    start_time: float,
    end_time: float,
    total_items: int,
    successful_items: int,
    errors: List[str] = None
) -> Dict[str, Any]:
    """
    Create a performance report for operations
    
    Args:
        operation: Name of the operation
        start_time: Start timestamp
        end_time: End timestamp
        total_items: Total number of items processed
        successful_items: Number of successful items
        errors: List of error messages
        
    Returns:
        Performance report dictionary
    """
    duration = end_time - start_time
    success_rate = (successful_items / total_items * 100) if total_items > 0 else 0
    throughput = successful_items / duration if duration > 0 else 0
    
    report = {
        "operation": operation,
        "timestamp": datetime.fromtimestamp(start_time).isoformat(),
        "duration_seconds": round(duration, 3),
        "total_items": total_items,
        "successful_items": successful_items,
        "failed_items": total_items - successful_items,
        "success_rate_percent": round(success_rate, 2),
        "throughput_items_per_second": round(throughput, 2),
        "errors": errors or []
    }
    
    return report


async def retry_async_operation(
    operation,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    *args,
    **kwargs
):
    """
    Retry an async operation with exponential backoff
    
    Args:
        operation: Async function to retry
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff_factor: Factor to multiply delay by after each retry
        *args: Arguments to pass to operation
        **kwargs: Keyword arguments to pass to operation
        
    Returns:
        Result of the operation
        
    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_retries + 1):
        try:
            return await operation(*args, **kwargs)
        
        except Exception as e:
            last_exception = e
            
            if attempt == max_retries:
                logger.error(f"❌ Operation failed after {max_retries + 1} attempts: {e}")
                break
            
            logger.warning(f"⚠️ Attempt {attempt + 1} failed, retrying in {current_delay}s: {e}")
            await asyncio.sleep(current_delay)
            current_delay *= backoff_factor
    
    raise last_exception


def get_memory_size_estimate(memories: List[str]) -> Dict[str, Any]:
    """
    Estimate memory usage and storage requirements
    
    Args:
        memories: List of memory strings
        
    Returns:
        Dictionary with size estimates
    """
    if not memories:
        return {
            "total_memories": 0,
            "total_characters": 0,
            "total_bytes": 0,
            "average_memory_length": 0,
            "estimated_storage_mb": 0
        }
    
    total_chars = sum(len(memory) for memory in memories)
    total_bytes = sum(len(memory.encode('utf-8')) for memory in memories)
    avg_length = total_chars / len(memories)
    
    # Rough estimate including vector embeddings and metadata overhead
    estimated_storage_bytes = total_bytes * 10  # 10x overhead for vectors/metadata
    estimated_storage_mb = estimated_storage_bytes / (1024 * 1024)
    
    return {
        "total_memories": len(memories),
        "total_characters": total_chars,
        "total_bytes": total_bytes,
        "average_memory_length": round(avg_length, 1),
        "estimated_storage_mb": round(estimated_storage_mb, 2)
    } 