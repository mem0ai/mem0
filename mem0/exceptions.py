"""Structured exception classes for Mem0 with error codes, suggestions, and debug information.

This module provides a comprehensive set of exception classes that replace the generic
APIError with specific, actionable exceptions. Each exception includes error codes,
user-friendly suggestions, and debug information to enable better error handling
and recovery in applications using Mem0.

Example:
    Basic usage:
        try:
            memory.add(content, user_id=user_id)
        except RateLimitError as e:
            # Implement exponential backoff
            time.sleep(e.debug_info.get('retry_after', 60))
        except MemoryQuotaExceededError as e:
            # Trigger quota upgrade flow
            logger.error(f"Quota exceeded: {e.error_code}")
        except ValidationError as e:
            # Return user-friendly error
            raise HTTPException(400, detail=e.suggestion)

    Advanced usage with error context:
        try:
            memory.update(memory_id, content=new_content)
        except MemoryNotFoundError as e:
            logger.warning(f"Memory {memory_id} not found: {e.message}")
            if e.suggestion:
                logger.info(f"Suggestion: {e.suggestion}")
"""

from typing import Any, Dict, Optional


class MemoryError(Exception):
    """Base exception for all memory-related errors.
    
    This is the base class for all Mem0-specific exceptions. It provides a structured
    approach to error handling with error codes, contextual details, suggestions for
    resolution, and debug information.
    
    Attributes:
        message (str): Human-readable error message.
        error_code (str): Unique error identifier for programmatic handling.
        details (dict): Additional context about the error.
        suggestion (str): User-friendly suggestion for resolving the error.
        debug_info (dict): Technical debugging information.
    
    Example:
        raise MemoryError(
            message="Memory operation failed",
            error_code="MEM_001",
            details={"operation": "add", "user_id": "user123"},
            suggestion="Please check your API key and try again",
            debug_info={"request_id": "req_456", "timestamp": "2024-01-01T00:00:00Z"}
        )
    """
    
    def __init__(
        self,
        message: str,
        error_code: str,
        details: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        debug_info: Optional[Dict[str, Any]] = None,
    ):
        """Initialize a MemoryError.
        
        Args:
            message: Human-readable error message.
            error_code: Unique error identifier.
            details: Additional context about the error.
            suggestion: User-friendly suggestion for resolving the error.
            debug_info: Technical debugging information.
        """
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.suggestion = suggestion
        self.debug_info = debug_info or {}
        super().__init__(self.message)
    
    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r}, "
            f"details={self.details!r}, "
            f"suggestion={self.suggestion!r}, "
            f"debug_info={self.debug_info!r})"
        )


class AuthenticationError(MemoryError):
    """Raised when authentication fails.
    
    This exception is raised when API key validation fails, tokens are invalid,
    or authentication credentials are missing or expired.
    
    Common scenarios:
        - Invalid API key
        - Expired authentication token
        - Missing authentication headers
        - Insufficient permissions
    
    Example:
        raise AuthenticationError(
            message="Invalid API key provided",
            error_code="AUTH_001",
            suggestion="Please check your API key in the Mem0 dashboard"
        )
    """
    pass


class RateLimitError(MemoryError):
    """Raised when rate limits are exceeded.
    
    This exception is raised when the API rate limit has been exceeded.
    It includes information about retry timing and current rate limit status.
    
    The debug_info typically contains:
        - retry_after: Seconds to wait before retrying
        - limit: Current rate limit
        - remaining: Remaining requests in current window
        - reset_time: When the rate limit window resets
    
    Example:
        raise RateLimitError(
            message="Rate limit exceeded",
            error_code="RATE_001",
            suggestion="Please wait before making more requests",
            debug_info={"retry_after": 60, "limit": 100, "remaining": 0}
        )
    """
    pass


class ValidationError(MemoryError):
    """Raised when input validation fails.
    
    This exception is raised when request parameters, memory content,
    or configuration values fail validation checks.
    
    Common scenarios:
        - Invalid user_id format
        - Missing required fields
        - Content too long or too short
        - Invalid metadata format
        - Malformed filters
    
    Example:
        raise ValidationError(
            message="Invalid user_id format",
            error_code="VAL_001",
            details={"field": "user_id", "value": "123", "expected": "string"},
            suggestion="User ID must be a non-empty string"
        )
    """
    pass


class MemoryNotFoundError(MemoryError):
    """Raised when a memory is not found.
    
    This exception is raised when attempting to access, update, or delete
    a memory that doesn't exist or is not accessible to the current user.
    
    Example:
        raise MemoryNotFoundError(
            message="Memory not found",
            error_code="MEM_404",
            details={"memory_id": "mem_123", "user_id": "user_456"},
            suggestion="Please check the memory ID and ensure it exists"
        )
    """
    pass


