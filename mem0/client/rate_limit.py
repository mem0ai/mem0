"""
Rate limiting decorators and utilities for the Mem0 client.
"""
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar, cast

from mem0.configs.rate_limit import RateLimitScope, RateLimitTier
from mem0.rate_limiter import RateLimitExceededError, QuotaExceededError, rate_limiter

F = TypeVar('F', bound=Callable[..., Any])

def rate_limited(
    scope: RateLimitScope,
    scope_params: Optional[Dict[str, Any]] = None,
    amount: int = 1,
    tier: Optional[RateLimitTier] = None,
) -> Callable[[F], F]:
    """Decorator to apply rate limiting to a method.
    
    Args:
        scope: The rate limit scope to apply
        scope_params: Parameters to format into the scope string
        amount: Amount to consume from quota (default: 1)
        tier: Rate limit tier to use (default: client's tier)
    
    Returns:
        Decorated function with rate limiting applied
    """
    if scope_params is None:
        scope_params = {}
    
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(self, *args: Any, **kwargs: Any) -> Any:
            # Get the client's rate limit tier if not specified
            current_tier = tier or getattr(self, 'rate_limit_tier', RateLimitTier.FREE)
            
            # Format the scope with provided parameters
            formatted_scope = scope.format(
                user_id=getattr(self, 'user_id', ''),
                project_id=getattr(self, 'project_id', ''),
                **scope_params
            )
            
            # Apply rate limiting
            try:
                rate_limiter.check(formatted_scope, amount=amount)
            except RateLimitExceededError as e:
                # Add retry-after header if this is a request
                if hasattr(self, 'client') and hasattr(self.client, 'headers'):
                    self.client.headers['Retry-After'] = str(int(e.retry_after))
                raise
            except QuotaExceededError as e:
                # Add rate limit headers
                if hasattr(self, 'client') and hasattr(self.client, 'headers'):
                    self.client.headers['X-RateLimit-Remaining'] = '0'
                    self.client.headers['X-RateLimit-Limit'] = str(e.limit)
                    self.client.headers['X-RateLimit-Reset'] = str(int(e.reset_time.timestamp()))
                raise
            
            # Call the original function
            return func(self, *args, **kwargs)
        
        return cast(F, wrapper)
    
    return decorator


def get_rate_limit_headers(scope: str) -> Dict[str, str]:
    """Get rate limit headers for a given scope.
    
    Args:
        scope: The scope to get rate limit headers for
        
    Returns:
        Dictionary of rate limit headers
    """
    usage = rate_limiter.get_usage(scope)
    headers = {
        'X-RateLimit-Limit': str(usage['rate_limit']['limit']),
        'X-RateLimit-Remaining': str(usage['rate_limit']['limit'] - usage['rate_limit']['current']),
        'X-RateLimit-Reset': str(int(time.time() + usage['rate_limit']['reset_in'])),
    }
    
    if 'quota' in usage:
        headers.update({
            'X-RateLimit-Quota-Limit': str(usage['quota']['limit']),
            'X-RateLimit-Quota-Remaining': str(usage['quota']['remaining']),
            'X-RateLimit-Quota-Reset': str(int(usage['quota']['reset_time'].timestamp())),
        })
    
    return headers
