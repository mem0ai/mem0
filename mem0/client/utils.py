import httpx
import logging

logger = logging.getLogger(__name__)

class APIError(Exception):
    """Exception raised for errors in the API."""
    pass


def api_error_handler(func):
    """Decorator to handle API errors consistently."""
    from functools import wraps

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise APIError(f"API request failed: {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {e}")
            raise APIError(f"Request failed: {str(e)}")

    return wrapper
