"""
Utility functions for memory tools.
Contains JSON encoding, serialization, and common helper functions.
"""

import json
import logging
import datetime
from typing import Any

logger = logging.getLogger(__name__)


class DateTimeJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects"""
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        elif isinstance(obj, datetime.date):
            return obj.isoformat()
        return super().default(obj)


def safe_json_dumps(data, **kwargs):
    """Safely serialize data to JSON, handling datetime objects"""
    try:
        return json.dumps(data, cls=DateTimeJSONEncoder, **kwargs)
    except Exception as e:
        # Fallback: convert data to string representation
        logger.warning(f"JSON serialization failed, using fallback: {e}")
        try:
            return json.dumps(str(data), **kwargs)
        except Exception as fallback_error:
            logger.error(f"Fallback JSON serialization also failed: {fallback_error}")
            return f'{{"error": "Serialization failed", "data_preview": "{str(data)[:200]}"}}'


def track_tool_usage(tool_name: str, properties: dict = None):
    """Analytics tracking - only active if enabled via environment variable"""
    # Placeholder for the actual analytics call to avoid breaking the code.
    # The original implementation in mcp_server can be moved to a dedicated analytics module.
    try:
        # Import here to avoid circular dependencies
        from app.analytics import track_tool_usage as track
        track(tool_name, properties)
    except ImportError:
        # Analytics module not available, skip tracking
        pass
    except Exception as e:
        logger.warning(f"Failed to track tool usage: {e}")


def format_memory_response(memories: list, total_count: int = None, query: str = None) -> str:
    """Format memory search results into a consistent response format."""
    if not memories:
        return safe_json_dumps({
            "status": "success",
            "message": "No memories found" + (f" for query: '{query}'" if query else ""),
            "memories": [],
            "total_count": 0
        })
    
    response = {
        "status": "success",
        "memories": memories,
        "total_count": total_count or len(memories)
    }
    
    if query:
        response["query"] = query
    
    return safe_json_dumps(response)


def format_error_response(error_message: str, operation: str = None) -> str:
    """Format error responses consistently."""
    response = {
        "status": "error",
        "error": error_message
    }
    
    if operation:
        response["operation"] = operation
    
    return safe_json_dumps(response)


def validate_memory_limits(user_id: str, current_count: int, limit_config: dict) -> tuple[bool, str]:
    """Validate if user can add more memories based on limits."""
    try:
        # Get user's subscription tier limit
        max_memories = limit_config.get('max_memories', 1000)  # Default limit
        
        if current_count >= max_memories:
            return False, f"Memory limit reached. You have {current_count}/{max_memories} memories."
        
        return True, ""
    except Exception as e:
        logger.error(f"Error validating memory limits: {e}")
        return True, ""  # Allow if validation fails


def truncate_text(text: str, max_length: int = 1000) -> str:
    """Truncate text to maximum length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def sanitize_tags(tags: list) -> list:
    """Sanitize and validate tags."""
    if not tags:
        return []
    
    sanitized = []
    for tag in tags:
        if isinstance(tag, str) and tag.strip():
            # Remove special characters and normalize
            clean_tag = tag.strip().lower()[:50]  # Limit tag length
            if clean_tag and clean_tag not in sanitized:
                sanitized.append(clean_tag)
    
    return sanitized[:10]  # Limit number of tags