class NetworkError(MemoryError):
    """Raised when network connectivity issues occur.
    
    This exception is raised for network-related problems such as
    connection timeouts, DNS resolution failures, or service unavailability.
    
    Common scenarios:
        - Connection timeout
        - DNS resolution failure
        - Service temporarily unavailable
        - Network connectivity issues
    
    Example:
        raise NetworkError(
            message="Connection timeout",
            error_code="NET_001",
            suggestion="Please check your internet connection and try again",
            debug_info={"timeout": 30, "endpoint": "api.mem0.ai"}
        )
    """
    pass


class ConfigurationError(MemoryError):
    """Raised when client configuration is invalid.
    
    This exception is raised when the client is improperly configured,
    such as missing required settings or invalid configuration values.
    
    Common scenarios:
        - Missing API key
        - Invalid host URL
        - Incompatible configuration options
        - Missing required environment variables
    
    Example:
        raise ConfigurationError(
            message="API key not configured",
            error_code="CFG_001",
            suggestion="Set MEM0_API_KEY environment variable or pass api_key parameter"
        )
    """
    pass


class MemoryQuotaExceededError(MemoryError):
    """Raised when user's memory quota is exceeded.
    
    This exception is raised when the user has reached their memory
    storage or usage limits.
    
    The debug_info typically contains:
        - current_usage: Current memory usage
        - quota_limit: Maximum allowed usage
        - usage_type: Type of quota (storage, requests, etc.)
    
    Example:
        raise MemoryQuotaExceededError(
            message="Memory quota exceeded",
            error_code="QUOTA_001",
            suggestion="Please upgrade your plan or delete unused memories",
            debug_info={"current_usage": 1000, "quota_limit": 1000, "usage_type": "memories"}
        )
    """
    pass


class MemoryCorruptionError(MemoryError):
    """Raised when memory data is corrupted.
    
    This exception is raised when stored memory data is found to be
    corrupted, malformed, or otherwise unreadable.
    
    Example:
        raise MemoryCorruptionError(
            message="Memory data is corrupted",
            error_code="CORRUPT_001",
            details={"memory_id": "mem_123"},
            suggestion="Please contact support for data recovery assistance"
        )
    """
    pass


class VectorSearchError(MemoryError):
    """Raised when vector search operations fail.
    
    This exception is raised when vector database operations fail,
    such as search queries, embedding generation, or index operations.
    
    Common scenarios:
        - Embedding model unavailable
        - Vector index corruption
        - Search query timeout
        - Incompatible vector dimensions
    
    Example:
        raise VectorSearchError(
            message="Vector search failed",
            error_code="VEC_001",
            details={"query": "find similar memories", "vector_dim": 1536},
            suggestion="Please try a simpler search query"
        )
    """
    pass


class CacheError(MemoryError):
    """Raised when caching operations fail.
    
    This exception is raised when cache-related operations fail,
    such as cache misses, cache invalidation errors, or cache corruption.
    
    Example:
        raise CacheError(
            message="Cache operation failed",
            error_code="CACHE_001",
            details={"operation": "get", "key": "user_memories_123"},
            suggestion="Cache will be refreshed automatically"
        )
    """
    pass


# OSS-specific exception classes
class VectorStoreError(MemoryError):
    """Raised when vector store operations fail.
    
    This exception is raised when vector store operations fail,
    such as embedding storage, similarity search, or vector operations.
    
    Example:
        raise VectorStoreError(
            message="Vector store operation failed",
            error_code="VECTOR_001",
            details={"operation": "search", "collection": "memories"},
            suggestion="Please check your vector store configuration and connection"
        )
    """
    def __init__(self, message: str, error_code: str = "VECTOR_001", details: dict = None, 
                 suggestion: str = "Please check your vector store configuration and connection", 
                 debug_info: dict = None):
        super().__init__(message, error_code, details, suggestion, debug_info)


class GraphStoreError(MemoryError):
    """Raised when graph store operations fail.
    
    This exception is raised when graph store operations fail,
    such as relationship creation, entity management, or graph queries.
    
    Example:
        raise GraphStoreError(
            message="Graph store operation failed",
            error_code="GRAPH_001",
            details={"operation": "create_relationship", "entity": "user_123"},
            suggestion="Please check your graph store configuration and connection"
        )
    """
    def __init__(self, message: str, error_code: str = "GRAPH_001", details: dict = None, 
                 suggestion: str = "Please check your graph store configuration and connection", 
                 debug_info: dict = None):
        super().__init__(message, error_code, details, suggestion, debug_info)


