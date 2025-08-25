"""Helper utilities for MCP server reliability"""

import logging
import asyncio
from typing import Any, Callable
from functools import wraps

logger = logging.getLogger(__name__)


def with_error_handling(operation_name: str) -> Callable:
    """Decorator for robust error handling in MCP operations."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> dict:
            try:
                result = await func(*args, **kwargs)
                if not isinstance(result, dict):
                    logger.warning(
                        "%s: Invalid result type: %s", operation_name, type(result)
                    )
                    return {"error": f"Invalid result format from {operation_name}"}
                return result
            except Exception as e:
                logger.exception("Error in %s: %s", operation_name, e)
                return {
                    "error": f"{operation_name} failed: {e}",
                    "operation": operation_name,
                    "success": False,
                }

        return wrapper

    return decorator


async def validate_memory_client(memory_client) -> bool:
    """Validate that memory client is functional."""
    if not memory_client:
        return False
    try:
        memory_client.search(query="test", user_id="test", limit=1)
        return True
    except Exception as e:
        logger.error("Memory client validation failed: %s", e)
        return False


async def retry_operation(operation_func: Callable, max_retries: int = 3, delay: float = 1.0) -> Any:
    """Retry an operation with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return await operation_func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            wait_time = delay * (2 ** attempt)
            logger.warning(
                "Operation failed (attempt %s), retrying in %ss: %s",
                attempt + 1,
                wait_time,
                e,
            )
            await asyncio.sleep(wait_time)

