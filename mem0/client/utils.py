import json
import logging
import httpx

from mem0.exceptions import (
    NetworkError,
    create_exception_from_response,
)

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Exception raised for errors in the API.
    
    Deprecated: Use specific exception classes from mem0.exceptions instead.
    This class is maintained for backward compatibility.
    """

    pass


def api_error_handler(func):
    """Decorator to handle API errors consistently.
    
    This decorator catches HTTP and request errors and converts them to
    appropriate structured exception classes with detailed error information.
    
    The decorator analyzes HTTP status codes and response content to create
    the most specific exception type with helpful error messages, suggestions,
    and debug information.
    """
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}")
            
            # Extract error details from response
            response_text = ""
            error_details = {}
            debug_info = {
                "status_code": e.response.status_code,
                "url": str(e.request.url),
                "method": e.request.method,
            }
            
            try:
                response_text = e.response.text
                # Try to parse JSON response for additional error details
                if e.response.headers.get("content-type", "").startswith("application/json"):
                    error_data = json.loads(response_text)
                    if isinstance(error_data, dict):
                        error_details = error_data
                        response_text = error_data.get("detail", response_text)
            except (json.JSONDecodeError, AttributeError):
                # Fallback to plain text response
                pass
            
            # Add rate limit information if available
            if e.response.status_code == 429:
                retry_after = e.response.headers.get("Retry-After")
                if retry_after:
                    try:
                        debug_info["retry_after"] = int(retry_after)
                    except ValueError:
                        pass
                
                # Add rate limit headers if available
                for header in ["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]:
                    value = e.response.headers.get(header)
                    if value:
                        debug_info[header.lower().replace("-", "_")] = value
            
            # Create specific exception based on status code
            exception = create_exception_from_response(
                status_code=e.response.status_code,
                response_text=response_text,
                details=error_details,
                debug_info=debug_info,
            )
            
            raise exception
            
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {e}")
            
            # Determine the appropriate exception type based on error type
            if isinstance(e, httpx.TimeoutException):
                raise NetworkError(
                    message=f"Request timed out: {str(e)}",
                    error_code="NET_TIMEOUT",
                    suggestion="Please check your internet connection and try again",
                    debug_info={"error_type": "timeout", "original_error": str(e)},
                )
            elif isinstance(e, httpx.ConnectError):
                raise NetworkError(
                    message=f"Connection failed: {str(e)}",
                    error_code="NET_CONNECT",
                    suggestion="Please check your internet connection and try again",
                    debug_info={"error_type": "connection", "original_error": str(e)},
                )
            else:
                # Generic network error for other request errors
                raise NetworkError(
                    message=f"Network request failed: {str(e)}",
                    error_code="NET_GENERIC",
                    suggestion="Please check your internet connection and try again",
                    debug_info={"error_type": "request", "original_error": str(e)},
                )

    return wrapper