class EmbeddingError(MemoryError):
    """Raised when embedding operations fail.
    
    This exception is raised when embedding operations fail,
    such as text embedding generation or embedding model errors.
    
    Example:
        raise EmbeddingError(
            message="Embedding generation failed",
            error_code="EMBED_001",
            details={"text_length": 1000, "model": "openai"},
            suggestion="Please check your embedding model configuration"
        )
    """
    def __init__(self, message: str, error_code: str = "EMBED_001", details: dict = None, 
                 suggestion: str = "Please check your embedding model configuration", 
                 debug_info: dict = None):
        super().__init__(message, error_code, details, suggestion, debug_info)


class LLMError(MemoryError):
    """Raised when LLM operations fail.
    
    This exception is raised when LLM operations fail,
    such as text generation, completion, or model inference errors.
    
    Example:
        raise LLMError(
            message="LLM operation failed",
            error_code="LLM_001",
            details={"model": "gpt-4", "prompt_length": 500},
            suggestion="Please check your LLM configuration and API key"
        )
    """
    def __init__(self, message: str, error_code: str = "LLM_001", details: dict = None, 
                 suggestion: str = "Please check your LLM configuration and API key", 
                 debug_info: dict = None):
        super().__init__(message, error_code, details, suggestion, debug_info)


class DatabaseError(MemoryError):
    """Raised when database operations fail.
    
    This exception is raised when database operations fail,
    such as SQLite operations, connection issues, or data corruption.
    
    Example:
        raise DatabaseError(
            message="Database operation failed",
            error_code="DB_001",
            details={"operation": "insert", "table": "memories"},
            suggestion="Please check your database configuration and connection"
        )
    """
    def __init__(self, message: str, error_code: str = "DB_001", details: dict = None, 
                 suggestion: str = "Please check your database configuration and connection", 
                 debug_info: dict = None):
        super().__init__(message, error_code, details, suggestion, debug_info)


class DependencyError(MemoryError):
    """Raised when required dependencies are missing.
    
    This exception is raised when required dependencies are missing,
    such as optional packages for specific providers or features.
    
    Example:
        raise DependencyError(
            message="Required dependency missing",
            error_code="DEPS_001",
            details={"package": "kuzu", "feature": "graph_store"},
            suggestion="Please install the required dependencies: pip install kuzu"
        )
    """
    def __init__(self, message: str, error_code: str = "DEPS_001", details: dict = None, 
                 suggestion: str = "Please install the required dependencies", 
                 debug_info: dict = None):
        super().__init__(message, error_code, details, suggestion, debug_info)


# Mapping of HTTP status codes to specific exception classes
HTTP_STATUS_TO_EXCEPTION = {
    400: ValidationError,
    401: AuthenticationError,
    403: AuthenticationError,
    404: MemoryNotFoundError,
    408: NetworkError,
    409: ValidationError,
    413: MemoryQuotaExceededError,
    422: ValidationError,
    429: RateLimitError,
    500: MemoryError,
    502: NetworkError,
    503: NetworkError,
    504: NetworkError,
}


def create_exception_from_response(
    status_code: int,
    response_text: str,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    debug_info: Optional[Dict[str, Any]] = None,
) -> MemoryError:
    """Create an appropriate exception based on HTTP response.
    
    This function analyzes the HTTP status code and response to create
    the most appropriate exception type with relevant error information.
    
    Args:
        status_code: HTTP status code from the response.
        response_text: Response body text.
        error_code: Optional specific error code.
        details: Additional error context.
        debug_info: Debug information.
    
    Returns:
        An instance of the appropriate MemoryError subclass.
    
    Example:
        exception = create_exception_from_response(
            status_code=429,
            response_text="Rate limit exceeded",
            debug_info={"retry_after": 60}
        )
        # Returns a RateLimitError instance
    """
    exception_class = HTTP_STATUS_TO_EXCEPTION.get(status_code, MemoryError)
    
    # Generate error code if not provided
    if not error_code:
        error_code = f"HTTP_{status_code}"
    
    # Create appropriate suggestion based on status code
    suggestions = {
        400: "Please check your request parameters and try again",
        401: "Please check your API key and authentication credentials",
        403: "You don't have permission to perform this operation",
        404: "The requested resource was not found",
        408: "Request timed out. Please try again",
        409: "Resource conflict. Please check your request",
        413: "Request too large. Please reduce the size of your request",
        422: "Invalid request data. Please check your input",
        429: "Rate limit exceeded. Please wait before making more requests",
        500: "Internal server error. Please try again later",
        502: "Service temporarily unavailable. Please try again later",
        503: "Service unavailable. Please try again later",
        504: "Gateway timeout. Please try again later",
    }
    
    suggestion = suggestions.get(status_code, "Please try again later")
    
    return exception_class(
        message=response_text or f"HTTP {status_code} error",
        error_code=error_code,
        details=details or {},
        suggestion=suggestion,
        debug_info=debug_info or {},
    )