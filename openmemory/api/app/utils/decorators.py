import asyncio
import time
import functools
import logging

logger = logging.getLogger(__name__)

def retry_on_exception(retries=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    A decorator to retry a function call with exponential backoff if it fails
    with a specified exception.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            _retries, _delay = retries, delay
            while _retries > 1:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    logger.warning(
                        f"Caught exception: {e}. Retrying in {_delay} seconds..."
                    )
                    await asyncio.sleep(_delay)
                    _retries -= 1
                    _delay *= backoff
            
            # Last attempt
            return await func(*args, **kwargs)
        return wrapper
    return decorator 